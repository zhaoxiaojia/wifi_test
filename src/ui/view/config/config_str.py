"""STR / RF-step specific widgets for the Config page."""

from __future__ import annotations

from typing import Sequence

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import LineEdit, PushButton


class RfStepSegmentsWidget(QWidget):
    """
    Composite widget that allows the user to define one or more RF step segments.

    A segment consists of a start, stop and step value. The widget provides
    editable fields with sensible defaults and Add/Delete buttons to maintain a
    list of segments. A hint is shown when no segments are added, and a list
    view presents currently defined segments.
    """

    DEFAULT_SEGMENT = (0, 75, 3)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._segments: list[tuple[int, int, int]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        form = QGridLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(4)

        from PyQt5.QtGui import QIntValidator

        self.start_edit = LineEdit(self)
        self.start_edit.setPlaceholderText("Start (default 0)")
        self.start_edit.setValidator(QIntValidator(0, 9999, self))
        self.start_edit.setText(str(self.DEFAULT_SEGMENT[0]))

        self.stop_edit = LineEdit(self)
        self.stop_edit.setPlaceholderText("Stop (default 75)")
        self.stop_edit.setValidator(QIntValidator(0, 9999, self))
        self.stop_edit.setText(str(self.DEFAULT_SEGMENT[1]))

        self.step_edit = LineEdit(self)
        self.step_edit.setPlaceholderText("Step (default 3)")
        self.step_edit.setValidator(QIntValidator(1, 9999, self))
        self.step_edit.setText(str(self.DEFAULT_SEGMENT[2]))

        form.addWidget(QLabel("Start"), 0, 0)
        form.addWidget(self.start_edit, 0, 1)
        form.addWidget(QLabel("Stop"), 1, 0)
        form.addWidget(self.stop_edit, 1, 1)
        form.addWidget(QLabel("Step"), 2, 0)
        form.addWidget(self.step_edit, 2, 1)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(8)

        self.add_btn = PushButton("Add", self)
        self.add_btn.clicked.connect(self._on_add_segment)
        btn_row.addWidget(self.add_btn)

        self.del_btn = PushButton("Del", self)
        self.del_btn.clicked.connect(self._on_delete_segment)
        btn_row.addWidget(self.del_btn)

        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        hint_text = (
            "If no range is added, the default 0-75 (step 3) range is used.\n"
            "Enter start/stop/step, click Add to append, and select one then click Del to remove."
        )

        self.segment_stack = QStackedWidget(self)

        self.segment_hint = QLabel(hint_text, self)
        self.segment_hint.setWordWrap(True)
        self.segment_hint.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.segment_hint.setStyleSheet("color: #6c6c6c;")
        self.segment_hint.setContentsMargins(4, 4, 4, 4)

        self.segment_list = QListWidget(self)
        self.segment_list.setSelectionMode(QListWidget.SingleSelection)
        self.segment_list.currentRowChanged.connect(self._on_segment_selected)

        self.segment_stack.addWidget(self.segment_hint)
        self.segment_stack.addWidget(self.segment_list)
        layout.addWidget(self.segment_stack, 1)

        self._refresh_segment_list()

    def segments(self) -> list[tuple[int, int, int]]:
        """Return current RF step segments."""
        return list(self._segments)

    def set_segments(self, segments: Sequence[tuple[int, int, int]]) -> None:
        """Replace the current segments and refresh the list."""
        self._segments = [(int(a), int(b), int(c)) for a, b, c in segments]
        self._refresh_segment_list()

    def _refresh_segment_list(self) -> None:
        self.segment_list.clear()
        for start, stop, step in self._segments:
            item_text = f"{start} - {stop} (step {step})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, (start, stop, step))
            self.segment_list.addItem(item)
        if self._segments:
            self.segment_stack.setCurrentWidget(self.segment_list)
            self.segment_list.setCurrentRow(0)
        else:
            self.segment_stack.setCurrentWidget(self.segment_hint)

    def _on_segment_selected(self, index: int) -> None:
        if 0 <= index < len(self._segments):
            start, stop, step = self._segments[index]
            self.start_edit.setText(str(start))
            self.stop_edit.setText(str(stop))
            self.step_edit.setText(str(step))

    def _on_add_segment(self) -> None:
        start = self._coerce_int(self.start_edit.text(), self.DEFAULT_SEGMENT[0])
        stop = self._coerce_int(self.stop_edit.text(), self.DEFAULT_SEGMENT[1])
        step = self._coerce_int(self.step_edit.text(), self.DEFAULT_SEGMENT[2])
        if step <= 0:
            step = self.DEFAULT_SEGMENT[2]
        if stop < start:
            start, stop = stop, start
        self._segments.append((start, stop, step))
        self._refresh_segment_list()

    def _on_delete_segment(self) -> None:
        row = self.segment_list.currentRow()
        if 0 <= row < len(self._segments):
            del self._segments[row]
            self._refresh_segment_list()

    def _coerce_int(self, text: str, default: int) -> int:
        try:
            value = int(text.strip())
        except Exception:
            return default
        return max(0, value)


__all__ = ["RfStepSegmentsWidget"]

