"""Section exposing debug toggles for performance workflows."""

from __future__ import annotations

from typing import Any

from PyQt5.QtWidgets import QCheckBox, QGroupBox, QLabel, QVBoxLayout

from ..sections import register_case_sections, register_section
from ..sections.base import ConfigSection


@register_section("debug", case_types=("default",))
class DebugSection(ConfigSection):
    """Render debug flags controlling optional workflow shortcuts."""

    panel = "execution"

    def build(self, config: dict[str, Any]) -> None:  # type: ignore[override]
        data = config.get("debug") if isinstance(config, dict) else {}
        if not isinstance(data, dict):
            data = {}
        group = QGroupBox("Debug Options", self.page)
        vbox = QVBoxLayout(group)
        debug_options = [
            (
                "database_mode",
                "Enable database debug mode",
                "When enabled, performance tests skip router/RF/corner setup and simulate iperf results for database debugging.",
            ),
            (
                "skip_router",
                "Skip router workflow",
                "Skip router instantiation, configuration, and Wi-Fi reconnection steps during performance tests.",
            ),
            (
                "skip_corner_rf",
                "Skip corner && RF workflow",
                "Skip corner turntable and RF attenuator initialization and adjustments.",
            ),
        ]
        for index, (option_key, label, hint_text) in enumerate(debug_options):
            checkbox = QCheckBox(label, self.page)
            checkbox.setChecked(bool(data.get(option_key)))
            vbox.addWidget(checkbox)
            if index == 0:
                self.page.database_debug_checkbox = checkbox
            if hint_text:
                hint_label = QLabel(hint_text, self.page)
                hint_label.setWordWrap(True)
                hint_label.setObjectName("debugHintLabel")
                vbox.addWidget(hint_label)
            self.register_field(f"debug.{option_key}", checkbox)
        self.register_group("debug", group, is_dut=False)


__all__ = ["DebugSection"]

register_case_sections("default", ["debug"])
