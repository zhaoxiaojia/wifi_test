"""
Reusable layout panel for case configuration group boxes.
"""

from __future__ import annotations

from PyQt5.QtCore import QEasingCurve, QPropertyAnimation, QRect, QTimer, Qt
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from .theme import apply_groupbox_style, apply_theme
from .windows_case_shared import GROUP_COLUMN_SPACING, GROUP_ROW_SPACING


class ConfigGroupPanel(QWidget):
    """
    Container widget that arranges configuration group boxes into three
    columns and animates their display.

    This panel is used by :class:`CaseConfigPage` to lay out multiple related
    parameter groups in a responsive manner.  Groups can grow or shrink as
    content changes and the panel will adjust spacing accordingly.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """
        Initialize the class instance, set up initial state and construct UI widgets.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(GROUP_ROW_SPACING)
        self._column_layouts: list[QVBoxLayout] = []
        for _ in range(3):
            column = QVBoxLayout()
            column.setSpacing(GROUP_COLUMN_SPACING)
            column.setAlignment(Qt.AlignTop)
            layout.addLayout(column, 1)
            self._column_layouts.append(column)
        self._group_entries: list[tuple[QWidget, int | None]] = []
        self._group_positions: dict[QWidget, int] = {}
        self._col_weight: list[int] = [0] * len(self._column_layouts)
        self._active_move_anims: dict[QWidget, QPropertyAnimation] = {}

    def clear(self) -> None:
        """
        Execute the clear routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        self._group_entries.clear()
        self._group_positions.clear()
        self._col_weight = [0] * len(self._column_layouts)
        for column in self._column_layouts:
            while column.count():
                item = column.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.setParent(None)

    def add_group(self, group: QWidget | None, weight: int | None = None, defer: bool = False) -> None:
        """
        Execute the add group routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if group is None:
            return
        apply_theme(group)
        apply_groupbox_style(group)
        for idx, (existing, _) in enumerate(self._group_entries):
            if existing is group:
                self._group_entries[idx] = (group, weight)
                break
        else:
            self._group_entries.append((group, weight))
        if not defer:
            self.request_rebalance()

    def set_groups(self, groups: list[QWidget]) -> None:
        """
        Set the groups property on the instance.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        self.clear()
        for group in groups:
            self.add_group(group, defer=True)
        self.request_rebalance()

    def request_rebalance(self) -> None:
        """
        Execute the request rebalance routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        self._rebalance_columns()
        QTimer.singleShot(0, self._rebalance_columns)

    def _estimate_group_weight(self, group: QWidget) -> int:
        """
        Execute the estimate group weight routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        from PyQt5.QtWidgets import (
            QLineEdit, QComboBox, QTextEdit, QSpinBox, QDoubleSpinBox, QCheckBox
        )
        inputs = group.findChildren((QLineEdit, QComboBox, QTextEdit, QSpinBox, QDoubleSpinBox, QCheckBox))
        return max(1, len(inputs))

    def _measure_group_height(self, group: QWidget, weight_override: int | None = None) -> int:
        """
        Execute the measure group height routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if weight_override is not None:
            return max(1, int(weight_override))
        hint = group.sizeHint()
        height = hint.height() if hint.isValid() else 0
        if height <= 0:
            min_hint = group.minimumSizeHint()
            height = min_hint.height() if min_hint.isValid() else 0
        if height <= 0:
            height = self._estimate_group_weight(group)
        return max(1, int(height))

    def _rebalance_columns(self) -> None:
        """
        Execute the rebalance columns routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if not self._column_layouts or not self._group_entries:
            return
        old_geometries: dict[QWidget, QRect] = {}
        for group, _ in self._group_entries:
            if group is not None and group.parent() is not None:
                old_geometries[group] = group.geometry()
        entries: list[tuple[QWidget, int]] = []
        for group, weight_override in self._group_entries:
            if group is None:
                continue
            entries.append((group, self._measure_group_height(group, weight_override)))
        if not entries:
            return
        entries.sort(key=lambda item: item[1], reverse=True)
        for layout in self._column_layouts:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.setParent(None)
        self._col_weight = [0] * len(self._column_layouts)
        initial_pass = not self._group_positions
        moved_groups: list[tuple[QWidget, QRect | None]] = []
        for group, height in entries:
            column_index = self._col_weight.index(min(self._col_weight))
            prev_col = self._group_positions.get(group)
            self._column_layouts[column_index].addWidget(group)
            self._col_weight[column_index] += height
            self._group_positions[group] = column_index
            if (prev_col is None and not initial_pass) or (prev_col is not None and prev_col != column_index):
                moved_groups.append((group, old_geometries.get(group)))
        self.updateGeometry()
        if moved_groups:
            QTimer.singleShot(0, lambda moves=tuple(moved_groups): self._animate_group_transitions(moves))

    def _animate_group_transitions(self, moves: tuple[tuple[QWidget, QRect | None], ...]) -> None:
        """
        Execute the animate group transitions routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        for group, old_rect in moves:
            if group is None or not group.isVisible():
                continue
            self._start_move_animation(group, old_rect)

    def _start_move_animation(self, group: QWidget, old_rect: QRect | None) -> None:
        """
        Execute the start move animation routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if old_rect is None:
            return
        current_rect = group.geometry()
        if current_rect == old_rect:
            return
        existing = self._active_move_anims.pop(group, None)
        if existing is not None:
            existing.stop()
        group.setGeometry(old_rect)
        group.raise_()
        animation = QPropertyAnimation(group, b"geometry", group)
        animation.setDuration(320)
        animation.setStartValue(old_rect)
        animation.setEndValue(current_rect)
        animation.setEasingCurve(QEasingCurve.InOutCubic)
        self._active_move_anims[group] = animation
        animation.finished.connect(lambda g=group: self._active_move_anims.pop(g, None))
        animation.start()


