"""Controller for the Report page behaviour.

This module contains the non-UI logic that previously lived in
``src.ui.report_page.ReportPage``.  It operates on a :class:`ReportView`
instance (from ``src.ui.view.report``) and wires the behaviour:

- Scanning the report directory and populating the file list.
- Tailing text log files into the text viewer.
- Detecting RVR/RVO/performance result files and rendering charts.
- Auto-refreshing charts and tail content via a timer.
"""

from __future__ import annotations

import logging
import os
import math
from pathlib import Path
from typing import Any, Optional
from html import escape

import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.lines import Line2D

import pandas as pd
from PyQt5.QtCore import Qt, QTimer, QEvent, QUrl, QObject
from PyQt5.QtGui import QPixmap, QImage, QFont, QDesktopServices
from PyQt5.QtWidgets import (
    QListWidget,
    QListWidgetItem,
    QTextEdit,
    QLabel,
    QStackedWidget,
    QTabWidget,
    QToolTip,
    QSizePolicy,
    QWidget,
)

from src.ui.view.theme import (
    ACCENT_COLOR,
    BACKGROUND_COLOR,
    FONT_FAMILY,
    STYLE_BASE,
    TEXT_COLOR,
)
from src.util.constants import (
    BANDWIDTH_ORDER,
    BANDWIDTH_ORDER_MAP,
    CHART_DPI,
    DIRECTION_ORDER,
    DIRECTION_ORDER_MAP,
    FREQ_BAND_ORDER,
    FREQ_BAND_ORDER_MAP,
    STANDARD_ORDER,
    STANDARD_ORDER_MAP,
    TEST_TYPE_ORDER,
    TEST_TYPE_ORDER_MAP,
)
from src.util.rvr_chart_logic import RvrChartLogic


class InteractiveChartLabel(QLabel):
    """QLabel subclass that supports HTML tooltips for chart points."""

    _TOOLTIP_CONFIGURED = False

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        if not InteractiveChartLabel._TOOLTIP_CONFIGURED:
            QToolTip.setFont(QFont(FONT_FAMILY, 11))
            if hasattr(QToolTip, "setStyleSheet"):
                QToolTip.setStyleSheet(
                    "QToolTip { color: #202020; background-color: #f5f5f5; "
                    "border: 1px solid #7f7f7f; padding: 4px; }"
                )
            InteractiveChartLabel._TOOLTIP_CONFIGURED = True

        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._points: list[dict[str, object]] = []
        self._hit_radius = 12
        self._last_point: Optional[dict[str, object]] = None
        self._base_points: list[dict[str, object]] = []
        self._original_pixmap: Optional[QPixmap] = None
        self._original_width: int = 0
        self._original_height: int = 0
        self._current_pixmap_width: int = 0
        self._current_pixmap_height: int = 0
        self.setMouseTracking(True)

    # ------------------------- public API -------------------------

    def set_points(self, points: list[dict[str, object]]) -> None:
        """Set the original-space point list and refresh the scaled copy."""
        self._base_points = points or []
        self._refresh_points()

    # ------------------------- events -------------------------

    def mouseMoveEvent(self, event):  # type: ignore[override]
        """Show or hide a tooltip while moving across the nearest chart point."""
        if self._points:
            target = self._find_point(event.pos())
            if target is not self._last_point:
                tooltip = target.get("tooltip", "") if target else ""
                if tooltip:
                    QToolTip.showText(self.mapToGlobal(event.pos()), tooltip, self)
                else:
                    QToolTip.hideText()
                self._last_point = target
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):  # type: ignore[override]
        """Hide any visible tooltip and propagate the event to the base class."""
        QToolTip.hideText()
        super().mousePressEvent(event)

    def leaveEvent(self, event):  # type: ignore[override]
        """Clear hover state and hide tooltip when the cursor leaves the label."""
        self._last_point = None
        QToolTip.hideText()
        super().leaveEvent(event)

    # ------------------ pixmap / resize plumbing ------------------

    def setPixmap(self, pixmap: QPixmap) -> None:  # type: ignore[override]
        """Store the original pixmap for scaling math, then update the display."""
        if pixmap is None or pixmap.isNull():
            self._original_pixmap = None
            self._original_width = 0
            self._original_height = 0
            self._current_pixmap_width = 0
            self._current_pixmap_height = 0
            super().setPixmap(pixmap)
            self._refresh_points()
            return
        self._original_pixmap = QPixmap(pixmap)
        self._original_width = self._original_pixmap.width()
        self._original_height = self._original_pixmap.height()
        self._update_scaled_pixmap()
        self._refresh_points()

    def resizeEvent(self, event):  # type: ignore[override]
        """Recompute the scaled pixmap and derived point positions on widget resize."""
        super().resizeEvent(event)
        if self._original_pixmap is not None:
            self._update_scaled_pixmap()
            self._refresh_points()

    # ------------------------- internals -------------------------

    def _find_point(self, pos):
        """Return the closest point within the hit radius; otherwise ``None``."""
        best = None
        best_dist = float("inf")
        x = pos.x()
        y = pos.y()
        radius_sq = self._hit_radius * self._hit_radius
        for pt in self._points:
            px, py = pt.get("position", (0, 0))
            dx = x - int(px)
            dy = y - int(py)
            dist_sq = dx * dx + dy * dy
            if dist_sq <= radius_sq and dist_sq < best_dist:
                best = pt
                best_dist = dist_sq
        return best

    def _refresh_points(self) -> None:
        """Recompute scaled copies of base points according to current label size."""
        if not self._base_points or not self._original_pixmap or self._current_pixmap_width <= 0:
            self._points = []
            return
        w = self.width()
        h = self.height()
        dx = (w - self._current_pixmap_width) // 2
        dy = (h - self._current_pixmap_height) // 2
        sx = self._current_pixmap_width / float(self._original_width or 1)
        sy = self._current_pixmap_height / float(self._original_height or 1)
        scaled: list[dict[str, object]] = []
        for pt in self._base_points:
            x0, y0 = pt.get("position", (0, 0))
            x = dx + int(float(x0) * sx)
            y = dy + int(float(y0) * sy)
            scaled.append({**pt, "position": (x, y)})
        self._points = scaled
        base_radius = 12
        self._hit_radius = max(6, int(base_radius * (sx + sy) / 2))

    def _update_scaled_pixmap(self) -> None:
        """Update the displayed pixmap according to the current widget size."""
        if self._original_pixmap is None:
            return
        if self.width() <= 1 or self.height() <= 1:
            scaled = self._original_pixmap
        else:
            scaled = self._original_pixmap.scaled(
                self.width(),
                self.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        self._current_pixmap_width = scaled.width()
        self._current_pixmap_height = scaled.height()
        super().setPixmap(scaled)


class ReportController(RvrChartLogic, QObject):
    """Controller that wires behaviour onto a ReportView instance."""

    def __init__(self, view: QWidget) -> None:
        super().__init__(view)
        self.view = view

        # State
        self._report_dir: Optional[Path] = None
        self._current_file: Optional[Path] = None
        self._fh = None  # raw binary file handle for tailing
        self._pos: int = 0  # last-read file size
        self._partial: str = ""  # last incomplete line buffer
        self._active_case_path: Optional[Path] = None
        self._selected_test_type: Optional[str] = None

        # Timer
        self._timer = QTimer(self)
        self._timer.setInterval(300)
        self._timer.timeout.connect(self._on_tail_tick)

        # Convenience aliases into the view
        self.title_label: QLabel = view.title_label  # type: ignore[attr-defined]
        self.dir_label: QLabel = view.dir_label  # type: ignore[attr-defined]
        self.file_list: QListWidget = view.file_list  # type: ignore[attr-defined]
        self.viewer_stack: QStackedWidget = view.viewer_stack  # type: ignore[attr-defined]
        self.viewer: QTextEdit = view.viewer  # type: ignore[attr-defined]
        self.chart_tabs: QTabWidget = view.chart_tabs  # type: ignore[attr-defined]

        # Wire UI interactions
        self.dir_label.mousePressEvent = self._open_report_dir  # type: ignore[assignment]
        self.file_list.itemSelectionChanged.connect(self._on_file_selected)

        self._view_mode: str = "text"  # 'text' or 'chart'
        self._rvr_last_mtime: float | None = None  # last chart render time

        # Track show/hide so we can start/stop tailing.
        self.view.installEventFilter(self)

    # ------------------------------------------------------------------
    # Qt event hook (show/hide)
    # ------------------------------------------------------------------

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # type: ignore[override]
        if obj is self.view:
            if event.type() == QEvent.Show:
                self._on_show()
            elif event.type() == QEvent.Hide:
                self._on_hide()
        return super().eventFilter(obj, event)

    def _on_show(self) -> None:
        """Refresh the file list and resume tailing when the view shows up."""
        self.refresh_file_list()
        if self._current_file and not self._timer.isActive():
            try:
                if self._fh is None:
                    self._start_tail(self._current_file)
                else:
                    self._timer.start()
            except Exception:
                pass

    def _on_hide(self) -> None:
        """Stop tailing when the view is hidden to avoid unnecessary I/O."""
        self._stop_tail()


    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_report_dir(self, path: str | Path) -> None:
        """Set the working report directory and refresh the file list if visible."""
        p = Path(path).resolve()
        previous = getattr(self, "_report_dir", None)
        if previous is None or p != previous:
            self._stop_tail()
            self._current_file = None
            self._rvr_last_mtime = None
            self.viewer.clear()
            self.chart_tabs.clear()
            self.viewer_stack.setCurrentWidget(self.viewer)
            self.file_list.clear()
        self._report_dir = p
        self.dir_label.setText(f"Report dir: {p.as_posix()}")
        if self.view.isVisible():
            self.refresh_file_list()

    def set_case_context(self, case_path: str | Path | None) -> None:
        """Provide the active test case path so the controller can infer test type."""
        if isinstance(case_path, str) and not case_path.strip():
            case_path = None
        if case_path:
            try:
                resolved = Path(case_path).resolve()
            except Exception:
                resolved = Path(str(case_path))
            self._active_case_path = resolved
        else:
            self._active_case_path = None
        inferred = (
            self._infer_test_type_from_case_path(self._active_case_path)
            if self._active_case_path
            else None
        )
        self._selected_test_type = inferred

    def refresh_file_list(self) -> None:
        """Populate the left-hand file list from the current report directory."""
        self.file_list.clear()
        if not self._report_dir or not self._report_dir.exists():
            return
        try:
            files = [
                f for f in sorted(self._report_dir.iterdir(), key=lambda x: x.name) if f.is_file()
            ]
        except Exception:
            files = []
        current = self._current_file.as_posix() if self._current_file else None
        selected_row = -1
        latest_row = -1
        latest_mtime: float | None = None
        for i, f in enumerate(files):
            it = QListWidgetItem(f.name)
            it.setToolTip(f.as_posix())
            self.file_list.addItem(it)
            if current and f.as_posix() == current:
                selected_row = i
            try:
                mtime = f.stat().st_mtime
            except Exception:
                mtime = None
            if mtime is not None and (latest_mtime is None or mtime > latest_mtime):
                latest_mtime = mtime
                latest_row = i
        if selected_row >= 0:
            self.file_list.setCurrentRow(selected_row)
        elif latest_row >= 0:
            self.file_list.setCurrentRow(latest_row)
        elif files:
            self.file_list.setCurrentRow(len(files) - 1)

    # ------------------------------------------------------------------
    # Selection / routing
    # ------------------------------------------------------------------

    def _on_file_selected(self) -> None:
        """Route to chart or text view based on the newly selected file."""
        items = self.file_list.selectedItems()
        if not items or not self._report_dir:
            self._stop_tail()
            self.viewer_stack.setCurrentWidget(self.viewer)
            return
        name = items[0].text()
        path = (self._report_dir / name).resolve()
        if self._should_show_rvr_chart(path):
            self._display_rvr_summary(path)
        else:
            self.viewer_stack.setCurrentWidget(self.viewer)
            self._start_tail(path)

    def _should_show_rvr_chart(self, path: Path) -> bool:
        """Return True if a file name/suffix suggests an RVR/RVO result file."""
        name = path.name.lower()
        suffix = path.suffix.lower()
        if suffix not in {".csv", ".xlsx", ".xls"}:
            return False
        keywords = (
            "rvr",
            "rvo",
            "performance",
            "peak_throughput",
            "peak-throughput",
            "peakthroughput",
        )
        return any(keyword in name for keyword in keywords)

    def _display_rvr_summary(self, path: Path) -> None:
        """Try to render charts for an RVR/RVO file; fall back to text view on failure."""
        self._stop_tail()
        self._current_file = path
        if self._render_rvr_charts(path, fallback_to_text=True):
            self._start_tail(path, force_view=False)
            self._view_mode = "chart"
            self.viewer_stack.setCurrentWidget(self.chart_tabs)
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._start_tail(path)

    # ------------------------------------------------------------------
    # Chart building
    # ------------------------------------------------------------------

    def _render_rvr_charts(self, path: Path, fallback_to_text: bool) -> bool:
        """Create/refresh chart tabs for an RVR/RVO file."""
        try:
            mtime = path.stat().st_mtime
        except FileNotFoundError:
            if fallback_to_text:
                self.viewer_stack.setCurrentWidget(self.viewer)
                self.viewer.clear()
                self.viewer.setPlainText("RVR result file not found")
                self._view_mode = "text"
                self._rvr_last_mtime = None
            return False
        except Exception as exc:
            logging.exception("Failed to stat RVR file: %s", exc)
            if fallback_to_text:
                self.viewer_stack.setCurrentWidget(self.viewer)
                self.viewer.clear()
                self.viewer.setPlainText(f"Failed to read RVR file: {exc}")
                self._view_mode = "text"
                self._rvr_last_mtime = None
            return False
        charts = self._build_rvr_charts(path)
        if not charts:
            if fallback_to_text:
                self.viewer_stack.setCurrentWidget(self.viewer)
                self.viewer.clear()
                self.viewer.setPlainText("No RVR data available for charting")
                self._view_mode = "text"
                self._rvr_last_mtime = None
            return False
        current_index = self.chart_tabs.currentIndex()
        charts_for_view = [
            (title, chart_widget) for title, chart_widget in charts if chart_widget is not None
        ]
        from src.ui.view.report import ReportView  # local import to avoid cycles

        if isinstance(self.view, ReportView):
            self.view.rebuild_chart_tabs(charts_for_view, keep_index=current_index)
        else:
            self.chart_tabs.clear()
            for title, widget in charts_for_view:
                if widget is not None:
                    self.chart_tabs.addTab(widget, title)
        self._rvr_last_mtime = mtime
        return True

    def _refresh_rvr_charts(self) -> None:
        """Refresh chart tabs when the underlying RVR file changes."""
        if not self._current_file or not self._current_file.exists():
            return
        try:
            mtime = self._current_file.stat().st_mtime
        except Exception:
            return
        if self._rvr_last_mtime is not None and mtime <= self._rvr_last_mtime:
            return
        self._render_rvr_charts(self._current_file, fallback_to_text=False)

    def _build_rvr_charts(self, path: Path) -> list[tuple[str, InteractiveChartLabel]]:
        """Build chart widgets for an RVR/RVO CSV/Excel file."""
        df = self._load_rvr_dataframe(path)
        charts_dir = path.parent / "rvr_charts"
        charts_dir.mkdir(exist_ok=True)
        if df.empty:
            title = path.stem or "RVR Chart"
            override_type = self._infer_test_type_from_selection()
            chart_kind = (
                "polar"
                if override_type and override_type.strip().upper() == "RVO"
                else "line"
            )
            placeholder = self._create_empty_chart_widget(title, charts_dir, chart_type=chart_kind)
            return [(title, placeholder)] if placeholder is not None else []
        results: list[tuple[str, InteractiveChartLabel]] = []
        grouped = df.groupby(
            [
                "__standard_display__",
                "__bandwidth_display__",
                "__freq_band_display__",
                "__test_type_display__",
                "__direction_display__",
            ],
            dropna=False,
        )
        sorted_groups = sorted(grouped, key=lambda item: self._group_sort_key(item[0]))
        for (standard, bandwidth, freq_band, test_type, direction), group in sorted_groups:
            if not direction:
                continue
            title = self._format_chart_title(standard, bandwidth, freq_band, test_type, direction)
            if not title:
                continue
            normalized_type = (test_type or "").strip().upper()
            if normalized_type == "RVO":
                widget = self._create_rvo_chart_widget(group, title, charts_dir)
            else:
                widget = self._create_line_chart_widget(group, title, charts_dir)
            if widget is not None:
                results.append((title, widget))
        if not results:
            title = path.stem or "RVR Chart"
            override_type = self._infer_test_type_from_selection()
            chart_kind = (
                "polar"
                if override_type and override_type.strip().upper() == "RVO"
                else "line"
            )
            placeholder = self._create_empty_chart_widget(title, charts_dir, chart_type=chart_kind)
            return [(title, placeholder)] if placeholder is not None else []
        return results

    def _create_line_chart_widget(
        self, group: pd.DataFrame, title: str, charts_dir: Path
    ) -> Optional[InteractiveChartLabel]:
        """Create a line chart of throughput vs. attenuation for RVR data."""
        steps = self._collect_step_labels(group)
        if not steps:
            return self._create_empty_chart_widget(title, charts_dir)
        x_positions = list(range(len(steps)))
        has_series = False
        fig, ax = plt.subplots(figsize=(7.8, 4.4), dpi=CHART_DPI)
        all_values: list[float] = []
        for channel, channel_df in group.groupby("__channel_display__", dropna=False):
            channel_name = channel or "Unknown"
            values: list[Optional[float]] = []
            for step in steps:
                subset = channel_df[channel_df["__step__"] == step]
                raw_values = [
                    v for v in subset["__throughput_value__"].tolist() if v is not None
                ]
                finite_values = [
                    float(v)
                    for v in raw_values
                    if isinstance(v, (int, float)) and math.isfinite(float(v))
                ]
                if finite_values:
                    avg_value = sum(finite_values) / len(finite_values)
                    values.append(avg_value)
                    all_values.append(avg_value)
                else:
                    values.append(None)
            if any(v is not None for v in values):
                has_series = True
                y_values = [v if v is not None else float("nan") for v in values]
                ax.plot(
                    x_positions,
                    y_values,
                    marker="o",
                    linestyle="-",
                    label=channel_name,
                )
        if not has_series:
            plt.close(fig)
            return self._create_empty_chart_widget(title, charts_dir)

        ax.set_title(title)
        ax.set_xlabel("Attenuation Step")
        ax.set_ylabel("Throughput (Mbps)")
        ax.set_xticks(x_positions)
        ax.set_xticklabels(steps, rotation=0)
        if all_values:
            max_val = max(all_values)
            ax.set_ylim(bottom=0, top=max_val * 1.1)
        ax.grid(True, linestyle="--", alpha=0.5)
        handles, labels = ax.get_legend_handles_labels()
        if handles:
            ax.legend(handles, labels, loc="best")

        canvas = FigureCanvasAgg(fig)
        canvas.draw()
        width, height = fig.get_size_inches() * fig.get_dpi()
        width = int(width)
        height = int(height)
        buf, (w, h) = canvas.print_to_buffer()
        image = QImage(buf, w, h, QImage.Format_RGBA8888)
        pixmap = QPixmap.fromImage(image)
        plt.close(fig)

        widget = InteractiveChartLabel()
        widget.setPixmap(pixmap)
        points: list[dict[str, object]] = []
        for line in ax.get_lines():
            if not isinstance(line, Line2D):
                continue
            xdata = line.get_xdata()
            ydata = line.get_ydata()
            for x, y in zip(xdata, ydata):
                if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
                    continue
                if not math.isfinite(y):
                    continue
                x_px = canvas.renderer.points_to_pixels(x)
                y_px = canvas.renderer.points_to_pixels(y)
                tooltip = self._make_tooltip_html(
                    title,
                    x_label="Step",
                    x_value=str(steps[int(x)]),
                    y_label="Throughput (Mbps)",
                    y_value=float(y),
                )
                points.append({"position": (x_px, y_px), "tooltip": tooltip})
        widget.set_points(points)

        try:
            charts_dir.mkdir(parents=True, exist_ok=True)
            out_path = charts_dir / f"{title}.png"
            pixmap.save(str(out_path), "PNG")
        except Exception:
            pass

        return widget

    def _create_rvo_chart_widget(
        self, group: pd.DataFrame, title: str, charts_dir: Path
    ) -> Optional[InteractiveChartLabel]:
        """Create a polar chart for RVO data."""
        angles = group["__angle__"].tolist()
        throughputs = group["__throughput_value__"].tolist()
        finite_pairs = [
            (float(a), float(t))
            for a, t in zip(angles, throughputs)
            if isinstance(a, (int, float))
            and isinstance(t, (int, float))
            and math.isfinite(a)
            and math.isfinite(t)
        ]
        if not finite_pairs:
            return self._create_empty_chart_widget(title, charts_dir, chart_type="polar")

        fig = plt.figure(figsize=(6.4, 6.4), dpi=CHART_DPI)
        ax = fig.add_subplot(111, projection="polar")
        theta = [math.radians(a) for a, _ in finite_pairs]
        r = [t for _, t in finite_pairs]
        ax.plot(theta, r, marker="o")
        ax.set_title(title)
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        ax.grid(True, linestyle="--", alpha=0.5)

        canvas = FigureCanvasAgg(fig)
        canvas.draw()
        width, height = fig.get_size_inches() * fig.get_dpi()
        width = int(width)
        height = int(height)
        buf, (w, h) = canvas.print_to_buffer()
        image = QImage(buf, w, h, QImage.Format_RGBA8888)
        pixmap = QPixmap.fromImage(image)
        plt.close(fig)

        widget = InteractiveChartLabel()
        widget.setPixmap(pixmap)
        points: list[dict[str, object]] = []
        for angle_deg, throughput in finite_pairs:
            angle_rad = math.radians(angle_deg)
            x = (angle_rad / (2 * math.pi)) * width
            y = height / 2 - (throughput / max(r)) * (height / 2)
            tooltip = self._make_tooltip_html(
                title,
                x_label="Angle (deg)",
                x_value=angle_deg,
                y_label="Throughput (Mbps)",
                y_value=throughput,
            )
            points.append({"position": (x, y), "tooltip": tooltip})
        widget.set_points(points)

        try:
            charts_dir.mkdir(parents=True, exist_ok=True)
            out_path = charts_dir / f"{title}.png"
            pixmap.save(str(out_path), "PNG")
        except Exception:
            pass

        return widget

    def _collect_step_labels(self, df: pd.DataFrame) -> list[str]:
        """Collect ordered step labels from a normalised RVR dataframe subset."""
        steps = df["__step__"].dropna().unique().tolist()
        steps = [str(s) for s in steps]
        try:
            steps.sort(key=lambda v: float(v))
        except Exception:
            steps.sort()
        return steps

    def _group_sort_key(self, key_tuple) -> tuple:
        """Return a sort key for grouped chart dimensions using configured orders."""
        standard, bandwidth, freq_band, test_type, direction = key_tuple
        standard_key = STANDARD_ORDER_MAP.get(str(standard).lower(), len(STANDARD_ORDER))
        bandwidth_key = BANDWIDTH_ORDER_MAP.get(str(bandwidth), len(BANDWIDTH_ORDER))
        freq_band_key = FREQ_BAND_ORDER_MAP.get(str(freq_band), len(FREQ_BAND_ORDER))
        test_type_key = TEST_TYPE_ORDER_MAP.get(str(test_type), len(TEST_TYPE_ORDER))
        direction_key = DIRECTION_ORDER_MAP.get(str(direction), len(DIRECTION_ORDER))
        return (standard_key, bandwidth_key, freq_band_key, test_type_key, direction_key)

    def _format_chart_title(
        self, standard: str, bandwidth: str, freq_band: str, test_type: str, direction: str
    ) -> str:
        """Format a human-readable chart title from group dimensions."""
        parts = []
        if standard:
            parts.append(str(standard))
        if bandwidth:
            parts.append(str(bandwidth))
        if freq_band:
            parts.append(str(freq_band))
        if test_type:
            parts.append(str(test_type))
        if direction:
            parts.append(str(direction))
        return " ".join(parts)

    def _create_empty_chart_widget(
        self, title: str, charts_dir: Path, *, chart_type: str = "line"
    ) -> Optional[InteractiveChartLabel]:
        """Create a placeholder chart widget when no data is available."""
        fig = None
        if chart_type == "polar":
            fig = plt.figure(figsize=(6.4, 6.4), dpi=CHART_DPI)
            ax = fig.add_subplot(111, projection="polar")
            ax.set_title(title)
            ax.text(0.5, 0.5, "No data", transform=ax.transAxes, ha="center", va="center")
        else:
            fig, ax = plt.subplots(figsize=(7.8, 4.4), dpi=CHART_DPI)
            ax.set_title(title)
            ax.text(0.5, 0.5, "No data", transform=ax.transAxes, ha="center", va="center")
        canvas = FigureCanvasAgg(fig)
        canvas.draw()
        width, height = fig.get_size_inches() * fig.get_dpi()
        width = int(width)
        height = int(height)
        buf, (w, h) = canvas.print_to_buffer()
        image = QImage(buf, w, h, QImage.Format_RGBA8888)
        pixmap = QPixmap.fromImage(image)
        plt.close(fig)
        widget = InteractiveChartLabel()
        widget.setPixmap(pixmap)
        try:
            charts_dir.mkdir(parents=True, exist_ok=True)
            out_path = charts_dir / f"{title}.png"
            pixmap.save(str(out_path), "PNG")
        except Exception:
            pass
        return widget

    def _make_tooltip_html(
        self,
        series: str,
        *,
        x_label: str,
        x_value: object,
        y_label: str,
        y_value: float,
    ) -> str:
        """Render a small HTML snippet describing a chart point."""
        try:
            value = float(y_value)
        except Exception:
            value_str = str(y_value)
        else:
            value_str = f"{value:.2f}".rstrip("0").rstrip(".")
        safe_series = escape(series)
        safe_step = escape(str(x_value))
        safe_x_label = escape(x_label)
        safe_y_label = escape(y_label)
        return (
            "<div style=\"color:#202020;\">"
            f"<b>{safe_series}</b><br/>"
            f"{safe_x_label}: {safe_step}<br/>"
            f"{safe_y_label}: {value_str}"
            "</div>"
        )

    # ------------------------------------------------------------------
    # Tailing
    # ------------------------------------------------------------------

    def _open_report_dir(self, event) -> None:
        """Open the current report directory in the system file browser (if it exists)."""
        if self._report_dir and self._report_dir.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._report_dir)))
        QLabel.mousePressEvent(self.dir_label, event)  # type: ignore[arg-type]

    def _start_tail(self, path: Path, *, force_view: bool = True) -> None:
        """Begin tailing a text file and optionally switch the UI to text mode."""
        self._stop_tail()
        if force_view:
            self.viewer_stack.setCurrentWidget(self.viewer)
            self._view_mode = "text"
            self._rvr_last_mtime = None
        self._current_file = path
        self.viewer.clear()
        try:
            fh = open(path, "rb", buffering=0)
        except Exception:
            self._fh = None
            return
        self._fh = fh
        try:
            size = os.fstat(fh.fileno()).st_size
        except Exception:
            size = path.stat().st_size if path.exists() else 0
        start = max(0, size - 64 * 1024)
        if start:
            try:
                fh.seek(start)
            except Exception:
                pass
        data = b""
        try:
            data = fh.read(max(0, size - start))
        except Exception:
            data = b""
        text = self._decode_bytes(data)
        lines = text.splitlines()
        tail_lines = lines[-500:] if len(lines) > 500 else lines
        if tail_lines:
            self._append_lines(tail_lines)
        self._pos = size
        self._partial = ""
        if self.view.isVisible():
            self._timer.start()

    def _stop_tail(self) -> None:
        """Stop the tail timer and close any open file handle."""
        if self._timer.isActive():
            self._timer.stop()
        if self._fh is not None:
            try:
                self._fh.close()
            except Exception:
                pass
        self._fh = None
        self._pos = 0
        self._partial = ""

    def _on_tail_tick(self) -> None:
        """Periodic callback that refreshes charts and appends any new log lines."""
        if self._view_mode == "chart":
            self._refresh_rvr_charts()
        if not self._fh or not self._current_file:
            return
        try:
            st = self._current_file.stat()
        except Exception:
            self._stop_tail()
            return
        size = st.st_size
        if size < self._pos:
            self._start_tail(self._current_file)
            return
        if size == self._pos:
            return
        try:
            self._fh.seek(self._pos)
            data = self._fh.read(size - self._pos)
        except Exception:
            self._stop_tail()
            return
        self._pos = size
        chunk = self._decode_bytes(data)
        if not chunk:
            return
        buf = self._partial + chunk
        lines = buf.split("\n")
        if not buf.endswith("\n"):
            self._partial = lines.pop() if lines else buf
        else:
            self._partial = ""
        if lines:
            self._append_lines(lines)

    def _append_lines(self, lines: list[str]) -> None:
        """Append a batch of lines to the text viewer and keep it scrolled to the end."""
        if not lines:
            return
        max_lines = 2000
        lines = lines[-max_lines:]
        html_lines = [
            (
                f"<span style='{STYLE_BASE} color:{TEXT_COLOR}; "
                "font-family: Consolas, \\'Courier New\\', monospace;'>"
                f"{escape(l)}</span>"
            )
            for l in lines
        ]
        self.viewer.append("\n".join(html_lines))
        cursor = self.viewer.textCursor()
        cursor.movePosition(cursor.End)
        self.viewer.setTextCursor(cursor)

    def _decode_bytes(self, data: bytes) -> str:
        """Decode a byte buffer to text using UTF-8 with fallbacks."""
        if not data:
            return ""
        try:
            return data.decode("utf-8", errors="replace")
        except Exception:
            try:
                return data.decode("gbk", errors="replace")
            except Exception:
                return data.decode("latin1", errors="replace")


__all__ = ["ReportController", "InteractiveChartLabel"]
