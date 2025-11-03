from __future__ import annotations

import os
import re
from pathlib import Path
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional, Sequence
from src.tools.router_tool.router_factory import router_list, get_router
from src.util.constants import (
    ANDROID_KERNEL_MAP,
    DEFAULT_ANDROID_VERSION_CHOICES,
    DEFAULT_KERNEL_VERSION_CHOICES,
    DEFAULT_RF_STEP_SPEC,
    FONT_FAMILY,
    RouterConst,
    TEXT_COLOR,
    WIFI_PRODUCT_PROJECT_MAP,
    get_config_base,
    get_src_base,
)
from src.tools.config_loader import load_config, save_config
from PyQt5.QtCore import (
    Qt,
    QSignalBlocker,
    QTimer,
    QEasingCurve,
    QDir,
    QSortFilterProxyModel,
    QModelIndex,
    QPropertyAnimation,
    QPoint,
    QRect,
    QRegularExpression,
    pyqtSignal,
    QEvent,
    QObject,
)
from PyQt5.QtGui import QIntValidator, QRegularExpressionValidator

from PyQt5.QtWidgets import (
    QSizePolicy,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QFileSystemModel,
    QCheckBox,
    QSplitter,
    QStackedWidget,
    QListWidget,
    QListWidgetItem,
    QSpinBox,
)

from qfluentwidgets import (
    CardWidget,
    LineEdit,
    PushButton,
    ComboBox,
    FluentIcon,
    TextEdit,
    InfoBar,
    InfoBarPosition,
    ScrollArea
)
try:
    from qfluentwidgets import StepView  # type: ignore
except Exception:  # pragma: no cover - 运行环境缺失时退化为自定义指示器
    StepView = None
from .animated_tree_view import AnimatedTreeView
from .theme import apply_theme, apply_font_and_selection, apply_groupbox_style


@dataclass
class EditableInfo:
    
    """Metadata describing which fields are editable for a test case."""
    fields: set[str] = field(default_factory=set)
    enable_csv: bool = False
    enable_rvr_wifi: bool = False


@dataclass
class ScriptConfigEntry:
    """Container for script-specific configuration widgets."""

    group: QGroupBox
    widgets: dict[str, QWidget]
    field_keys: set[str]
    section_controls: dict[str, tuple[QCheckBox, Sequence[QWidget]]]
    case_key: str
    case_path: str


class TestFileFilterModel(QSortFilterProxyModel):
    def filterAcceptsRow(self, source_row, source_parent):
        index = self.sourceModel().index(source_row, 0, source_parent)
        file_name = self.sourceModel().fileName(index)
        is_dir = self.sourceModel().isDir(index)

        # 过滤 __pycache__ 文件夹 和 __init__.py 文件
        if is_dir and file_name == "__pycache__":
            return False
        if not is_dir:
            if not file_name.startswith("test_") or not file_name.endswith(".py"):
                return False
            if file_name == "__init__.py":
                return False
        return True

    def hasChildren(self, parent: QModelIndex) -> bool:
        
        """Ensure directories remain expandable even when children are filtered."""
        src_parent = self.mapToSource(parent)
        # 原始模型中的节点是否是目录
        if not self.sourceModel().isDir(src_parent):
            return False
        # 强制认为目录有子项（即便都被过滤了）
        return True


class _StepSwitcher(QWidget):
    """Lightweight fallback step indicator when StepView is unavailable."""

    stepActivated = pyqtSignal(int)

    def __init__(self, steps: Sequence[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._labels: list[QLabel] = []
        self._current = -1
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        for index, text in enumerate(steps):
            label = QLabel(text, self)
            label.setObjectName("wizardStepLabel")
            label.setCursor(Qt.PointingHandCursor)
            label.installEventFilter(self)
            self._labels.append(label)
            layout.addWidget(label)
        layout.addStretch(1)
        self.set_current_index(0)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # type: ignore[override]
        if event.type() == QEvent.MouseButtonRelease and obj in self._labels:
            if getattr(event, "button", lambda: Qt.LeftButton)() == Qt.LeftButton:
                self.stepActivated.emit(self._labels.index(obj))  # type: ignore[arg-type]
                return True
        return super().eventFilter(obj, event)

    def set_current_index(self, index: int) -> None:
        if not (0 <= index < len(self._labels)):
            return
        if self._current == index:
            return
        self._current = index
        for i, label in enumerate(self._labels):
            if i == index:
                label.setStyleSheet("color: #0078d4; font-weight: 600;")
            else:
                label.setStyleSheet("color: #6c6c6c; font-weight: 400;")


class RfStepSegmentsWidget(QWidget):

    """RF Step 多段输入控件，支持通过表单维护区间列表。"""

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

        self.start_edit = LineEdit(self)
        self.start_edit.setPlaceholderText("起始 (默认 0)")
        self.start_edit.setValidator(QIntValidator(0, 9999, self))
        self.start_edit.setText(str(self.DEFAULT_SEGMENT[0]))

        self.stop_edit = LineEdit(self)
        self.stop_edit.setPlaceholderText("结束 (默认 75)")
        self.stop_edit.setValidator(QIntValidator(0, 9999, self))
        self.stop_edit.setText(str(self.DEFAULT_SEGMENT[1]))

        self.step_edit = LineEdit(self)
        self.step_edit.setPlaceholderText("步长 (默认 3)")
        self.step_edit.setValidator(QIntValidator(1, 9999, self))
        self.step_edit.setText(str(self.DEFAULT_SEGMENT[2]))

        form.addWidget(QLabel("起始"), 0, 0)
        form.addWidget(self.start_edit, 0, 1)
        form.addWidget(QLabel("结束"), 1, 0)
        form.addWidget(self.stop_edit, 1, 1)
        form.addWidget(QLabel("步长"), 2, 0)
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
            "未添加区间时将自动使用默认区间 0-75（步长 3）。\n"
            "填写起始、结束与步长后点击 Add 添加区间，选中后可用 Del 删除。"
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
        if 0 <= row < len(self._segments):
            start, stop, step = self._segments[row]
            self.start_edit.setText(str(start))
            self.stop_edit.setText(str(stop))
            self.step_edit.setText(str(step))

    def _show_error(self, message: str) -> None:
        InfoBar.error(
            title="RF Step",
            content=message,
            parent=self,
            position=InfoBarPosition.TOP,
            duration=3000,
        )

    def _parse_inputs(self) -> tuple[int, int, int] | None:
        start_text = self.start_edit.text().strip()
        stop_text = self.stop_edit.text().strip()
        step_text = self.step_edit.text().strip() or str(self.DEFAULT_SEGMENT[2])

        if not start_text or not stop_text:
            self._show_error("请填写起始与结束值。")
            return None

        try:
            start = int(start_text)
            stop = int(stop_text)
            step = int(step_text)
        except ValueError:
            self._show_error("起始、结束与步长必须为整数。")
            return None

        if step <= 0:
            self._show_error("步长必须大于 0。")
            return None

        if stop < start:
            start, stop = stop, start

        return start, stop, step

    def _on_add_segment(self) -> None:
        parsed = self._parse_inputs()
        if parsed is None:
            return
        if parsed in self._segments:
            self._show_error("该区间已存在。")
            return

        self._segments.append(parsed)
        self._refresh_segment_list()

    def _on_delete_segment(self) -> None:
        row = self.segment_list.currentRow()
        if row < 0 or row >= len(self._segments):
            self._show_error("请先选择要删除的区间。")
            return

        del self._segments[row]
        self._refresh_segment_list()

    def segments(self) -> list[tuple[int, int, int]]:
        return list(self._segments)

    def set_segments_from_config(self, raw_value: object) -> None:
        segments = self._convert_raw_to_segments(raw_value)
        self._segments = segments
        self._refresh_segment_list()

    def serialize(self) -> str:
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
        segments: list[tuple[int, int, int]] = []

        for text in self._collect_segments(raw_value):
            parsed = self._parse_segment_text(text)
            if parsed is not None:
                segments.append(parsed)

        return segments

    def _collect_segments(self, raw_value: object) -> list[str]:
        segments: list[str] = []

        def _collect(value: object) -> None:
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

class ConfigGroupPanel(QWidget):
    
    """Container that arranges groups into three columns with animations."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self._column_layouts: list[QVBoxLayout] = []
        for _ in range(3):
            column = QVBoxLayout()
            column.setSpacing(8)
            column.setAlignment(Qt.AlignTop)
            layout.addLayout(column, 1)
            self._column_layouts.append(column)
        self._group_entries: list[tuple[QWidget, int | None]] = []
        self._group_positions: dict[QWidget, int] = {}
        self._col_weight: list[int] = [0] * len(self._column_layouts)
        self._active_move_anims: dict[QWidget, QPropertyAnimation] = {}

    def clear(self) -> None:
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
        self.clear()
        for group in groups:
            self.add_group(group, defer=True)
        self.request_rebalance()

    def request_rebalance(self) -> None:
        self._rebalance_columns()
        QTimer.singleShot(0, self._rebalance_columns)

    def _estimate_group_weight(self, group: QWidget) -> int:
        from PyQt5.QtWidgets import (
            QLineEdit, QComboBox, QTextEdit, QSpinBox, QDoubleSpinBox, QCheckBox
        )
        inputs = group.findChildren((QLineEdit, QComboBox, QTextEdit, QSpinBox, QDoubleSpinBox, QCheckBox))
        return max(1, len(inputs))

    def _measure_group_height(self, group: QWidget, weight_override: int | None = None) -> int:
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
        for group, old_rect in moves:
            if group is None or not group.isVisible():
                continue
            self._start_move_animation(group, old_rect)

    def _start_move_animation(self, group: QWidget, old_rect: QRect | None) -> None:
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

class CaseConfigPage(CardWidget):
    
    """Main page widget for configuring test cases."""

    routerInfoChanged = pyqtSignal()
    csvFileChanged = pyqtSignal(str)

    def __init__(self, on_run_callback):
        super().__init__()
        self.setObjectName("caseConfigPage")
        self.on_run_callback = on_run_callback
        apply_theme(self)
        # -------------------- load config --------------------
        self.config: dict = self._load_config()
        # -------------------- state --------------------
        self._refreshing = False
        self._pending_path: str | None = None
        self.field_widgets: dict[str, QWidget] = {}
        self.router_obj = None
        self.selected_csv_path: str | None = None
        self._enable_rvr_wifi: bool = False
        self._locked_fields: set[str] | None = None
        self._current_case_path: str = ""
        self._last_editable_info: EditableInfo | None = None
        # -------------------- layout --------------------
        self.splitter = QSplitter(Qt.Horizontal, self)
        self.splitter.setChildrenCollapsible(False)
        # ----- left: case tree -----
        self.case_tree = AnimatedTreeView(self)
        apply_theme(self.case_tree)
        apply_font_and_selection(self.case_tree)
        logging.debug("TreeView font: %s", self.case_tree.font().family())
        logging.debug("TreeView stylesheet: %s", self.case_tree.styleSheet())
        self._init_case_tree(Path(self._get_application_base()) / "test")
        self.splitter.addWidget(self.case_tree)

        # ----- right: parameters & run button -----
        scroll_area = ScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setContentsMargins(0, 0, 0, 0)
        self.scroll_area = scroll_area
        container = QWidget()
        right = QVBoxLayout(container)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(10)
        self._android_versions = list(DEFAULT_ANDROID_VERSION_CHOICES)
        self._kernel_versions = list(DEFAULT_KERNEL_VERSION_CHOICES)
        self._right_layout = right
        self._page_label_map: dict[str, str] = {
            "dut": "DUT Settings",
            "execution": "Execution Settings",
            "stability": "Stability Settings",
        }
        self.step_view_widget = self._create_step_view([self._page_label_map["dut"]])
        self.step_view_widget.setVisible(False)
        right.addWidget(self.step_view_widget)

        self.stack = QStackedWidget(self)
        right.addWidget(self.stack, 1)

        self._page_panels: dict[str, ConfigGroupPanel] = {
            "dut": ConfigGroupPanel(self),
            "execution": ConfigGroupPanel(self),
            "stability": ConfigGroupPanel(self),
        }
        self._dut_panel = self._page_panels["dut"]
        self._execution_panel = self._page_panels["execution"]
        self._stability_panel = self._page_panels["stability"]
        self._page_widgets: dict[str, QWidget] = {}
        self._wizard_pages: list[QWidget] = []
        self._run_buttons: list[PushButton] = []
        self._run_locked = False
        for key in ("dut", "execution", "stability"):
            panel = self._page_panels[key]
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(0, 0, 0, 0)
            page_layout.setSpacing(8)
            page_layout.addWidget(panel)
            page_layout.addStretch(1)
            run_btn = self._create_run_button(page)
            page_layout.addWidget(run_btn)
            self._page_widgets[key] = page
            self._wizard_pages.append(page)
        self._current_page_keys: list[str] = []
        self._script_config_factories: dict[str, Callable[[str, str, Mapping[str, Any]], ScriptConfigEntry]] = {
            "test/stability/test_str.py": self._create_test_str_config_entry,
        }
        self._script_groups: dict[str, ScriptConfigEntry] = {}
        self._active_script_case: str | None = None
        self._config_panels = tuple(self._page_panels[key] for key in ("dut", "execution", "stability"))
        self._sync_run_buttons_enabled()
        scroll_area.setWidget(container)
        self.splitter.addWidget(scroll_area)
        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 3)

        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.addWidget(self.splitter)
        # render form fields from yaml
        self._dut_groups: dict[str, QWidget] = {}
        self._other_groups: dict[str, QWidget] = {}
        self.render_all_fields()
        self._initialize_script_config_groups()
        self._build_wizard_pages()
        self._set_available_pages(["dut"])
        self._refresh_script_section_states()
        self.stack.currentChanged.connect(self._on_page_changed)
        self._request_rebalance_for_panels()
        self._on_page_changed(self.stack.currentIndex())
        self.routerInfoChanged.connect(self._update_csv_options)
        self._update_csv_options()
        # connect signals AFTER UI ready
        self.case_tree.clicked.connect(self.on_case_tree_clicked)
        self.case_tree.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        QTimer.singleShot(0, lambda: self.get_editable_fields(""))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.splitter.setSizes([int(self.width() * 0.2), int(self.width() * 0.8)])

    def _create_run_button(self, parent: QWidget) -> PushButton:
        button = PushButton("Run", parent)
        button.setIcon(FluentIcon.PLAY)
        if hasattr(button, "setUseRippleEffect"):
            button.setUseRippleEffect(True)
        if hasattr(button, "setUseStateEffect"):
            button.setUseStateEffect(True)
        button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        button.clicked.connect(self.on_run)
        self._run_buttons.append(button)
        return button

    def _create_step_view(self, labels: Sequence[str]) -> QWidget:
        labels = list(labels)
        if not labels:
            labels = [self._page_label_map["dut"]]
        if StepView is not None:
            try:
                step_view = StepView(self)
                configured = False
                for attr in ("setSteps", "setStepList", "setStepTextList"):
                    if hasattr(step_view, attr):
                        try:
                            getattr(step_view, attr)(labels)
                            configured = True
                            break
                        except Exception as exc:
                            logging.debug("StepView.%s failed: %s", attr, exc)
                if not configured and hasattr(step_view, "addStep"):
                    add_step = getattr(step_view, "addStep")
                    for label in labels:
                        try:
                            add_step(label)
                        except TypeError:
                            add_step(label, label)
                for attr in (
                    "setStepNumberVisible",
                    "setNumberVisible",
                    "setIndexVisible",
                    "setShowNumber",
                    "setDisplayIndex",
                ):
                    if hasattr(step_view, attr):
                        try:
                            getattr(step_view, attr)(False)
                        except Exception as exc:
                            logging.debug("StepView.%s failed: %s", attr, exc)
                for attr in ("setStepClickable", "setStepsClickable", "setAllClickable"):
                    if hasattr(step_view, attr):
                        try:
                            getattr(step_view, attr)(True)
                        except Exception as exc:
                            logging.debug("StepView.%s failed: %s", attr, exc)
                self._attach_step_navigation(step_view)
                return step_view
            except Exception as exc:  # pragma: no cover - 动态环境差异
                logging.debug("Failed to initialize StepView: %s", exc)
        fallback = _StepSwitcher(labels, self)
        fallback.stepActivated.connect(self._on_step_activated)
        return fallback

    def _update_step_indicator(self, index: int) -> None:
        view = getattr(self, "step_view_widget", None)
        if view is None:
            return
        for attr in ("setCurrentIndex", "setCurrentStep", "setCurrentRow", "setCurrent"):
            if hasattr(view, attr):
                try:
                    getattr(view, attr)(index)
                    return
                except Exception as exc:
                    logging.debug("StepView %s failed: %s", attr, exc)
        if hasattr(view, "set_current_index"):
            try:
                view.set_current_index(index)
            except Exception as exc:
                logging.debug("Fallback step indicator failed: %s", exc)

    def _attach_step_navigation(self, view: QWidget) -> None:
        if isinstance(view, _StepSwitcher):
            view.stepActivated.connect(self._on_step_activated)
            return
        handler_connected = False

        def _handler(*args, **kwargs):
            index = self._coerce_step_index(*(args or []), *(kwargs.values()))
            if index is not None:
                self._on_step_activated(index)

        for signal_name in (
            "stepClicked",
            "currentIndexChanged",
            "currentChanged",
            "currentRowChanged",
            "clicked",
            "activated",
        ):
            signal = getattr(view, signal_name, None)
            if signal is None or not hasattr(signal, "connect"):
                continue
            try:
                signal.connect(_handler)
                handler_connected = True
                break
            except Exception as exc:
                logging.debug("Failed to connect StepView.%s: %s", signal_name, exc)
        if handler_connected:
            return
        for child in view.findChildren(QWidget):
            if child is view:
                continue
            try:
                self._attach_step_navigation(child)
                handler_connected = True
                break
            except Exception as exc:
                logging.debug("StepView child hookup failed: %s", exc)
        if not handler_connected:
            logging.debug("Step navigation hookup failed; relying on fallback behaviour")

    def _on_step_activated(self, *args) -> None:
        index = self._coerce_step_index(*args)
        if index is None:
            return
        self._navigate_to_index(index)

    def _coerce_step_index(self, *args) -> Optional[int]:
        for arg in args:
            if isinstance(arg, int):
                return arg
            if isinstance(arg, (list, tuple)):
                nested = self._coerce_step_index(*arg)
                if nested is not None:
                    return nested
            if isinstance(arg, str) and arg.strip().isdigit():
                return int(arg.strip())
            if hasattr(arg, "row") and callable(getattr(arg, "row")):
                row = arg.row()
                if isinstance(row, int) and row >= 0:
                    return row
            if isinstance(arg, Mapping) and "index" in arg:
                nested = self._coerce_step_index(arg["index"])
                if nested is not None:
                    return nested
            if hasattr(arg, "index"):
                idx = getattr(arg, "index")
                if isinstance(idx, int):
                    return idx
        return None

    def _navigate_to_index(self, target_index: int) -> None:
        if self.stack.count() == 0:
            return
        target_index = max(0, min(target_index, self.stack.count() - 1))
        current = self.stack.currentIndex()
        if target_index == current:
            return
        if current == 0 and target_index > current and not self._validate_first_page():
            self.stack.setCurrentIndex(0)
            return
        self._sync_widgets_to_config()
        self.stack.setCurrentIndex(target_index)

    def _sync_run_buttons_enabled(self) -> None:
        enabled = not self._run_locked
        for btn in self._run_buttons:
            btn.setEnabled(enabled)

    def _info_bar_parent(self) -> QWidget:
        parent = self.window()
        if isinstance(parent, QWidget):
            return parent
        return self

    def _show_info_bar(
        self,
        level: str,
        title: str,
        content: str,
        **kwargs: Any,
    ):
        bar_fn = getattr(InfoBar, level, None)
        if not callable(bar_fn):
            logging.debug("InfoBar level %s unavailable", level)
            return None
        info_parent = self._info_bar_parent()
        params = {
            "title": title,
            "content": content,
            "parent": info_parent,
            "position": InfoBarPosition.TOP,
        }
        params.update(kwargs)
        try:
            bar = bar_fn(**params)
        except Exception as exc:
            logging.debug("InfoBar.%s failed: %s", level, exc)
            return None
        scroll = getattr(self, "scroll_area", None)
        if scroll is not None:
            try:
                scrollbar = scroll.verticalScrollBar()
                if scrollbar is not None:
                    scrollbar.setValue(scrollbar.minimum())
            except Exception as exc:
                logging.debug("Failed to reset scroll position: %s", exc)
        if hasattr(bar, "raise_"):
            bar.raise_()
        if hasattr(info_parent, "raise_"):
            info_parent.raise_()
        if hasattr(info_parent, "activateWindow"):
            info_parent.activateWindow()
        return bar

    def _request_rebalance_for_panels(self, *panels: ConfigGroupPanel) -> None:
        targets = panels or self._config_panels
        for panel in targets:
            panel.request_rebalance()

    def _build_wizard_pages(self) -> None:
        self._dut_panel.set_groups(list(self._dut_groups.values()))
        self._execution_panel.set_groups(self._compose_other_groups())

    def _compose_other_groups(self) -> list[QWidget]:
        return list(self._other_groups.values())

    def _list_serial_ports(self) -> list[tuple[str, str]]:
        ports: list[tuple[str, str]] = []
        try:
            from serial.tools import list_ports  # type: ignore
        except Exception:
            logging.debug("serial.tools.list_ports unavailable", exc_info=True)
            return ports
        try:
            for info in list_ports.comports():
                label = info.device
                description = getattr(info, "description", "") or ""
                if description and description != info.device:
                    label = f"{info.device} ({description})"
                ports.append((info.device, label))
        except Exception as exc:
            logging.debug("Failed to enumerate serial ports: %s", exc)
            return []
        return ports


    def _refresh_step_view(self, page_keys: Sequence[str]) -> None:
        labels = [self._page_label_map.get(key, key.title()) for key in page_keys]
        if not labels:
            labels = [self._page_label_map["dut"]]
        new_view = self._create_step_view(labels)
        old_view = getattr(self, "step_view_widget", None)
        layout = getattr(self, "_right_layout", None)
        if layout is not None:
            if old_view is not None:
                index = layout.indexOf(old_view)
                if index < 0:
                    index = 0
                layout.insertWidget(index, new_view)
                layout.removeWidget(old_view)
                old_view.setParent(None)
            else:
                layout.insertWidget(0, new_view)
        self.step_view_widget = new_view
        self.step_view_widget.setVisible(len(page_keys) > 1)

    def _set_available_pages(self, page_keys: Sequence[str]) -> None:
        normalized: list[str] = []
        for key in page_keys:
            if key not in self._page_widgets:
                continue
            if key not in normalized:
                normalized.append(key)
        if "dut" not in normalized:
            normalized.insert(0, "dut")
        if normalized == getattr(self, "_current_page_keys", []):
            return
        current_widget = self.stack.currentWidget() if self.stack.count() else None
        current_key: str | None = None
        if current_widget is not None:
            for key, widget in self._page_widgets.items():
                if widget is current_widget:
                    current_key = key
                    break
        while self.stack.count():
            widget = self.stack.widget(0)
            self.stack.removeWidget(widget)
        for key in normalized:
            self.stack.addWidget(self._page_widgets[key])
        self._current_page_keys = normalized
        self._refresh_step_view(normalized)
        target_index = 0
        if current_key in normalized:
            target_index = normalized.index(current_key)
        self.stack.setCurrentIndex(target_index)
        self._update_step_indicator(target_index)
        if hasattr(self, "step_view_widget") and self.step_view_widget is not None:
            self.step_view_widget.setVisible(len(self._current_page_keys) > 1)
        self._update_navigation_state()

    def _determine_pages_for_case(self, case_path: str, info: EditableInfo) -> list[str]:

        if not case_path:
            return ["dut"]
        keys = ["dut"]
        if self._is_performance_case(case_path) or info.enable_csv:
            if "execution" not in keys:
                keys.append("execution")
        else:
            case_key = self._script_case_key(case_path)
            if case_key in self._script_groups:
                keys.append("stability")
        return keys

    def _script_case_key(self, case_path: str | Path) -> str:
        if not case_path:
            return ""
        path_obj = case_path if isinstance(case_path, Path) else Path(case_path)
        if path_obj.is_absolute():
            try:
                path_obj = path_obj.resolve().relative_to(self._get_application_base())
            except ValueError:
                path_obj = path_obj.resolve()
        normalized = path_obj.as_posix()
        if not normalized.startswith("test/"):
            normalized = self._display_to_case_path(normalized)
        return normalized.replace('/', '__').replace('.', '_').lower()

    def _script_field_key(self, case_key: str, *parts: str) -> str:
        suffix = ".".join(parts)
        return f"script_params.{case_key}.{suffix}"

    def _initialize_script_config_groups(self) -> None:
        script_section = self.config.get("script_params")
        if not isinstance(script_section, dict):
            script_section = {}
            self.config["script_params"] = script_section
        self._script_groups.clear()
        for case_path, factory in self._script_config_factories.items():
            case_key = self._script_case_key(case_path)
            entry_config = self._ensure_script_case_defaults(case_key, case_path)
            entry = factory(case_key, case_path, entry_config)
            entry.group.setVisible(False)
            self._script_groups[case_key] = entry
            self.field_widgets.update(entry.widgets)
        self._stability_panel.set_groups([])

    def _ensure_script_case_defaults(self, case_key: str, case_path: str) -> dict[str, Any]:
        script_section = self.config.setdefault("script_params", {})
        entry = script_section.get(case_key)
        if not isinstance(entry, dict):
            entry = {}
        entry["case_path"] = self._display_to_case_path(case_path)

        def _ensure_branch(name: str) -> None:
            branch = entry.get(name)
            if not isinstance(branch, dict):
                branch = {}
            branch.setdefault("enabled", False)
            branch.setdefault("on_duration", 0)
            branch.setdefault("off_duration", 0)
            branch.setdefault("port", "")
            branch.setdefault("mode", "NO")
            branch.setdefault("ping", False)
            entry[name] = branch

        _ensure_branch("ac")
        _ensure_branch("str")
        script_section[case_key] = entry
        return entry

    def _update_script_config_ui(self, case_path: str | Path) -> None:
        case_key = self._script_case_key(case_path)
        changed = False
        active_entry: ScriptConfigEntry | None = None
        if case_key not in self._script_groups:
            if self._active_script_case is not None:
                self._active_script_case = None
                for entry in self._script_groups.values():
                    if entry.group.isVisible():
                        entry.group.setVisible(False)
                self._stability_panel.set_groups([])
                self._request_rebalance_for_panels(self._stability_panel)
            self._refresh_script_section_states()
            return
        if self._active_script_case != case_key:
            self._active_script_case = case_key
            changed = True
        for key, entry in self._script_groups.items():
            visible = key == case_key
            if entry.group.isVisible() != visible:
                entry.group.setVisible(visible)
                changed = True
            if visible:
                data = self._ensure_script_case_defaults(key, entry.case_path)
                self._load_script_config_into_widgets(entry, data)
                active_entry = entry
        if active_entry is not None:
            self._stability_panel.set_groups([active_entry.group])
        else:
            self._stability_panel.set_groups([])
        self._request_rebalance_for_panels(self._stability_panel)
        self._refresh_script_section_states()

    def _load_script_config_into_widgets(
        self,
        entry: ScriptConfigEntry,
        data: Mapping[str, Any] | None,
    ) -> None:
        data = data or {}
        ac_cfg = data.get("ac", {})
        str_cfg = data.get("str", {})

        def _set_spin(key: str, raw_value: Any) -> None:
            widget = entry.widgets.get(key)
            if isinstance(widget, QSpinBox):
                try:
                    value = int(raw_value)
                except (TypeError, ValueError):
                    value = 0
                with QSignalBlocker(widget):
                    widget.setValue(max(0, value))

        def _set_checkbox(key: str, raw_value: Any) -> None:
            widget = entry.widgets.get(key)
            if isinstance(widget, QCheckBox):
                widget.setChecked(bool(raw_value))

        def _set_combo(key: str, raw_value: Any) -> None:
            widget = entry.widgets.get(key)
            if not isinstance(widget, ComboBox):
                return
            value = str(raw_value or "").strip()
            with QSignalBlocker(widget):
                if value:
                    index = widget.findData(value)
                    if index < 0:
                        index = next(
                            (i for i in range(widget.count()) if widget.itemText(i) == value),
                            -1,
                        )
                    if index < 0:
                        widget.addItem(value, value)
                        index = widget.findData(value)
                    widget.setCurrentIndex(index if index >= 0 else max(widget.count() - 1, 0))
                else:
                    widget.setCurrentIndex(0 if widget.count() else -1)
        case_key = entry.case_key
        _set_checkbox(self._script_field_key(case_key, "ac", "enabled"), ac_cfg.get("enabled"))
        _set_spin(self._script_field_key(case_key, "ac", "on_duration"), ac_cfg.get("on_duration"))
        _set_spin(self._script_field_key(case_key, "ac", "off_duration"), ac_cfg.get("off_duration"))
        _set_combo(self._script_field_key(case_key, "ac", "port"), ac_cfg.get("port"))
        _set_combo(self._script_field_key(case_key, "ac", "mode"), ac_cfg.get("mode"))
        _set_checkbox(self._script_field_key(case_key, "ac", "ping"), ac_cfg.get("ping"))

        _set_checkbox(self._script_field_key(case_key, "str", "enabled"), str_cfg.get("enabled"))
        _set_spin(self._script_field_key(case_key, "str", "on_duration"), str_cfg.get("on_duration"))
        _set_spin(self._script_field_key(case_key, "str", "off_duration"), str_cfg.get("off_duration"))
        _set_combo(self._script_field_key(case_key, "str", "port"), str_cfg.get("port"))
        _set_combo(self._script_field_key(case_key, "str", "mode"), str_cfg.get("mode"))
        _set_checkbox(self._script_field_key(case_key, "str", "ping"), str_cfg.get("ping"))

        for checkbox, controls in entry.section_controls.values():
            self._set_section_controls_state(controls, checkbox.isChecked())
    @staticmethod
    def _set_section_controls_state(controls: Sequence[QWidget], enabled: bool) -> None:
        for widget in controls:
            widget.setEnabled(enabled)

    def _refresh_script_section_states(self) -> None:
        for entry in self._script_groups.values():
            for checkbox, controls in entry.section_controls.values():
                self._set_section_controls_state(controls, checkbox.isEnabled() and checkbox.isChecked())

    def _bind_script_section(self, checkbox: QCheckBox, controls: Sequence[QWidget]) -> None:
        def _apply(checked: bool) -> None:
            self._set_section_controls_state(controls, checked)

        checkbox.toggled.connect(_apply)
        _apply(checkbox.isChecked())

    def _create_test_str_config_entry(
        self,
        case_key: str,
        case_path: str,
        data: Mapping[str, Any],
    ) -> ScriptConfigEntry:
        group = QGroupBox("test_str.py Stability", self)
        apply_theme(group)
        apply_groupbox_style(group)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        intro = QLabel("Configure AC/STR cycling parameters for test_str.py.", group)
        intro.setWordWrap(True)
        layout.addWidget(intro)

        widgets: dict[str, QWidget] = {}
        section_controls: dict[str, tuple[QCheckBox, Sequence[QWidget]]] = {}

        def _build_port_combo(parent: QWidget) -> ComboBox:
            combo = ComboBox(parent)
            combo.setMinimumWidth(220)
            combo.addItem("Select port", "")

            def _refresh_ports(preserve_current: bool = True) -> None:
                """Reload available serial ports while optionally preserving selection."""
                current_value = ""
                if preserve_current:
                    data = combo.currentData()
                    if isinstance(data, str):
                        current_value = data
                combo.blockSignals(True)
                try:
                    combo.clear()
                    combo.addItem("Select port", "")
                    for device, label in self._list_serial_ports():
                        combo.addItem(label, device)
                    if current_value:
                        index = combo.findData(current_value)
                        if index < 0:
                            combo.addItem(current_value, current_value)
                            index = combo.findData(current_value)
                        combo.setCurrentIndex(index if index >= 0 else 0)
                    else:
                        combo.setCurrentIndex(0)
                finally:
                    combo.blockSignals(False)

            combo.refresh_ports = _refresh_ports  # type: ignore[attr-defined]
            _refresh_ports(preserve_current=False)

            original_show_popup = combo.showPopup

            def _show_popup() -> None:
                """Refresh port list whenever the dropdown is opened."""
                try:
                    _refresh_ports()
                finally:
                    original_show_popup()

            combo.showPopup = _show_popup  # type: ignore[method-assign]
            return combo

        def _set_port_default(combo: ComboBox, value: str) -> None:
            value = (value or "").strip()
            refresh_ports = getattr(combo, "refresh_ports", None)
            if callable(refresh_ports):
                refresh_ports(preserve_current=False)
            if not value:
                combo.setCurrentIndex(0 if combo.count() else -1)
                return
            index = combo.findData(value)
            if index < 0:
                combo.addItem(value, value)
                index = combo.findData(value)
            combo.setCurrentIndex(index if index >= 0 else 0)

        def _set_mode_default(combo: ComboBox, value: str) -> None:
            target = (value or "NO").strip().upper() or "NO"
            # ComboBoxBase.findText only supports the text argument, so we perform
            # an explicit case-insensitive match to keep the previous behavior.
            index = next(
                (i for i in range(combo.count()) if combo.itemText(i).strip().upper() == target),
                -1,
            )
            if index < 0:
                combo.addItem(target)
                index = next(
                    (i for i in range(combo.count()) if combo.itemText(i).strip().upper() == target),
                    -1,
                )
            combo.setCurrentIndex(index if index >= 0 else 0)

        ac_checkbox = QCheckBox("Enable AC cycle", group)
        layout.addWidget(ac_checkbox)

        ac_grid = QGridLayout()
        ac_grid.setContentsMargins(24, 0, 0, 0)
        ac_grid.setHorizontalSpacing(12)
        ac_grid.setVerticalSpacing(6)

        ac_on_label = QLabel("AC on duration (s)", group)
        ac_on_spin = QSpinBox(group)
        ac_on_spin.setRange(0, 24 * 60 * 60)
        ac_on_spin.setSuffix(" s")

        ac_off_label = QLabel("AC off duration (s)", group)
        ac_off_spin = QSpinBox(group)
        ac_off_spin.setRange(0, 24 * 60 * 60)
        ac_off_spin.setSuffix(" s")

        ac_port_label = QLabel("USB relay port", group)
        ac_port_combo = _build_port_combo(group)

        ac_mode_label = QLabel("Wiring mode", group)
        ac_mode_combo = ComboBox(group)
        ac_mode_combo.setMinimumWidth(160)
        ac_mode_combo.addItems(["NO", "NC"])

        ac_ping_checkbox = QCheckBox("Ping after AC cycle", group)

        ac_grid.addWidget(ac_on_label, 0, 0)
        ac_grid.addWidget(ac_on_spin, 0, 1)
        ac_grid.addWidget(ac_off_label, 1, 0)
        ac_grid.addWidget(ac_off_spin, 1, 1)
        ac_grid.addWidget(ac_port_label, 2, 0)
        ac_grid.addWidget(ac_port_combo, 2, 1)
        ac_grid.addWidget(ac_mode_label, 3, 0)
        ac_grid.addWidget(ac_mode_combo, 3, 1)
        ac_grid.addWidget(ac_ping_checkbox, 4, 0, 1, 2)
        layout.addLayout(ac_grid)

        self._bind_script_section(
            ac_checkbox,
            (ac_on_spin, ac_off_spin, ac_port_combo, ac_mode_combo, ac_ping_checkbox),
        )
        section_controls["ac"] = (
            ac_checkbox,
            (ac_on_spin, ac_off_spin, ac_port_combo, ac_mode_combo, ac_ping_checkbox),
        )

        str_checkbox = QCheckBox("Enable STR cycle", group)
        layout.addWidget(str_checkbox)

        str_grid = QGridLayout()
        str_grid.setContentsMargins(24, 0, 0, 0)
        str_grid.setHorizontalSpacing(12)
        str_grid.setVerticalSpacing(6)

        str_on_label = QLabel("STR on duration (s)", group)
        str_on_spin = QSpinBox(group)
        str_on_spin.setRange(0, 24 * 60 * 60)
        str_on_spin.setSuffix(" s")

        str_off_label = QLabel("STR off duration (s)", group)
        str_off_spin = QSpinBox(group)
        str_off_spin.setRange(0, 24 * 60 * 60)
        str_off_spin.setSuffix(" s")

        str_port_label = QLabel("USB relay port", group)
        str_port_combo = _build_port_combo(group)

        str_mode_label = QLabel("Wiring mode", group)
        str_mode_combo = ComboBox(group)
        str_mode_combo.setMinimumWidth(160)
        str_mode_combo.addItems(["NO", "NC"])

        str_ping_checkbox = QCheckBox("Ping after STR cycle", group)

        str_grid.addWidget(str_on_label, 0, 0)
        str_grid.addWidget(str_on_spin, 0, 1)
        str_grid.addWidget(str_off_label, 1, 0)
        str_grid.addWidget(str_off_spin, 1, 1)
        str_grid.addWidget(str_port_label, 2, 0)
        str_grid.addWidget(str_port_combo, 2, 1)
        str_grid.addWidget(str_mode_label, 3, 0)
        str_grid.addWidget(str_mode_combo, 3, 1)
        str_grid.addWidget(str_ping_checkbox, 4, 0, 1, 2)
        layout.addLayout(str_grid)

        self._bind_script_section(
            str_checkbox,
            (str_on_spin, str_off_spin, str_port_combo, str_mode_combo, str_ping_checkbox),
        )
        section_controls["str"] = (
            str_checkbox,
            (str_on_spin, str_off_spin, str_port_combo, str_mode_combo, str_ping_checkbox),
        )

        layout.addStretch(1)

        ac_cfg = data.get("ac", {})
        str_cfg = data.get("str", {})

        ac_checkbox.setChecked(bool(ac_cfg.get("enabled")))
        ac_on_spin.setValue(int(ac_cfg.get("on_duration") or 0))
        ac_off_spin.setValue(int(ac_cfg.get("off_duration") or 0))
        ac_ping_checkbox.setChecked(bool(ac_cfg.get("ping")))
        ac_port = str(ac_cfg.get("port", "") or "").strip()
        ac_mode = str(ac_cfg.get("mode", "") or "").strip().upper() or "NO"
        _set_port_default(ac_port_combo, ac_port)
        _set_mode_default(ac_mode_combo, ac_mode)

        str_checkbox.setChecked(bool(str_cfg.get("enabled")))
        str_on_spin.setValue(int(str_cfg.get("on_duration") or 0))
        str_off_spin.setValue(int(str_cfg.get("off_duration") or 0))
        str_ping_checkbox.setChecked(bool(str_cfg.get("ping")))
        str_port = str(str_cfg.get("port", "") or "").strip()
        str_mode = str(str_cfg.get("mode", "") or "").strip().upper() or "NO"
        _set_port_default(str_port_combo, str_port)
        _set_mode_default(str_mode_combo, str_mode)

        widgets[self._script_field_key(case_key, "ac", "enabled")] = ac_checkbox
        widgets[self._script_field_key(case_key, "ac", "on_duration")] = ac_on_spin
        widgets[self._script_field_key(case_key, "ac", "off_duration")] = ac_off_spin
        widgets[self._script_field_key(case_key, "ac", "port")] = ac_port_combo
        widgets[self._script_field_key(case_key, "ac", "mode")] = ac_mode_combo
        widgets[self._script_field_key(case_key, "ac", "ping")] = ac_ping_checkbox

        widgets[self._script_field_key(case_key, "str", "enabled")] = str_checkbox
        widgets[self._script_field_key(case_key, "str", "on_duration")] = str_on_spin
        widgets[self._script_field_key(case_key, "str", "off_duration")] = str_off_spin
        widgets[self._script_field_key(case_key, "str", "port")] = str_port_combo
        widgets[self._script_field_key(case_key, "str", "mode")] = str_mode_combo
        widgets[self._script_field_key(case_key, "str", "ping")] = str_ping_checkbox

        field_keys = set(widgets.keys())

        return ScriptConfigEntry(
            group=group,
            widgets=widgets,
            field_keys=field_keys,
            section_controls=section_controls,
            case_key=case_key,
            case_path=case_path,
        )

        if not case_path:
            return ["dut"]
        keys = ["dut"]
        if self._is_performance_case(case_path) or info.enable_csv:
            keys.append("execution")
        else:
            case_key = self._script_case_key(case_path)
            if case_key in self._script_groups:
                keys.append("stability")
        return keys

    def _register_group(self, key: str, group: QWidget, is_dut: bool) -> None:
        if is_dut:
            self._dut_groups[key] = group
        else:
            self._other_groups[key] = group

    @staticmethod
    def _is_dut_key(key: str) -> bool:
        return key in {
            "connect_type",
            "fpga",
            "serial_port",
            "software_info",
            "hardware_info",
            "android_system",
        }

    @staticmethod
    def _normalize_fpga_token(value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip().upper()

    @staticmethod
    def _split_legacy_fpga_value(raw: str) -> tuple[str, str]:
        parts = raw.split("_", 1)
        wifi_module = parts[0] if parts and parts[0] else ""
        interface = parts[1] if len(parts) > 1 and parts[1] else ""
        return wifi_module.upper(), interface.upper()

    def _guess_fpga_project(
        self,
        wifi_module: str,
        interface: str,
        main_chip: str = "",
        *,
        customer: str = "",
        product_line: str = "",
        project: str = "",
    ) -> tuple[str, str, str, Optional[dict[str, str]]]:
        wifi_upper = wifi_module.strip().upper()
        interface_upper = interface.strip().upper()
        chip_upper = main_chip.strip().upper()
        customer_upper = customer.strip().upper()
        product_upper = product_line.strip().upper()
        project_upper = project.strip().upper()
        for customer_name, product_lines in WIFI_PRODUCT_PROJECT_MAP.items():
            if customer_upper and customer_name != customer_upper:
                continue
            for product_name, projects in product_lines.items():
                if product_upper and product_name != product_upper:
                    continue
                for project_name, info in projects.items():
                    if project_upper and project_name != project_upper:
                        continue
                    info_wifi = self._normalize_fpga_token(info.get("wifi_module"))
                    info_if = self._normalize_fpga_token(info.get("interface"))
                    info_chip = self._normalize_fpga_token(info.get("main_chip"))
                    if wifi_upper and info_wifi and info_wifi != wifi_upper:
                        continue
                    if interface_upper and info_if and info_if != interface_upper:
                        continue
                    if chip_upper and info_chip and info_chip != chip_upper:
                        continue
                    return customer_name, product_name, project_name, info
        return "", "", "", None

    def _normalize_fpga_section(self, raw_value: Any) -> dict[str, str]:
        normalized = {
            "customer": "",
            "product_line": "",
            "project": "",
            "main_chip": "",
            "wifi_module": "",
            "interface": "",
        }
        if isinstance(raw_value, Mapping):
            customer = self._normalize_fpga_token(raw_value.get("customer"))
            product_line = self._normalize_fpga_token(raw_value.get("product_line"))
            project = self._normalize_fpga_token(raw_value.get("project"))
            main_chip = self._normalize_fpga_token(raw_value.get("main_chip"))
            wifi_module = raw_value.get("wifi_module") or raw_value.get("series") or ""
            interface = raw_value.get("interface") or ""
            normalized.update(
                {
                    "customer": customer,
                    "product_line": product_line,
                    "project": project,
                    "main_chip": main_chip,
                    "wifi_module": self._normalize_fpga_token(wifi_module),
                    "interface": self._normalize_fpga_token(interface),
                }
            )
            guessed_customer, guessed_product, guessed_project, info = self._guess_fpga_project(
                normalized["wifi_module"],
                normalized["interface"],
                main_chip,
                customer=customer,
                product_line=product_line,
                project=project,
            )
            if guessed_customer:
                normalized["customer"] = guessed_customer
            if guessed_product:
                normalized["product_line"] = guessed_product
            if guessed_project:
                normalized["project"] = guessed_project
            if info:
                if not normalized["main_chip"]:
                    normalized["main_chip"] = self._normalize_fpga_token(info.get("main_chip"))
                if not normalized["wifi_module"]:
                    normalized["wifi_module"] = self._normalize_fpga_token(info.get("wifi_module"))
                if not normalized["interface"]:
                    normalized["interface"] = self._normalize_fpga_token(info.get("interface"))
        elif isinstance(raw_value, str):
            wifi_module, interface = self._split_legacy_fpga_value(raw_value)
            normalized["wifi_module"] = wifi_module
            normalized["interface"] = interface
            customer, product, project, info = self._guess_fpga_project(wifi_module, interface)
            if customer:
                normalized["customer"] = customer
            if product:
                normalized["product_line"] = product
            if project:
                normalized["project"] = project
            if info:
                normalized["main_chip"] = self._normalize_fpga_token(info.get("main_chip"))
                normalized["wifi_module"] = self._normalize_fpga_token(info.get("wifi_module"))
                normalized["interface"] = self._normalize_fpga_token(info.get("interface"))
        return normalized

    def _normalize_connect_type_section(self, raw_value: Any) -> dict[str, Any]:
        normalized: dict[str, Any] = {}
        if isinstance(raw_value, Mapping):
            normalized.update(raw_value)

        type_value = normalized.get("type", "adb")
        if isinstance(type_value, str):
            type_value = type_value.strip() or "adb"
        else:
            type_value = str(type_value).strip() or "adb"
        normalized["type"] = type_value

        adb_cfg = normalized.get("adb")
        if isinstance(adb_cfg, Mapping):
            adb_dict = dict(adb_cfg)
        else:
            adb_dict = {}
            if adb_cfg not in (None, ""):
                adb_dict["device"] = str(adb_cfg)
        device = adb_dict.get("device", "")
        adb_dict["device"] = str(device).strip() if device is not None else ""
        normalized["adb"] = adb_dict

        telnet_cfg = normalized.get("telnet")
        if isinstance(telnet_cfg, Mapping):
            telnet_dict = dict(telnet_cfg)
        else:
            telnet_dict = {}
            if isinstance(telnet_cfg, str) and telnet_cfg.strip():
                telnet_dict["ip"] = telnet_cfg.strip()
        telnet_ip = telnet_dict.get("ip", "")
        telnet_dict["ip"] = str(telnet_ip).strip() if telnet_ip is not None else ""
        wildcard = telnet_dict.get("wildcard", "")
        telnet_dict["wildcard"] = str(wildcard).strip() if wildcard is not None else ""
        normalized["telnet"] = telnet_dict

        third_cfg = normalized.get("third_party")
        if isinstance(third_cfg, Mapping):
            third_dict = dict(third_cfg)
        else:
            third_dict = {}
        enabled_val = third_dict.get("enabled", False)
        if isinstance(enabled_val, str):
            enabled_bool = enabled_val.strip().lower() in {"1", "true", "yes", "on"}
        else:
            enabled_bool = bool(enabled_val)
        third_dict["enabled"] = enabled_bool
        wait_val = third_dict.get("wait_seconds")
        wait_seconds: Optional[int]
        if wait_val in (None, ""):
            wait_seconds = None
        else:
            try:
                wait_seconds = int(str(wait_val).strip())
            except (TypeError, ValueError):
                wait_seconds = None
        if wait_seconds is not None and wait_seconds < 0:
            wait_seconds = None
        third_dict["wait_seconds"] = wait_seconds
        normalized["third_party"] = third_dict

        return normalized

    def _refresh_fpga_product_lines(
        self,
        customer: str,
        product_to_select: Optional[str] = None,
        *,
        block_signals: bool = False,
    ) -> None:
        if not hasattr(self, "fpga_product_combo"):
            return
        combo = self.fpga_product_combo
        blocker = QSignalBlocker(combo) if block_signals else None
        customer_upper = customer.strip().upper()
        product_lines = WIFI_PRODUCT_PROJECT_MAP.get(customer_upper, {}) if customer_upper else {}
        combo.clear()
        for product_name in product_lines.keys():
            combo.addItem(product_name)
        if product_to_select and product_to_select in product_lines:
            combo.setCurrentText(product_to_select)
        else:
            combo.setCurrentIndex(-1)
        if blocker is not None:
            del blocker

    def _refresh_fpga_projects(
        self,
        customer: str,
        product_line: str,
        project_to_select: Optional[str] = None,
        *,
        block_signals: bool = False,
    ) -> None:
        if not hasattr(self, "fpga_project_combo"):
            return
        combo = self.fpga_project_combo
        blocker = QSignalBlocker(combo) if block_signals else None
        customer_upper = customer.strip().upper()
        product_upper = product_line.strip().upper()
        projects = {}
        if customer_upper:
            projects = WIFI_PRODUCT_PROJECT_MAP.get(customer_upper, {}).get(product_upper, {})
        elif product_upper:
            for product_lines in WIFI_PRODUCT_PROJECT_MAP.values():
                if product_upper in product_lines:
                    projects = product_lines.get(product_upper, {})
                    break
        combo.clear()
        for project_name in projects.keys():
            combo.addItem(project_name)
        if project_to_select and project_to_select in projects:
            combo.setCurrentText(project_to_select)
        else:
            combo.setCurrentIndex(-1)
        if blocker is not None:
            del blocker

    def _update_fpga_hidden_fields(self) -> None:
        customer = self.fpga_customer_combo.currentText().strip().upper() if hasattr(self, "fpga_customer_combo") else ""
        product = self.fpga_product_combo.currentText().strip().upper() if hasattr(self, "fpga_product_combo") else ""
        project = self.fpga_project_combo.currentText().strip().upper() if hasattr(self, "fpga_project_combo") else ""
        info: Mapping[str, str] | None = None
        if customer and product and project:
            info = (
                WIFI_PRODUCT_PROJECT_MAP.get(customer, {})
                .get(product, {})
                .get(project, {})
            )
        elif product and project:
            for customer_name, product_lines in WIFI_PRODUCT_PROJECT_MAP.items():
                project_info = product_lines.get(product, {}).get(project)
                if project_info:
                    if not customer:
                        customer = customer_name
                    info = project_info
                    break
        if product and project and info:
            normalized = {
                "customer": customer,
                "product_line": product,
                "project": project,
                "main_chip": self._normalize_fpga_token(info.get("main_chip")),
                "wifi_module": self._normalize_fpga_token(info.get("wifi_module")),
                "interface": self._normalize_fpga_token(info.get("interface")),
            }
        else:
            normalized = {
                "customer": customer,
                "product_line": product,
                "project": project,
                "main_chip": "",
                "wifi_module": "",
                "interface": "",
            }
        self._fpga_details = normalized
        self.config["fpga"] = dict(normalized)

    def on_fpga_customer_changed(self, customer: str) -> None:
        if not hasattr(self, "fpga_product_combo") or not hasattr(self, "fpga_project_combo"):
            return
        current_product = self.fpga_product_combo.currentText().strip().upper()
        customer_upper = customer.strip().upper()
        product_lines = WIFI_PRODUCT_PROJECT_MAP.get(customer_upper, {}) if customer_upper else {}
        product_to_select = current_product if current_product in product_lines else None
        self._refresh_fpga_product_lines(customer, product_to_select, block_signals=True)
        selected_product = self.fpga_product_combo.currentText()
        self.on_fpga_product_line_changed(selected_product)

    def on_fpga_product_line_changed(self, product_line: str) -> None:
        if not hasattr(self, "fpga_project_combo"):
            return
        current_project = self.fpga_project_combo.currentText().strip().upper()
        customer = self.fpga_customer_combo.currentText() if hasattr(self, "fpga_customer_combo") else ""
        projects = WIFI_PRODUCT_PROJECT_MAP.get(customer.strip().upper(), {}).get(product_line.strip().upper(), {})
        project_to_select = current_project if current_project in projects else None
        self._refresh_fpga_projects(customer, product_line, project_to_select, block_signals=True)
        self._update_fpga_hidden_fields()

    def on_fpga_project_changed(self, project: str) -> None:
        self._update_fpga_hidden_fields()

    def _sync_widgets_to_config(self) -> None:
        if not isinstance(self.config, dict):
            self.config = {}
        for key, widget in self.field_widgets.items():
            parts = key.split('.')
            ref = self.config
            for part in parts[:-1]:
                child = ref.get(part)
                if not isinstance(child, dict):
                    child = {}
                    ref[part] = child
                ref = child
            leaf = parts[-1]
            if isinstance(widget, LineEdit):
                val = widget.text()
                if key == "connect_type.third_party.wait_seconds":
                    val = val.strip()
                    ref[leaf] = int(val) if val else 0
                    continue
                if key == "rf_solution.step":
                    ref[leaf] = val.strip()
                    continue
                old_val = ref.get(leaf)
                if isinstance(old_val, list):
                    items = [x.strip() for x in val.split(',') if x.strip()]
                    if all(i.isdigit() for i in items):
                        ref[leaf] = [int(i) for i in items]
                    else:
                        ref[leaf] = items
                else:
                    val = val.strip()
                    if len(parts) >= 2 and parts[-2] == "router" and leaf.startswith("passwd") and not val:
                        ref[leaf] = ""
                    else:
                        ref[leaf] = val
            elif isinstance(widget, RfStepSegmentsWidget):
                ref[leaf] = widget.serialize()
            elif isinstance(widget, ComboBox):
                data = widget.currentData()
                if data not in (None, "", widget.currentText()):
                    ref[leaf] = data
                else:
                    text = widget.currentText().strip()
                    if text.lower() == 'select port':
                        text = ''
                    ref[leaf] = True if text == 'True' else False if text == 'False' else text
            elif isinstance(widget, QSpinBox):
                ref[leaf] = widget.value()
            elif isinstance(widget, QCheckBox):
                ref[leaf] = widget.isChecked()
        if hasattr(self, "_fpga_details"):
            self.config["fpga"] = dict(self._fpga_details)
        base = Path(self._get_application_base())
        case_display = self.field_widgets.get("text_case")
        display_text = case_display.text().strip() if isinstance(case_display, LineEdit) else ""
        storage_path = self._current_case_path or self._display_to_case_path(display_text)
        case_path = Path(storage_path).as_posix() if storage_path else ""
        self._current_case_path = case_path
        if case_path:
            abs_case_path = (base / case_path).resolve().as_posix()
        else:
            abs_case_path = ""
        self.config["text_case"] = case_path
        if self.selected_csv_path:
            base_cfg = get_config_base()
            try:
                rel_csv = os.path.relpath(Path(self.selected_csv_path).resolve(), base_cfg)
            except ValueError:
                rel_csv = Path(self.selected_csv_path).resolve().as_posix()
            self.config["csv_path"] = Path(rel_csv).as_posix()
        else:
            self.config.pop("csv_path", None)
        proxy_idx = self.case_tree.currentIndex()
        model = self.case_tree.model()
        src_idx = (
            model.mapToSource(proxy_idx)
            if isinstance(model, QSortFilterProxyModel)
            else proxy_idx
        )
        selected_path = self.fs_model.filePath(src_idx)
        if os.path.isfile(selected_path) and selected_path.endswith(".py"):
            abs_path = Path(selected_path).resolve()
            display_path = os.path.relpath(abs_path, base)
            case_path = Path(display_path).as_posix()
            self._current_case_path = case_path
            self.config["text_case"] = case_path
        self._update_step_indicator(self.stack.currentIndex())

    def _validate_first_page(self) -> bool:
        errors: list[str] = []
        connect_type = ""
        focus_widget: QWidget | None = None
        if hasattr(self, "connect_type_combo"):
            connect_type = self.connect_type_combo.currentText().strip()
            if not connect_type:
                errors.append("Connect type is required.")
                focus_widget = focus_widget or self.connect_type_combo
            elif connect_type == "adb" and hasattr(self, "adb_device_edit"):
                if not self.adb_device_edit.text().strip():
                    errors.append("ADB device is required.")
                    focus_widget = focus_widget or self.adb_device_edit
            elif connect_type == "telnet" and hasattr(self, "telnet_ip_edit"):
                if not self.telnet_ip_edit.text().strip():
                    errors.append("Telnet IP is required.")
                    focus_widget = focus_widget or self.telnet_ip_edit
                kernel_text = ""
                if hasattr(self, "kernel_version_combo"):
                    kernel_text = self.kernel_version_combo.currentText().strip()
                if not kernel_text:
                    errors.append("Kernel version is required for telnet access.")
                    focus_widget = focus_widget or getattr(self, "kernel_version_combo", None)
            if hasattr(self, "third_party_checkbox") and self.third_party_checkbox.isChecked():
                wait_text = self.third_party_wait_edit.text().strip() if hasattr(self, "third_party_wait_edit") else ""
                if not wait_text or not wait_text.isdigit() or int(wait_text) <= 0:
                    errors.append("Third-party wait time must be a positive integer.")
                    if hasattr(self, "third_party_wait_edit"):
                        focus_widget = focus_widget or self.third_party_wait_edit
        else:
            errors.append("Connect type widget missing.")
        if hasattr(self, "android_version_combo") and connect_type == "adb" and not self.android_version_combo.currentText().strip():
            errors.append("Android version is required.")
            focus_widget = focus_widget or self.android_version_combo
        fpga_valid = (
            hasattr(self, "fpga_customer_combo")
            and hasattr(self, "fpga_product_combo")
            and hasattr(self, "fpga_project_combo")
        )
        customer_text = self.fpga_customer_combo.currentText().strip() if fpga_valid else ""
        product_text = self.fpga_product_combo.currentText().strip() if fpga_valid else ""
        project_text = self.fpga_project_combo.currentText().strip() if fpga_valid else ""
        if not fpga_valid or not customer_text or not product_text or not project_text:
            errors.append("Wi-Fi chipset customer, product line and project are required.")
            if fpga_valid:
                focus_widget = focus_widget or (
                    self.fpga_customer_combo
                    if not customer_text
                    else self.fpga_product_combo
                    if not product_text
                    else self.fpga_project_combo
                )
        if errors:
            self._show_info_bar(
                "warning",
                "Validation",
                "\n".join(errors),
                duration=3000,
            )
            if focus_widget is not None:
                focus_widget.setFocus()
                if hasattr(focus_widget, "selectAll"):
                    focus_widget.selectAll()
            return False
        return True

    def _reset_second_page_inputs(self) -> None:
        if hasattr(self, "csv_combo"):
            self._set_selected_csv(self.selected_csv_path, sync_combo=True)
            self.csv_combo.setEnabled(bool(self._enable_rvr_wifi))
        else:
            self._set_selected_csv(None, sync_combo=False)

    def _reset_wizard_after_run(self) -> None:
        self.stack.setCurrentIndex(0)
        self._update_step_indicator(0)
        self._update_navigation_state()
        self._reset_second_page_inputs()

    def _on_page_changed(self, index: int) -> None:
        self._update_step_indicator(index)
        self._update_navigation_state()

    def _update_navigation_state(self) -> None:
        self._sync_run_buttons_enabled()

    def on_next_clicked(self) -> None:
        self._navigate_to_index(self.stack.currentIndex() + 1)

    def on_previous_clicked(self) -> None:
        self._navigate_to_index(self.stack.currentIndex() - 1)

    def _is_performance_case(self, abs_case_path) -> bool:
        """
        判断 abs_case_path 是否位于 test/performance 目录（任何层级都算）。
        不依赖工程根路径，只看路径片段。
        """
        logging.debug("Checking performance case path: %s", abs_case_path)
        if not abs_case_path:
            logging.debug("_is_performance_case: empty path -> False")
            return False
        try:
            from pathlib import Path
            p = Path(abs_case_path).resolve()
            # 检查父链中是否出现 .../test/performance
            for node in (p, *p.parents):
                if node.name == "performance" and node.parent.name == "test":
                    logging.debug("_is_performance_case: True")
                    return True
                logging.debug("_is_performance_case: False")
            return False
        except Exception as e:
            logging.error("_is_performance_case exception: %s", e)
            return False

    def _init_case_tree(self, root_dir: Path) -> None:
        self.fs_model = QFileSystemModel(self.case_tree)
        root_index = self.fs_model.setRootPath(str(root_dir))  # ← use return value
        self.fs_model.setNameFilters(["test_*.py"])
        # show directories regardless of filter
        self.fs_model.setNameFilterDisables(True)
        self.fs_model.setFilter(
            QDir.Filter.AllDirs | QDir.Filter.NoDotAndDotDot | QDir.Filter.Files
        )
        self.proxy_model = TestFileFilterModel()
        self.proxy_model.setSourceModel(self.fs_model)
        self.case_tree.setModel(self.proxy_model)
        self.case_tree.setRootIndex(self.proxy_model.mapFromSource(root_index))

        # 隐藏非名称列
        self.case_tree.header().hide()
        for col in range(1, self.fs_model.columnCount()):
            self.case_tree.hideColumn(col)

    def _load_config(self) -> dict:
        try:
            config = load_config(refresh=True) or {}

            app_base = self._get_application_base()
            changed = False
            path = config.get("text_case", "")
            if path:
                abs_path = Path(path)
                if not abs_path.is_absolute():
                    abs_path = app_base / abs_path
                abs_path = abs_path.resolve()
                if abs_path.exists():
                    try:
                        rel_path = abs_path.relative_to(app_base)
                    except ValueError:
                        config["text_case"] = ""
                        changed = True
                    else:
                        rel_str = rel_path.as_posix()
                        if rel_str != path:
                            config["text_case"] = rel_str
                            changed = True
                else:
                    config["text_case"] = ""
                    changed = True
            else:
                config["text_case"] = ""

            if changed:
                try:
                    save_config(config)
                except Exception as exc:
                    logging.error("Failed to normalize and persist config: %s", exc)
                    QTimer.singleShot(
                        0,
                        lambda exc=exc: InfoBar.error(
                            title="Error",
                            content=f"Failed to write config: {exc}",
                            parent=self,
                            position=InfoBarPosition.TOP,
                        ),
                    )
            return config
        except Exception as exc:
            QTimer.singleShot(
                0,
                lambda exc=exc: InfoBar.error(
                    title="Error",
                    content=f"Failed to load config : {exc}",
                    parent=self,
                    position=InfoBarPosition.TOP,
                ),
            )
            return {}

    def _save_config(self):
        logging.debug("[save] data=%s", self.config)
        try:
            save_config(self.config)
            logging.info("Configuration saved")
            self.config = self._load_config()
            logging.info("Configuration saved")
        except Exception as exc:
            logging.error("[save] failed: %s", exc)
            QTimer.singleShot(
                0,
                lambda exc=exc: InfoBar.error(
                    title="Error",
                    content=f"Failed to save config: {exc}",
                    parent=self,
                    position=InfoBarPosition.TOP,
                ),
            )

    def _get_application_base(self) -> Path:
        """获取应用根路径"""
        return Path(get_src_base()).resolve()

    def _resolve_case_path(self, path: str | Path) -> Path:
        """将相对用例路径转换为绝对路径"""
        if not path:
            return Path()
        p = Path(path)
        base = Path(self._get_application_base())
        return str(p) if p.is_absolute() else str((base / p).resolve())

    def on_connect_type_changed(self, type_str):
        """切换连接方式时，仅展示对应参数组"""
        self.adb_group.setVisible(type_str == "adb")
        self.telnet_group.setVisible(type_str == "telnet")
        self._update_android_system_for_connect_type(type_str)
        self._request_rebalance_for_panels(self._dut_panel)
    def _update_android_system_for_connect_type(self, connect_type: str) -> None:
        if not hasattr(self, "android_version_combo") or not hasattr(self, "kernel_version_combo"):
            return
        is_adb = connect_type == "adb"
        # Android version selectors are only shown for ADB connections.
        self.android_version_label.setVisible(is_adb)
        self.android_version_combo.setVisible(is_adb)
        # Kernel selector is always visible but toggles between auto-fill and manual modes.
        self.kernel_version_label.setVisible(True)
        self.kernel_version_combo.setVisible(True)
        if is_adb:
            self.kernel_version_combo.setEnabled(False)
            self._apply_android_kernel_mapping()
        else:
            self.kernel_version_combo.setEnabled(True)
            if not self.kernel_version_combo.currentText().strip():
                self.kernel_version_combo.setCurrentIndex(-1)

    def _on_android_version_changed(self, version: str) -> None:
        if not hasattr(self, "connect_type_combo"):
            return
        if self.connect_type_combo.currentText().strip() == "adb":
            self._apply_android_kernel_mapping()

    def _apply_android_kernel_mapping(self) -> None:
        if not hasattr(self, "android_version_combo") or not hasattr(self, "kernel_version_combo"):
            return
        version = self.android_version_combo.currentText().strip()
        kernel = ANDROID_KERNEL_MAP.get(version, "")
        if kernel:
            self._ensure_kernel_option(kernel)
            self.kernel_version_combo.setCurrentText(kernel)
        else:
            self.kernel_version_combo.setCurrentIndex(-1)

    def _ensure_kernel_option(self, kernel: str) -> None:
        if not kernel or not hasattr(self, "kernel_version_combo"):
            return
        combo = self.kernel_version_combo
        existing = {combo.itemText(i) for i in range(combo.count())}
        if kernel not in existing:
            combo.addItem(kernel)
        if kernel not in self._kernel_versions:
            self._kernel_versions.append(kernel)


    def on_third_party_toggled(self, checked: bool, allow_wait_edit: bool | None = None) -> None:
        if not hasattr(self, "third_party_wait_edit"):
            return
        if allow_wait_edit is None:
            checkbox = getattr(self, "third_party_checkbox", None)
            allow_wait_edit = checkbox.isEnabled() if isinstance(checkbox, QCheckBox) else True
        enable_wait = bool(checked and allow_wait_edit)
        self.third_party_wait_edit.setEnabled(enable_wait)
        if hasattr(self, "third_party_wait_label"):
            self.third_party_wait_label.setEnabled(enable_wait)

    def on_rf_model_changed(self, model_str):
        """
        切换rf_solution.model时，仅展示当前选项参数
        现在只有RS232Board5，如果有别的model，添加隐藏/显示逻辑
        """
        # 当前只有RS232Board5，后续有其它model可以加if-else
        if hasattr(self, "xin_group"):
            self.xin_group.setVisible(model_str == "RS232Board5")
        if hasattr(self, "rc4_group"):
            self.rc4_group.setVisible(model_str == "RC4DAT-8G-95")
        if hasattr(self, "rack_group"):
            self.rack_group.setVisible(model_str == "RADIORACK-4-220")
        if hasattr(self, "lda_group"):
            self.lda_group.setVisible(model_str == "LDA-908V-8")
        self._request_rebalance_for_panels(self._execution_panel)

    # 添加到类里：响应 Tool 下拉，切换子参数可见性
    def on_rvr_tool_changed(self, tool: str):
        """选择 iperf / ixchariot 时，动态显示对应子参数"""
        self.rvr_iperf_group.setVisible(tool == "iperf")
        self.rvr_ix_group.setVisible(tool == "ixchariot")
        self._request_rebalance_for_panels(self._execution_panel)

    def on_serial_enabled_changed(self, text: str):
        self.serial_cfg_group.setVisible(text == "True")
        self._request_rebalance_for_panels(self._dut_panel)

    def on_router_changed(self, name: str):
        cfg = self.config.get("router", {})
        addr = cfg.get("address") if cfg.get("name") == name else None
        self.router_obj = get_router(name, addr)
        self.router_addr_edit.setText(self.router_obj.address)
        self.routerInfoChanged.emit()

    def on_router_address_changed(self, text: str) -> None:
        if self.router_obj is not None:
            self.router_obj.address = text
        self.routerInfoChanged.emit()

    def _update_csv_options(self):
        """刷新 CSV 下拉框"""
        if not hasattr(self, "csv_combo"):
            return
        router_name = ""
        if hasattr(self, "router_name_combo"):
            router_name = self.router_name_combo.currentText().lower()
        csv_dir = get_config_base() / "performance_test_csv"
        logging.debug("_update_csv_options router=%s dir=%s", router_name, csv_dir)
        with QSignalBlocker(self.csv_combo):
            self.csv_combo.clear()
            if csv_dir.exists():
                for csv_file in sorted(csv_dir.glob("*.csv")):
                    logging.debug("found csv: %s", csv_file)
                    # qfluentwidgets.ComboBox 在 Qt5 和 Qt6 下对 userData 的处理不一致，
                    # 直接通过 addItem(text, userData) 可能导致无法获取到数据。
                    # 因此先添加文本，再显式设置 UserRole 数据，确保 itemData 能正确返回文件路径。
                    self.csv_combo.addItem(csv_file.name)
                    idx = self.csv_combo.count() - 1
                    self.csv_combo.setItemData(idx, str(csv_file.resolve()))
        self._set_selected_csv(None, sync_combo=True)

    def _normalize_csv_path(self, path: Any) -> str | None:
        """Normalize CSV paths to absolute strings for reliable comparisons."""
        if not path:
            return None
        try:
            return str(Path(path).resolve())
        except Exception:
            return str(path)

    def _find_csv_index(self, normalized_path: str) -> int:
        """Return the combo index for a normalized CSV path."""
        if not hasattr(self, "csv_combo"):
            return -1
        for idx in range(self.csv_combo.count()):
            data = self.csv_combo.itemData(idx)
            if not data:
                continue
            candidate = self._normalize_csv_path(data)
            if candidate == normalized_path:
                return idx
        return -1

    def _set_selected_csv(self, path: str | None, *, sync_combo: bool = True) -> bool:
        """
        Update the cached CSV selection and optionally sync the combo box.

        Returns True when the selection actually changes.
        """
        normalized = self._normalize_csv_path(path)
        target_index = -1
        if sync_combo and normalized and hasattr(self, "csv_combo"):
            target_index = self._find_csv_index(normalized)
            if target_index == -1:
                normalized = None
        changed = normalized != self.selected_csv_path
        self.selected_csv_path = normalized
        if sync_combo and hasattr(self, "csv_combo"):
            with QSignalBlocker(self.csv_combo):
                self.csv_combo.setCurrentIndex(target_index)
        self._update_rvr_nav_button()
        return changed

    def _update_rvr_nav_button(self) -> None:
        """根据当前状态更新 RVR 导航按钮可用性"""
        main_window = self.window()
        if hasattr(main_window, "rvr_nav_button"):
            enabled = bool(self._enable_rvr_wifi and self.selected_csv_path)
            main_window.rvr_nav_button.setEnabled(enabled)

    def _case_path_to_display(self, case_path: str) -> str:
        if not case_path:
            return ""
        normalized = Path(case_path).as_posix()
        return normalized[5:] if normalized.startswith("test/") else normalized

    def _display_to_case_path(self, display_path: str) -> str:
        if not display_path:
            return ""
        normalized = display_path.replace('\\', '/')
        if normalized.startswith('./'):
            normalized = normalized[2:]
        path_obj = Path(normalized)
        if path_obj.is_absolute() or normalized.startswith('../'):
            return path_obj.as_posix()
        return normalized if normalized.startswith("test/") else f"test/{normalized}"

    def _update_test_case_display(self, storage_path: str) -> None:
        normalized = Path(storage_path).as_posix() if storage_path else ""
        self._current_case_path = normalized
        if hasattr(self, 'test_case_edit'):
            self.test_case_edit.setText(self._case_path_to_display(normalized))

    def render_all_fields(self):
        """自动渲染配置字段，支持 LineEdit / ComboBox（可扩展 Checkbox）。"""
        self._dut_groups.clear()
        self._other_groups.clear()
        # Ensure DUT metadata placeholders exist
        defaults_for_dut = {
            "software_info": {},
            "hardware_info": {},
            "android_system": {},
        }
        for _key, _default in defaults_for_dut.items():
            existing = self.config.get(_key)
            if not isinstance(existing, dict):
                self.config[_key] = _default.copy()
            else:
                self.config[_key] = dict(existing)
        def _coerce_debug_flag(value) -> bool:
            if isinstance(value, str):
                return value.strip().lower() in {"1", "true", "yes", "on"}
            return bool(value)

        def _normalize_debug_section(raw_value) -> dict[str, bool]:
            if isinstance(raw_value, dict):
                normalized = dict(raw_value)
            else:
                normalized = {"database_mode": raw_value}
            for option in ("database_mode", "skip_router", "skip_corner_rf"):
                normalized[option] = _coerce_debug_flag(normalized.get(option))
            return normalized

        self.config["debug"] = _normalize_debug_section(self.config.get("debug"))
        self.config["connect_type"] = self._normalize_connect_type_section(self.config.get("connect_type"))
        telnet_cfg = self.config["connect_type"].get("telnet")
        if isinstance(telnet_cfg, dict) and "kernel_version" in telnet_cfg:
            self.config.setdefault("android_system", {})["kernel_version"] = telnet_cfg.pop("kernel_version")
        self.config["fpga"] = self._normalize_fpga_section(self.config.get("fpga"))
        for i, (key, value) in enumerate(self.config.items()):
            if key == "script_params":
                continue
            if key == "software_info":
                data = value if isinstance(value, dict) else {}
                group = QGroupBox("Software Info")
                vbox = QVBoxLayout(group)
                self.software_version_edit = LineEdit(self)
                self.software_version_edit.setPlaceholderText("e.g. V1.2.3")
                self.software_version_edit.setText(str(data.get("software_version", "")))
                vbox.addWidget(QLabel("Software Version:"))
                vbox.addWidget(self.software_version_edit)
                self.driver_version_edit = LineEdit(self)
                self.driver_version_edit.setPlaceholderText("Driver build")
                self.driver_version_edit.setText(str(data.get("driver_version", "")))
                vbox.addWidget(QLabel("Driver Version:"))
                vbox.addWidget(self.driver_version_edit)
                self._register_group(key, group, True)
                self.field_widgets["software_info.software_version"] = self.software_version_edit
                self.field_widgets["software_info.driver_version"] = self.driver_version_edit
                continue
            if key == "hardware_info":
                data = value if isinstance(value, dict) else {}
                group = QGroupBox("Hardware Info")
                vbox = QVBoxLayout(group)
                self.hardware_version_edit = LineEdit(self)
                self.hardware_version_edit.setPlaceholderText("PCB revision / BOM")
                self.hardware_version_edit.setText(str(data.get("hardware_version", "")))
                vbox.addWidget(QLabel("Hardware Version:"))
                vbox.addWidget(self.hardware_version_edit)
                self._register_group(key, group, True)
                self.field_widgets["hardware_info.hardware_version"] = self.hardware_version_edit
                continue
            if key == "android_system":
                data = value if isinstance(value, dict) else {}
                group = QGroupBox("Android System")
                vbox = QVBoxLayout(group)
                self.android_version_label = QLabel("Android Version:")
                vbox.addWidget(self.android_version_label)
                self.android_version_combo = ComboBox(self)
                self.android_version_combo.addItems(self._android_versions)
                current_version = str(data.get("version", ""))
                if current_version and current_version not in self._android_versions:
                    self.android_version_combo.addItem(current_version)
                if current_version:
                    self.android_version_combo.setCurrentText(current_version)
                else:
                    self.android_version_combo.setCurrentIndex(-1)
                self.android_version_combo.currentTextChanged.connect(self._on_android_version_changed)
                vbox.addWidget(self.android_version_combo)
                self.kernel_version_label = QLabel("Kernel Version:")
                vbox.addWidget(self.kernel_version_label)
                self.kernel_version_combo = ComboBox(self)
                self.kernel_version_combo.addItems(self._kernel_versions)
                kernel_value = str(data.get("kernel_version", ""))
                if kernel_value and kernel_value not in self._kernel_versions:
                    self.kernel_version_combo.addItem(kernel_value)
                if kernel_value:
                    self.kernel_version_combo.setCurrentText(kernel_value)
                else:
                    self.kernel_version_combo.setCurrentIndex(-1)
                vbox.addWidget(self.kernel_version_combo)
                self._register_group(key, group, True)
                self.field_widgets["android_system.version"] = self.android_version_combo
                self.field_widgets["android_system.kernel_version"] = self.kernel_version_combo
                continue
            if key == "connect_type":
                group = QGroupBox("Control Type")
                vbox = QVBoxLayout(group)
                self.connect_type_combo = ComboBox(self)
                self.connect_type_combo.addItems(["adb", "telnet"])
                self.connect_type_combo.setCurrentText(value.get("type", "adb"))
                self.connect_type_combo.currentTextChanged.connect(self.on_connect_type_changed)
                vbox.addWidget(self.connect_type_combo)
                # 独立的 ADB / Telnet 参数面板
                self.adb_group = QWidget()
                adb_vbox = QVBoxLayout(self.adb_group)
                self.adb_device_edit = LineEdit(self)
                self.adb_device_edit.setPlaceholderText("adb.device")
                adb_vbox.addWidget(QLabel("ADB Device:"))
                adb_vbox.addWidget(self.adb_device_edit)

                self.telnet_group = QWidget()
                telnet_vbox = QVBoxLayout(self.telnet_group)
                telnet_cfg = value.get("telnet", {}) if isinstance(value, dict) else {}
                self.telnet_ip_edit = LineEdit(self)
                self.telnet_ip_edit.setPlaceholderText("telnet.ip")
                telnet_vbox.addWidget(QLabel("Telnet IP:"))
                telnet_vbox.addWidget(self.telnet_ip_edit)

                self.third_party_group = QWidget()
                third_party_vbox = QVBoxLayout(self.third_party_group)
                third_cfg = value.get("third_party", {}) if isinstance(value, dict) else {}
                enabled = bool(third_cfg.get("enabled", False))
                wait_seconds = third_cfg.get("wait_seconds")
                wait_text = "" if wait_seconds in (None, "") else str(wait_seconds)

                self.third_party_checkbox = QCheckBox("Enable third-party control", self)
                self.third_party_checkbox.setChecked(enabled)
                self.third_party_checkbox.toggled.connect(self.on_third_party_toggled)
                third_party_vbox.addWidget(self.third_party_checkbox)

                self.third_party_wait_label = QLabel("Wait seconds:")
                third_party_vbox.addWidget(self.third_party_wait_label)
                self.third_party_wait_edit = LineEdit(self)
                self.third_party_wait_edit.setPlaceholderText("wait seconds (e.g. 3)")
                self.third_party_wait_edit.setValidator(QIntValidator(1, 999999, self))
                self.third_party_wait_edit.setText(wait_text)
                third_party_vbox.addWidget(self.third_party_wait_edit)

                vbox.addWidget(self.adb_group)
                vbox.addWidget(self.telnet_group)
                vbox.addWidget(self.third_party_group)
                self._register_group(key, group, self._is_dut_key(key))
                self.adb_device_edit.setText(value.get("adb", {}).get("device", ""))
                self.telnet_ip_edit.setText(telnet_cfg.get("ip", ""))
                self.on_third_party_toggled(self.third_party_checkbox.isChecked())
                self.on_connect_type_changed(self.connect_type_combo.currentText())
                self.field_widgets["connect_type.type"] = self.connect_type_combo
                self.field_widgets["connect_type.adb.device"] = self.adb_device_edit
                self.field_widgets["connect_type.telnet.ip"] = self.telnet_ip_edit
                self.field_widgets["connect_type.third_party.enabled"] = self.third_party_checkbox
                self.field_widgets["connect_type.third_party.wait_seconds"] = self.third_party_wait_edit
                continue
                continue
            if key == "fpga":
                group = QGroupBox("Project")
                vbox = QVBoxLayout(group)
                defaults = self._normalize_fpga_section(value)
                customer_default = defaults.get("customer", "")
                product_default = defaults.get("product_line", "")
                project_default = defaults.get("project", "")

                if not customer_default and product_default:
                    for customer_name, product_lines in WIFI_PRODUCT_PROJECT_MAP.items():
                        if product_default in product_lines:
                            customer_default = customer_name
                            break

                self.fpga_customer_combo = ComboBox(self)
                for customer_name in WIFI_PRODUCT_PROJECT_MAP.keys():
                    self.fpga_customer_combo.addItem(customer_name)
                if customer_default and customer_default in WIFI_PRODUCT_PROJECT_MAP:
                    self.fpga_customer_combo.setCurrentText(customer_default)
                else:
                    self.fpga_customer_combo.setCurrentIndex(-1)

                self.fpga_product_combo = ComboBox(self)
                self.fpga_project_combo = ComboBox(self)

                self._refresh_fpga_product_lines(customer_default, product_default, block_signals=True)
                if (
                    customer_default
                    and product_default
                    and product_default in WIFI_PRODUCT_PROJECT_MAP.get(customer_default, {})
                ):
                    self.fpga_product_combo.setCurrentText(product_default)
                else:
                    self.fpga_product_combo.setCurrentIndex(-1)

                self._refresh_fpga_projects(customer_default, product_default, project_default, block_signals=True)
                if (
                    customer_default
                    and product_default
                    and project_default
                    and project_default
                    in WIFI_PRODUCT_PROJECT_MAP.get(customer_default, {}).get(product_default, {})
                ):
                    self.fpga_project_combo.setCurrentText(project_default)
                else:
                    self.fpga_project_combo.setCurrentIndex(-1)

                vbox.addWidget(QLabel("Customer:"))
                vbox.addWidget(self.fpga_customer_combo)
                vbox.addWidget(QLabel("Product Line:"))
                vbox.addWidget(self.fpga_product_combo)
                vbox.addWidget(QLabel("Project:"))
                vbox.addWidget(self.fpga_project_combo)

                self.fpga_customer_combo.currentTextChanged.connect(self.on_fpga_customer_changed)
                self.fpga_product_combo.currentTextChanged.connect(self.on_fpga_product_line_changed)
                self.fpga_project_combo.currentTextChanged.connect(self.on_fpga_project_changed)

                self._fpga_details = defaults
                self._update_fpga_hidden_fields()
                self._register_group(key, group, self._is_dut_key(key))
                self.field_widgets["fpga.customer"] = self.fpga_customer_combo
                self.field_widgets["fpga.product_line"] = self.fpga_product_combo
                self.field_widgets["fpga.project"] = self.fpga_project_combo
                continue
            if key == "rf_solution":
                group = QGroupBox("Attenuator")
                vbox = QVBoxLayout(group)
                # -------- 下拉：选择型号 --------
                self.rf_model_combo = ComboBox(self)
                self.rf_model_combo.addItems([
                    "RS232Board5",
                    "RC4DAT-8G-95",
                    "RADIORACK-4-220",
                    "LDA-908V-8",
                ])
                self.rf_model_combo.setCurrentText(value.get("model", "RS232Board5"))
                self.rf_model_combo.currentTextChanged.connect(self.on_rf_model_changed)
                vbox.addWidget(QLabel("Model:"))
                vbox.addWidget(self.rf_model_combo)

                # ========== ① RS232Board5 参数区（目前无额外字段，可放提醒文字） ==========
                self.xin_group = QWidget()
                xin_box = QVBoxLayout(self.xin_group)
                xin_box.addWidget(QLabel("SH - New Wi-Fi full-wave anechoic chamber "))
                vbox.addWidget(self.xin_group)

                # ========== ② RC4DAT-8G-95 参数区 ==========
                self.rc4_group = QWidget()
                rc4_box = QVBoxLayout(self.rc4_group)
                rc4_cfg = value.get("RC4DAT-8G-95", {})
                self.rc4_vendor_edit = LineEdit(self)
                self.rc4_product_edit = LineEdit(self)
                self.rc4_ip_edit = LineEdit(self)
                self.rc4_vendor_edit.setPlaceholderText("idVendor")
                self.rc4_product_edit.setPlaceholderText("idProduct")
                self.rc4_ip_edit.setPlaceholderText("ip_address")
                self.rc4_vendor_edit.setText(str(rc4_cfg.get("idVendor", "")))
                self.rc4_product_edit.setText(str(rc4_cfg.get("idProduct", "")))
                self.rc4_ip_edit.setText(rc4_cfg.get("ip_address", ""))
                rc4_box.addWidget(QLabel("idVendor:"))
                rc4_box.addWidget(self.rc4_vendor_edit)
                rc4_box.addWidget(QLabel("idProduct:"))
                rc4_box.addWidget(self.rc4_product_edit)
                rc4_box.addWidget(QLabel("IP address :"))
                rc4_box.addWidget(self.rc4_ip_edit)
                vbox.addWidget(self.rc4_group)

                # ========== ③ RADIORACK-4-220 参数区 ==========
                self.rack_group = QWidget()
                rack_box = QVBoxLayout(self.rack_group)
                rack_cfg = value.get("RADIORACK-4-220", {})
                self.rack_ip_edit = LineEdit(self)
                self.rack_ip_edit.setPlaceholderText("ip_address")
                self.rack_ip_edit.setText(rack_cfg.get("ip_address", ""))
                rack_box.addWidget(QLabel("IP address :"))
                rack_box.addWidget(self.rack_ip_edit)
                vbox.addWidget(self.rack_group)

                # ========== ④ LDA-908V-8 参数区 ==========
                self.lda_group = QWidget()
                lda_box = QVBoxLayout(self.lda_group)
                lda_cfg = value.get("LDA-908V-8", {})
                if not isinstance(lda_cfg, dict):
                    lda_cfg = {}
                    value["LDA-908V-8"] = lda_cfg
                channels_value = lda_cfg.setdefault("channels", [])
                self.lda_ip_edit = LineEdit(self)
                self.lda_ip_edit.setPlaceholderText("ip_address")
                self.lda_ip_edit.setText(lda_cfg.get("ip_address", ""))
                lda_channels = lda_cfg.get("channels", "")
                if isinstance(lda_channels, (list, tuple, set)):
                    lda_channels_text = ",".join(map(str, lda_channels))
                else:
                    lda_channels_text = str(lda_channels or "")
                self.lda_channels_edit = LineEdit(self)
                self.lda_channels_edit.setPlaceholderText("channels (1-8, e.g. 1,2,3)")
                self.lda_channels_edit.setText(lda_channels_text)
                lda_box.addWidget(QLabel("IP address :"))
                lda_box.addWidget(self.lda_ip_edit)
                lda_box.addWidget(QLabel("Channels (1-8):"))
                lda_box.addWidget(self.lda_channels_edit)
                vbox.addWidget(self.lda_group)

                # -------- 通用字段：step --------
                self.rf_step_widget = RfStepSegmentsWidget(self)
                self.rf_step_widget.set_segments_from_config(value.get("step"))
                vbox.addWidget(QLabel("Step:"))
                vbox.addWidget(self.rf_step_widget)

                # ---- 加入表单 & 初始化可见性 ----
                self._register_group(key, group, self._is_dut_key(key))
                self.on_rf_model_changed(self.rf_model_combo.currentText())

                # ---- 注册控件 ----
                self.field_widgets["rf_solution.model"] = self.rf_model_combo
                self.field_widgets["rf_solution.RC4DAT-8G-95.idVendor"] = self.rc4_vendor_edit
                self.field_widgets["rf_solution.RC4DAT-8G-95.idProduct"] = self.rc4_product_edit
                self.field_widgets["rf_solution.RC4DAT-8G-95.ip_address"] = self.rc4_ip_edit
                self.field_widgets["rf_solution.RADIORACK-4-220.ip_address"] = self.rack_ip_edit
                self.field_widgets["rf_solution.LDA-908V-8.ip_address"] = self.lda_ip_edit
                self.field_widgets["rf_solution.LDA-908V-8.channels"] = self.lda_channels_edit
                self.field_widgets["rf_solution.step"] = self.rf_step_widget
                continue  # 跳过后面的通用字段处理
            if key == "debug":
                data = self.config.get("debug", {}) if isinstance(self.config, dict) else {}
                group = QGroupBox("Debug Options")
                vbox = QVBoxLayout(group)

                debug_options = [
                    (
                        "database_mode",
                        "Enable database debug mode",
                        "When enabled, performance tests skip router/RF/corner setup and "
                        "simulate iperf results for database debugging.",
                    ),
                    (
                        "skip_router",
                        "Skip router workflow",
                        "Skip router instantiation, configuration, and Wi-Fi reconnection steps "
                        "during performance tests.",
                    ),
                    (
                        "skip_corner_rf",
                        "Skip corner && RF workflow",
                        "Skip corner turntable and RF attenuator initialization and adjustments.",
                    ),
                ]

                for index, (option_key, label, hint_text) in enumerate(debug_options):
                    checkbox = QCheckBox(label, self)
                    checkbox.setChecked(bool(data.get(option_key)))
                    vbox.addWidget(checkbox)
                    self.field_widgets[f"debug.{option_key}"] = checkbox
                    if index == 0:
                        self.database_debug_checkbox = checkbox
                    if hint_text:
                        hint_label = QLabel(hint_text)
                        hint_label.setWordWrap(True)
                        hint_label.setObjectName("debugHintLabel")
                        vbox.addWidget(hint_label)

                self._register_group(key, group, self._is_dut_key(key))
                continue
            if key == "rvr":
                group = QGroupBox("RvR Config")  # 外层分组
                vbox = QVBoxLayout(group)
                # Tool 下拉
                self.rvr_tool_combo = ComboBox(self)
                self.rvr_tool_combo.addItems(["iperf", "ixchariot"])
                self.rvr_tool_combo.setCurrentText(value.get("tool", "iperf"))
                self.rvr_tool_combo.currentTextChanged.connect(self.on_rvr_tool_changed)
                vbox.addWidget(QLabel("Data Generator:"))
                vbox.addWidget(self.rvr_tool_combo)

                # ----- iperf 子组 -----
                self.rvr_iperf_group = QWidget()
                iperf_box = QVBoxLayout(self.rvr_iperf_group)

                self.iperf_path_edit = LineEdit(self)
                self.iperf_path_edit.setPlaceholderText("iperf path (DUT)")
                self.iperf_path_edit.setText(value.get("iperf", {}).get("path", ""))
                iperf_box.addWidget(QLabel("Path:"))
                iperf_box.addWidget(self.iperf_path_edit)

                self.iperf_server_edit = LineEdit(self)
                self.iperf_server_edit.setPlaceholderText("iperf -s command")
                self.iperf_server_edit.setText(value.get("iperf", {}).get("server_cmd", ""))
                iperf_box.addWidget(QLabel("Server cmd:"))
                iperf_box.addWidget(self.iperf_server_edit)

                self.iperf_client_edit = LineEdit(self)
                self.iperf_client_edit.setPlaceholderText("iperf -c command")
                self.iperf_client_edit.setText(value.get("iperf", {}).get("client_cmd", ""))
                iperf_box.addWidget(QLabel("Client cmd:"))
                iperf_box.addWidget(self.iperf_client_edit)
                vbox.addWidget(self.rvr_iperf_group)

                # ----- ixchariot 子组 -----
                self.rvr_ix_group = QWidget()
                ix_box = QVBoxLayout(self.rvr_ix_group)
                # CSV 选择框
                vbox.addWidget(QLabel("Select config csv file"))
                self.csv_combo = ComboBox(self)
                self.csv_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                self.csv_combo.setEnabled(False)
                # currentIndexChanged 在选择相同项时不会触发，activated 每次用户点击都会触发
                self.csv_combo.currentIndexChanged.connect(self.on_csv_changed)
                self.csv_combo.activated.connect(self.on_csv_activated)
                vbox.addWidget(self.csv_combo)

                self.ix_path_edit = LineEdit(self)
                self.ix_path_edit.setPlaceholderText("IxChariot path")
                self.ix_path_edit.setText(value.get("ixchariot", {}).get("path", ""))
                ix_box.addWidget(self.ix_path_edit)
                vbox.addWidget(self.rvr_ix_group)

                # ----- 其它通用字段 -----
                self.repeat_combo = LineEdit()
                self.repeat_combo.setText(str(value.get("repeat", 0)))

                vbox.addWidget(QLabel("Repeat:"))
                vbox.addWidget(self.repeat_combo)
                self.rvr_threshold_edit = LineEdit()
                self.rvr_threshold_edit.setPlaceholderText("throughput threshold")
                self.rvr_threshold_edit.setText(str(value.get("throughput_threshold", 0)))

                vbox.addWidget(QLabel("Zero Point Threshold:"))
                vbox.addWidget(self.rvr_threshold_edit)
                # 加入表单
                self._register_group(key, group, self._is_dut_key(key))

                # 字段注册（供启用/禁用和收集参数用）
                self.field_widgets["rvr.tool"] = self.rvr_tool_combo
                self.field_widgets["rvr.iperf.path"] = self.iperf_path_edit
                self.field_widgets["rvr.iperf.server_cmd"] = self.iperf_server_edit
                self.field_widgets["rvr.iperf.client_cmd"] = self.iperf_client_edit
                self.field_widgets["rvr.ixchariot.path"] = self.ix_path_edit
                self.field_widgets["rvr.repeat"] = self.repeat_combo
                self.field_widgets["rvr.throughput_threshold"] = self.rvr_threshold_edit
                # 根据当前 Tool 值隐藏/显示子组
                self.on_rvr_tool_changed(self.rvr_tool_combo.currentText())
                continue  # 跳过默认 LineEdit 处理

                # ---------- 其余简单字段 ----------
            if key == "corner_angle":
                group = QGroupBox("Turntable")
                vbox = QVBoxLayout(group)

                # —— IP 地址 ——
                self.corner_ip_edit = LineEdit(self)
                self.corner_ip_edit.setPlaceholderText("ip_address")
                self.corner_ip_edit.setText(value.get("ip_address", ""))  # 默认值

                # —— 角度步进 ——
                self.corner_step_edit = LineEdit(self)
                self.corner_step_edit.setPlaceholderText("step; such as 0,361")
                self.corner_step_edit.setText(",".join(map(str, value.get("step", []))))

                static_db_value = value.get("static_db", "")
                self.corner_static_db_edit = LineEdit(self)
                self.corner_static_db_edit.setPlaceholderText("static attenuation (dB)")
                self.corner_static_db_edit.setText(
                    "" if static_db_value is None else str(static_db_value)
                )

                target_rssi_value = value.get("target_rssi", "")
                self.corner_target_rssi_edit = LineEdit(self)
                self.corner_target_rssi_edit.setPlaceholderText("target RSSI (dBm)")
                self.corner_target_rssi_edit.setText(
                    "" if target_rssi_value is None else str(target_rssi_value)
                )

                vbox.addWidget(QLabel("IP address:"))
                vbox.addWidget(self.corner_ip_edit)
                vbox.addWidget(QLabel("Step:"))
                vbox.addWidget(self.corner_step_edit)
                vbox.addWidget(QLabel("Static dB:"))
                vbox.addWidget(self.corner_static_db_edit)
                vbox.addWidget(QLabel("Target RSSI:"))
                vbox.addWidget(self.corner_target_rssi_edit)
                self.corner_static_db_edit.textChanged.connect(
                    lambda _text, source="static": self._ensure_corner_inputs_exclusive(source)
                )
                self.corner_target_rssi_edit.textChanged.connect(
                    lambda _text, source="target": self._ensure_corner_inputs_exclusive(source)
                )
                self._ensure_corner_inputs_exclusive(None)

                # 加入表单
                self._register_group(key, group, self._is_dut_key(key))

                # 注册控件（用于启用/禁用、保存回 YAML）
                self.field_widgets["corner_angle.ip_address"] = self.corner_ip_edit
                self.field_widgets["corner_angle.step"] = self.corner_step_edit
                self.field_widgets["corner_angle.static_db"] = self.corner_static_db_edit
                self.field_widgets["corner_angle.target_rssi"] = self.corner_target_rssi_edit
                continue  # 跳过后面的通用处理
            if key == "router":
                group = QGroupBox("Router")
                vbox = QVBoxLayout(group)

                self.router_name_combo = ComboBox(self)
                self.router_name_combo.addItems(router_list.keys())
                self.router_name_combo.setCurrentText(value.get("name", "xiaomiax3000"))
                addr = value.get("address")
                self.router_obj = get_router(self.router_name_combo.currentText(), addr)
                self.router_addr_edit = LineEdit(self)
                self.router_addr_edit.setPlaceholderText("Gateway")
                self.router_addr_edit.setText(self.router_obj.address)
                self.router_addr_edit.textChanged.connect(self.on_router_address_changed)

                vbox.addWidget(QLabel("Model:"))
                vbox.addWidget(self.router_name_combo)
                vbox.addWidget(QLabel("Gateway:"))
                vbox.addWidget(self.router_addr_edit)
                self._register_group(key, group, self._is_dut_key(key))
                # 注册控件
                self.field_widgets["router.name"] = self.router_name_combo
                self.field_widgets["router.address"] = self.router_addr_edit
                self.router_name_combo.currentTextChanged.connect(self.on_router_changed)
                self.on_router_changed(self.router_name_combo.currentText())
                continue  # ← 继续下一顶层 key
            if key == "serial_port":
                group = QGroupBox("Serial Port")
                vbox = QVBoxLayout(group)

                # 开关（True/False 下拉，同一套保存逻辑即可）
                self.serial_enable_combo = ComboBox(self)
                self.serial_enable_combo.addItems(["False", "True"])
                self.serial_enable_combo.setCurrentText(
                    str(value.get("status", False))
                )
                self.serial_enable_combo.currentTextChanged.connect(
                    self.on_serial_enabled_changed
                )
                vbox.addWidget(QLabel("Enable:"))
                vbox.addWidget(self.serial_enable_combo)

                # —— 子参数区 ——（默认隐藏，开关=True 时可见）
                self.serial_cfg_group = QWidget()
                cfg_box = QVBoxLayout(self.serial_cfg_group)

                self.serial_port_edit = LineEdit(self)
                self.serial_port_edit.setPlaceholderText("port (e.g. COM5)")
                self.serial_port_edit.setText(value.get("port", ""))

                self.serial_baud_edit = LineEdit(self)
                self.serial_baud_edit.setPlaceholderText("baud (e.g. 115200)")
                self.serial_baud_edit.setText(str(value.get("baud", "")))

                cfg_box.addWidget(QLabel("Port:"))
                cfg_box.addWidget(self.serial_port_edit)
                cfg_box.addWidget(QLabel("Baud:"))
                cfg_box.addWidget(self.serial_baud_edit)

                vbox.addWidget(self.serial_cfg_group)
                self._register_group(key, group, self._is_dut_key(key))

                # 初始化显隐
                self.on_serial_enabled_changed(self.serial_enable_combo.currentText())

                # 注册控件
                self.field_widgets["serial_port.status"] = self.serial_enable_combo
                self.field_widgets["serial_port.port"] = self.serial_port_edit
                self.field_widgets["serial_port.baud"] = self.serial_baud_edit
                continue
            if key == "csv_path":
                continue
            # ------- 默认处理：创建 LineEdit 保存未覆盖字段 -------
            group = QGroupBox(key)
            vbox = QVBoxLayout(group)
            edit = LineEdit(self)
            edit.setText(str(value) if value is not None else "")
            vbox.addWidget(edit)
            self._register_group(key, group, self._is_dut_key(key))
            self.field_widgets[key] = edit

    def _ensure_corner_inputs_exclusive(self, source: str | None) -> None:
        if not hasattr(self, "corner_static_db_edit") or not hasattr(self, "corner_target_rssi_edit"):
            return
        static_text = self.corner_static_db_edit.text().strip()
        target_text = self.corner_target_rssi_edit.text().strip()
        if not static_text or not target_text:
            return

        if source == "target":
            cleared = self.corner_static_db_edit
            focus_widget = self.corner_target_rssi_edit
        elif source == "static":
            cleared = self.corner_target_rssi_edit
            focus_widget = self.corner_static_db_edit
        else:
            cleared = self.corner_target_rssi_edit
            focus_widget = None

        with QSignalBlocker(cleared):
            cleared.clear()

        self._show_corner_conflict_warning(focus_widget)

    def _show_corner_conflict_warning(self, focus_widget: QWidget | None) -> None:
        if focus_widget is None or not focus_widget.hasFocus():
            return
        message = (
            "Static dB and Target RSSI cannot be configured at the same time. "
            "The other field has been cleared."
        )
        try:
            bar = self._show_info_bar(
                "warning",
                "Configuration Conflict",
                message,
                duration=2600,
            )
            if bar is None:
                raise RuntimeError("InfoBar unavailable")
        except Exception:
            from PyQt5.QtWidgets import QMessageBox

            QMessageBox.warning(self, "Configuration Conflict", message)

    def populate_case_tree(self, root_dir):
        """
        遍历 test 目录，只将 test_ 开头的 .py 文件作为节点加入树结构。
        其它 py 文件不显示。
        """
        from PyQt5.QtGui import QStandardItemModel, QStandardItem
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(['Pls select test case '])  # 可选，设置表头显示

        # 正确设置根节点为 'test' 或实际目录名
        root_item = QStandardItem(os.path.basename(root_dir))
        root_item.setData(root_dir)

        def add_items(parent_item, dir_path):
            for fname in sorted(os.listdir(dir_path)):
                logging.debug("fname %s", fname)
                if fname == '__pycache__' or fname.startswith('.'):
                    continue
                path = os.path.join(dir_path, fname)
                if os.path.isdir(path):
                    dir_item = QStandardItem(fname)
                    dir_item.setData(path)
                    parent_item.appendRow(dir_item)
                    add_items(dir_item, path)
                elif os.path.isfile(path):
                    file_item = QStandardItem(fname)
                    file_item.setData(path)
                    parent_item.appendRow(file_item)

        add_items(root_item, root_dir)
        model.appendRow(root_item)
        self.case_tree.setModel(model)
        # 展开根节点
        self.case_tree.expand(model.index(0, 0))

    def on_case_tree_clicked(self, proxy_idx):
        """
        proxy_idx: 用户在界面点击到的索引（始终是代理模型的）
        """
        model = self.case_tree.model()

        # —— 用源索引只负责取真实文件路径 ——
        source_idx = (
            model.mapToSource(proxy_idx)
            if isinstance(model, QSortFilterProxyModel) else proxy_idx
        )
        path = self.fs_model.filePath(source_idx)
        base = Path(self._get_application_base())
        try:
            display_path = os.path.relpath(path, base)
        except ValueError:
            display_path = path
        logging.debug("on_case_tree_clicked path=%s display=%s", path, display_path)
        logging.debug("on_case_tree_clicked is_performance=%s", self._is_performance_case(path))
        # ---------- 目录：只负责展开/折叠 ----------
        if os.path.isdir(path):
            if self.case_tree.isExpanded(proxy_idx):
                self.case_tree.collapse(proxy_idx)
            else:
                self.case_tree.expand(proxy_idx)
            self.set_fields_editable(set())
            return

        # ---------- 非 test_*.py 直接禁用 ----------
        if not (os.path.isfile(path)
                and os.path.basename(path).startswith("test_")
                and path.endswith(".py")):
            self.set_fields_editable(set())
            return

        normalized_display = Path(display_path).as_posix() if display_path else ""
        self._update_test_case_display(normalized_display)

        # ---------- 有效用例 ----------
        if self._refreshing:
            self._pending_path = path
            return
        self.get_editable_fields(path)

    def _compute_editable_info(self, case_path) -> EditableInfo:
        """根据用例名与路径返回可编辑字段以及相关 UI 使能状态"""
        basename = os.path.basename(case_path)
        logging.debug("testcase name %s", basename)
        logging.debug("_compute_editable_info case_path=%s basename=%s", case_path, basename)
        peak_keys = {
            "rvr",
            "rvr.tool",
            "rvr.iperf.path",
            "rvr.iperf.server_cmd",
            "rvr.iperf.client_cmd",
            "rvr.ixchariot.path",
            "rvr.repeat",
        }
        rvr_keys = peak_keys | {
            "rvr.throughput_threshold",
        }
        info = EditableInfo()
        # 永远让 connect_type 可编辑
        info.fields |= {
            "connect_type.type",
            "connect_type.adb.device",
            "connect_type.telnet.ip",
            "connect_type.telnet.wildcard",
            "connect_type.third_party.enabled",
            "connect_type.third_party.wait_seconds",
            "router.name",
            "router.address",
            "serial_port.status",
            "serial_port.port",
            "serial_port.baud",
            "fpga.product_line",
            "fpga.project",
        }
        if basename == "test_wifi_peak_throughput.py":
            info.fields |= peak_keys
        if self._is_performance_case(case_path):
            info.fields |= rvr_keys
            info.enable_csv = True
            info.enable_rvr_wifi = True
        if "rvo" in basename:
            info.fields |= {
                "corner_angle",
                "corner_angle.ip_address",
                "corner_angle.step",
                "corner_angle.static_db",
                "corner_angle.target_rssi",
            }
        if "rvr" in basename:
            info.fields |= {
                "rf_solution.step",
                "rf_solution.model",
                "rf_solution.RC4DAT-8G-95.idVendor",
                "rf_solution.RC4DAT-8G-95.idProduct",
                "rf_solution.RC4DAT-8G-95.ip_address",
                "rf_solution.RADIORACK-4-220.ip_address",
                "rf_solution.LDA-908V-8.ip_address",
                "rf_solution.LDA-908V-8.channels",
            }
        case_key = self._script_case_key(case_path)
        entry = self._script_groups.get(case_key)
        if entry is not None:
            info.fields |= entry.field_keys
        # 如果你需要所有字段都可编辑，直接 return EditableInfo(set(self.field_widgets.keys()), True, True)
        return info

    def _apply_editable_info(self, info: EditableInfo | None) -> None:
        if info is None:
            fields: set[str] = set()
            enable_csv = False
            enable_rvr_wifi = False
        else:
            fields = set(info.fields)
            enable_csv = info.enable_csv
            enable_rvr_wifi = info.enable_rvr_wifi
        snapshot = EditableInfo(fields=fields, enable_csv=enable_csv, enable_rvr_wifi=enable_rvr_wifi)
        self._last_editable_info = snapshot
        self.set_fields_editable(snapshot.fields)
        self._enable_rvr_wifi = snapshot.enable_rvr_wifi
        if hasattr(self, "csv_combo"):
            if snapshot.enable_csv:
                self.csv_combo.setEnabled(True)
                self._set_selected_csv(self.selected_csv_path, sync_combo=True)
            else:
                self._set_selected_csv(None, sync_combo=True)
                self.csv_combo.setEnabled(False)
        else:
            if not snapshot.enable_csv:
                self._set_selected_csv(None, sync_combo=False)

    def _restore_editable_state(self) -> None:
        self._apply_editable_info(self._last_editable_info)

    def get_editable_fields(self, case_path) -> EditableInfo:
        """选中用例后控制字段可编辑性并返回相关信息"""
        logging.debug("get_editable_fields case_path=%s", case_path)
        if self._refreshing:
            # 极少见：递归进入，直接丢弃
            logging.debug("get_editable_fields: refreshing, return empty")
            return EditableInfo()

        # ---------- 进入刷新 ----------
        self._refreshing = True
        self.case_tree.setEnabled(False)  # 锁定用例树
        self.setUpdatesEnabled(False)  # 暂停全局重绘

        try:
            self._update_script_config_ui(case_path)
            info = self._compute_editable_info(case_path)
            logging.debug("get_editable_fields enable_csv=%s", info.enable_csv)
            if info.enable_csv and not hasattr(self, "csv_combo"):
                info.enable_csv = False
            self._apply_editable_info(info)
            page_keys = self._determine_pages_for_case(case_path, info)
            self._set_available_pages(page_keys)
        finally:
            # ---------- 刷新结束 ----------
            self.setUpdatesEnabled(True)
            self.case_tree.setEnabled(True)
            self._refreshing = False

        main_window = self.window()
        if hasattr(main_window, "setCurrentIndex"):
            logging.debug("get_editable_fields: before switch to case_config_page")
            main_window.setCurrentIndex(main_window.case_config_page)
            logging.debug("get_editable_fields: after switch to case_config_page")
        if not hasattr(self, "csv_combo"):
            logging.debug("csv_combo disabled")
        # 若用户在刷新过程中又点了别的用例，延迟 0 ms 处理它
        if self._pending_path:
            path = self._pending_path
            self._pending_path = None
            QTimer.singleShot(0, lambda: self.get_editable_fields(path))
        return info

    def set_fields_editable(self, editable_fields: set[str]) -> None:
        """批量更新字段的可编辑状态；DUT 区域始终保持可操作"""
        self.setUpdatesEnabled(False)
        try:
            always_enabled_roots = {"debug"}
            for key, widget in self.field_widgets.items():
                root_key = key.split(".", 1)[0]
                if self._is_dut_key(root_key) or root_key in always_enabled_roots:
                    desired = True
                else:
                    desired = key in editable_fields
                if widget.isEnabled() == desired:
                    continue
                with QSignalBlocker(widget):
                    widget.setEnabled(desired)
            if hasattr(self, "third_party_checkbox") and hasattr(self, "third_party_wait_edit"):
                allow_wait = (
                    "connect_type.third_party.enabled" in editable_fields
                    and "connect_type.third_party.wait_seconds" in editable_fields
                )
                self.on_third_party_toggled(self.third_party_checkbox.isChecked(), allow_wait)
            self._refresh_script_section_states()
        finally:
            self.setUpdatesEnabled(True)
            self.update()

    def lock_for_running(self, locked: bool) -> None:
        
        """Enable or disable widgets while a test run is active."""
        self.case_tree.setEnabled(not locked)
        self._run_locked = locked
        self._sync_run_buttons_enabled()
        if locked:
            for w in self.field_widgets.values():
                w.setEnabled(False)
            if hasattr(self, "csv_combo"):
                self.csv_combo.setEnabled(False)
        else:
            self._restore_editable_state()
        if not locked:
            self._update_navigation_state()

    def on_csv_activated(self, index: int) -> None:
        
        """Reload CSV data even if the same entry is activated again."""
        logging.debug("on_csv_activated index=%s", index)
        self.on_csv_changed(index, force=True)

    def on_csv_changed(self, index: int, force: bool = False) -> None:
        
        """Store the selected CSV path and emit a change signal."""
        if index < 0:
            self._set_selected_csv(None, sync_combo=False)
            return
        # 明确使用 UserRole 获取数据，避免在不同 Qt 版本下默认角色不一致
        data = self.csv_combo.itemData(index)
        logging.debug("on_csv_changed index=%s data=%s", index, data)
        new_path = self._normalize_csv_path(data)
        if not force and new_path == self.selected_csv_path:
            return
        self._set_selected_csv(new_path, sync_combo=False)
        logging.debug("selected_csv_path=%s", self.selected_csv_path)
        self.csvFileChanged.emit(self.selected_csv_path or "")

    def on_run(self):
        if not self._validate_first_page():
            self.stack.setCurrentIndex(0)
            return
        self.config = self._load_config()
        self._sync_widgets_to_config()
        logging.info(
            "[on_run] start case=%s csv=%s config=%s",
            self.field_widgets['text_case'].text().strip(),
            self.selected_csv_path,
            self.config,
        )
        base = Path(self._get_application_base())
        case_path = self.config.get("text_case", "")
        abs_case_path = (
            (base / case_path).resolve().as_posix() if case_path else ""
        )
        logging.debug("[on_run] before performance check abs_case_path=%s csv=%s", abs_case_path,
                      self.selected_csv_path)
        # 先将当前用例路径及 CSV 选择写入配置
        logging.debug("[on_run] after performance check abs_case_path=%s csv=%s", abs_case_path, self.selected_csv_path)
        # 若树状视图中选择了有效用例，则覆盖默认路径
        proxy_idx = self.case_tree.currentIndex()
        model = self.case_tree.model()
        src_idx = (
            model.mapToSource(proxy_idx)
            if isinstance(model, QSortFilterProxyModel)
            else proxy_idx
        )
        selected_path = self.fs_model.filePath(src_idx)
        if os.path.isfile(selected_path) and selected_path.endswith(".py"):
            abs_path = Path(selected_path).resolve()
            display_path = os.path.relpath(abs_path, base)
            case_path = Path(display_path).as_posix()

            abs_case_path = abs_path.as_posix()
            self.config["text_case"] = case_path
        # 保存配置
        logging.debug("[on_run] before _save_config")
        self._save_config()
        logging.debug("[on_run] after _save_config")
        try:
            if self._is_performance_case(abs_case_path) and not getattr(self, "selected_csv_path", None):
                try:
                    # 如果你工程里有 InfoBar（QFluentWidgets），用这个更友好
                    bar = self._show_info_bar(
                        "warning",
                        "Hint",
                        "This is a performance test. Please select a CSV file before running.",
                        duration=3000,
                    )
                    if bar is None:
                        raise RuntimeError("InfoBar unavailable")
                except Exception:
                    # 没有 InfoBar 就退化到标准对话框
                    from PyQt5.QtWidgets import QMessageBox
                    QMessageBox.warning(
                        self,
                        "Hint",
                        "This is a performance test.\nPlease select a CSV file before running."
                    )
                return
        except Exception:
            # 兜底避免因为路径解析等异常导致崩溃
            pass

        if os.path.isfile(abs_case_path) and abs_case_path.endswith(".py"):
            try:
                self.on_run_callback(abs_case_path, case_path, self.config)
            except Exception as exc:  # pragma: no cover - 运行回调抛错时记录日志
                logging.exception("Run callback failed: %s", exc)
            else:
                self._reset_wizard_after_run()
        else:
            self._show_info_bar(
                "warning",
                "Hint",
                "Pls select a test case before test",
                duration=1800,
            )
