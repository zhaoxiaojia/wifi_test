#!/usr/bin/env python
# encoding: utf-8

from __future__ import annotations

import logging
import os
import math
from pathlib import Path
from typing import Optional
from html import escape

import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.lines import Line2D

import pandas as pd
from PyQt5.QtCore import Qt, QTimer, QEvent
from PyQt5.QtGui import QPixmap, QImage, QFont
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
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
from qfluentwidgets import CardWidget, StrongBodyLabel

from .theme import apply_theme
from src.util.constants import (
    BACKGROUND_COLOR,
    BANDWIDTH_ORDER,
    BANDWIDTH_ORDER_MAP,
    CHART_DPI,
    DIRECTION_ORDER,
    DIRECTION_ORDER_MAP,
    FREQ_BAND_ORDER,
    FREQ_BAND_ORDER_MAP,
    FONT_FAMILY,
    STANDARD_ORDER,
    STANDARD_ORDER_MAP,
    STYLE_BASE,
    TEST_TYPE_ORDER,
    TEST_TYPE_ORDER_MAP,
    TEXT_COLOR,
)
from src.util.rvr_chart_logic import RvrChartLogic

class InteractiveChartLabel(QLabel):
    """QLabel subclass that shows tooltips for chart points when hovered."""

    _TOOLTIP_CONFIGURED = False

    def __init__(self, parent=None):
        super().__init__(parent)
        if not InteractiveChartLabel._TOOLTIP_CONFIGURED:
            QToolTip.setFont(QFont(FONT_FAMILY, 11))
            if hasattr(QToolTip, 'setStyleSheet'):
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

    def set_points(self, points: list[dict[str, object]]) -> None:
        self._base_points = points or []
        self._refresh_points()

    def mouseMoveEvent(self, event):
        if self._points:
            target = self._find_point(event.pos())
            if target is not self._last_point:
                tooltip = target.get('tooltip', '') if target else ''
                if tooltip:
                    QToolTip.showText(self.mapToGlobal(event.pos()), tooltip, self)
                else:
                    QToolTip.hideText()
                self._last_point = target
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        QToolTip.hideText()
        super().mousePressEvent(event)

    def leaveEvent(self, event):
        self._last_point = None
        QToolTip.hideText()
        super().leaveEvent(event)

    def setPixmap(self, pixmap: QPixmap) -> None:  # type: ignore[override]
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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._original_pixmap is not None:
            self._update_scaled_pixmap()
            self._refresh_points()

    def _find_point(self, pos):
        radius_sq = float(self._hit_radius * self._hit_radius)
        best_point = None
        best_distance = radius_sq
        x = float(pos.x())
        y = float(pos.y())
        for point in self._points:
            px, py = point.get('position', (None, None))
            if px is None or py is None:
                continue
            dx = x - float(px)
            dy = y - float(py)
            dist_sq = dx * dx + dy * dy
            if dist_sq <= best_distance:
                best_distance = dist_sq
                best_point = point
        return best_point

    def _refresh_points(self) -> None:
        self._hit_radius = 12
        if not self._base_points:
            self._points = []
        elif not self._original_width or not self._original_height:
            self._points = [dict(point) for point in self._base_points]
        elif not self._current_pixmap_width or not self._current_pixmap_height:
            self._points = [dict(point) for point in self._base_points]
        else:
            scale_x = self._current_pixmap_width / float(self._original_width)
            scale_y = self._current_pixmap_height / float(self._original_height)
            offset_x = max(0.0, (self.width() - self._current_pixmap_width) / 2.0)
            offset_y = max(0.0, (self.height() - self._current_pixmap_height) / 2.0)
            scaled_points: list[dict[str, object]] = []
            for point in self._base_points:
                raw_pos = point.get('position', (None, None))
                if not isinstance(raw_pos, (tuple, list)) or len(raw_pos) != 2:
                    continue
                px, py = raw_pos
                if px is None or py is None:
                    continue
                new_point = dict(point)
                new_point['position'] = (
                    offset_x + float(px) * scale_x,
                    offset_y + float(py) * scale_y,
                )
                scaled_points.append(new_point)
            avg_scale = (scale_x + scale_y) / 2.0
            self._hit_radius = max(6, int(round(12 * avg_scale)))
            self._points = scaled_points
        self._last_point = None
        has_points = bool(self._points)
        self.setMouseTracking(has_points)
        self.setCursor(Qt.PointingHandCursor if has_points else Qt.ArrowCursor)
        if not has_points:
            QToolTip.hideText()

    def _update_scaled_pixmap(self) -> None:
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

class ReportPage(RvrChartLogic, CardWidget):
    """Simple report viewer page.

    - Disabled in navigation by default; MainWindow enables it once report_dir is created
    - Lists all files under current report_dir
    - When a file is selected, shows its content as text and tails while page is visible
    - Stops tailing and releases file handle when page is hidden or switched away
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("reportPage")
        apply_theme(self)

        self._report_dir: Optional[Path] = None
        self._current_file: Optional[Path] = None
        self._fh = None  # type: ignore
        self._pos: int = 0
        self._partial: str = ""
        self._active_case_path: Optional[Path] = None
        self._selected_test_type: Optional[str] = None

        # timer for tailing
        self._timer = QTimer(self)
        self._timer.setInterval(300)
        self._timer.timeout.connect(self._on_tail_tick)

        # UI
        root = QVBoxLayout(self)
        root.setSpacing(12)

        self.title_label = StrongBodyLabel("Reports")
        apply_theme(self.title_label)
        self.title_label.setStyleSheet(
            f"border-left: 4px solid #0067c0; padding-left: 8px; font-family:{FONT_FAMILY};"
        )
        root.addWidget(self.title_label)

        self.dir_label = QLabel("Report dir: -")
        apply_theme(self.dir_label)
        root.addWidget(self.dir_label)

        body = QHBoxLayout()
        body.setSpacing(12)
        root.addLayout(body)

        # left: files
        self.file_list = QListWidget(self)
        apply_theme(self.file_list)
        self.file_list.setSelectionMode(self.file_list.SingleSelection)
        self.file_list.itemSelectionChanged.connect(self._on_file_selected)
        body.addWidget(self.file_list, 1)

        # right: stacked viewer (text tail + chart tabs)
        self.viewer_stack = QStackedWidget(self)
        body.addWidget(self.viewer_stack, 3)

        self.viewer = QTextEdit(self.viewer_stack)
        self.viewer.setReadOnly(True)
        apply_theme(self.viewer)
        self.viewer.document().setMaximumBlockCount(5000)
        self.viewer.setMinimumHeight(400)
        self.viewer_stack.addWidget(self.viewer)

        self.chart_tabs = QTabWidget(self.viewer_stack)
        apply_theme(self.chart_tabs)
        self.chart_tabs.setDocumentMode(True)
        self.chart_tabs.setElideMode(Qt.ElideRight)
        pane_style = f"""
        QTabWidget::pane {{
            background: {BACKGROUND_COLOR};
            border: 1px solid #3a3a3a;
        }}
        """
        tab_bar_style = f"""
        QTabBar::tab {{
            {STYLE_BASE}
            color: {TEXT_COLOR};
            background: #3a3a3a;
            padding: 6px 14px;
            margin: 2px 8px 0 0;
            border-radius: 4px;
        }}
        QTabBar::tab:selected {{
            background: #565656;
            color: {TEXT_COLOR};
        }}
        QTabBar::tab:hover {{
            background: #464646;
        }}
        """
        self.chart_tabs.setStyleSheet(self.chart_tabs.styleSheet() + pane_style)
        tab_bar = self.chart_tabs.tabBar()
        if tab_bar is not None:
            tab_bar.setStyleSheet(tab_bar.styleSheet() + tab_bar_style)
        self.viewer_stack.addWidget(self.chart_tabs)
        self.viewer_stack.setCurrentWidget(self.viewer)

        self.setLayout(root)

        self._view_mode: str = 'text'
        self._rvr_last_mtime: float | None = None

    # -------- public API ---------
    def set_report_dir(self, path: str | Path) -> None:
        p = Path(path).resolve()
        previous = getattr(self, "_report_dir", None)
        if previous is None or p != previous:
            self._stop_tail()
            self._current_file = None
            self._rvr_last_mtime = None
            if hasattr(self, "viewer"):
                self.viewer.clear()
            if hasattr(self, "chart_tabs"):
                self.chart_tabs.clear()
            if hasattr(self, "viewer_stack"):
                self.viewer_stack.setCurrentWidget(self.viewer)
            if hasattr(self, "file_list"):
                self.file_list.clear()
        self._report_dir = p
        self.dir_label.setText(f"Report dir: {p.as_posix()}")
        # refresh now if visible
        if self.isVisible():
            self.refresh_file_list()

    def set_case_context(self, case_path: str | Path | None) -> None:
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
        inferred = self._infer_test_type_from_case_path(self._active_case_path) if self._active_case_path else None
        self._selected_test_type = inferred

    def refresh_file_list(self) -> None:
        self.file_list.clear()
        if not self._report_dir or not self._report_dir.exists():
            return
        try:
            files = [
                f for f in sorted(self._report_dir.iterdir(), key=lambda x: x.name)
                if f.is_file()
            ]
        except Exception:
            files = []
        # preserve selection if possible
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

    # -------- events ---------
    def showEvent(self, event: QEvent):
        super().showEvent(event)
        # refresh files whenever entering this page
        self.refresh_file_list()
        # resume tail if a file is already selected
        if self._current_file and not self._timer.isActive():
            # safe-guard: re-open handle if needed
            try:
                if self._fh is None:
                    self._start_tail(self._current_file)
                else:
                    self._timer.start()
            except Exception:
                pass

    def hideEvent(self, event: QEvent):
        self._stop_tail()
        super().hideEvent(event)

    # -------- internal tail logic ---------
    def _on_file_selected(self):
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
        name = path.name.lower()
        suffix = path.suffix.lower()
        if suffix not in {'.csv', '.xlsx', '.xls'}:
            return False
        keywords = ('rvr', 'rvo', 'performance', 'peak_throughput', 'peak-throughput', 'peakthroughput')
        return any(keyword in name for keyword in keywords)

    def _display_rvr_summary(self, path: Path) -> None:
        self._stop_tail()
        self._current_file = path
        if self._render_rvr_charts(path, fallback_to_text=True):
            self._start_tail(path, force_view=False)
            self._view_mode = 'chart'
            self.viewer_stack.setCurrentWidget(self.chart_tabs)
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._start_tail(path)


    def _render_rvr_charts(self, path: Path, fallback_to_text: bool) -> bool:
        try:
            mtime = path.stat().st_mtime
        except FileNotFoundError:
            if fallback_to_text:
                self.viewer_stack.setCurrentWidget(self.viewer)
                self.viewer.clear()
                self.viewer.setPlainText('RVR result file not found')
                self._view_mode = 'text'
                self._rvr_last_mtime = None
            return False
        except Exception as exc:
            logging.exception('Failed to stat RVR file: %s', exc)
            if fallback_to_text:
                self.viewer_stack.setCurrentWidget(self.viewer)
                self.viewer.clear()
                self.viewer.setPlainText(f'Failed to read RVR file: {exc}')
                self._view_mode = 'text'
                self._rvr_last_mtime = None
            return False
        charts = self._build_rvr_charts(path)
        if not charts:
            if fallback_to_text:
                self.viewer_stack.setCurrentWidget(self.viewer)
                self.viewer.clear()
                self.viewer.setPlainText('No RVR data available for charting')
                self._view_mode = 'text'
                self._rvr_last_mtime = None
            return False
        current_index = self.chart_tabs.currentIndex()
        self.chart_tabs.blockSignals(True)
        try:
            self.chart_tabs.clear()
            for title, chart_widget in charts:
                if chart_widget is None:
                    continue
                container = QWidget(self.chart_tabs)
                container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                layout = QVBoxLayout(container)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(0)
                layout.addWidget(chart_widget)
                self.chart_tabs.addTab(container, title)
        finally:
            self.chart_tabs.blockSignals(False)
        if 0 <= current_index < self.chart_tabs.count():
            self.chart_tabs.setCurrentIndex(current_index)
        elif self.chart_tabs.count() > 0:
            self.chart_tabs.setCurrentIndex(0)
        self._rvr_last_mtime = mtime
        return True

    def _refresh_rvr_charts(self) -> None:
        if self._current_file is None:
            return
        try:
            mtime = self._current_file.stat().st_mtime
        except Exception:
            return
        if self._rvr_last_mtime is not None and mtime <= self._rvr_last_mtime:
            return
        if self._render_rvr_charts(self._current_file, fallback_to_text=False):
            self._view_mode = 'chart'
            self.viewer_stack.setCurrentWidget(self.chart_tabs)

    def _build_rvr_charts(self, path: Path) -> list[tuple[str, InteractiveChartLabel]]:
        df = self._load_rvr_dataframe(path)
        charts_dir = path.parent / 'rvr_charts'
        charts_dir.mkdir(exist_ok=True)
        if df.empty:
            title = path.stem or 'RVR Chart'
            override_type = self._infer_test_type_from_selection()
            chart_kind = 'polar' if override_type and override_type.strip().upper() == 'RVO' else 'line'
            placeholder = self._create_empty_chart_widget(title, charts_dir, chart_type=chart_kind)
            return [(title, placeholder)] if placeholder is not None else []
        results: list[tuple[str, InteractiveChartLabel]] = []
        grouped = df.groupby(
            [
                '__standard_display__',
                '__bandwidth_display__',
                '__freq_band_display__',
                '__test_type_display__',
                '__direction_display__',
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
            if normalized_type == 'RVO':
                widget = self._create_rvo_chart_widget(group, title, charts_dir)
            else:
                widget = self._create_line_chart_widget(group, title, charts_dir)
            if widget is not None:
                results.append((title, widget))
        if not results:
            title = path.stem or 'RVR Chart'
            override_type = self._infer_test_type_from_selection()
            chart_kind = 'polar' if override_type and override_type.strip().upper() == 'RVO' else 'line'
            placeholder = self._create_empty_chart_widget(title, charts_dir, chart_type=chart_kind)
            return [(title, placeholder)] if placeholder is not None else []
        return results

    def _create_line_chart_widget(
        self,
        group: pd.DataFrame,
        title: str,
        charts_dir: Path,
    ) -> Optional[InteractiveChartLabel]:
        steps = self._collect_step_labels(group)
        if not steps:
            return self._create_empty_chart_widget(title, charts_dir)
        x_positions = list(range(len(steps)))
        has_series = False
        fig, ax = plt.subplots(figsize=(7.8, 4.4), dpi=CHART_DPI)
        all_values: list[float] = []
        for channel, channel_df in group.groupby('__channel_display__', dropna=False):
            channel_name = channel or 'Unknown'
            values: list[Optional[float]] = []
            for step in steps:
                subset = channel_df[channel_df['__step__'] == step]
                raw_values = [v for v in subset['__throughput_value__'].tolist() if v is not None]
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
                ax.plot(
                    x_positions,
                    self._series_with_nan(values),
                    marker='o',
                    markersize=5,
                    label=self._format_channel_series_label(channel_name),
                )
        if not has_series:
            plt.close(fig)
            return self._create_empty_chart_widget(title, charts_dir, steps)
        self._configure_step_axis(ax, steps)
        ax.set_xlabel('attenuation (dB)')
        ax.set_ylabel('throughput (Mbps)')
        ax.set_title(title, loc='left', pad=4)
        ax.grid(alpha=0.3, linestyle='--')
        if all_values:
            y_max = max(all_values)
            y_min = min(all_values)
            span = max(y_max - y_min, 1.0)
            extra = max(span * 0.15, y_max * 0.05, 1.0)
            ax.set_ylim(bottom=0, top=y_max + extra)
        else:
            ax.set_ylim(bottom=0)
        handles, labels = ax.get_legend_handles_labels()
        handles = list(handles)
        labels = list(labels)
        legend = None
        if handles:
            annotations = self._collect_user_annotations(group)
            if annotations:
                dummy_handles = [Line2D([], [], linestyle='None', marker='', linewidth=0) for _ in annotations]
                handles.extend(dummy_handles)
                labels.extend(annotations)
            column_count = max(1, min(len(handles), 4))
            legend = ax.legend(
                handles,
                labels,
                loc='lower center',
                bbox_to_anchor=(0.5, 0.02),
                ncol=column_count,
                borderaxespad=0.2,
                frameon=False,
            )
        if legend is not None:
            for text_item in legend.get_texts():
                text_item.set_ha('center')
        fig.tight_layout(pad=0.6)
        save_path = charts_dir / f"{self._safe_chart_name(title)}.png"
        return self._figure_to_label(fig, ax, steps, save_path)

    def _create_rvo_chart_widget(
        self,
        group: pd.DataFrame,
        title: str,
        charts_dir: Path,
    ) -> Optional[InteractiveChartLabel]:
        angle_positions = self._collect_angle_positions(group)
        if not angle_positions:
            return self._create_empty_chart_widget(title, charts_dir, chart_type='polar')
        angle_values = [value for value, _ in angle_positions]
        angle_labels = [label for _, label in angle_positions]
        theta = [math.radians(value) for value in angle_values]
        theta_cycle = theta + [theta[0]] if theta else []
        fig, ax = plt.subplots(figsize=(6.6, 6.6), dpi=CHART_DPI, subplot_kw={'projection': 'polar'})
        ax.set_theta_zero_location('N')
        ax.set_theta_direction(-1)
        ax.set_xticks(theta)
        ax.set_xticklabels(angle_labels)
        channel_series = self._collect_rvo_channel_series(group, angle_values)
        if not channel_series:
            plt.close(fig)
            return self._create_empty_chart_widget(title, charts_dir, chart_type='polar')
        all_values: list[float] = []
        for series_label, values in channel_series:
            cycle_values = list(values)
            cycle_values.append(values[0] if values else None)
            ax.plot(theta_cycle, self._series_with_nan(cycle_values), marker='o', label=series_label)
            all_values.extend([v for v in values if v is not None])
        if all_values:
            max_value = max(all_values)
            if max_value <= 0:
                max_value = 1.0
            extra = max(max_value * 0.15, 1.0)
            ax.set_ylim(0, max_value + extra)
        else:
            ax.set_ylim(0, 1)
        ax.set_rlabel_position(135)
        ax.grid(alpha=0.3, linestyle='--')
        ax.set_title(title, pad=8)
        handles, labels = ax.get_legend_handles_labels()
        handles = list(handles)
        labels = list(labels)
        if handles:
            annotations = self._collect_user_annotations(group)
            if annotations:
                dummy_handles = [Line2D([], [], linestyle='None', marker='', linewidth=0) for _ in annotations]
                handles.extend(dummy_handles)
                labels.extend(annotations)
            legend = ax.legend(
                handles,
                labels,
                loc='lower center',
                bbox_to_anchor=(0.5, -0.08),
                ncol=max(1, min(len(handles), 3)),
                frameon=False,
            )
            if legend is not None:
                for text_item in legend.get_texts():
                    text_item.set_ha('center')
        fig.tight_layout(pad=0.7)
        save_path = charts_dir / f"{self._safe_chart_name(title)}.png"
        return self._figure_to_label(fig, ax, [], save_path)

    def _create_empty_chart_widget(
        self,
        title: str,
        charts_dir: Path,
        steps: Optional[list[str]] = None,
        chart_type: str = 'line',
    ) -> Optional[InteractiveChartLabel]:
        chart_type = (chart_type or 'line').lower()
        if chart_type == 'polar':
            fig = plt.figure(figsize=(6.6, 6.6), dpi=CHART_DPI)
            ax = fig.add_subplot(111, projection='polar')
            ax.set_theta_zero_location('N')
            ax.set_theta_direction(-1)
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_ylim(0, 1)
            ax.grid(alpha=0.25, linestyle='--')
            ax.set_title(title, pad=8)
            ax.text(0.5, 0.5, 'No data collected yet', transform=ax.transAxes, ha='center', va='center', color='#888888')
            fig.tight_layout(pad=0.6)
            save_path = charts_dir / f"{self._safe_chart_name(title)}.png"
            return self._figure_to_label(fig, ax, [], save_path)

        fig, ax = plt.subplots(figsize=(7.5, 4.2), dpi=CHART_DPI)
        steps = steps or []
        if steps:
            self._configure_step_axis(ax, steps)
        else:
            ax.set_xticks([])
            ax.set_xlim(0, 1)
        ax.set_xlabel('attenuation (dB)')
        ax.set_ylabel('throughput (Mbps)')
        ax.set_title(title, loc='left', pad=4)
        ax.grid(alpha=0.2, linestyle='--')
        ax.set_ylim(0, 1)
        ax.text(0.5, 0.5, 'No data collected yet', transform=ax.transAxes, ha='center', va='center', color='#888888')
        fig.tight_layout(pad=0.6)
        save_path = charts_dir / f"{self._safe_chart_name(title)}.png"
        return self._figure_to_label(fig, ax, steps, save_path)

    def _figure_to_label(self, fig, ax, steps: list[str], save_path: Optional[Path]) -> Optional[InteractiveChartLabel]:
        try:
            canvas = FigureCanvasAgg(fig)
            canvas.draw()
            width, height = canvas.get_width_height()
            buffer = canvas.buffer_rgba()
            image = QImage(buffer, width, height, QImage.Format_RGBA8888).copy()
            pixmap = QPixmap.fromImage(image)
            label = InteractiveChartLabel()
            label.setPixmap(pixmap)
            points = self._extract_chart_points(ax, steps, width, height)
            label.set_points(points)
            if save_path is not None:
                save_path.parent.mkdir(parents=True, exist_ok=True)
                fig.savefig(str(save_path), dpi=fig.dpi)
            plt.close(fig)
            return label
        except Exception:
            logging.exception('Failed to render chart figure')
            plt.close(fig)
            return None
          

    def _extract_chart_points(self, ax, steps: list[str], width: int, height: int) -> list[dict[str, object]]:
        points: list[dict[str, object]] = []
        if ax is None:
            return points
        x_label = (ax.get_xlabel() or 'X').strip() or 'X'
        y_label = (ax.get_ylabel() or 'Y').strip() or 'Y'
        step_count = len(steps)
        for line in ax.get_lines():
            label = line.get_label()
            if not label or label.startswith('_'):
                continue
            x_data = line.get_xdata()
            y_data = line.get_ydata()
            for x, y in zip(x_data, y_data):
                if y is None:
                    continue
                try:
                    y_val = float(y)
                except (TypeError, ValueError):
                    continue
                if math.isnan(y_val):
                    continue
                try:
                    x_val = float(x)
                except (TypeError, ValueError):
                    continue
                if math.isnan(x_val):
                    continue
                index = int(round(x_val))
                if 0 <= index < step_count:
                    raw_step = steps[index]
                    step_label = self._format_step_label(str(raw_step)) or str(raw_step)
                else:
                    step_label = self._format_step_label(str(x_val)) or str(x_val)
                step_label = step_label or str(x_val)
                display_x, display_y = ax.transData.transform((x_val, y_val))
                tooltip = self._build_point_tooltip(label, step_label, y_val, x_label, y_label)
                points.append(
                    {
                        'position': (float(display_x), float(height - display_y)),
                        'tooltip': tooltip,
                    }
                )
        return points


    def _build_point_tooltip(self, series: str, step: str, value: float, x_label: str, y_label: str) -> str:

        value_str = f"{value:.2f}".rstrip('0').rstrip('.')

        safe_series = escape(series)

        safe_step = escape(step)

        safe_x_label = escape(x_label)

        safe_y_label = escape(y_label)

        return (

            '<div style="color:#202020;">'

            f'<b>{safe_series}</b><br/>'

            f'{safe_x_label}: {safe_step}<br/>'

            f'{safe_y_label}: {value_str}'

            '</div>'

        )

    def _start_tail(self, path: Path, *, force_view: bool = True):
        # stop previous
        self._stop_tail()
        if force_view:
            self.viewer_stack.setCurrentWidget(self.viewer)
            self._view_mode = 'text'
            self._rvr_last_mtime = None
        self._current_file = path
        self.viewer.clear()
        # open and jump to last N lines
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

        # read tail chunk (last ~64KB) and show last 500 lines
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
        # start timer only if page visible
        if self.isVisible():
            self._timer.start()

    def _stop_tail(self):
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

    def _on_tail_tick(self):
        if self._view_mode == 'chart':
            self._refresh_rvr_charts()
        if not self._fh or not self._current_file:
            return
        try:
            st = self._current_file.stat()
        except Exception:
            # file removed; stop
            self._stop_tail()
            return
        size = st.st_size
        if size < self._pos:
            # truncated or rotated; restart
            self._start_tail(self._current_file)
            return
        if size == self._pos:
            return
        try:
            self._fh.seek(self._pos)
            data = self._fh.read(size - self._pos)
        except Exception:
            # read failed; try reopen next tick
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
        if not lines:
            return
        # limit render per tick to avoid UI jank
        max_lines = 2000
        lines = lines[-max_lines:]
        html_lines = [
            f"<span style='{STYLE_BASE} color:{TEXT_COLOR}; font-family: Consolas, \'Courier New\', monospace;'>{escape(l)}</span>"
            for l in lines
        ]
        self.viewer.append("\n".join(html_lines))
        # auto-scroll
        cursor = self.viewer.textCursor()
        cursor.movePosition(cursor.End)
        self.viewer.setTextCursor(cursor)

    def _decode_bytes(self, data: bytes) -> str:
        if not data:
            return ""
        try:
            return data.decode("utf-8", errors="replace")
        except Exception:
            try:
                return data.decode("gbk", errors="replace")
            except Exception:
                return data.decode("latin1", errors="replace")
            data = self._fh.read(size - self._pos)
        except Exception:
            # read failed; try reopen next tick
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
        if not lines:
            return
        # limit render per tick to avoid UI jank
        max_lines = 2000
        lines = lines[-max_lines:]
        html_lines = [
            f"<span style='{STYLE_BASE} color:{TEXT_COLOR}; font-family: Consolas, \'Courier New\', monospace;'>{escape(l)}</span>"
            for l in lines
        ]
        self.viewer.append("\n".join(html_lines))
        # auto-scroll
        cursor = self.viewer.textCursor()
        cursor.movePosition(cursor.End)
        self.viewer.setTextCursor(cursor)

    def _decode_bytes(self, data: bytes) -> str:
        if not data:
            return ""
        try:
            return data.decode("utf-8", errors="replace")
        except Exception:
            try:
                return data.decode("gbk", errors="replace")
            except Exception:
                return data.decode("latin1", errors="replace")

