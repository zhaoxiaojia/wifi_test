"""Config page view package.

This package hosts all view-only components for the Config sidebar page:

- :class:`ConfigView` – main DUT/Execution/Stability layout.
- Script-specific helpers (e.g. switch Wi-Fi / STR widgets).
"""

from __future__ import annotations

from typing import Any

from PyQt5.QtWidgets import QWidget, QGroupBox
from qfluentwidgets import ComboBox

from .page import ConfigView
from .config_switch_wifi import SwitchWifiManualEditor, SwitchWifiCsvPreview
from .config_str import RfStepSegmentsWidget
from src.ui.view.common import ConfigGroupPanel, ScriptConfigEntry
from src.ui.controller.case_ctl import (
    _register_switch_wifi_csv_combo,
    _unregister_switch_wifi_csv_combo,
)


def init_stability_common_groups(page: Any) -> None:
    """Bind common stability groups (Duration Control / Check Point) to the page.

    These two groups are defined in ``config_stability_ui.yaml`` under the
    ``stability`` panel and are shared by all stability test cases.  The
    schema builder registers them into ``page._other_groups`` keyed by the
    section id (``\"duration_control\"`` and ``\"check_point\"``).  This helper
    simply resolves those QGroupBox instances and attaches them to the page as
    ``_duration_control_group`` and ``_check_point_group`` so that controller
    logic can compose stability layouts without duplicating lookup code.
    """
    other_groups = getattr(page, "_other_groups", None)
    if not isinstance(other_groups, dict):
        return

    setattr(page, "_duration_control_group", other_groups.get("duration_control"))
    setattr(page, "_check_point_group", other_groups.get("check_point"))


def compose_stability_groups(page: Any, active_entry: ScriptConfigEntry | None) -> list[QGroupBox]:
    """Combine shared stability controls with the active script group.

    """
    groups: list[QGroupBox] = []
    # Shared Duration / Check Point groups.
    duration_group = getattr(page, "_duration_control_group", None)
    if isinstance(duration_group, QGroupBox):
        groups.append(duration_group)
    check_point_group = getattr(page, "_check_point_group", None)
    if isinstance(check_point_group, QGroupBox):
        groups.append(check_point_group)
    # Optional \"Selected Test Case\" group defined in the stability UI schema.
    other_groups = getattr(page, "_other_groups", None)
    if isinstance(other_groups, dict):
        selected_group = other_groups.get("stability_text_case")
        if isinstance(selected_group, QGroupBox):
            groups.append(selected_group)
    # Active script-specific group (e.g. test_str / test_switch_wifi).
    if isinstance(active_entry, ScriptConfigEntry) and isinstance(active_entry.group, QGroupBox):
        groups.append(active_entry.group)
    return groups


def register_switch_wifi_csv_combo(page: Any, combo: ComboBox) -> None:
    """Register a switch‑Wi‑Fi router CSV combo with the shared RvR proxy."""
    _register_switch_wifi_csv_combo(page, combo)


def unregister_switch_wifi_csv_combo(page: Any, combo: ComboBox) -> None:
    """Unregister a switch‑Wi‑Fi router CSV combo from the shared RvR proxy."""
    _unregister_switch_wifi_csv_combo(page, combo)


__all__ = [
    "ConfigView",
    "SwitchWifiManualEditor",
    "SwitchWifiCsvPreview",
    "RfStepSegmentsWidget",
    "init_stability_common_groups",
    "compose_stability_groups",
    "register_switch_wifi_csv_combo",
    "unregister_switch_wifi_csv_combo",
]
