"""Section covering turntable configuration controls."""

from __future__ import annotations

from typing import Any

from PyQt5.QtWidgets import QLabel, QGroupBox, QVBoxLayout

from qfluentwidgets import ComboBox, LineEdit

from src.util.constants import (
    TURN_TABLE_FIELD_IP_ADDRESS,
    TURN_TABLE_FIELD_MODEL,
    TURN_TABLE_FIELD_STATIC_DB,
    TURN_TABLE_FIELD_STEP,
    TURN_TABLE_FIELD_TARGET_RSSI,
    TURN_TABLE_MODEL_CHOICES,
    TURN_TABLE_MODEL_RS232,
    TURN_TABLE_SECTION_KEY,
)

from ..sections import register_case_sections, register_section
from ..sections.base import ConfigSection


@register_section(TURN_TABLE_SECTION_KEY, case_types=("default",))
class TurntableSection(ConfigSection):
    """Render turntable model selection and RSSI controls."""

    panel = "execution"

    def build(self, config: dict[str, Any]) -> None:  # type: ignore[override]
        value = config.get(TURN_TABLE_SECTION_KEY) if isinstance(config, dict) else {}
        if not isinstance(value, dict):
            value = {}
        group = QGroupBox("Turntable", self.page)
        vbox = QVBoxLayout(group)
        self.page.turntable_model_combo = ComboBox(self.page)
        self.page.turntable_model_combo.addItems(list(TURN_TABLE_MODEL_CHOICES))
        model_value = str(value.get(TURN_TABLE_FIELD_MODEL, TURN_TABLE_MODEL_RS232))
        if model_value not in TURN_TABLE_MODEL_CHOICES:
            model_value = TURN_TABLE_MODEL_RS232
        self.page.turntable_model_combo.setCurrentText(model_value)
        vbox.addWidget(QLabel("Turntable:", group))
        vbox.addWidget(self.page.turntable_model_combo)

        self.page.turntable_ip_label = QLabel("IP address:", group)
        self.page.turntable_ip_edit = LineEdit(self.page)
        self.page.turntable_ip_edit.setPlaceholderText(TURN_TABLE_FIELD_IP_ADDRESS)
        ip_value = value.get(TURN_TABLE_FIELD_IP_ADDRESS, "")
        self.page.turntable_ip_edit.setText(str(ip_value))
        vbox.addWidget(self.page.turntable_ip_label)
        vbox.addWidget(self.page.turntable_ip_edit)

        self.page.turntable_step_edit = LineEdit(self.page)
        self.page.turntable_step_edit.setPlaceholderText("Step; e.g. 0,361")
        step_value = value.get(TURN_TABLE_FIELD_STEP, "")
        if isinstance(step_value, (list, tuple, set)):
            step_text = ",".join(str(item) for item in step_value)
        else:
            step_text = str(step_value) if step_value is not None else ""
        self.page.turntable_step_edit.setText(step_text)
        vbox.addWidget(QLabel("Step:", group))
        vbox.addWidget(self.page.turntable_step_edit)

        self.page.turntable_static_db_edit = LineEdit(self.page)
        self.page.turntable_static_db_edit.setPlaceholderText("Static attenuation (dB)")
        static_db_value = value.get(TURN_TABLE_FIELD_STATIC_DB, "")
        self.page.turntable_static_db_edit.setText("" if static_db_value is None else str(static_db_value))
        vbox.addWidget(QLabel("Static dB:", group))
        vbox.addWidget(self.page.turntable_static_db_edit)

        self.page.turntable_target_rssi_edit = LineEdit(self.page)
        self.page.turntable_target_rssi_edit.setPlaceholderText("Target RSSI (dBm)")
        target_rssi_value = value.get(TURN_TABLE_FIELD_TARGET_RSSI, "")
        self.page.turntable_target_rssi_edit.setText("" if target_rssi_value is None else str(target_rssi_value))
        vbox.addWidget(QLabel("Target RSSI:", group))
        vbox.addWidget(self.page.turntable_target_rssi_edit)

        self.page.turntable_model_combo.currentTextChanged.connect(self.page._on_turntable_model_changed)
        self.page.turntable_static_db_edit.textChanged.connect(
            lambda _text, source="static": self.page._ensure_turntable_inputs_exclusive(source)
        )
        self.page.turntable_target_rssi_edit.textChanged.connect(
            lambda _text, source="target": self.page._ensure_turntable_inputs_exclusive(source)
        )
        self.page._ensure_turntable_inputs_exclusive(None)
        self.page._on_turntable_model_changed(self.page.turntable_model_combo.currentText())

        self.register_group(TURN_TABLE_SECTION_KEY, group, is_dut=False)
        self.register_field(f"{TURN_TABLE_SECTION_KEY}.{TURN_TABLE_FIELD_MODEL}", self.page.turntable_model_combo)
        self.register_field(f"{TURN_TABLE_SECTION_KEY}.{TURN_TABLE_FIELD_IP_ADDRESS}", self.page.turntable_ip_edit)
        self.register_field(f"{TURN_TABLE_SECTION_KEY}.{TURN_TABLE_FIELD_STEP}", self.page.turntable_step_edit)
        self.register_field(f"{TURN_TABLE_SECTION_KEY}.{TURN_TABLE_FIELD_STATIC_DB}", self.page.turntable_static_db_edit)
        self.register_field(f"{TURN_TABLE_SECTION_KEY}.{TURN_TABLE_FIELD_TARGET_RSSI}", self.page.turntable_target_rssi_edit)


__all__ = ["TurntableSection"]

register_case_sections("default", [TURN_TABLE_SECTION_KEY])
