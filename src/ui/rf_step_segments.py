"""RF step segment editor widgets."""
from __future__ import annotations

import re
from typing import Sequence

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIntValidator
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

    A segment consists of a start, stop and step value.  The widget provides
    editable fields with sensible defaults and Add/Delete buttons to maintain a
    list of segments.  A hint is shown when no segments are added, and a list
    view presents currently defined segments.
    """

    DEFAULT_SEGMENT = (0, 75, 3)

    def __init__(self, parent: QWidget | None = None) -> None:
        """
        Initialize the class instance, set up initial state and construct UI widgets.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        super().__init__(parent)
        self._segments: list[tuple[int, int, int]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        form = QGridLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(4)

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

    def _refresh_segment_list(self) -> None:
        """
        Refresh the  segment list to ensure the UI is up to date.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        self.segment_list.clear()
        for start, stop, step in self._segments:
            item_text = f"{start} - {stop} (step {step})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, (start, stop, step))
            self.segment_list.addItem(item)

        if self._segments:
            self.segment_stack.setCurrentWidget(self.segment_list)
            self.segment_list.setCurrentRow(len(self._segments) - 1)
        else:
            self.segment_stack.setCurrentWidget(self.segment_hint)

    def _on_segment_selected(self, row: int) -> None:
        """
        Handle the segment selected event triggered by user interaction.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if 0 <= row < len(self._segments):
            start, stop, step = self._segments[row]
            self.start_edit.setText(str(start))
            self.stop_edit.setText(str(stop))
            self.step_edit.setText(str(step))

    def _show_error(self, message: str) -> None:
        """
        Execute the show error routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        InfoBar.error(
            title="RF Step",
            content=message,
            parent=self,
            position=InfoBarPosition.TOP,
            duration=3000,
        )

    def _parse_inputs(self) -> tuple[int, int, int] | None:
        """
        Parse  inputs from user input or configuration.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        start_text = self.start_edit.text().strip()
        stop_text = self.stop_edit.text().strip()
        step_text = self.step_edit.text().strip() or str(self.DEFAULT_SEGMENT[2])

        if not start_text or not stop_text:
            self._show_error("Please provide both start and stop values.")
            return None

        try:
            start = int(start_text)
            stop = int(stop_text)
            step = int(step_text)
        except ValueError:
            self._show_error("Start, stop, and step must be integers.")
            return None

        if step <= 0:
            self._show_error("Step must be greater than 0.")
            return None

        if stop < start:
            start, stop = stop, start

        return start, stop, step

    def _on_add_segment(self) -> None:
        """
        Handle the add segment event triggered by user interaction.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        parsed = self._parse_inputs()
        if parsed is None:
            return
        if parsed in self._segments:
            self._show_error("This range already exists.")
            return

        self._segments.append(parsed)
        self._refresh_segment_list()

    def _on_delete_segment(self) -> None:
        """
        Handle the delete segment event triggered by user interaction.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        row = self.segment_list.currentRow()
        if row < 0 or row >= len(self._segments):
            self._show_error("Select a range to delete first.")
            return

        del self._segments[row]
        self._refresh_segment_list()

    def segments(self) -> list[tuple[int, int, int]]:
        """
        Execute the segments routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        return list(self._segments)

    def set_segments_from_config(self, raw_value: object) -> None:
        """
        Set the segments from config property on the instance.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        segments = self._convert_raw_to_segments(raw_value)
        self._segments = segments
        self._refresh_segment_list()

    def serialize(self) -> str:
        """
        Serialize the current state into a configuration object for persistence.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        unique_segments: list[tuple[int, int, int]] = []
        seen: set[tuple[int, int, int]] = set()
        for segment in self._segments:
            if segment not in seen:
                unique_segments.append(segment)
                seen.add(segment)

        if not unique_segments:
            return ""
        parts = [f"{start},{stop}:{step}" for start, stop, step in unique_segments]
        return ";".join(parts)

    def _convert_raw_to_segments(self, raw_value: object) -> list[tuple[int, int, int]]:
        """
        Execute the convert raw to segments routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        segments: list[tuple[int, int, int]] = []

        for text in self._collect_segments(raw_value):
            parsed = self._parse_segment_text(text)
            if parsed is not None:
                segments.append(parsed)

        return segments

    def _collect_segments(self, raw_value: object) -> list[str]:
        """
        Collect  segments from internal state for processing or serialization.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        segments: list[str] = []

        def _collect(value: object) -> None:
            """
            Collect data from internal state for processing or serialization.

            This method encapsulates the logic necessary to perform its function.
            Refer to the implementation for details on parameters and return values.
            """
            if value is None:
                return
            if isinstance(value, str):
                text = value.strip()
                if not text:
                    return
                normalized = (
                    text.replace("；", ";")
                    .replace("，", ",")
                    .replace("：", ":")
                )
                for part in re.split(r"[;；|\n]+", normalized):
                    part = part.strip()
                    if part:
                        segments.append(part)
                return
            if isinstance(value, (list, tuple, set)):
                items = list(value)
                if len(items) == 2 and all(not isinstance(i, (list, tuple, set, dict)) for i in items):
                    start = str(items[0]).strip()
                    stop = str(items[1]).strip()
                    if start and stop:
                        segments.append(f"{start},{stop}")
                    return
                for item in items:
                    _collect(item)
                return
            text = str(value).strip()
            if text:
                segments.append(text)

        _collect(raw_value)
        return segments

    def _parse_segment_text(self, segment: str) -> tuple[int, int, int] | None:
        """
        Parse  segment text from user input or configuration.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        normalized = (
            segment.replace("；", ";")
            .replace("，", ",")
            .replace("：", ":")
        )

        if ":" in normalized:
            range_part, step_part = normalized.split(":", 1)
            step_text = step_part.strip()
        else:
            range_part = normalized
            step_text = ""

        tokens = [tok for tok in re.split(r"[\s,]+", range_part) if tok]
        if not tokens:
            return None

        start_text = tokens[0]
        stop_text = tokens[1] if len(tokens) >= 2 else tokens[0]

        try:
            start = int(start_text)
            stop = int(stop_text)
        except ValueError:
            return None

        if step_text:
            try:
                step = int(step_text)
            except ValueError:
                step = self.DEFAULT_SEGMENT[2]
        else:
            step = self.DEFAULT_SEGMENT[2]

        if step <= 0:
            step = self.DEFAULT_SEGMENT[2]

        if stop < start:
            start, stop = stop, start

        return start, stop, step


