"""Sections covering Wi-Fi and DUT related configuration groups."""

from __future__ import annotations

from typing import Any

from PyQt5.QtGui import QIntValidator
from PyQt5.QtWidgets import QCheckBox, QFormLayout, QGroupBox, QLabel, QVBoxLayout, QWidget

from qfluentwidgets import ComboBox, LineEdit

from src.util.constants import WIFI_PRODUCT_PROJECT_MAP

from ..forms import FieldSchema, FormBuilder
from ..sections import register_case_sections, register_section
from ..sections.base import ConfigSection


@register_section("software_info", case_types=("default",))
class SoftwareInfoSection(ConfigSection):
    """Render editable metadata about DUT software builds."""

    panel = "dut"

    def build(self, config: dict[str, Any]) -> None:  # type: ignore[override]
        data = config.get("software_info") if isinstance(config, dict) else {}
        if not isinstance(data, dict):
            data = {}
        group = QGroupBox("Software Info", self.page)
        vbox = QVBoxLayout(group)
        form, widgets = FormBuilder(self.page).build_form(
            QFormLayout(),
            [
                FieldSchema(
                    name="software_info.software_version",
                    label="Software Version:",
                    default=str(data.get("software_version", "")),
                    placeholder="e.g. V1.2.3",
                ),
                FieldSchema(
                    name="software_info.driver_version",
                    label="Driver Version:",
                    default=str(data.get("driver_version", "")),
                    placeholder="Driver build",
                ),
            ],
        )
        vbox.addWidget(form)
        self.register_group("software_info", group, is_dut=True)
        for key, widget in widgets.items():
            self.register_field(key, widget)


@register_section("hardware_info", case_types=("default",))
class HardwareInfoSection(ConfigSection):
    """Render editable metadata about DUT hardware builds."""

    panel = "dut"

    def build(self, config: dict[str, Any]) -> None:  # type: ignore[override]
        data = config.get("hardware_info") if isinstance(config, dict) else {}
        if not isinstance(data, dict):
            data = {}
        group = QGroupBox("Hardware Info", self.page)
        vbox = QVBoxLayout(group)
        form, widgets = FormBuilder(self.page).build_form(
            QFormLayout(),
            [
                FieldSchema(
                    name="hardware_info.hardware_version",
                    label="Hardware Version:",
                    default=str(data.get("hardware_version", "")),
                    placeholder="PCB revision / BOM",
                ),
            ],
        )
        vbox.addWidget(form)
        self.register_group("hardware_info", group, is_dut=True)
        for key, widget in widgets.items():
            self.register_field(key, widget)


@register_section("android_system", case_types=("default",))
class AndroidSystemSection(ConfigSection):
    """Render selectors for Android and kernel versions."""

    panel = "dut"

    def build(self, config: dict[str, Any]) -> None:  # type: ignore[override]
        data = config.get("android_system") if isinstance(config, dict) else {}
        if not isinstance(data, dict):
            data = {}
        group = QGroupBox("Android System", self.page)
        vbox = QVBoxLayout(group)
        self.page.android_version_label = QLabel("Android Version:", group)
        vbox.addWidget(self.page.android_version_label)
        self.page.android_version_combo = ComboBox(self.page)
        for value in self.page._android_versions:
            self.page.android_version_combo.addItem(value)
        current_version = str(data.get("version", ""))
        if current_version and current_version not in self.page._android_versions:
            self.page.android_version_combo.addItem(current_version)
        if current_version:
            self.page.android_version_combo.setCurrentText(current_version)
        else:
            self.page.android_version_combo.setCurrentIndex(-1)
        self.page.android_version_combo.currentTextChanged.connect(
            self.page._on_android_version_changed
        )
        vbox.addWidget(self.page.android_version_combo)

        self.page.kernel_version_label = QLabel("Kernel Version:", group)
        vbox.addWidget(self.page.kernel_version_label)
        self.page.kernel_version_combo = ComboBox(self.page)
        for value in self.page._kernel_versions:
            self.page.kernel_version_combo.addItem(value)
        kernel_value = str(data.get("kernel_version", ""))
        if kernel_value and kernel_value not in self.page._kernel_versions:
            self.page.kernel_version_combo.addItem(kernel_value)
        if kernel_value:
            self.page.kernel_version_combo.setCurrentText(kernel_value)
        else:
            self.page.kernel_version_combo.setCurrentIndex(-1)
        vbox.addWidget(self.page.kernel_version_combo)
        self.register_group("android_system", group, is_dut=True)
        self.register_field("android_system.version", self.page.android_version_combo)
        self.register_field("android_system.kernel_version", self.page.kernel_version_combo)
        self.page._update_android_system_for_connect_type(self.page._current_connect_type())


@register_section("connect_type", case_types=("default",))
class ConnectTypeSection(ConfigSection):
    """Render Android/Linux connection controls."""

    panel = "dut"

    def build(self, config: dict[str, Any]) -> None:  # type: ignore[override]
        value = config.get("connect_type") if isinstance(config, dict) else {}
        if not isinstance(value, dict):
            value = {}
        group = QGroupBox("Control Type", self.page)
        vbox = QVBoxLayout(group)
        self.page.connect_type_combo = ComboBox(self.page)
        self.page.connect_type_combo.addItem("Android", "Android")
        self.page.connect_type_combo.addItem("Linux", "Linux")
        self.page._set_connect_type_combo_selection(value.get("type", "Android"))
        self.page.connect_type_combo.currentTextChanged.connect(self.page.on_connect_type_changed)
        vbox.addWidget(self.page.connect_type_combo)

        self.page.adb_group = QWidget(group)
        adb_vbox = QVBoxLayout(self.page.adb_group)
        self.page.adb_device_edit = LineEdit(self.page)
        self.page.adb_device_edit.setPlaceholderText("Android.device")
        self.page.adb_device_edit.setText(value.get("Android", {}).get("device", ""))
        adb_vbox.addWidget(QLabel("Android Device:", group))
        adb_vbox.addWidget(self.page.adb_device_edit)

        self.page.telnet_group = QWidget(group)
        telnet_vbox = QVBoxLayout(self.page.telnet_group)
        telnet_cfg = value.get("Linux", {}) if isinstance(value, dict) else {}
        if not isinstance(telnet_cfg, dict):
            telnet_cfg = {}
        self.page.telnet_ip_edit = LineEdit(self.page)
        self.page.telnet_ip_edit.setPlaceholderText("Linux.ip")
        self.page.telnet_ip_edit.setText(telnet_cfg.get("ip", ""))
        telnet_vbox.addWidget(QLabel("Linux IP:", group))
        telnet_vbox.addWidget(self.page.telnet_ip_edit)

        self.page.third_party_group = QWidget(group)
        third_vbox = QVBoxLayout(self.page.third_party_group)
        third_cfg = value.get("third_party", {}) if isinstance(value, dict) else {}
        if not isinstance(third_cfg, dict):
            third_cfg = {}
        enabled = bool(third_cfg.get("enabled", False))
        wait_seconds = third_cfg.get("wait_seconds")
        wait_text = "" if wait_seconds in (None, "") else str(wait_seconds)
        self.page.third_party_checkbox = QCheckBox("Enable third-party control", self.page)
        self.page.third_party_checkbox.setChecked(enabled)
        self.page.third_party_checkbox.toggled.connect(self.page.on_third_party_toggled)
        third_vbox.addWidget(self.page.third_party_checkbox)
        self.page.third_party_wait_label = QLabel("Wait seconds:", group)
        third_vbox.addWidget(self.page.third_party_wait_label)
        self.page.third_party_wait_edit = LineEdit(self.page)
        self.page.third_party_wait_edit.setPlaceholderText("wait seconds (e.g. 3)")
        self.page.third_party_wait_edit.setValidator(QIntValidator(1, 999999, self.page))
        self.page.third_party_wait_edit.setText(wait_text)
        third_vbox.addWidget(self.page.third_party_wait_edit)

        vbox.addWidget(self.page.adb_group)
        vbox.addWidget(self.page.telnet_group)
        vbox.addWidget(self.page.third_party_group)
        self.register_group("connect_type", group, is_dut=True)
        self.register_field("connect_type.type", self.page.connect_type_combo)
        self.register_field("connect_type.Android.device", self.page.adb_device_edit)
        self.register_field("connect_type.Linux.ip", self.page.telnet_ip_edit)
        self.register_field("connect_type.third_party.enabled", self.page.third_party_checkbox)
        self.register_field("connect_type.third_party.wait_seconds", self.page.third_party_wait_edit)
        self.page.on_third_party_toggled(self.page.third_party_checkbox.isChecked())
        self.page.on_connect_type_changed(self.page._current_connect_type())


@register_section("fpga", case_types=("default",))
class FpgaSection(ConfigSection):
    """Render project selectors for FPGA/product combinations."""

    panel = "dut"

    def build(self, config: dict[str, Any]) -> None:  # type: ignore[override]
        defaults = self.page._normalize_fpga_section(config.get("fpga"))
        customer_default = defaults.get("customer", "")
        product_default = defaults.get("product_line", "")
        project_default = defaults.get("project", "")

        if not customer_default and product_default:
            for customer_name, product_lines in WIFI_PRODUCT_PROJECT_MAP.items():
                if product_default in product_lines:
                    customer_default = customer_name
                    break

        group = QGroupBox("Project", self.page)
        vbox = QVBoxLayout(group)
        self.page.fpga_customer_combo = ComboBox(self.page)
        for customer_name in WIFI_PRODUCT_PROJECT_MAP.keys():
            self.page.fpga_customer_combo.addItem(customer_name)
        if customer_default and customer_default in WIFI_PRODUCT_PROJECT_MAP:
            self.page.fpga_customer_combo.setCurrentText(customer_default)
        else:
            self.page.fpga_customer_combo.setCurrentIndex(-1)
        vbox.addWidget(QLabel("Customer:", group))
        vbox.addWidget(self.page.fpga_customer_combo)

        self.page.fpga_product_combo = ComboBox(self.page)
        self.page.fpga_project_combo = ComboBox(self.page)

        self.page._refresh_fpga_product_lines(customer_default, product_default, block_signals=True)
        if (
            customer_default
            and product_default
            and product_default in WIFI_PRODUCT_PROJECT_MAP.get(customer_default, {})
        ):
            self.page.fpga_product_combo.setCurrentText(product_default)
        else:
            self.page.fpga_product_combo.setCurrentIndex(-1)

        self.page._refresh_fpga_projects(customer_default, product_default, project_default, block_signals=True)
        if (
            customer_default
            and product_default
            and project_default
            and project_default
            in WIFI_PRODUCT_PROJECT_MAP.get(customer_default, {}).get(product_default, {})
        ):
            self.page.fpga_project_combo.setCurrentText(project_default)
        else:
            self.page.fpga_project_combo.setCurrentIndex(-1)

        vbox.addWidget(QLabel("Product Line:", group))
        vbox.addWidget(self.page.fpga_product_combo)
        vbox.addWidget(QLabel("Project:", group))
        vbox.addWidget(self.page.fpga_project_combo)

        self.page.fpga_customer_combo.currentTextChanged.connect(self.page.on_fpga_customer_changed)
        self.page.fpga_product_combo.currentTextChanged.connect(self.page.on_fpga_product_line_changed)
        self.page.fpga_project_combo.currentTextChanged.connect(self.page.on_fpga_project_changed)
        self.page._fpga_details = defaults
        self.page._update_fpga_hidden_fields()
        self.register_group("fpga", group, is_dut=True)
        self.register_field("fpga.customer", self.page.fpga_customer_combo)
        self.register_field("fpga.product_line", self.page.fpga_product_combo)
        self.register_field("fpga.project", self.page.fpga_project_combo)


__all__ = [
    "SoftwareInfoSection",
    "HardwareInfoSection",
    "AndroidSystemSection",
    "ConnectTypeSection",
    "FpgaSection",
]

register_case_sections(
    "default",
    [
        "software_info",
        "hardware_info",
        "android_system",
        "connect_type",
        "fpga",
    ],
)
