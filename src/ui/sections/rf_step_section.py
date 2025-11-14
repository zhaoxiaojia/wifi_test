"""Section encapsulating RF attenuator and step configuration."""

from __future__ import annotations

from typing import Any

from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget, QGroupBox

from qfluentwidgets import ComboBox, LineEdit

from ..rf_step_segments import RfStepSegmentsWidget
from ..sections import register_case_sections, register_section
from ..sections.base import ConfigSection


@register_section("rf_solution", case_types=("default",))
class RfSolutionSection(ConfigSection):
    """Render RF attenuator configuration and step editor."""

    panel = "execution"

    def build(self, config: dict[str, Any]) -> None:  # type: ignore[override]
        value = config.get("rf_solution") if isinstance(config, dict) else {}
        if not isinstance(value, dict):
            value = {}
        group = QGroupBox("Attenuator", self.page)
        vbox = QVBoxLayout(group)
        self.page.rf_model_combo = ComboBox(self.page)
        self.page.rf_model_combo.addItems([
            "RS232Board5",
            "RC4DAT-8G-95",
            "RADIORACK-4-220",
            "LDA-908V-8",
        ])
        self.page.rf_model_combo.setCurrentText(value.get("model", "RS232Board5"))
        self.page.rf_model_combo.currentTextChanged.connect(self.page.on_rf_model_changed)
        vbox.addWidget(QLabel("Model:", group))
        vbox.addWidget(self.page.rf_model_combo)

        self.page.xin_group = QWidget(group)
        xin_box = QVBoxLayout(self.page.xin_group)
        xin_box.addWidget(QLabel("SH - New Wi-Fi full-wave anechoic chamber ", group))
        vbox.addWidget(self.page.xin_group)

        self.page.rc4_group = QWidget(group)
        rc4_box = QVBoxLayout(self.page.rc4_group)
        rc4_cfg = value.get("RC4DAT-8G-95", {})
        if not isinstance(rc4_cfg, dict):
            rc4_cfg = {}
        self.page.rc4_vendor_edit = LineEdit(self.page)
        self.page.rc4_product_edit = LineEdit(self.page)
        self.page.rc4_ip_edit = LineEdit(self.page)
        self.page.rc4_vendor_edit.setPlaceholderText("idVendor")
        self.page.rc4_product_edit.setPlaceholderText("idProduct")
        self.page.rc4_ip_edit.setPlaceholderText("ip_address")
        self.page.rc4_vendor_edit.setText(str(rc4_cfg.get("idVendor", "")))
        self.page.rc4_product_edit.setText(str(rc4_cfg.get("idProduct", "")))
        self.page.rc4_ip_edit.setText(rc4_cfg.get("ip_address", ""))
        rc4_box.addWidget(QLabel("idVendor:", group))
        rc4_box.addWidget(self.page.rc4_vendor_edit)
        rc4_box.addWidget(QLabel("idProduct:", group))
        rc4_box.addWidget(self.page.rc4_product_edit)
        rc4_box.addWidget(QLabel("IP address :", group))
        rc4_box.addWidget(self.page.rc4_ip_edit)
        vbox.addWidget(self.page.rc4_group)

        self.page.rack_group = QWidget(group)
        rack_box = QVBoxLayout(self.page.rack_group)
        rack_cfg = value.get("RADIORACK-4-220", {})
        if not isinstance(rack_cfg, dict):
            rack_cfg = {}
        self.page.rack_ip_edit = LineEdit(self.page)
        self.page.rack_ip_edit.setPlaceholderText("ip_address")
        self.page.rack_ip_edit.setText(rack_cfg.get("ip_address", ""))
        rack_box.addWidget(QLabel("IP address :", group))
        rack_box.addWidget(self.page.rack_ip_edit)
        vbox.addWidget(self.page.rack_group)

        self.page.lda_group = QWidget(group)
        lda_box = QVBoxLayout(self.page.lda_group)
        lda_cfg = value.get("LDA-908V-8", {})
        if not isinstance(lda_cfg, dict):
            lda_cfg = {}
            value["LDA-908V-8"] = lda_cfg
        channels_value = lda_cfg.setdefault("channels", [])
        self.page.lda_ip_edit = LineEdit(self.page)
        self.page.lda_ip_edit.setPlaceholderText("ip_address")
        self.page.lda_ip_edit.setText(lda_cfg.get("ip_address", ""))
        lda_channels = lda_cfg.get("channels", "")
        if isinstance(lda_channels, (list, tuple, set)):
            lda_channels_text = ",".join(map(str, lda_channels))
        else:
            lda_channels_text = str(lda_channels or "")
        self.page.lda_channels_edit = LineEdit(self.page)
        self.page.lda_channels_edit.setPlaceholderText("channels (1-8, e.g. 1,2,3)")
        self.page.lda_channels_edit.setText(lda_channels_text)
        lda_box.addWidget(QLabel("IP address :", group))
        lda_box.addWidget(self.page.lda_ip_edit)
        lda_box.addWidget(QLabel("Channels (1-8):", group))
        lda_box.addWidget(self.page.lda_channels_edit)
        vbox.addWidget(self.page.lda_group)

        self.page.rf_step_widget = RfStepSegmentsWidget(self.page)
        self.page.rf_step_widget.set_segments_from_config(value.get("step"))
        vbox.addWidget(QLabel("Step:", group))
        vbox.addWidget(self.page.rf_step_widget)

        self.register_group("rf_solution", group, is_dut=False)
        self.register_field("rf_solution.model", self.page.rf_model_combo)
        self.register_field("rf_solution.RC4DAT-8G-95.idVendor", self.page.rc4_vendor_edit)
        self.register_field("rf_solution.RC4DAT-8G-95.idProduct", self.page.rc4_product_edit)
        self.register_field("rf_solution.RC4DAT-8G-95.ip_address", self.page.rc4_ip_edit)
        self.register_field("rf_solution.RADIORACK-4-220.ip_address", self.page.rack_ip_edit)
        self.register_field("rf_solution.LDA-908V-8.ip_address", self.page.lda_ip_edit)
        self.register_field("rf_solution.LDA-908V-8.channels", self.page.lda_channels_edit)
        self.register_field("rf_solution.step", self.page.rf_step_widget)
        self.page.on_rf_model_changed(self.page.rf_model_combo.currentText())


__all__ = ["RfSolutionSection"]

register_case_sections("default", ["rf_solution"])
