"""UI action helpers for the Config page.

These functions live in the *view* layer and encapsulate pure UI behaviour
for CaseConfigPage and ConfigView (show/hide groups, enable/disable fields,
update step indicators, etc.).  Controllers should delegate visual tweaks
to these helpers instead of hard-coding widget manipulation.
"""

from __future__ import annotations

from typing import Any

from PyQt5.QtWidgets import QWidget, QCheckBox

from src.util.constants import TURN_TABLE_MODEL_OTHER, WIFI_PRODUCT_PROJECT_MAP
from src.ui.view.builder import build_groups_from_schema, load_ui_schema


def update_step_indicator(page: Any, index: int) -> None:
    """Update the wizard step indicator to reflect the current page index."""
    view = getattr(page, "step_view_widget", None)
    if view is None:
        return
    for attr in ("setCurrentIndex", "setCurrentStep", "setCurrentRow", "setCurrent"):
        if hasattr(view, attr):
            try:
                getattr(view, attr)(index)
                return
            except Exception:
                continue
    if hasattr(view, "set_current_index"):
        try:
            view.set_current_index(index)
        except Exception:
            pass


def apply_rf_model_ui_state(page: Any, model_str: str) -> None:
    """Toggle RF-solution parameter groups based on the selected model."""
    if hasattr(page, "xin_group"):
        page.xin_group.setVisible(model_str == "RS232Board5")
    if hasattr(page, "rc4_group"):
        page.rc4_group.setVisible(model_str == "RC4DAT-8G-95")
    if hasattr(page, "rack_group"):
        page.rack_group.setVisible(model_str == "RADIORACK-4-220")
    if hasattr(page, "lda_group"):
        page.lda_group.setVisible(model_str == "LDA-908V-8")


def apply_rvr_tool_ui_state(page: Any, tool: str) -> None:
    """Toggle RvR tool-specific parameter groups (iperf vs ixchariot)."""
    if hasattr(page, "rvr_iperf_group"):
        page.rvr_iperf_group.setVisible(tool == "iperf")
    if hasattr(page, "rvr_ix_group"):
        page.rvr_ix_group.setVisible(tool == "ixchariot")


def apply_serial_enabled_ui_state(page: Any, text: str) -> None:
    """Show/hide the serial config group when serial is enabled/disabled."""
    if hasattr(page, "serial_cfg_group"):
        page.serial_cfg_group.setVisible(text == "True")


def apply_turntable_model_ui_state(page: Any, model: str) -> None:
    """Toggle visibility/enabled state for turntable IP controls."""
    if not hasattr(page, "turntable_ip_edit") or not hasattr(page, "turntable_ip_label"):
        return
    requires_ip = model == TURN_TABLE_MODEL_OTHER
    page.turntable_ip_label.setVisible(requires_ip)
    page.turntable_ip_edit.setVisible(requires_ip)
    page.turntable_ip_edit.setEnabled(requires_ip)


def apply_run_lock_ui_state(page: Any, locked: bool) -> None:
    """Apply UI changes when a test run is locked/unlocked."""
    if hasattr(page, "case_tree"):
        page.case_tree.setEnabled(not locked)
    # Sync run button enabled state via controller helper if available.
    if hasattr(page, "_sync_run_buttons_enabled"):
        try:
            page._sync_run_buttons_enabled()
        except Exception:
            pass
    if locked:
        # During a run, prevent user edits across all fields and CSV combos.
        field_widgets = getattr(page, "field_widgets", {}) or {}
        for w in field_widgets.values():
            try:
                w.setEnabled(False)
            except Exception:
                continue
        if hasattr(page, "csv_combo"):
            try:
                page.csv_combo.setEnabled(False)
            except Exception:
                pass
    else:
        # Restore editable state and navigation when unlocking.
        if hasattr(page, "_restore_editable_state"):
            try:
                page._restore_editable_state()
            except Exception:
                pass
        if hasattr(page, "_update_navigation_state"):
            try:
                page._update_navigation_state()
            except Exception:
                pass


def refresh_config_page_controls(page: Any) -> None:
    """构建并刷新 Config 页所有控件状态（包括 FPGA 映射）。

    - 归一化 ``debug`` / ``connect_type`` / ``fpga`` / ``stability`` 配置；
    - 通过 YAML schema 构建 DUT / Execution / Stability 三个面板；
    - 调用 ``init_fpga_dropdowns`` 让 FPGA 下拉与 ``WIFI_PRODUCT_PROJECT_MAP`` 联动。
    """
    # 清空已有分组缓存，确保重新构建 UI 时不会重复叠加。
    if hasattr(page, "_dut_groups"):
        page._dut_groups.clear()
    if hasattr(page, "_other_groups"):
        page._other_groups.clear()

    config = getattr(page, "config", None)
    if not isinstance(config, dict):
        config = {}
        page.config = config

    defaults_for_dut = {
        "software_info": {},
        "hardware_info": {},
        "system": {},
    }
    for key, default in defaults_for_dut.items():
        existing = config.get(key)
        if not isinstance(existing, dict):
            config[key] = default.copy()
        else:
            config[key] = dict(existing)

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

    config["debug"] = _normalize_debug_section(config.get("debug"))
    if hasattr(page, "_normalize_connect_type_section"):
        config["connect_type"] = page._normalize_connect_type_section(config.get("connect_type"))
    linux_cfg = config.get("connect_type", {}).get("Linux")
    if isinstance(linux_cfg, dict) and "kernel_version" in linux_cfg:
        config.setdefault("system", {})["kernel_version"] = linux_cfg.pop("kernel_version")
    if hasattr(page, "_normalize_fpga_section"):
        config["fpga"] = page._normalize_fpga_section(config.get("fpga"))
    if hasattr(page, "_normalize_stability_settings"):
        config["stability"] = page._normalize_stability_settings(config.get("stability"))

    # YAML schema 构建三个 panel 的控件
    dut_schema = load_ui_schema("dut")
    build_groups_from_schema(page, config, dut_schema, panel_key="dut")

    exec_schema = load_ui_schema("execution")
    build_groups_from_schema(page, config, exec_schema, panel_key="execution")

    stability_cfg = config.get("stability") or {}
    stab_schema = load_ui_schema("stability")
    build_groups_from_schema(page, stability_cfg, stab_schema, panel_key="stability")

    # 初始 FPGA 下拉联动 + Control Type / Third‑party wiring
    init_fpga_dropdowns(page)
    init_connect_type_actions(page)


def init_fpga_dropdowns(view: Any) -> None:
    """Wire FPGA customer/product/project combos and keep them in sync.


    该函数只做 UI 行为：
    - 通过 ``field_widgets`` 找出 ``fpga.customer / fpga.product_line / fpga.project`` 对应的 ComboBox；
    - 在 view/page 对象上挂上 ``fpga_*_combo`` 属性；
    - 绑定信号，调用 ``refresh_fpga_product_lines`` / ``refresh_fpga_projects``
      让 Project 选项跟 ``WIFI_PRODUCT_PROJECT_MAP`` 联动。
    """
    # Discover FPGA-related combos from field_widgets.
    field_widgets = getattr(view, "field_widgets", {}) or {}

    customer_combo = None
    product_combo = None
    project_combo = None

    for key, widget in field_widgets.items():
        logical = str(key).strip().lower()
        if not logical.startswith("fpga."):
            continue
        if not hasattr(widget, "currentTextChanged"):
            continue
        if logical == "fpga.customer":
            customer_combo = widget
        elif logical == "fpga.product_line":
            product_combo = widget
        elif logical == "fpga.project":
            project_combo = widget

    if not (customer_combo and product_combo and project_combo):
        logging.warning("[DEBUG_FPGA] init_fpga_dropdowns: required combos missing, abort")
        return

    setattr(view, "fpga_customer_combo", customer_combo)
    setattr(view, "fpga_product_combo", product_combo)
    setattr(view, "fpga_project_combo", project_combo)

    def _sync_hidden_fields() -> None:
        """Invoke shared helper to update config + visible fields."""
        update_fpga_hidden_fields(view)


    def _on_customer_changed(text: str) -> None:
        refresh_fpga_product_lines(view, text)
        current_product = product_combo.currentText()
        refresh_fpga_projects(view, text, current_product)
        _sync_hidden_fields()

    def _on_product_changed(text: str) -> None:
        current_customer = customer_combo.currentText()
        refresh_fpga_projects(view, current_customer, text)
        _sync_hidden_fields()

    def _on_project_changed(text: str) -> None:
        _sync_hidden_fields()

    customer_combo.currentTextChanged.connect(_on_customer_changed)
    product_combo.currentTextChanged.connect(_on_product_changed)
    project_combo.currentTextChanged.connect(_on_project_changed)

    # Initial population based on current selections.
    initial_customer = customer_combo.currentText()
    refresh_fpga_product_lines(view, initial_customer)
    initial_product = product_combo.currentText()
    refresh_fpga_projects(view, initial_customer, initial_product)
    # 初始时也同步一次隐藏字段和可见字段。
    update_fpga_hidden_fields(view)

    setattr(view, "_fpga_dropdowns_wired", True)


def refresh_fpga_product_lines(view: Any, customer: str) -> None:
    """Populate the FPGA product-line combo for a given customer."""
    combo = getattr(view, "fpga_product_combo", None)
    if combo is None:
        logging.warning("[DEBUG_FPGA] refresh_fpga_product_lines: no fpga_product_combo")
        return
    customer_upper = (customer or "").strip().upper()
    product_lines = WIFI_PRODUCT_PROJECT_MAP.get(customer_upper, {}) if customer_upper else {}
    combo.clear()
    for product_name in product_lines.keys():
        combo.addItem(product_name)
    if combo.count() == 0:
        combo.setCurrentIndex(-1)


def refresh_fpga_projects(view: Any, customer: str, product_line: str) -> None:
    """Populate the FPGA project combo for a given customer/product-line."""
    combo = getattr(view, "fpga_project_combo", None)
    if combo is None:
        logging.warning("[DEBUG_FPGA] refresh_fpga_projects: no fpga_project_combo")
        return
    customer_upper = (customer or "").strip().upper()
    product_upper = (product_line or "").strip().upper()
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
    if combo.count() == 0:
        combo.setCurrentIndex(-1)


def update_fpga_hidden_fields(page: Any) -> None:
    """同步 FPGA project 选择到 config 和三个只读字段。

    - 读取 ``fpga_*_combo`` 当前选择；
    - 使用 ``_guess_fpga_project`` 在 ``WIFI_PRODUCT_PROJECT_MAP`` 里做大小写无关匹配；
    - 更新 ``page.config['fpga']`` / ``page._fpga_details``；
    - 把 main_chip / wifi_module / interface 写回对应的 LineEdit。
    """
    customer_combo = getattr(page, "fpga_customer_combo", None)
    product_combo = getattr(page, "fpga_product_combo", None)
    project_combo = getattr(page, "fpga_project_combo", None)
    if not (customer_combo and product_combo and project_combo):
        return

    customer = (customer_combo.currentText() or "").strip().upper()
    product = (product_combo.currentText() or "").strip().upper()
    project = (project_combo.currentText() or "").strip().upper()

    info = None
    if product and project and hasattr(page, "_guess_fpga_project"):
        guessed_customer, guessed_product, guessed_project, guessed_info = page._guess_fpga_project(
            "",
            "",
            "",
            customer=customer,
            product_line=product,
            project=project,
        )
        if guessed_info:
            customer = guessed_customer or customer
            product = guessed_product or product
            project = guessed_project or project
            info = guessed_info

    normalize_token = getattr(page, "_normalize_fpga_token", None)

    def _norm(value: Any) -> str:
        if callable(normalize_token):
            return normalize_token(value)
        return str(value or "").strip().upper()

    if product and project and info:
        normalized = {
            "customer": customer,
            "product_line": product,
            "project": project,
            "main_chip": _norm(info.get("main_chip")),
            "wifi_module": _norm(info.get("wifi_module")),
            "interface": _norm(info.get("interface")),
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

    setattr(page, "_fpga_details", normalized)
    config = getattr(page, "config", None)
    if isinstance(config, dict):
        config["fpga"] = dict(normalized)

    field_widgets = getattr(page, "field_widgets", {}) or {}
    for key, field_key in (
        ("main_chip", "fpga.main_chip"),
        ("wifi_module", "fpga.wifi_module"),
        ("interface", "fpga.interface"),
    ):
        widget = field_widgets.get(field_key)
        if widget is not None and hasattr(widget, "setText"):
            widget.setText(normalized.get(key, "") or "")


def apply_connect_type_ui_state(page: Any, connect_type: str) -> None:
    """根据 Control Type 切换连接方式相关控件状态.

    - Android: 禁用 Linux IP, 启用 Android Device;
    - Linux:   启用 Linux IP, 禁用 Android Device.
    System 区域由规则和上层 handler 处理。
    """
    # 兼容旧版 group 显示/隐藏
    if hasattr(page, "adb_group"):
        page.adb_group.setVisible(connect_type == "Android")
    if hasattr(page, "telnet_group"):
        page.telnet_group.setVisible(connect_type == "Linux")

    field_widgets = getattr(page, "field_widgets", {}) or {}

    android_device = field_widgets.get("connect_type.Android.device")
    linux_ip = field_widgets.get("connect_type.Linux.ip")

    is_android = connect_type == "Android"
    is_linux = connect_type == "Linux"

    if android_device is not None and hasattr(android_device, "setEnabled"):
        android_device.setEnabled(is_android)
    if linux_ip is not None and hasattr(linux_ip, "setEnabled"):
        linux_ip.setEnabled(is_linux)

def apply_third_party_ui_state(page: Any, enabled: bool) -> None:
    """根据第三方控制开关, 切换 Wait seconds 的可编辑状态."""
    field_widgets = getattr(page, "field_widgets", {}) or {}
    wait_widget = field_widgets.get("connect_type.third_party.wait_seconds")
    if wait_widget is None:
        # 回退到旧属性命名
        wait_widget = getattr(page, "third_party_wait_edit", None)
    if wait_widget is None or not hasattr(wait_widget, "setEnabled"):
        return
    wait_widget.setEnabled(bool(enabled))

def handle_connect_type_changed(page: Any, display_text: str) -> None:
    """统一处理 Control Type 改变时的 UI + 业务逻辑 + System 区域."""

    text = str(display_text or "")
    normalized = text
    if hasattr(page, "_normalize_connect_type_label"):
        normalized = page._normalize_connect_type_label(text)

    # 1) 纯 UI：只管 Android Device / Linux IP
    apply_connect_type_ui_state(page, normalized)

    # 2) 业务逻辑：让 CaseConfigPage 自己做 kernel 映射 + 规则
    if hasattr(page, "on_connect_type_changed"):
        # 这里仍传原始 display text，保持原有逻辑不变
        page.on_connect_type_changed(text)

    # 3) System 区域兜底
    field_widgets = getattr(page, "field_widgets", {}) or {}
    version_widget = field_widgets.get("system.version")
    kernel_widget = field_widgets.get("system.kernel_version")
    is_android = normalized == "Android"

    if version_widget is not None:
        if hasattr(version_widget, "setVisible"):
            version_widget.setVisible(is_android)
        if hasattr(version_widget, "setEnabled"):
            version_widget.setEnabled(is_android)

    if kernel_widget is not None:
        if hasattr(kernel_widget, "setVisible"):
            kernel_widget.setVisible(True)
        if hasattr(kernel_widget, "setEnabled"):
            kernel_widget.setEnabled(True)


def handle_third_party_toggled(page: Any, checked: bool) -> None:
    """统一处理 Third‑party 勾选时的 UI 和规则刷新."""
    enabled = bool(checked)
    apply_third_party_ui_state(page, enabled)
    if hasattr(page, "_apply_config_ui_rules"):
        page._apply_config_ui_rules()

def init_connect_type_actions(page: Any) -> None:
    """发现并绑定 Control Type / Third‑party 相关控件到对应的槽函数."""

    field_widgets = getattr(page, "field_widgets", {}) or {}

    connect_combo = field_widgets.get("connect_type.type")
    third_checkbox = field_widgets.get("connect_type.third_party.enabled")
    third_wait = field_widgets.get("connect_type.third_party.wait_seconds")

    # Wire Control Type combo -> centralized handler
    if connect_combo is not None:
        setattr(page, "connect_type_combo", connect_combo)
        # 优先使用 currentTextChanged, 否则退回 currentIndexChanged
        if hasattr(connect_combo, "currentTextChanged"):
            connect_combo.currentTextChanged.connect(
                lambda text: handle_connect_type_changed(page, text)
            )
        elif hasattr(connect_combo, "currentIndexChanged"):
            connect_combo.currentIndexChanged.connect(
                lambda _idx: handle_connect_type_changed(page, connect_combo.currentText())
            )
        # 应用一次初始 UI 状态
        handle_connect_type_changed(page, connect_combo.currentText())

    # Wire third‑party checkbox -> centralized handler
    if isinstance(third_checkbox, QCheckBox):
        setattr(page, "third_party_checkbox", third_checkbox)
        third_checkbox.toggled.connect(lambda checked: handle_third_party_toggled(page, checked))

    # Track Wait seconds editor
    if third_wait is not None:
        setattr(page, "third_party_wait_edit", third_wait)
        # 初始根据复选框状态刷新一次
        if isinstance(third_checkbox, QCheckBox):
            apply_third_party_ui_state(page, third_checkbox.isChecked())

__all__ = [
    "update_step_indicator",
    "apply_rf_model_ui_state",
    "apply_rvr_tool_ui_state",
    "apply_serial_enabled_ui_state",
    "apply_turntable_model_ui_state",
    "apply_run_lock_ui_state",
    "refresh_config_page_controls",
    "init_fpga_dropdowns",
    "refresh_fpga_product_lines",
    "refresh_fpga_projects",
    "update_fpga_hidden_fields",
    "apply_connect_type_ui_state",
    "apply_third_party_ui_state",
    "handle_connect_type_changed",
    "handle_third_party_toggled",
]
