"""
Tree and wizard navigation helpers for the Windows case configuration UI.
"""

from __future__ import annotations

from typing import Sequence

from PyQt5.QtCore import QEvent, QModelIndex, QObject, Qt, pyqtSignal
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QWidget
from PyQt5.QtCore import QSortFilterProxyModel

from .windows_case_shared import PAGE_CONTENT_MARGIN, STEP_LABEL_SPACING, create_step_font
from .theme import STEP_LABEL_FONT_PIXEL_SIZE


class TestFileFilterModel(QSortFilterProxyModel):
    """
    Proxy model that filters a :class:`QFileSystemModel` to focus on test script files.
    """

    def filterAcceptsRow(self, source_row, source_parent):
        """Return True for directories (except ``__pycache__``) and test_* Python files."""
        index = self.sourceModel().index(source_row, 0, source_parent)
        file_name = self.sourceModel().fileName(index)
        is_dir = self.sourceModel().isDir(index)

        if is_dir and file_name == "__pycache__":
            return False
        if not is_dir:
            if not file_name.startswith("test_") or not file_name.endswith(".py"):
                return False
            if file_name == "__init__.py":
                return False
        return True

    def hasChildren(self, parent: QModelIndex) -> bool:
        """Keep directories expandable even if filtered children are hidden."""
        src_parent = self.mapToSource(parent)
        if not self.sourceModel().isDir(src_parent):
            return False
        return True


class _StepSwitcher(QWidget):
    """
    Lightweight fallback widget used to indicate and navigate between wizard steps.
    """

    stepActivated = pyqtSignal(int)

    def __init__(self, steps: Sequence[str], parent: QWidget | None = None) -> None:
        """Create the clickable labels shown as wizard steps."""
        super().__init__(parent)
        self._labels: list[QLabel] = []
        self._current = -1
        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            PAGE_CONTENT_MARGIN,
            PAGE_CONTENT_MARGIN,
            PAGE_CONTENT_MARGIN,
            PAGE_CONTENT_MARGIN,
        )
        layout.setSpacing(STEP_LABEL_SPACING)
        step_font = create_step_font(self.font())
        for index, text in enumerate(steps):
            label = QLabel(text, self)
            label.setFont(step_font)
            label.setObjectName("wizardStepLabel")
            label.setCursor(Qt.PointingHandCursor)
            label.installEventFilter(self)
            self._labels.append(label)
            layout.addWidget(label)
        layout.addStretch(1)
        self.set_current_index(0)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # type: ignore[override]
        """Emit the `stepActivated` signal when a label is clicked."""
        if event.type() == QEvent.MouseButtonRelease and obj in self._labels:
            if getattr(event, "button", lambda: Qt.LeftButton)() == Qt.LeftButton:
                self.stepActivated.emit(self._labels.index(obj))  # type: ignore[arg-type]
                return True
        return super().eventFilter(obj, event)

    def set_current_index(self, index: int) -> None:
        """Update the highlighted wizard step label."""
        if not (0 <= index < len(self._labels)):
            return
        if self._current == index:
            return
        self._current = index
        for i, label in enumerate(self._labels):
            font_size_rule = ""
            if STEP_LABEL_FONT_PIXEL_SIZE > 0:
                font_size_rule = f"font-size: {STEP_LABEL_FONT_PIXEL_SIZE}px;"
            if i == index:
                label.setStyleSheet(f"{font_size_rule} color: #0078d4; font-weight: 600;")
            else:
                label.setStyleSheet(f"{font_size_rule} color: #6c6c6c; font-weight: 400;")


__all__ = ["TestFileFilterModel", "_StepSwitcher"]
