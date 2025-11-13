from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping

from PyQt5.QtCore import QSignalBlocker
from PyQt5.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import ComboBox, LineEdit

from src.tools.router_tool.router_factory import get_router, router_list

from . import build_groupbox
from .theme import apply_groupbox_style, apply_theme

if TYPE_CHECKING:  # pragma: no cover - circular import guard
    from .case_config_page import CaseConfigPage


def _build_network_group(
    page: "CaseConfigPage", value: Mapping[str, Any] | None
) -> None:
    """Create the router configuration group (model + gateway)."""
    data = value if isinstance(value, Mapping) else {}
    group, vbox = build_groupbox("Router")

    page.router_name_combo = ComboBox(page)
    page.router_name_combo.addItems(router_list.keys())
    page.router_name_combo.setCurrentText(str(data.get("name", "xiaomiax3000")))
    addr = data.get("address")
    page.router_obj = get_router(page.router_name_combo.currentText(), addr)

    page.router_addr_edit = LineEdit(page)
    page.router_addr_edit.setPlaceholderText("Gateway")
    page.router_addr_edit.setText(page.router_obj.address)
    page.router_addr_edit.textChanged.connect(page.on_router_address_changed)

    vbox.addWidget(QLabel("Model:"))
    vbox.addWidget(page.router_name_combo)
    vbox.addWidget(QLabel("Gateway:"))
    vbox.addWidget(page.router_addr_edit)
    page._register_group("router", group, page._is_dut_key("router"))

    page.field_widgets["router.name"] = page.router_name_combo
    page.field_widgets["router.address"] = page.router_addr_edit
    page.router_name_combo.currentTextChanged.connect(page.on_router_changed)
    page.on_router_changed(page.router_name_combo.currentText())


def _build_traffic_group(
    page: "CaseConfigPage", value: Mapping[str, Any] | None
) -> None:
    """Create serial/traffic controls used by stability runs."""
    data = value if isinstance(value, Mapping) else {}
    group, vbox = build_groupbox("Serial Port")

    page.serial_enable_combo = ComboBox(page)
    page.serial_enable_combo.addItems(["False", "True"])
    page.serial_enable_combo.setCurrentText(str(data.get("status", False)))
    page.serial_enable_combo.currentTextChanged.connect(
        page.on_serial_enabled_changed
    )
    vbox.addWidget(QLabel("Enable:"))
    vbox.addWidget(page.serial_enable_combo)

    page.serial_cfg_group = QWidget()
    cfg_box = QVBoxLayout(page.serial_cfg_group)

    page.serial_port_edit = LineEdit(page)
    page.serial_port_edit.setPlaceholderText("port (e.g. COM5)")
    page.serial_port_edit.setText(str(data.get("port", "")))

    page.serial_baud_edit = LineEdit(page)
    page.serial_baud_edit.setPlaceholderText("baud (e.g. 115200)")
    page.serial_baud_edit.setText(str(data.get("baud", "")))

    cfg_box.addWidget(QLabel("Port:"))
    cfg_box.addWidget(page.serial_port_edit)
    cfg_box.addWidget(QLabel("Baud:"))
    cfg_box.addWidget(page.serial_baud_edit)

    vbox.addWidget(page.serial_cfg_group)
    page._register_group("serial_port", group, page._is_dut_key("serial_port"))

    page.on_serial_enabled_changed(page.serial_enable_combo.currentText())

    page.field_widgets["serial_port.status"] = page.serial_enable_combo
    page.field_widgets["serial_port.port"] = page.serial_port_edit
    page.field_widgets["serial_port.baud"] = page.serial_baud_edit


def _build_duration_group(page: "CaseConfigPage") -> None:
    """Attach duration/checkpoint groups derived from stability config."""
    stability_cfg = page.config.get("stability", {})
    duration_cfg = (
        stability_cfg.get("duration_control")
        if isinstance(stability_cfg, Mapping)
        else None
    )
    checkpoint_cfg = (
        stability_cfg.get("check_point")
        if isinstance(stability_cfg, Mapping)
        else None
    )
    page._duration_control_group = page._build_duration_control_group(duration_cfg)
    page._check_point_group = page._build_check_point_group(checkpoint_cfg)


def _build_duration_control_group(
    page: "CaseConfigPage", data: Mapping[str, Any] | None
) -> QGroupBox:
    """Construct the duration control group."""

    normalized = data if isinstance(data, Mapping) else {}
    group, layout = build_groupbox("Duration control", parent=page)
    apply_theme(group)
    apply_groupbox_style(group)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(8)

    intro = QLabel(
        "Configure either loop count or duration in hours. Leave both empty to run until stopped.",
        group,
    )
    intro.setWordWrap(True)
    layout.addWidget(intro)

    grid = QGridLayout()
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(12)
    grid.setVerticalSpacing(6)
    layout.addLayout(grid)

    loops_label = QLabel("Loop count", group)
    loops_spin = QSpinBox(group)
    loops_spin.setRange(0, 999_999)
    loops_spin.setToolTip("Total number of test iterations. Set to zero to disable loop control.")

    duration_label = QLabel("Duration (hours)", group)
    duration_spin = QDoubleSpinBox(group)
    duration_spin.setRange(0.0, 999.0)
    duration_spin.setDecimals(2)
    duration_spin.setSingleStep(0.5)
    duration_spin.setSuffix(" h")
    duration_spin.setToolTip("Run until the configured number of hours elapses. Set to zero to disable.")

    grid.addWidget(loops_label, 0, 0)
    grid.addWidget(loops_spin, 0, 1)
    grid.addWidget(duration_label, 1, 0)
    grid.addWidget(duration_spin, 1, 1)

    exitfirst_checkbox = QCheckBox("Stop immediately on failure (exitfirst)", group)
    retry_label = QLabel("Retry count", group)
    retry_spin = QSpinBox(group)
    retry_spin.setRange(0, 10)
    retry_spin.setToolTip("Retries failed iterations before aborting. 0 disables retries.")

    grid.addWidget(exitfirst_checkbox, 2, 0, 1, 2)
    retry_row = QHBoxLayout()
    retry_row.setContentsMargins(0, 0, 0, 0)
    retry_row.addWidget(retry_label)
    retry_row.addWidget(retry_spin, 1)
    layout.addLayout(retry_row)
    layout.addStretch(1)

    loop_value = normalized.get("loop")
    duration_value = normalized.get("duration_hours")
    exitfirst_value = bool(normalized.get("exitfirst"))
    retry_value = normalized.get("retry_limit", 0) or 0
    with QSignalBlocker(loops_spin):
        try:
            loops_spin.setValue(int(loop_value))
        except (TypeError, ValueError):
            loops_spin.setValue(0)
    with QSignalBlocker(duration_spin):
        try:
            duration_spin.setValue(float(duration_value))
        except (TypeError, ValueError):
            duration_spin.setValue(0.0)
    with QSignalBlocker(exitfirst_checkbox):
        exitfirst_checkbox.setChecked(exitfirst_value)
    with QSignalBlocker(retry_spin):
        try:
            retry_spin.setValue(int(retry_value))
        except (TypeError, ValueError):
            retry_spin.setValue(0)

    def _sync_controls(source: str | None = None) -> None:
        """Ensure mutually exclusive selection between loop and duration controls."""
        loop_current = loops_spin.value()
        duration_current = duration_spin.value()
        if source == "loop" and loop_current > 0 and duration_current > 0:
            with QSignalBlocker(duration_spin):
                duration_spin.setValue(0.0)
        elif source == "duration" and loop_current > 0 and duration_current > 0:
            with QSignalBlocker(loops_spin):
                loops_spin.setValue(0)
        loops_spin.setEnabled(duration_spin.value() == 0.0)
        duration_spin.setEnabled(loops_spin.value() == 0)

    _sync_controls()
    retry_spin.setEnabled(exitfirst_checkbox.isChecked())

    loops_spin.valueChanged.connect(lambda _value: _sync_controls("loop"))
    duration_spin.valueChanged.connect(lambda _value: _sync_controls("duration"))
    exitfirst_checkbox.toggled.connect(retry_spin.setEnabled)

    page.field_widgets["stability.duration_control.loop"] = loops_spin
    page.field_widgets["stability.duration_control.duration_hours"] = duration_spin
    page.field_widgets["stability.duration_control.exitfirst"] = exitfirst_checkbox
    page.field_widgets["stability.duration_control.retry_limit"] = retry_spin

    return group


def _build_check_point_group(
    page: "CaseConfigPage", data: Mapping[str, Any] | None
) -> QGroupBox:
    """Construct the checkpoint selection group."""

    normalized = data if isinstance(data, Mapping) else {}
    group, layout = build_groupbox("Check point", parent=page)
    apply_theme(group)
    apply_groupbox_style(group)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(8)

    ping_checkbox = QCheckBox("Ping after each step", group)
    ping_checkbox.setChecked(bool(normalized.get("ping")))
    layout.addWidget(ping_checkbox)

    targets_label = QLabel("Ping targets (comma separated)", group)
    targets_edit = LineEdit(group)
    targets_edit.setPlaceholderText("192.168.50.1,www.baidu.com")
    targets_edit.setText(str(normalized.get("ping_targets", "") or ""))
    targets_edit.setClearButtonEnabled(True)
    targets_edit.setEnabled(ping_checkbox.isChecked())
    ping_checkbox.toggled.connect(targets_edit.setEnabled)
    layout.addWidget(targets_label)
    layout.addWidget(targets_edit)
    layout.addStretch(1)

    page.field_widgets["stability.check_point.ping"] = ping_checkbox
    page.field_widgets["stability.check_point.ping_targets"] = targets_edit

    return group
