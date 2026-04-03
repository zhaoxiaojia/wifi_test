"""Schema-driven UI builder helpers for config views.

This module reads UI schema YAML files from ``src/ui/model/config``
and constructs Qt widgets (group boxes + field controls) for a given
Config panel. It is used to render Basic / Performance / Stability
panels from YAML.
"""

from __future__ import annotations

import logging
import time
import re
from dataclasses import dataclass
from operator import truediv
from pathlib import Path
from typing import Any, Dict, Mapping

from PyQt5.QtWidgets import (
    QCheckBox, QGroupBox, QFormLayout, QSpinBox, QWidget, QLabel,
    QHBoxLayout, QVBoxLayout, QGridLayout, QFrame, QLayout, QSizePolicy, QSplitter, QSpacerItem, QComboBox,
)
from qfluentwidgets import ComboBox, LineEdit
from PyQt5.QtCore import Qt

from src.util.constants import (
    RF_MODEL_RS232,
    get_model_config_base,
    get_model_toolbar_base,
)
from src.ui.model.options import get_field_choices
from src.ui.view.common import RfStepSegmentsWidget
from PyQt5.QtGui import QFont
import yaml


@dataclass
class FieldSpec:
    key: str
    widget: str
    label: str
    placeholder: str | None = None
    minimum: int | None = None
    maximum: int | None = None
    choices: list[str] | None = None
    group: str | None = None  # 新增：字段分组标识（仅新布局使用）


def _load_yaml_schema(filename: str, *, base: Path | None = None) -> Dict[str, Any]:
    base_dir = base if base is not None else get_model_config_base()
    path = base_dir / filename
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return {}
    try:
        data = yaml.safe_load(text) or {}
    except Exception:
        return {}
    return data


def load_ui_schema(section: str) -> Dict[str, Any]:
    """Load the UI schema for the given high-level section."""
    mapping = {
        "basic": "config_basic_ui.yaml",
        "dut": "config_basic_ui.yaml",
        "execution": "config_performance_ui.yaml",
        "stability": "config_stability_ui.yaml",
        "compatibility": "config_compatibility_ui.yaml",
    }
    if section == "toolbar":
        return _load_yaml_schema("config_toolbar_ui.yaml", base=get_model_toolbar_base())
    filename = mapping.get(section)
    if not filename:
        return {}
    return _load_yaml_schema(filename)


def build_inline_fields_from_schema(
        page: Any,
        config: Mapping[str, Any],
        ui_schema: Mapping[str, Any],
        panel_key: str,
        section_id: str,
        *,
        parent: QWidget,
) -> list[tuple[str, QWidget, str]]:
    """Build a flat list of fields for inline layouts (e.g. toolbar rows).

    Returns a list of (key, widget, label_text).
    """
    panels = ui_schema.get("panels") or {}
    panel_spec = panels.get(panel_key) or {}
    sections = panel_spec.get("sections") or []
    for section in sections:
        if str(section.get("id") or "") != section_id:
            continue
        fields = section.get("fields") or []
        built: list[tuple[str, QWidget, str]] = []
        for field in fields:
            key = str(field.get("key") or "").strip()
            if not key:
                continue
            widget_type = str(field.get("widget") or "line_edit")
            label_text = str(field.get("label") or key)
            placeholder = field.get("placeholder")
            minimum = field.get("minimum")
            maximum = field.get("maximum")
            choices = field.get("choices") or None
            group = field.get("group")  # 保留group字段（新布局使用）
            spec = FieldSpec(
                key=key,
                widget=widget_type,
                label=label_text,
                placeholder=placeholder,
                minimum=int(minimum) if isinstance(minimum, int) else None,
                maximum=int(maximum) if isinstance(maximum, int) else None,
                choices=[str(c) for c in choices] if isinstance(choices, list) else None,
                group=group,
            )
            value = _get_nested(config, key)
            widget = _create_widget(page, spec, value)
            built.append((key, widget, label_text))
        return built
    return []


def _get_nested(config: Mapping[str, Any], dotted_key: str) -> Any:
    """Return nested value from config using dotted key (best-effort)."""
    parts = dotted_key.split(".")
    current: Any = config
    for part in parts:
        if not isinstance(current, Mapping):
            return None
        current = current.get(part)
    return current


def _normalize_control_token(value: str) -> str:
    """Normalise a token for use in config_controls IDs."""
    text = (str(value) or "").strip().lower()
    text = re.sub(r"[^0-9a-z]+", "_", text)
    return text.strip("_") or "x"


def _widget_suffix(widget: QWidget) -> str:
    """Return a short type suffix for ``widget`` (text/combo/check/spin/...)."""
    if isinstance(widget, ComboBox):
        return "combo"
    if isinstance(widget, LineEdit):
        return "text"
    if isinstance(widget, QCheckBox):
        return "check"
    if isinstance(widget, QSpinBox):
        return "spin"
    return "widget"


def _register_config_control(
        page: Any,
        panel: str,
        group: str,
        field: str,
        widget: QWidget,
) -> None:
    """Store a logical identifier for a Config page control on ``page``.

    The identifier follows the pattern ``config_panel_group_field_type``
    where each token is normalised to lower case and uses underscores
    instead of spaces or punctuation. The mapping is stored on
    ``page.config_controls`` when present and ignored otherwise.
    """
    controls = page.config_controls
    panel_token = _normalize_control_token(panel or "main")
    group_token = _normalize_control_token(group or panel or "group")
    field_token = _normalize_control_token(field or group or "field")
    suffix = _widget_suffix(widget)
    control_id = f"config_{panel_token}_{group_token}_{field_token}_{suffix}"
    controls[control_id] = widget


def _create_widget(page: Any, spec: FieldSpec, value: Any) -> QWidget:
    """Create a Qt widget for a single field according to FieldSpec."""
    wtype = spec.widget

    if wtype == "checkbox":
        cb = QCheckBox(spec.label, page)
        cb.setChecked(bool(value))
        return cb

    if wtype in {"int", "spin"}:
        # For third-party wait seconds we use a LineEdit to match other edits.
        if spec.key == "connect_type.third_party.wait_seconds":
            edit = LineEdit(page)
            if spec.placeholder:
                edit.setPlaceholderText(spec.placeholder)
            if value not in (None, ""):
                edit.setText(str(value))
            return edit
        spin = QSpinBox(page)
        if spec.minimum is not None:
            spin.setMinimum(spec.minimum)
        if spec.maximum is not None:
            spin.setMaximum(spec.maximum)
        spin.setValue(int(value) if value is not None else 0)
        return spin

    if wtype == "read_only_text":
        # Read-only text display, used for "Selected Test Case" groups.
        edit = LineEdit(page)
        edit.setReadOnly(True)
        # Also disable the control so it appears greyed-out and
        # clearly non-editable; the value is driven by the case tree.
        edit.setEnabled(False)
        if value not in (None, ""):
            edit.setText(str(value))
        return edit

    if wtype == "custom":
        # RF Solution step editor uses a dedicated composite widget that
        # manages start/stop/step segments with Add/Del controls.
        if spec.key == "rf_solution.step":
            widget = RfStepSegmentsWidget(page)
            widget.load_from_raw(value)
            return widget

    # Default: line edit or combo box.
    if wtype == "line_edit":
        edit = LineEdit(page)
        if spec.placeholder:
            edit.setPlaceholderText(spec.placeholder)
        if value not in (None, ""):
            edit.setText(str(value))
        edit.show()
        return edit

    if wtype == "combo_box":
        combo = ComboBox(page)
        # Prefer explicit choices from the schema; otherwise fall back to
        # centralised model options keyed by the field name.
        choices = spec.choices or get_field_choices(spec.key)
        for choice in choices or []:
            combo.addItem(str(choice), str(choice))
        if value not in (None, ""):
            text = str(value)
            # Prefer userData matches when available; fall back to a
            # text-based lookup so that persisted values such as
            # "Android 11" or "RS232Board5" are restored correctly even
            # when ComboBox.findData does not recognise the string.
            idx = combo.findData(text)
            if idx < 0:
                idx = combo.findText(text)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            elif combo.count():
                combo.setCurrentIndex(0)
        return combo

    # Fallback: simple line edit.
    edit = LineEdit(page)
    if spec.placeholder:
        edit.setPlaceholderText(spec.placeholder)
    if value not in (None, ""):
        edit.setText(str(value))
    return edit


# ========== 新增布局辅助函数（仅当YAML指定layout时启用） ==========
def _create_layout_for_section(layout_type: str, parent=None) -> QLayout:
    """根据布局类型创建对应的布局管理器"""
    if layout_type == "horizontal":
        layout = QHBoxLayout(parent)
        layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)  # 关键：设置左对齐
        return layout
    elif layout_type == "grid":
        layout = QGridLayout(parent)
        layout.setSpacing(15)
        layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)  # 关键：设置左对齐
        return layout
    elif layout_type == "vertical" or layout_type is None:
        layout = QVBoxLayout(parent)
        layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)  # 关键：设置左对齐
        return layout
    else:  # 默认vertical
        layout = QVBoxLayout(parent)
        layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)  # 关键：设置左对齐
        return layout


def _add_single_field_to_layout(page, config, field, layout, section_id, panel_key, page_ref, is_right_panel=False):
    """添加单个字段到布局，并处理注册逻辑（与原逻辑完全一致）"""
    key = str(field.get("key") or "").strip()
    if not key:
        return
    widget_type = str(field.get("widget") or "line_edit")
    label_text = str(field.get("label") or key)
    placeholder = field.get("placeholder")
    minimum = field.get("minimum")
    maximum = field.get("maximum")
    choices = field.get("choices") or None
    group_attr = field.get("group")  # 保留group属性（新布局使用）

    # 特殊处理：RF Solution model
    if not choices and key == "rf_solution.model":
        rf_cfg = config.get("rf_solution")
        derived = [
            str(model_key)
            for model_key in rf_cfg.keys()
            if model_key not in {"model", "step"}
        ]
        if RF_MODEL_RS232 not in derived:
            derived.append(RF_MODEL_RS232)
        if derived:
            choices = sorted(derived)

    spec = FieldSpec(
        key=key,
        widget=widget_type,
        label=label_text,
        placeholder=placeholder,
        minimum=int(minimum) if isinstance(minimum, int) else None,
        maximum=int(maximum) if isinstance(maximum, int) else None,
        choices=[str(c) for c in choices] if isinstance(choices, list) else None,
        group=group_attr,
    )
    value = _get_nested(config, key)
    widget = _create_widget(page, spec, value)
    # === 【关键修复】注册控件！===
    logical_key = key
    # For Stability panel: special handling for "Selected Test Case"
    if not (panel_key == "stability" and logical_key == "text_case"):
        if hasattr(page, 'field_widgets'):
            page.field_widgets[logical_key] = widget
    if panel_key == "stability":
        stability_key = f"stability.{logical_key}"
        if hasattr(page, 'field_widgets'):
            page.field_widgets[stability_key] = widget

    # Maintain config_controls mapping
    group_name = section_id or key.split(".")[0]
    field_name = key.split(".")[-1]
    _register_config_control(page_ref, panel_key, group_name, field_name, widget)

    # 添加到布局（关键修改：实现标签左对齐，控件右对齐）
    # 确保 widget 不为 None
    if widget is None:
        return

    # 添加到布局（关键修改：实现标签左对齐，控件右对齐）
    if isinstance(widget, QCheckBox):
        layout.addWidget(widget)
    else:
        field_layout = QHBoxLayout()  # ← 直接使用 QHBoxLayout，不包裹在 field_container 中
        field_layout.setContentsMargins(0, 0, 0, 0)
        spacing = 80 if is_right_panel else 25
        field_layout.setSpacing(spacing)

        # === 1. 标签：右对齐，固定宽度 ===
        label = QLabel(label_text)
        label.setAlignment(Qt.AlignLeft  | Qt.AlignVCenter)  # ← 标签右对齐
        label.setMinimumWidth(150)
        label.setMaximumWidth(150)
        field_layout.addWidget(label)

        # === 2. 控件：设置尺寸策略，允许拉伸填充剩余空间 ===
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        # === 3. 根据控件类型设置对齐（只有支持 setAlignment 的控件才调用）===
        if hasattr(widget, 'setAlignment'):
            #widget.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            widget.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        field_layout.addWidget(widget)

        # === 4. 添加布局到主布局 ===
        layout.addLayout(field_layout)
    # ========== 以下注册逻辑与原build_groups_from_schema完全一致 ==========
    # Register widget in page.field_widgets
    logical_key = key
    # For Stability panel: special handling for "Selected Test Case"
    if not (panel_key == "stability" and logical_key == "text_case"):
        if hasattr(page, 'field_widgets'):
            page.field_widgets[logical_key] = widget
    if panel_key == "stability":
        stability_key = f"stability.{logical_key}"
        if hasattr(page, 'field_widgets'):
            page.field_widgets[stability_key] = widget

    # Maintain config_controls mapping
    group_name = section_id or key.split(".")[0]
    field_name = key.split(".")[-1]
    _register_config_control(page_ref, panel_key, group_name, field_name, widget)


def _add_fields_to_two_column_layout(page, config, fields, layout, section_id, panel_key, page_ref):
    """将字段添加到2列网格布局（自动换行），并确保左对齐"""
    grid_layout = QGridLayout()
    grid_layout.setSpacing(10)
    grid_layout.setColumnStretch(0, 1)  # 左列可拉伸
    grid_layout.setColumnStretch(1, 1)  # 右列可拉伸
    grid_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

    row = 0
    col = 0

    for field in fields:
        key = str(field.get("key") or "").strip()
        if not key:
            continue

        # 创建字段（复用原有逻辑）
        widget_type = str(field.get("widget") or "line_edit")
        label_text = str(field.get("label") or key)
        placeholder = field.get("placeholder")
        minimum = field.get("minimum")
        maximum = field.get("maximum")
        choices = field.get("choices") or None
        group_attr = field.get("group")

        # 特殊处理：RF Solution model
        if not choices and key == "rf_solution.model":
            rf_cfg = config.get("rf_solution")
            derived = [
                str(model_key)
                for model_key in rf_cfg.keys()
                if model_key not in {"model", "step"}
            ]
            if RF_MODEL_RS232 not in derived:
                derived.append(RF_MODEL_RS232)
            if derived:
                choices = sorted(derived)

        spec = FieldSpec(
            key=key,
            widget=widget_type,
            label=label_text,
            placeholder=placeholder,
            minimum=int(minimum) if isinstance(minimum, int) else None,
            maximum=int(maximum) if isinstance(maximum, int) else None,
            choices=[str(c) for c in choices] if isinstance(choices, list) else None,
            group=group_attr,
        )

        value = _get_nested(config, key)
        widget = _create_widget(page, spec, value)

        # === 【关键修复】注册控件！===
        logical_key = key
        # For Stability panel: special handling for "Selected Test Case"
        if not (panel_key == "stability" and logical_key == "text_case"):
            if hasattr(page, 'field_widgets'):
                page.field_widgets[logical_key] = widget
        if panel_key == "stability":
            stability_key = f"stability.{logical_key}"
            if hasattr(page, 'field_widgets'):
                page.field_widgets[stability_key] = widget

        # Maintain config_controls mapping
        group_name = section_id or key.split(".")[0]
        field_name = key.split(".")[-1]
        _register_config_control(page_ref, panel_key, group_name, field_name, widget)
        # === 修复结束 ===

        # 创建字段容器（标签+控件水平布局）
        field_container = QWidget()
        field_container.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        field_container.setFixedWidth(360)  # 限制宽度
        field_container.setStyleSheet("margin: 0; padding: 0;")
        field_container.setStyleSheet("""
            padding: 0;
            margin: 0;
        """)
        field_layout = QHBoxLayout(field_container)
        field_layout.setContentsMargins(0, 0, 0, 0)
        field_layout.setSpacing(30)
        field_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        # 添加标签（复选框不需要单独标签）
        if not (isinstance(widget, QCheckBox) and spec.widget == "checkbox"):
            label = QLabel(label_text)
            label.setMinimumWidth(120)  # ← 【关键】统一标签宽度
            label.setMaximumWidth(120)  # 防止过长
            widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            widget.setAlignment(Qt.AlignRight  | Qt.AlignVCenter)
            field_layout.addWidget(label)

        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        widget.setAlignment(Qt.AlignRight  | Qt.AlignVCenter)  # 控件内容左对齐且垂直居中
        field_layout.addWidget(widget)

        # 添加控件
        if isinstance(widget, (ComboBox, LineEdit, QSpinBox)):
            widget.setFixedWidth(180)  # ← 【关键】统一控件宽度
        elif isinstance(widget, QCheckBox):
            widget.setChecked(value is True)  # 处理 checkbox 值
        field_layout.addWidget(widget)
        field_layout.addStretch()

        # 添加到网格
        grid_layout.addWidget(field_container, row, col)

        # 换行逻辑
        col += 1
        if col >= 2:  # 超过2列就换行
            col = 0
            row += 1

    # 将网格布局添加到主布局
    container = QWidget()
    container.setLayout(grid_layout)
    layout.addWidget(container)

def _add_fields_to_layout(page, config, fields, layout, section_id, panel_key, page_ref, is_right_panel=False):
    """将字段添加到指定布局，支持字段分组（仅新布局使用）"""

    # 按group属性分组字段
    field_groups = {}
    for field in fields:
        group_key = field.get("group", "default")
        if group_key not in field_groups:
            field_groups[group_key] = []
        field_groups[group_key].append(field)

    # 处理每个分组
    for group_key, group_fields in field_groups.items():
        if group_key == "default" and len(field_groups) == 1:
            for field in group_fields:
                _add_single_field_to_layout(page, config, field, layout, section_id, panel_key, page_ref, is_right_panel=is_right_panel)
        else:
            group_widget = QWidget()
            # 关键：使用水平布局 + 显式左对齐
            group_layout = QHBoxLayout(group_widget)
            group_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)  # 左对齐
            group_layout.setContentsMargins(0, 0, 0, 0)
            group_layout.setSpacing(10)

            # === 关键修改：将字段按顺序放入水平布局 ===
            for field in group_fields:
                _add_single_field_to_layout(page, config, field, group_layout, section_id, panel_key, page_ref)

            # === 关键修改：添加弹性空间，防止撑满 ===
            group_layout.addStretch()

            #layout.addWidget(group_widget)

# ===========================================================================

def get_underlined_text(text):
    """如果文本是特定关键词，返回带下划线的HTML文本，否则返回原文本"""
    underlined_keywords = ["Coex Mode", "Lab"]  # 把需要加下划线的词都放这里
    if text in underlined_keywords:
        return f"<u>{text}</u>"
    return text

def build_groups_from_schema(
        page: Any,
        config: Mapping[str, Any],
        ui_schema: Mapping[str, Any],
        panel_key: str,
        *,
        parent: QWidget | None = None,
) -> None:
    """Build all sections for ``panel_key`` described in ``ui_schema``.
    支持两种模式：
    1. 传统模式（默认）：当YAML未指定layout时，使用原有QFormLayout逻辑
    2. 增强模式：当YAML指定layout/grid等属性时，启用新布局引擎
    """

    panels = ui_schema.get("panels") or {}
    panel_spec = panels.get(panel_key) or {}
    sections = panel_spec.get("sections") or []

    # ========== 检查是否启用新布局引擎 ==========
    layout_type = panel_spec.get("layout")
    if layout_type is not None:
        # ====== 启用新布局逻辑：左右分栏 (3:7) ======
        if parent is None:
            return
        parent_layout = parent.layout() if parent.layout() is not None else QVBoxLayout(parent)
        parent.setLayout(parent_layout)

        # 清空现有内容
        while parent_layout.count() > 0:
            item = parent_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()  # ← 关键：安排删除
            else:
                # 处理嵌套 layout
                sub_layout = item.layout()
                if sub_layout is not None:
                    while sub_layout.count():
                        sub_item = sub_layout.takeAt(0)
                        sub_widget = sub_item.widget()
                        if sub_widget is not None:
                            sub_widget.deleteLater()

        # 创建带边框的主容器
        main_container = QWidget(parent)
        main_layout = QHBoxLayout(main_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(30)

        left_panel = QWidget()
        right_panel = QWidget()
        # 为左右 panel 分别设置样式
        left_panel.setObjectName("LeftPanel")
        right_panel.setObjectName("RightPanel")

        left_panel.setStyleSheet("""
            #LeftPanel {
                border: 1px solid rgba(255, 255, 255, 0.6);
                border-radius: 4px;
                background-color: transparent;
                padding: 16px 8px 8px 8px;
            }
        """)

        right_panel.setStyleSheet("""
            #RightPanel {
                border: 1px solid rgba(255, 255, 255, 0.6);
                border-radius: 4px;
                background-color: transparent;
                padding: 16px 8px 8px 8px;
            }
        """)

        # === 关键修复：设置尺寸策略，允许垂直拉伸 ===
        left_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        right_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        # === 修复结束 ===

        left_layout = QVBoxLayout(left_panel)
        right_layout = QVBoxLayout(right_panel)
        # 设置内边距和间距
        for layout in [left_layout, right_layout]:
            layout.setContentsMargins(0, 0, 0, 0)
        if layout == left_layout:
            layout.setSpacing(16) #右面板向下拉升12
        if layout == right_layout:
            layout.setSpacing(12) #右面板向下拉升28


        # 添加到主布局
        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel)
        main_layout.setStretch(0, 3)  # 左侧 30%
        main_layout.setStretch(1, 7)  # 右侧 70%

        # 添加主容器到 parent
        parent_layout.addWidget(main_container, alignment=Qt.AlignTop)
        main_layout.setAlignment(Qt.AlignTop)

        # 分配 sections 到左右面板
        left_sections = []
        right_sections = []
        for section in sections:
            section_id = str(section.get("id") or "")
            group_label = str(section.get("label") or section_id or "Section").lower()
            LEFT_SECTION_IDS = {
                "system", "project",  # Basic 面板
                "text_case", "csv_path", "mode",  "throughput", "debug" # Performance 面板
            }
            if section_id in LEFT_SECTION_IDS:
                left_sections.append(section)
            else:
                right_sections.append(section)

        # 辅助函数：创建单个 GroupBox
        def _create_group_widget(section, parent_widget, page, config, panel_key, is_right_panel=False):
            section_id = str(section.get("id") or "")
            group_label = section.get("label")
            if group_label is None:
                group_label = section_id or "Section"
            else:
                group_label = str(group_label)

            group_box = QGroupBox(group_label, parent_widget)
            group_box.setFlat(False)
            group_box.setAlignment(Qt.AlignTop)
            parent_bg_color = parent_widget.palette().color(parent_widget.backgroundRole()).name()
            group_box.setStyleSheet("""
            QGroupBox {
                border: none;
                margin-top: 12px;
                font-weight: bold;
                color: rgba(255, 255, 255, 0.85);
                font-weight: bold; /* 加粗 */
                text-decoration: underline; /* 下划线  #202020*/
                background-color: transparent;
                padding-top: 0;
                margin-bottom: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
                color: rgba(255, 255, 255, 0.9);
                margin-bottom: 4px;
            }
            """)

            fields = section.get("fields") or []

            # --- 关键修改：为 rf_solution 使用 QFormLayout ---
            if section_id == "rf_solution" or section_id == "mode" or section_id == "Turntable":
                inner_layout = QFormLayout(group_box)
                # inner_layout.setLabelAlignment(Qt.AlignRight)
                inner_layout.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
                #调整UI下左右对齐，但有个问题是groupbox内部的间隔不太一致
                #inner_layout.setFormAlignment(Qt.AlignJustify | Qt.AlignTop)
                inner_layout.setFormAlignment(Qt.AlignTop)
                inner_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                #inner_layout.setFieldGrowthPolicy(QFormLayout.FieldsStayAtSizeHint)
                inner_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
                inner_layout.setVerticalSpacing(8)
                if section_id == "rf_solution":
                    # rf_solution 是第一个，保留所有边距
                    inner_layout.setContentsMargins(16, 6, 16, 6)
                elif section_id == "Turntable":
                    # Turntable 紧跟在 rf_solution 后面，移除顶部边距以减小间距
                    inner_layout.setContentsMargins(16, 6, 16, 6)  # 上边距设为 0
                    #inner_layout.setHorizontalSpacing(120)
                else:
                    # 其他情况保持默认
                    inner_layout.setContentsMargins(16, 6, 16, 6)

                for i, field in enumerate(fields):
                    key = str(field.get("key") or "").strip()
                    if not key:
                        continue

                    widget_type = str(field.get("widget") or "line_edit")
                    label_text = str(field.get("label") or key)
                    placeholder = field.get("placeholder")
                    minimum = field.get("minimum")
                    maximum = field.get("maximum")
                    choices = field.get("choices") or None
                    group_attr = field.get("group")


                    # 特殊处理：RF Solution model
                    if not choices and key == "rf_solution.model":
                        inner_layout.setHorizontalSpacing(105)
                        rf_cfg = config.get("rf_solution")
                        derived = [
                            str(model_key) for model_key in rf_cfg.keys()
                            if model_key not in {"model", "step"}
                        ]
                        if RF_MODEL_RS232 not in derived:
                            derived.append(RF_MODEL_RS232)
                        if derived:
                            choices = sorted(derived)
                    elif section_id == "Turntable":
                        inner_layout.setHorizontalSpacing(114)
                    else:
                        inner_layout.setHorizontalSpacing(93)

                    spec = FieldSpec(
                        key=key,
                        widget=widget_type,
                        label=label_text,
                        placeholder=placeholder,
                        minimum=int(minimum) if isinstance(minimum, int) else None,
                        maximum=int(maximum) if isinstance(maximum, int) else None,
                        choices=[str(c) for c in choices] if isinstance(choices, list) else None,
                        group=group_attr,
                    )

                    value = _get_nested(config, key)

                    widget = _create_widget(page, spec, value)
                    if widget is None:
                        continue

                    # === 【关键修复】注册控件到 page.field_widgets！===
                    logical_key = key

                    # For Stability panel: special handling for "Selected Test Case"
                    should_register_normal = not (panel_key == "stability" and logical_key == "text_case")
                    if should_register_normal:
                        if hasattr(page, 'field_widgets'):
                            page.field_widgets[logical_key] = widget
                    if panel_key == "stability":
                        stability_key = f"stability.{logical_key}"
                        if hasattr(page, 'field_widgets'):
                            page.field_widgets[stability_key] = widget

                    # Maintain config_controls mapping
                    group_name = section_id or key.split(".")[0]
                    field_name = key.split(".")[-1]
                    _register_config_control(page, panel_key, group_name, field_name, widget)
                    # === 【关键修复结束】===

                    # --- 添加到 QFormLayout ---
                    if widget_type == "checkbox":
                        inner_layout.addRow(widget)
                    else:
                        if hasattr(widget, 'setSizePolicy'):
                            sp = widget.sizePolicy()
                            sp.setHorizontalPolicy(QSizePolicy.Expanding)
                            #sp.setVerticalPolicy(QSizePolicy.Preferred)
                            widget.setSizePolicy(sp)

                        label = QLabel(label_text)
                        if label_text in ["Coex Mode", "Lab"]:
                            # 使用样式表强制加下划线
                            current_font = label.font()
                            underline_font = QFont(current_font)
                            underline_font.setUnderline(True)

                        if  key == "rf_solution.step":
                            # 只添加 Widget，不添加 Label
                            #inner_layout.addRow(widget)
                            placeholder_label = QLabel("")
                            placeholder_label.setFixedWidth(100)  # 可选：固定宽度以保持对齐，或者不设置让它自动匹配其他Label的宽度
                            inner_layout.addRow(placeholder_label, widget)
                        else:
                            widget.setMinimumWidth(200)
                            inner_layout.addRow(label_text, widget)

                # --- Final State Check ---
                if hasattr(page, 'field_widgets'):
                    rf_keys_in_map = [k for k in page.field_widgets.keys() if k.startswith('rf_solution.')]
                    for k in sorted(rf_keys_in_map):
                        w = page.field_widgets[k]

            else:
                # --- 其他 section 使用原有的增强模式布局逻辑 ---
                section_layout_type = section.get("layout", "vertical")
                inner_layout = _create_layout_for_section(section_layout_type, group_box)
                inner_layout.setSpacing(10)
                inner_layout.setContentsMargins(16, 10, 16, 10)

                if section_layout_type == "two_column":
                    _add_fields_to_two_column_layout(page, config, fields, inner_layout, section_id, panel_key, page)
                else:
                    _add_fields_to_layout(page, config, fields, inner_layout, section_id, panel_key, page,
                                          is_right_panel)

            inner_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            #group_box.setStyleSheet("")
            return group_box


        # 创建左侧 GroupBox
        first_left = True
        for section in left_sections:
            widget = _create_group_widget(section, left_panel, page, config, panel_key, is_right_panel=False)
            if first_left:
                left_layout.addSpacing(12)  # ← 关键：在第一个 group 前加间距
                first_left = False
            left_layout.addWidget(widget, alignment=Qt.AlignTop)
        left_layout.addStretch()  # ← 确保左侧内容顶部对齐

        is_basic_panel = panel_key in {"basic", "dut"}
        target = page._basic_groups if is_basic_panel else page._other_groups
        # 创建右侧 GroupBox
        for i, section in enumerate(right_sections):
            widget = _create_group_widget(section, right_panel, page, config, panel_key, is_right_panel=True)
            if i == 0:
                right_layout.addSpacing(12)  # ← 关键：在第一个 group 前加间距
                first_right = False
            right_layout.addWidget(widget, alignment=Qt.AlignTop)
            if i == len(right_sections) - 1:
                #调整不同面板UI(Basic/Performanc等)向下拉升的长度，
                if is_basic_panel:
                    right_layout.addSpacing(200)
                else:
                    right_layout.addSpacing(0)
                    print(f"[DEBUG] {section}{section_id} sizeHint: {widget.sizeHint()}")
                    print(f"[DEBUG] {section}{section_id} minSize: {widget.minimumSize()}")

            #right_layout.addStretch()  # ← 确保右侧内容顶部对齐
        for section in sections:
            section_id = str(section.get("id") or "")
            target[section_id] = None

        if hasattr(parent, 'request_rebalance'):
            parent.request_rebalance()
        return

    # ===========================================================================
    # ===== 传统模式：使用原有QFormLayout逻辑 =====
    if parent is None:
        return

    # 清理现有组（通过 ConfigGroupPanel 的 API）
    if hasattr(parent, 'clear_groups'):
        parent.clear_groups()
    else:
        # 回退：手动清理子控件（但不删除 layout）
        for child in parent.findChildren(QGroupBox):
            if hasattr(child, '_is_config_group') or 'ConfigGroup' in child.__class__.__name__:
                child.deleteLater()

    for section_idx, section in enumerate(sections):
        section_id = section.get("id", f"section_{section_idx}")
        section_label = section.get("label", "")

        # 创建组框
        #group_box = QGroupBox(section_label)
        group_parent = parent if parent is not None else page
        group_box = QGroupBox(section_label, group_parent)
        group_layout = QFormLayout(group_box)
        group_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        group_layout.setLabelAlignment(Qt.AlignRight)
        group_layout.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        group_layout.setHorizontalSpacing(24)
        group_layout.setVerticalSpacing(16)
        group_layout.setContentsMargins(10, 20, 10, 10)

        fields = section.get("fields") or []

        for field_idx, field in enumerate(fields):
            key = str(field.get("key") or "").strip()
            if not key:
                continue
            widget_type = str(field.get("widget") or "line_edit")
            label_text = str(field.get("label") or key)
            placeholder = field.get("placeholder")
            minimum = field.get("minimum")
            maximum = field.get("maximum")
            choices = field.get("choices") or None
            group_attr = field.get("group")

            # 特殊处理：RF Solution model
            if not choices and key == "rf_solution.model":
                rf_cfg = config.get("rf_solution")
                if isinstance(rf_cfg, dict):
                    derived = [
                        str(model_key)
                        for model_key in rf_cfg.keys()
                        if model_key not in {"model", "step"}
                    ]
                    if RF_MODEL_RS232 not in derived:
                        derived.append(RF_MODEL_RS232)
                    if derived:
                        choices = sorted(derived)

            spec = FieldSpec(
                key=key,
                widget=widget_type,
                label=label_text,
                placeholder=placeholder,
                minimum=int(minimum) if isinstance(minimum, int) else None,
                maximum=int(maximum) if isinstance(maximum, int) else None,
                choices=[str(c) for c in choices] if isinstance(choices, list) else None,
                group=group_attr,
            )
            value = _get_nested(config, key)
            widget = _create_widget(page, spec, value)

            # Add to layout.
            if isinstance(widget, QCheckBox) and spec.widget == "checkbox":
                group_layout.addRow(widget)
            else:
                group_layout.addRow(label_text, widget)

            # Register widget in page.field_widgets.
            logical_key = key
            if not (panel_key == "stability" and logical_key == "text_case"):
                if hasattr(page, 'field_widgets'):
                    page.field_widgets[logical_key] = widget
            if panel_key == "stability":
                stability_key = f"stability.{logical_key}"
                if hasattr(page, 'field_widgets'):
                    page.field_widgets[stability_key] = widget

            group_name = section.get("id") or key.split(".")[0]
            field_name = key.split(".")[-1]
            _register_config_control(page, panel_key, group_name, field_name, widget)

            # # Add to group layout
            # if widget_type == "checkbox":
            #     group_layout.addRow(widget)
            # else:
            #     group_layout.addRow(label_text, widget)


        # if widget_type == "checkbox":
        #     group_layout.addRow(widget)
        # else:
        #     group_layout.addRow(label_text, widget)
        if parent is not None:
            parent.add_group(group_box, defer=False)  # defer=False 立即显示
        else:
            # 如果没有 parent，则直接添加到 page（模仿 default 行为）
            page.layout().addWidget(group_box)
        # 记录组信息
        is_basic_panel = panel_key in {"basic", "dut"}
        target = page._basic_groups if is_basic_panel else page._other_groups
        section_id = str(section.get("id") or "")
        target[section_id] = group_box
        # for section in sections:
        #     section_id = str(section.get("id") or "")
        #     target[section_id] = None

    if hasattr(parent, 'request_rebalance'):
        parent.request_rebalance()

# ===== 恢复GroupBox原始样式 =====
def apply_original_groupbox_style(widget):
    """应用原始GroupBox样式"""
    widget.setStyleSheet("""
        QGroupBox {
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 4px;
            margin-top: 1ex;
            font-weight: bold;
            color: white;
            background-color: transparent;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px;
            color: white;
        }
    """)



__all__ = ["load_ui_schema", "build_groups_from_schema", "build_inline_fields_from_schema"]
