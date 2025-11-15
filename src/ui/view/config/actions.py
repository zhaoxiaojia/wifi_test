"""UI action helpers for the Config page.

These functions live in the *view* layer and encapsulate pure UI behaviour
for CaseConfigPage and ConfigView (show/hide groups, enable/disable fields,
update step indicators, etc.).  Controllers should delegate visual tweaks
to these helpers instead of hard-coding widget manipulation.
"""

from __future__ import annotations

from typing import Any

from PyQt5.QtWidgets import QWidget

from src.util.constants import TURN_TABLE_MODEL_OTHER


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
                # Fall through to try other variants
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


__all__ = [
    "update_step_indicator",
    "apply_rf_model_ui_state",
    "apply_rvr_tool_ui_state",
    "apply_serial_enabled_ui_state",
    "apply_turntable_model_ui_state",
    "apply_run_lock_ui_state",
]

