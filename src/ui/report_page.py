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
import pandas as pd
from PyQt5.QtCore import Qt, QTimer, QEvent
from PyQt5.QtGui import QPixmap
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
)
from qfluentwidgets import CardWidget, StrongBodyLabel

from src.util.constants import Paths
from .theme import apply_theme, FONT_FAMILY, STYLE_BASE, TEXT_COLOR, BACKGROUND_COLOR

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

        self._rvr_config_cache: dict[tuple[str, str, str, str], dict[str, str]] | None = None
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
            for title, pixmap in charts:
                scroll = QScrollArea(self.chart_tabs)
                scroll.setWidgetResizable(True)
                label = QLabel(scroll)
                label.setAlignment(Qt.AlignCenter)
                label.setPixmap(pixmap)
                scroll.setWidget(label)
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

    def _build_rvr_charts(self, path: Path) -> list[tuple[str, QPixmap]]:
        df = self._load_rvr_dataframe(path)
        if df.empty:
            return []
        config_map = self._load_rvr_config_map()
        charts_dir = path.parent / 'rvr_charts'
        charts_dir.mkdir(exist_ok=True)
        results: list[tuple[str, QPixmap]] = []
        grouped = df.groupby(['Freq_Band', 'Standard', 'BW', 'CH_Freq_MHz'], dropna=False)
        for (band, mode, bw, channel), group in grouped:
            title = self._format_scenario_label(str(band or ''), str(mode or ''), str(channel or ''), str(bw or ''), config_map)
            pixmap = self._create_chart_pixmap(group, title, charts_dir)
            if pixmap is not None:
                results.append((title, pixmap))
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
            logging.exception('读取 RVR 结果失败: %s', exc)
            return pd.DataFrame()
        if df.empty:
            return df
        df = df.copy()
        df.columns = [str(c).strip() for c in df.columns]
        for col in df.columns:
            df[col] = df[col].apply(lambda v: v if not isinstance(v, str) else v.strip())
        if 'Direction' in df.columns:
            df['Direction'] = df['Direction'].astype(str).str.upper()
        for col in ('Freq_Band', 'Standard', 'BW', 'CH_Freq_MHz', 'DB'):
            if col in df.columns:
                df[col] = df[col].astype(str)
            elif col != 'DB':
                df[col] = ''
        return df

    def _load_rvr_config_map(self) -> dict[tuple[str, str, str, str], dict[str, str]]:
        if self._rvr_config_cache is not None:
            return self._rvr_config_cache
        config_map: dict[tuple[str, str, str, str], dict[str, str]] = {}
        cfg_path = Path(Paths.CONFIG_DIR) / 'performance_test_csv' / 'rvr_wifi_setup.csv'
        if cfg_path.exists():
            try:
                cfg_df = pd.read_csv(cfg_path)
                for _, row in cfg_df.iterrows():
                    key = (
                        self._normalize_value(row.get('band')),
                        self._normalize_value(row.get('wireless_mode')),
                        self._normalize_value(row.get('channel')),
                        self._normalize_bandwidth(row.get('bandwidth')),
                    )
                    config_map[key] = {col: str(row.get(col, '')) for col in cfg_df.columns}
            except Exception as exc:
                logging.exception('Failed to read rvr_wifi_setup.csv: %s', exc)
        else:
            logging.info('rvr_wifi_setup.csv not found; fallback to result metadata')
        self._rvr_config_cache = config_map
        return config_map

    def _format_scenario_label(self, band: str, mode: str, channel: str, bw: str,
                               config_map: dict[tuple[str, str, str, str], dict[str, str]]) -> str:
        key = (
            self._normalize_value(band),
            self._normalize_value(mode),
            self._normalize_value(channel),
            self._normalize_bandwidth(bw),
        )
        cfg = config_map.get(key)
        if cfg:
            parts = [cfg.get('band', ''), cfg.get('ssid', ''), cfg.get('wireless_mode', ''),
                     cfg.get('channel', ''), cfg.get('bandwidth', ''), cfg.get('security_mode', '')]
            parts = [p for p in parts if p]
            return ','.join(parts)
        fallback = [band, mode, channel, bw]
        fallback = [p for p in fallback if p and p.lower() != 'nan']
        return ','.join(fallback) or 'scenario'

    def _create_chart_pixmap(self, group: pd.DataFrame, title: str, charts_dir: Path) -> Optional[QPixmap]:
        if 'Direction' not in group.columns:
            return None
        ul_df = group[group['Direction'] == 'UL'].copy()
        dl_df = group[group['Direction'] == 'DL'].copy()
        steps: list[str] = []
        for df_part in (ul_df, dl_df):
            if 'DB' in df_part.columns:
                for step in df_part['DB']:
                    norm = self._normalize_step(step)
                    if norm and norm not in steps:
                        steps.append(norm)
        if not steps:
            count = max(len(ul_df), len(dl_df))
            steps = [str(i + 1) for i in range(count)]
        ul_throughput, ul_expect = self._build_series(ul_df, steps)
        dl_throughput, dl_expect = self._build_series(dl_df, steps)
        if not any(v is not None for v in ul_throughput + dl_throughput + ul_expect + dl_expect):
            return None
        x_positions = list(range(len(steps)))
        fig, ax = plt.subplots(figsize=(7.5, 4.2), dpi=120)
        if any(v is not None for v in ul_throughput):
            ax.plot(x_positions, self._series_with_nan(ul_throughput), marker='o', label='UL Throughput')
        if any(v is not None for v in dl_throughput):
            ax.plot(x_positions, self._series_with_nan(dl_throughput), marker='o', label='DL Throughput')
        if any(v is not None for v in ul_expect):
            ax.plot(x_positions, self._series_with_nan(ul_expect), linestyle='--', label='UL Expect_Rate')
        if any(v is not None for v in dl_expect):
            ax.plot(x_positions, self._series_with_nan(dl_expect), linestyle='--', label='DL Expect_Rate')
        ax.set_xticks(x_positions)
        ax.set_xticklabels(steps, rotation=30, ha='right')
        ax.set_ylabel('Mbps')
        ax.set_title(title)
        ax.grid(alpha=0.3, linestyle='--')
        ax.margins(y=0.08)
        ax.legend(loc='upper left', bbox_to_anchor=(0.02, 0.98), ncol=2, frameon=False)
        fig.tight_layout(rect=[0, 0, 1, 0.95])
        safe_name = re.sub(r'[^0-9A-Za-z_-]+', '_', title).strip('_') or 'rvr_chart'
        img_path = charts_dir / f'{safe_name}.png'
        fig.savefig(img_path, dpi=150)
        plt.close(fig)
        pixmap = QPixmap(str(img_path))
        return pixmap if not pixmap.isNull() else None

    def _build_series(self, df: pd.DataFrame, steps: list[str]) -> tuple[list[Optional[float]], list[Optional[float]]]:
        throughput_series: list[Optional[float]] = []
        expect_series: list[Optional[float]] = []
        if df.empty:
            return [None] * len(steps), [None] * len(steps)
        df = df.copy()
        if 'DB' in df.columns:
            df['__step__'] = df['DB'].apply(self._normalize_step)
        else:
            df['__step__'] = None
        for step in steps:
            subset = df[df['__step__'] == step]
            if subset.empty:
                throughput_series.append(None)
                expect_series.append(None)
                continue
            throughput_col = subset['Throughput'] if 'Throughput' in subset.columns else pd.Series(dtype=float)
            expect_col = subset['Expect_Rate'] if 'Expect_Rate' in subset.columns else pd.Series(dtype=float)
            throughput_values = [self._safe_float(v) for v in throughput_col.tolist()]
            throughput_values = [v for v in throughput_values if v is not None]
            expect_values = [self._safe_float(v) for v in expect_col.tolist()]
            expect_values = [v for v in expect_values if v is not None]
            throughput_series.append(sum(throughput_values) / len(throughput_values) if throughput_values else None)
            expect_series.append(sum(expect_values) / len(expect_values) if expect_values else None)
        return throughput_series, expect_series

    def _series_with_nan(self, values: list[Optional[float]]) -> list[float]:
        series: list[float] = []
        for value in values:
            series.append(math.nan if value is None else float(value))
        return series

    def _normalize_value(self, value) -> str:
        return str(value).strip().lower() if value is not None else ''

    def _normalize_bandwidth(self, value) -> str:
        s = self._normalize_value(value)
        return s.replace('mhz', '').strip()

    def _normalize_step(self, value) -> Optional[str]:
        if value is None:
            return None
        s = str(value).strip()
        if not s or s.lower() in {'nan', 'null'}:
            return None
        return s

    def _safe_float(self, value) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        s = str(value).strip()
        if not s or s.lower() in {'nan', 'null', 'n/a', 'false'}:
            return None
        try:
            return float(s)
        except Exception:
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

