#!/usr/bin/env python
# encoding: utf-8

from __future__ import annotations

import logging
import os
import re
import math
from pathlib import Path
from typing import Optional
from html import escape

import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg

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
    QScrollArea,
    QToolTip,
)
from qfluentwidgets import CardWidget, StrongBodyLabel

from .theme import apply_theme, FONT_FAMILY, STYLE_BASE, TEXT_COLOR, BACKGROUND_COLOR
CHART_DPI = 150

STANDARD_ORDER = ("11ax", "11ac", "11n")
BANDWIDTH_ORDER = ("20MHz", "40MHz", "80MHz", "160MHz")
FREQ_BAND_ORDER = ("2.4G", "5G", "6G")
TEST_TYPE_ORDER = ("RVR", "RVO")
DIRECTION_ORDER = ("TX", "RX")

STANDARD_ORDER_MAP = {value.lower(): index for index, value in enumerate(STANDARD_ORDER)}
BANDWIDTH_ORDER_MAP = {value.lower(): index for index, value in enumerate(BANDWIDTH_ORDER)}
FREQ_BAND_ORDER_MAP = {value.lower(): index for index, value in enumerate(FREQ_BAND_ORDER)}
TEST_TYPE_ORDER_MAP = {value.upper(): index for index, value in enumerate(TEST_TYPE_ORDER)}
DIRECTION_ORDER_MAP = {value.upper(): index for index, value in enumerate(DIRECTION_ORDER)}

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
        self._points: list[dict[str, object]] = []
        self._hit_radius = 12
        self._last_point: Optional[dict[str, object]] = None
        self.setMouseTracking(True)

    def set_points(self, points: list[dict[str, object]]) -> None:
        self._points = points or []
        self._last_point = None
        has_points = bool(self._points)
        self.setMouseTracking(has_points)
        self.setCursor(Qt.PointingHandCursor if has_points else Qt.ArrowCursor)
        if not has_points:
            QToolTip.hideText()

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

class ReportPage(CardWidget):
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
        self._report_dir = p
        self.dir_label.setText(f"Report dir: {p.as_posix()}")
        # refresh now if visible
        if self.isVisible():
            self.refresh_file_list()

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
        for i, f in enumerate(files):
            it = QListWidgetItem(f.name)
            it.setToolTip(f.as_posix())
            self.file_list.addItem(it)
            if current and f.as_posix() == current:
                selected_row = i
        if selected_row >= 0:
            self.file_list.setCurrentRow(selected_row)

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
        return 'rvr' in name

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
                scroll = QScrollArea(self.chart_tabs)
                scroll.setWidgetResizable(True)
                chart_widget.setParent(scroll)
                scroll.setWidget(chart_widget)
                self.chart_tabs.addTab(scroll, title)
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
            placeholder = self._create_empty_chart_widget(title, charts_dir)
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
            if test_type.upper() == 'RVO':
                widget = self._create_pie_chart_widget(group, title, charts_dir)
            else:
                widget = self._create_line_chart_widget(group, title, charts_dir)
            if widget is not None:
                results.append((title, widget))
        if not results:
            title = path.stem or 'RVR Chart'
            placeholder = self._create_empty_chart_widget(title, charts_dir)
            return [(title, placeholder)] if placeholder is not None else []
        return results

    def _load_rvr_dataframe(self, path: Path) -> pd.DataFrame:
        try:
            if path.suffix.lower() == '.csv':
                try:
                    df = pd.read_csv(path)
                except UnicodeDecodeError:
                    df = pd.read_csv(path, encoding='gbk')
            else:
                sheets = pd.read_excel(path, sheet_name=None)
                frames = [sheet for sheet in sheets.values() if sheet is not None and not sheet.empty]
                df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        except Exception as exc:
            logging.exception('Failed to read RVR results: %s', exc)
            return pd.DataFrame()
        if df is None or df.empty:
            return pd.DataFrame()
        return self._prepare_rvr_dataframe(df)

    def _prepare_rvr_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()
        prepared = df.copy()
        prepared.columns = [str(c).strip() for c in prepared.columns]
        for column in prepared.columns:
            prepared[column] = prepared[column].apply(lambda v: v.strip() if isinstance(v, str) else v)
        if 'Direction' in prepared.columns:
            prepared['Direction'] = prepared['Direction'].astype(str).str.upper()
        for col in ('Freq_Band', 'Standard', 'BW', 'CH_Freq_MHz', 'DB'):
            if col in prepared.columns:
                prepared[col] = prepared[col].astype(str)
        row_count = len(prepared)

        def source_series(*names: str) -> pd.Series:
            for name in names:
                if name in prepared.columns:
                    return prepared[name]
            return pd.Series([''] * row_count, index=prepared.index, dtype=object)

        standard_series = source_series('Standard')
        prepared['__standard_display__'] = standard_series.apply(self._format_standard_display).replace('', 'Unknown')

        bandwidth_series = source_series('BW', 'Bandwidth')
        prepared['__bandwidth_display__'] = bandwidth_series.apply(self._format_bandwidth_display).replace('', 'Unknown')

        freq_series = source_series('Freq_Band', 'Frequency Band', 'Band')
        freq_display = freq_series.apply(self._format_freq_band_display)
        if freq_display.eq('').all() and 'CH_Freq_MHz' in prepared.columns:
            channel_freq = source_series('CH_Freq_MHz').apply(self._format_freq_band_display)
            freq_display = freq_display.where(freq_display != '', channel_freq)
        prepared['__freq_band_display__'] = freq_display.replace('', 'Unknown')

        prepared['__direction_display__'] = source_series('Direction').apply(self._format_direction_display)

        prepared['__channel_display__'] = source_series('CH_Freq_MHz', 'Channel').apply(self._format_channel_display)

        prepared['__db_display__'] = source_series('DB', 'Total_Path_Loss', 'RxP', 'Attenuation', 'Path_Loss').apply(self._format_db_display)

        prepared['__rssi_display__'] = source_series('RSSI', 'Data_RSSI', 'Data RSSI').apply(self._format_metric_display)

        prepared['__test_type_display__'] = prepared.apply(self._detect_test_type_from_row, axis=1)

        step_candidates = ('DB', 'Total_Path_Loss', 'RxP', 'Step', 'Attenuation')

        def resolve_step(row: pd.Series) -> str | None:
            for name in step_candidates:
                if name in row:
                    value = row.get(name)
                    display = self._format_db_display(value)
                    if display:
                        return display
                    normalized = self._normalize_step(value)
                    if normalized:
                        return normalized
            return None

        prepared['__step__'] = prepared.apply(resolve_step, axis=1)
        fallback_steps = pd.Series([str(i + 1) for i in range(row_count)], index=prepared.index)
        prepared['__step__'] = prepared['__step__'].fillna(fallback_steps)
        empty_mask = prepared['__step__'] == ''
        if empty_mask.any():
            prepared.loc[empty_mask, '__step__'] = fallback_steps[empty_mask]

        throughput_columns = self._resolve_throughput_columns(prepared.columns)
        if throughput_columns:
            prepared['__throughput_value__'] = prepared.apply(
                lambda row: self._aggregate_throughput_row(row, throughput_columns),
                axis=1,
            )
        else:
            prepared['__throughput_value__'] = source_series('Throughput').apply(self._safe_float)

        prepared['__throughput_value__'] = prepared['__throughput_value__'].apply(
            lambda value: float(value) if isinstance(value, (int, float)) else value
        )

        return prepared.reset_index(drop=True)


    def _resolve_throughput_columns(self, columns: pd.Index) -> list[str]:
        if 'Throughput' not in columns:
            return []
        start = columns.get_loc('Throughput')
        if 'Expect_Rate' in columns:
            end = columns.get_loc('Expect_Rate')
            if end <= start:
                end = start + 1
        else:
            end = len(columns)
        return list(columns[start:end])

    def _aggregate_throughput_row(self, row: pd.Series, columns: list[str]) -> Optional[float]:
        values: list[float] = []
        for col in columns:
            values.extend(self._parse_numeric_list(row.get(col)))
        if not values:
            return None
        return sum(values) / len(values)

    def _parse_numeric_list(self, value) -> list[float]:
        if value is None:
            return []
        if isinstance(value, (int, float)):
            return [float(value)]
        s = str(value).strip()
        if not s:
            return []
        parts = re.split(r'[\s,;/]+', s)
        numbers: list[float] = []
        for part in parts:
            if not part:
                continue
            try:
                numbers.append(float(part))
            except ValueError:
                continue
        return numbers

    def _detect_test_type_from_row(self, row: pd.Series) -> str:
        for column in ('Test_Category', 'Sub_Category', 'Data_Rate', 'Protocol'):
            value = row.get(column)
            normalized = self._normalize_value(value)
            if not normalized:
                continue
            if 'rvo' in normalized:
                return 'RVO'
            if 'rvr' in normalized:
                return 'RVR'
        for value in row.tolist():
            normalized = self._normalize_value(value)
            if not normalized:
                continue
            if 'rvo' in normalized:
                return 'RVO'
            if 'rvr' in normalized:
                return 'RVR'
        return 'RVR'

    def _format_standard_display(self, value) -> str:
        if value is None:
            return ''
        s = str(value).strip()
        if not s or s.lower() in {'nan', 'null'}:
            return ''
        compact = s.replace(' ', '').replace('_', '')
        lower = compact.lower()
        if lower.startswith('11'):
            return lower
        return compact

    def _format_bandwidth_display(self, value) -> str:
        if value is None:
            return ''
        s = str(value).strip()
        if not s or s.lower() in {'nan', 'null'}:
            return ''
        match = re.search(r'-?\d+(?:\.\d+)?', s)
        if match:
            num = match.group()
            if num.endswith('.0'):
                num = num[:-2]
            return f'{num}MHz'
        return s.replace(' ', '')

    def _format_freq_band_display(self, value) -> str:
        if value is None:
            return ''
        s = str(value).strip()
        if not s:
            return ''
        lowered = s.lower()
        if lowered in {'nan', 'null', 'none', 'n/a', 'na', '-'}:
            return ''
        compact = lowered.replace(' ', '')
        if '2g4' in compact or '2.4g' in compact:
            return '2.4G'
        if '5g' in compact and '2.4g' not in compact:
            return '5G'
        if '6g' in compact or '6e' in compact:
            return '6G'
        match = re.search(r'-?\d+(?:\.\d+)?', compact)
        if match:
            try:
                num = float(match.group())
            except ValueError:
                num = None
            if num is not None:
                if 'mhz' in compact and num >= 100:
                    ghz = num / 1000.0
                elif num >= 1000:
                    ghz = num / 1000.0
                else:
                    ghz = num
                if ghz < 3.5:
                    return '2.4G'
                if ghz < 6.0:
                    return '5G'
                if ghz < 8.0:
                    return '6G'
                if num <= 14:
                    return '2.4G'
                if 30 <= num < 200:
                    return '5G'
                if num >= 200:
                    return '6G'
        cleaned = s.upper().replace('GHZ', 'G').replace(' ', '')
        return cleaned

    def _format_direction_display(self, value) -> str:
        if value is None:
            return ''
        s = str(value).strip().upper()
        if not s or s in {'NAN', 'NULL'}:
            return ''
        if s in {'UL', 'UP', 'TX'}:
            return 'TX'
        if s in {'DL', 'DOWN', 'RX'}:
            return 'RX'
        return s

    def _format_channel_display(self, value) -> str:
        if value is None:
            return ''
        s = str(value).strip()
        if not s or s.lower() in {'nan', 'null'}:
            return ''
        if s.endswith('.0'):
            s = s[:-2]
        return s

    def _format_db_display(self, value) -> str:
        if value is None:
            return ''
        s = str(value).strip()
        if not s or s.lower() in {'nan', 'null'}:
            return ''
        match = re.search(r'-?\d+(?:\.\d+)?', s)
        if match:
            num = match.group()
            if num.endswith('.0'):
                num = num[:-2]
            return num
        return s

    def _format_metric_display(self, value) -> str:
        if value is None:
            return ''
        s = str(value).strip()
        if not s or s.lower() in {'nan', 'null', 'n/a', 'false'}:
            return ''
        match = re.search(r'-?\d+(?:\.\d+)?', s)
        if match:
            num = match.group()
            if num.endswith('.0'):
                num = num[:-2]
            return num
        return s

    def _parse_db_numeric(self, value) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        s = str(value).strip()
        if not s:
            return None
        match = re.search(r'-?\d+(?:\.\d+)?', s)
        if not match:
            return None
        try:
            return float(match.group())
        except ValueError:
            return None

    def _group_sort_key(self, key: tuple[str, str, str, str, str]):
        standard, bandwidth, freq_band, test_type, direction = key
        standard_idx = STANDARD_ORDER_MAP.get((standard or '').lower(), len(STANDARD_ORDER_MAP))
        bandwidth_idx = BANDWIDTH_ORDER_MAP.get((bandwidth or '').lower(), len(BANDWIDTH_ORDER_MAP))
        freq_idx = FREQ_BAND_ORDER_MAP.get((freq_band or '').lower(), len(FREQ_BAND_ORDER_MAP))
        test_idx = TEST_TYPE_ORDER_MAP.get((test_type or '').upper(), len(TEST_TYPE_ORDER_MAP))
        direction_idx = DIRECTION_ORDER_MAP.get((direction or '').upper(), len(DIRECTION_ORDER_MAP))
        return (
            standard_idx,
            bandwidth_idx,
            freq_idx,
            test_idx,
            direction_idx,
            standard,
            bandwidth,
            freq_band,
            test_type,
            direction,
        )

    def _format_chart_title(
        self,
        standard: str,
        bandwidth: str,
        freq_band: str,
        test_type: str,
        direction: str,
    ) -> str:
        parts: list[str] = []
        std = (standard or '').strip()
        bw = (bandwidth or '').strip()
        freq = (freq_band or '').strip()
        tt = (test_type or '').strip().upper()
        direction = (direction or '').strip().upper()
        parts.append(std or 'Unknown')
        if bw:
            parts.append(bw)
        if freq:
            parts.append(freq)
        label = f'{tt or "RVR"} Throughput'
        parts.append(label)
        if direction:
            parts.append(direction)
        return ' '.join(parts).strip()

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
                    label=self._format_channel_series_label(channel_name),
                )
        if not has_series:
            plt.close(fig)
            return self._create_empty_chart_widget(title, charts_dir, steps)
        ax.set_xticks(x_positions)
        ax.set_xticklabels([self._format_step_label(step) for step in steps], rotation=30, ha='right')
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
        legend = None
        if handles:
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

    def _collect_step_labels(self, group: pd.DataFrame) -> list[str]:
        steps: list[str] = []
        for step in group['__step__']:
            if step and step not in steps:
                steps.append(step)
        if not steps:
            count = int(group['__throughput_value__'].notna().sum())
            if count <= 0:
                count = len(group.index)
            if count <= 0:
                return []
            steps = [str(i + 1) for i in range(count)]
        steps.sort(key=lambda item: (0, self._parse_db_numeric(item)) if self._parse_db_numeric(item) is not None else (1, item))
        return steps

    def _format_step_label(self, step: str) -> str:
        if not step:
            return ''
        formatted = self._format_db_display(step)
        return formatted or step

    def _format_channel_series_label(self, channel: str) -> str:
        channel = (channel or '').strip()
        return f'CH{channel}' if channel else 'Unknown'

    def _create_pie_chart_widget(
        self,
        group: pd.DataFrame,
        title: str,
        charts_dir: Path,
    ) -> Optional[InteractiveChartLabel]:
        channel_values: list[tuple[str, float]] = []
        for channel, channel_df in group.groupby('__channel_display__', dropna=False):
            throughput_values = [v for v in channel_df['__throughput_value__'].tolist() if v is not None]
            if not throughput_values:
                continue
            avg_value = sum(throughput_values) / len(throughput_values)
            label = self._format_pie_channel_label(channel, channel_df)
            channel_values.append((label, avg_value))
        if not channel_values:
            return self._create_empty_chart_widget(title, charts_dir)
        labels, values = zip(*channel_values)
        fig, ax = plt.subplots(figsize=(6.2, 6.2), dpi=CHART_DPI)
        autopct = self._make_pie_autopct(values)
        wedges, _, autotexts = ax.pie(
            values,
            startangle=120,
            autopct=autopct,
            pctdistance=0.7,
            textprops={'color': TEXT_COLOR},
        )
        ax.set_title(title, pad=6)
        ax.axis('equal')
        legend = ax.legend(
            wedges,
            labels,
            loc='center left',
            bbox_to_anchor=(1.02, 0.5),
            frameon=False,
        )
        if legend is not None:
            for text_item in legend.get_texts():
                text_item.set_ha('left')
        for autotext in autotexts:
            autotext.set_color(TEXT_COLOR)
        fig.tight_layout(pad=0.6)
        save_path = charts_dir / f"{self._safe_chart_name(title)}.png"
        return self._figure_to_label(fig, ax, [], save_path)

    def _format_pie_channel_label(self, channel: str, df: pd.DataFrame) -> str:
        channel_name = (channel or '').strip()
        if not channel_name:
            channel_name = 'Unknown'
        rssi_values = [
            value for value in df['__rssi_display__'].tolist() if value and value not in {'-1', '0'}
        ]
        db_values = [value for value in df['__db_display__'].tolist() if value]
        label_parts: list[str] = []
        if rssi_values:
            label_parts.append(f"rssi{rssi_values[0]}_ch{channel_name}")
        if db_values:
            label_parts.append(f"db{db_values[0]}_ch{channel_name}")
        if not label_parts:
            label_parts.append(f"ch{channel_name}")
        return ' '.join(label_parts)

    def _make_pie_autopct(self, values: tuple[float, ...]):
        total = sum(values)

        def _formatter(pct):
            absolute = pct * total / 100.0
            return f"{pct:.1f}%\n{absolute:.1f} Mbps"

        return _formatter


    def _create_empty_chart_widget(self, title: str, charts_dir: Path, steps: Optional[list[str]] = None) -> Optional[InteractiveChartLabel]:
        fig, ax = plt.subplots(figsize=(7.5, 4.2), dpi=CHART_DPI)
        steps = steps or []
        if steps:
            x_positions = list(range(len(steps)))
            ax.set_xticks(x_positions)
            ax.set_xticklabels(steps, rotation=30, ha='right')
        else:
            ax.set_xticks([])
        ax.set_xlabel('attenuation (dB)')
        ax.set_ylabel('throughput (Mbps)')
        ax.set_title(title, loc='left', pad=4)
        ax.grid(alpha=0.2, linestyle='--')
        if steps:
            ax.set_xlim(-0.5, len(steps) - 0.5)
        else:
            ax.set_xlim(0, 1)
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
            label.setAlignment(Qt.AlignCenter)
            label.setPixmap(pixmap)
            label.setFixedSize(pixmap.size())
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


    def _safe_float(self, value) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        s = str(value).strip()
        if not s:
            return None
        lowered = s.lower()
        if lowered in {'nan', 'null', 'n/a', 'false'}:
            return None
        normalized = s.replace('，', ',')
        match = re.search(r'-?\d+(?:\.\d+)?', normalized)
        if match:
            try:
                return float(match.group())
            except ValueError:
                return None
        try:
            return float(normalized)
        except Exception:
            return None
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

    def _safe_chart_name(self, title: str) -> str:
        safe = re.sub(r'[^0-9A-Za-z_-]+', '_', title).strip('_')
        return safe or 'rvr_chart'

    def _series_with_nan(self, values: list[Optional[float]]) -> list[float]:
        series: list[float] = []
        for value in values:
            series.append(math.nan if value is None else float(value))
        return series

    def _normalize_value(self, value) -> str:
        return str(value).strip().lower() if value is not None else ''

    def _normalize_step(self, value) -> Optional[str]:
        if value is None:
            return None
        s = str(value).strip()
        if not s or s.lower() in {'nan', 'null'}:
            return None
        return s

    def _extract_first_non_empty(self, row: pd.Series, columns: tuple[str, ...]):
        for column in columns:
            if column not in row:
                continue
            value = row.get(column)
            if value is None:
                continue
            s = str(value).strip()
            if not s or s.lower() in {'nan', 'null', 'none', 'n/a', 'na', '-'}:
                continue
            return value
        return None

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

