"""Common reusable view components and animations.

This module hosts shared widgets used across multiple pages, such as the
`ConfigGroupPanel` that arranges configuration group boxes into columns
with simple layout animations, and helpers for wizard step indicators and
tree views.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated, Any, Mapping, Sequence

from PyQt5.QtCore import (
    QEvent,
    QEasingCurve,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QRect,
    QSortFilterProxyModel,
    QTimer,
    Qt,
    QModelIndex,
    QObject,
    pyqtProperty,
    pyqtSignal,
)
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QCheckBox,
    QBoxLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import TreeView

from src.ui.view.theme import (
    STEP_LABEL_FONT_PIXEL_SIZE,
    apply_groupbox_style,
    apply_theme,
)


# Layout/spacing constants used across config-related views.
STEP_LABEL_SPACING: Annotated[int, "Spacing in pixels between step labels in the GUI"] = 16
USE_QFLUENT_STEP_VIEW: Annotated[
    bool,
    "Whether to use the QFluent StepView component if available",
] = False
GROUP_COLUMN_SPACING: Annotated[int, "Horizontal spacing between columns in grouped form layouts"] = 16
GROUP_ROW_SPACING: Annotated[int, "Vertical spacing between rows in grouped form layouts"] = 12
PAGE_CONTENT_MARGIN: Annotated[int, "Margin applied around content within pages and panels"] = 8


@dataclass
class EditableInfo:
    """
    Describe which fields within a test case can be edited by the user.
    """

    fields: set[str] = field(default_factory=set)
    enable_csv: bool = False
    enable_rvr_wifi: bool = False


@dataclass
class ScriptConfigEntry:
    """
    Aggregates widget references and metadata for a single script configuration panel.
    """

    group: QGroupBox
    widgets: dict[str, QWidget]
    field_keys: set[str]
    section_controls: dict[str, tuple[QCheckBox, Sequence[QWidget]]]
    case_key: str
    case_path: str
    extras: dict[str, Any] = field(default_factory=dict)


def create_step_font(base_font: QFont) -> QFont:
    """Return a bold font honoring the configured wizard label size."""
    font = QFont(base_font)
    if STEP_LABEL_FONT_PIXEL_SIZE > 0:
        font.setPixelSize(STEP_LABEL_FONT_PIXEL_SIZE)
    else:
        font.setPointSize(font.pointSize() or 12)
    font.setWeight(QFont.DemiBold)
    return font


def _apply_step_font(widget: QWidget) -> None:
    """Apply the wizard font styling to the widget and its child labels."""
    step_font = create_step_font(widget.font())
    widget.setFont(step_font)
    for label in widget.findChildren(QLabel):
        label.setFont(step_font)
    layout = widget.layout()
    if layout is not None:
        margins = layout.contentsMargins()
        if margins.left() == 0 and margins.top() == 0 and margins.right() == 0:
            layout.setContentsMargins(
                PAGE_CONTENT_MARGIN,
                PAGE_CONTENT_MARGIN,
                PAGE_CONTENT_MARGIN,
                PAGE_CONTENT_MARGIN,
            )


class _RowHeightWrapper(QObject):
    """
    Helper object that bridges a single index's row height to a Qt property.

    The wrapper allows using :class:`QPropertyAnimation` on a per-index basis.
    It stores and retrieves heights in the parent tree's private height map
    (``tree._row_heights``), then triggers geometry updates on change.
    """

    def __init__(self, tree: "AnimatedTreeView", index) -> None:
        super().__init__(tree)
        self._tree = tree
        self._index = index

    def _set_height(self, height: int) -> None:
        self._tree._row_heights[self._index] = height
        self._tree.updateGeometries()

    def _get_height(self) -> int:
        return self._tree._row_heights.get(self._index, 0)

    #: Qt property used by QPropertyAnimation.
    height = pyqtProperty(int, fset=_set_height, fget=_get_height)


class AnimatedTreeView(TreeView):
    """
    A TreeView with expand animation for child rows.

    Behavior
    --------
    - When expanding an index, the control pre-expands the node (so children
      exist), then animates each direct child's row height from 0 to its native
      size hint using a parallel animation group.
    - While the animation runs, :meth:`indexRowSizeHint` serves the temporary
      heights from ``_row_heights`` so the viewport progressively reveals rows.
    - After the animation finishes, temporary overrides are cleared, updates are
      re-enabled, and the viewport is repainted once.
    """

    ANIMATION_DURATION = 180  # ms

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._row_heights: dict[object, int] = {}

    def indexRowSizeHint(self, index):  # noqa: N802 (Qt naming convention)
        """Return row height for ``index`` honoring active animations."""
        return self._row_heights.get(index, super().indexRowSizeHint(index))

    def setExpanded(self, index, expand):  # noqa: D401, N802
        """Reimplemented to animate child rows on expand."""
        model = self.model()
        if expand and model is not None:
            self.setUpdatesEnabled(False)
            super().setExpanded(index, expand)
            group = QParallelAnimationGroup(self)
            for row in range(model.rowCount(index)):
                child = model.index(row, 0, index)
                target = super().indexRowSizeHint(child)
                self._row_heights[child] = 0
                wrapper = _RowHeightWrapper(self, child)
                anim = QPropertyAnimation(wrapper, b"height", self)
                anim.setDuration(self.ANIMATION_DURATION)
                anim.setStartValue(0)
                anim.setEndValue(target)
                group.addAnimation(anim)

            def _on_finished() -> None:
                for row in range(model.rowCount(index)):
                    child = model.index(row, 0, index)
                    self._row_heights.pop(child, None)
                self.setUpdatesEnabled(True)
                self.viewport().update()

            group.finished.connect(_on_finished)
            group.start(QPropertyAnimation.DeleteWhenStopped)
        else:
            super().setExpanded(index, expand)


class ConfigGroupPanel(QWidget):
    """
    Container widget that arranges configuration group boxes into three
    columns and animates their display.

    This panel is used by configuration pages to lay out multiple related
    parameter groups in a responsive manner. Groups can grow or shrink as
    content changes and the panel will adjust spacing accordingly.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
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
        """Remove all tracked groups from this panel."""
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
        """Add a group widget to the panel, optionally deferring layout."""
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
        """Replace all groups with ``groups`` and rebalance layout."""
        self.clear()
        for group in groups:
            self.add_group(group, defer=True)
        self.request_rebalance()

    def request_rebalance(self) -> None:
        """Schedule a rebalance of the column layout."""
        self._rebalance_columns()
        QTimer.singleShot(0, self._rebalance_columns)

    def _estimate_group_weight(self, group: QWidget) -> int:
        """Estimate a group's visual weight based on number of inputs."""
        from PyQt5.QtWidgets import (
            QLineEdit,
            QComboBox,
            QTextEdit,
            QSpinBox,
            QDoubleSpinBox,
            QCheckBox,
        )

        inputs = group.findChildren(
            (QLineEdit, QComboBox, QTextEdit, QSpinBox, QDoubleSpinBox, QCheckBox)
        )
        return max(1, len(inputs))

    def _measure_group_height(self, group: QWidget, weight_override: int | None = None) -> int:
        """Measure or estimate a group's height used for balancing columns."""
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
        """Re-assign groups to columns to keep heights balanced."""
        if not self._column_layouts or not self._group_entries:
            return
        old_geometries: dict[QWidget, QRect] = {}
        for group, _ in self._group_entries:
            if group is not None and group.parent() is not None:
                old_geometries[group] = group.geometry()
        entries: list[tuple[QWidget, int]] = []
        initial_pass = not self._group_positions
        for group, weight_override in self._group_entries:
            if group is None:
                continue
            if not initial_pass and not group.isVisible():
                # On the first layout pass groups may not yet be visible
                # because the window has not been shown.  On subsequent
                # passes we skip hidden groups so rule-driven visibility
                # takes effect.
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
            QTimer.singleShot(
                0,
                lambda moves=tuple(moved_groups): self._animate_group_transitions(moves),
            )

    def _animate_group_transitions(self, moves: tuple[tuple[QWidget, QRect | None], ...]) -> None:
        """Animate group movement when their column assignment changes."""
        for group, old_rect in moves:
            if group is None or not group.isVisible():
                continue
            self._start_move_animation(group, old_rect)

    def _start_move_animation(self, group: QWidget, old_rect: QRect | None) -> None:
        """Start a geometry animation from old_rect to current geometry."""
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


def attach_view_to_page(
    page: QWidget,
    view: QWidget,
    *,
    orientation: Qt.Orientation = Qt.Vertical,
    margins: tuple[int, int, int, int] = (0, 0, 0, 0),
    spacing: int = 0,
    ) -> None:
    """
    Attach a single view widget to a page using a simple box layout.

    This helper centralises the common pattern:
    - create a QVBoxLayout/QHBoxLayout on the page,
    - set margins/spacing,
    - add the view as the sole child.
    """
    if orientation == Qt.Horizontal:
        layout: QBoxLayout = QHBoxLayout(page)
    else:
        layout = QVBoxLayout(page)
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    layout.addWidget(view)


def animate_progress_fill(
    fill_frame: QFrame,
    container: QFrame,
    percent: int,
    *,
    min_delta_px: int = 2,
    duration_ms: int = 300,
) -> QPropertyAnimation | None:
    """
    Animate the width of a progress fill frame inside ``container``.

    Parameters
    ----------
    fill_frame : QFrame
        The child frame that visually represents the progress bar fill.
    container : QFrame
        The parent frame whose width determines the full progress range.
    percent : int
        Target progress percentage [0, 100].
    min_delta_px : int
        If the width change is smaller than this threshold, apply it
        directly without animation.
    duration_ms : int
        Duration of the animation in milliseconds.
    """
    rect = container.rect()
    total_w = rect.width() or 300
    target_w = total_w if percent >= 99 else int(total_w * percent / 100)

    current_geo = fill_frame.geometry()
    current_w = current_geo.width()
    if abs(target_w - current_w) < min_delta_px:
        fill_frame.setGeometry(0, 0, target_w, rect.height())
        return None

    anim = QPropertyAnimation(fill_frame, b"geometry", fill_frame)
    anim.setDuration(duration_ms)
    anim.setStartValue(current_geo)
    anim.setEndValue(QRect(0, 0, target_w, rect.height()))
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.start()
    return anim


class TestFileFilterModel(QSortFilterProxyModel):
    """
    Proxy model that filters a QFileSystemModel to focus on test_* Python files.
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


__all__ = [
    "AnimatedTreeView",
    "ConfigGroupPanel",
    "EditableInfo",
    "ScriptConfigEntry",
    "create_step_font",
    "_apply_step_font",
    "STEP_LABEL_SPACING",
    "USE_QFLUENT_STEP_VIEW",
    "GROUP_COLUMN_SPACING",
    "GROUP_ROW_SPACING",
    "PAGE_CONTENT_MARGIN",
    "TestFileFilterModel",
    "_StepSwitcher",
]
