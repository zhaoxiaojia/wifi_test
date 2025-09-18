#!/usr/bin/env python
# encoding: utf-8

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
from html import escape

from PyQt5.QtCore import Qt, QTimer, QEvent
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QListWidget,
    QListWidgetItem,
    QTextEdit,
    QLabel,
)
from qfluentwidgets import CardWidget, StrongBodyLabel

from .theme import apply_theme, FONT_FAMILY, STYLE_BASE, TEXT_COLOR


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

        # right: viewer
        self.viewer = QTextEdit(self)
        self.viewer.setReadOnly(True)
        apply_theme(self.viewer)
        # cap blocks to control memory
        self.viewer.document().setMaximumBlockCount(5000)
        self.viewer.setMinimumHeight(400)
        body.addWidget(self.viewer, 3)

        self.setLayout(root)

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
            return
        name = items[0].text()
        path = (self._report_dir / name).resolve()
        self._start_tail(path)

    def _start_tail(self, path: Path):
        # stop previous
        self._stop_tail()
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

