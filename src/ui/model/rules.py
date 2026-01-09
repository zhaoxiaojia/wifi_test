#!/usr/bin/env python
# encoding: utf-8
"""
Declarative UI interaction rules for the Config page.

This module lives in the *model* layer (``src/ui/model``).  It exposes a
single rule engine based on ``SimpleRuleSpec`` so that all view/controller
code can drive widget state without hard‑coding if/else logic in the UI.

The design is intentionally small:

- Rules are stored in ``CUSTOM_SIMPLE_UI_RULES`` as ``SimpleRuleSpec``.
- Views expose a UI adapter implementing ``show``, ``hide``, ``enable``,
  ``disable``, ``set_value`` and ``set_options``.
- ``apply_rules`` executes rules for a given trigger field.
- ``evaluate_all_rules`` is the unified entry point used by views and
  controllers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional
import logging
import os

from PyQt5.QtCore import QSignalBlocker

from src.util.constants import TURN_TABLE_MODEL_OTHER


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def normalize_connect_type_label(label: str) -> str:
    """Normalize a raw connect-type label to a canonical value."""
    text = (label or "").strip()
    lowered = text.lower()
    if lowered in {"android", "adb"}:
        return "Android"
    if lowered in {"linux", "telnet"}:
        return "Linux"
    return text


def current_connect_type(page: Any) -> str:
    """Return the canonical connect type for the given page (best-effort)."""
    try:
        if hasattr(page, "_current_connect_type"):
            return page._current_connect_type() or ""
        combo = getattr(page, "connect_type_combo", None)
        if combo is None:
            return ""
        data = combo.currentData()
        if isinstance(data, str) and data.strip():
            return data.strip()
        text = combo.currentText()
        return normalize_connect_type_label(text) if isinstance(text, str) else ""
    except Exception:
        return ""


def needs_throughput(values: Mapping[str, Any]) -> bool:
    """Return whether the selected testcase requires traffic generation."""

    return bool(
        values.get("testcase.is_peak_throughput")
        or values.get("testcase.is_performance")
        or values.get("testcase.is_rvr")
        or values.get("testcase.is_rvo")
        or values.get("testcase.is_stability")
        or values.get("testcase.is_compatibility")
    )


def _value_as_bool(values: Dict[str, Any], key: str) -> bool:
    """Best-effort conversion of a mixed-type field value into bool."""
    v = values.get(key)
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        return v.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _serial_port_option_labels() -> List[str]:
    """Return a list of serial-port labels suitable for combo options."""
    try:
        from src.ui.controller import list_serial_ports

        ports = list_serial_ports()
    except Exception:
        logging.debug("Failed to enumerate serial ports in rules", exc_info=True)
        ports = []

    labels: List[str] = []
    for p in ports:
        if isinstance(p, (list, tuple)) and len(p) > 1:
            labels.append(p[1])
        else:
            labels.append(str(p))

    if not labels:
        # Provide a user-visible hint rather than an empty combo box.
        labels.append("No serial ports detected")
    return labels


# ---------------------------------------------------------------------------
# Simple rule engine
# ---------------------------------------------------------------------------

@dataclass
class SimpleFieldEffect:
    """
    Describe a UI effect applied to a target field when a rule is triggered.

    Parameters
    ----------
    target_field:
        Dotted key identifying the field widget to affect (e.g. ``"rvr.tool"``).
    action:
        One of ``"show"``, ``"hide"``, ``"enable"``, ``"disable"``,
        ``"set_value"``, or ``"set_options"``.
    value:
        Optional static value or callable providing the value for
        ``set_value`` / ``set_options`` actions.
    condition:
        Optional predicate receiving the full value map; the effect is only
        applied when the predicate returns True.
    """

    target_field: str
    action: str
    value: Optional[Any] = None
    condition: Optional[Callable[[Dict[str, Any]], bool]] = None


@dataclass
class SimpleRuleSpec:
    """
    High level description of a simple UI rule.

    Parameters
    ----------
    trigger_field:
        Dotted key for the field whose change should trigger this rule.
    effects:
        List of :class:`SimpleFieldEffect` to apply when the rule fires.
    """

    trigger_field: str
    effects: List[SimpleFieldEffect]


# Registry of custom simple rules.  All UI behaviour is described here.
CUSTOM_SIMPLE_UI_RULES: List[SimpleRuleSpec] = []

# Testcase-specific rules generated at runtime.  These are applied before the
# global `CUSTOM_SIMPLE_UI_RULES` so testcase-scoped enable/disable rules can
# override static behaviour when a test case is selected.
CUSTOM_TESTCASE_UI_RULES: List[SimpleRuleSpec] = []


# ---------------------------------------------------------------------------
# Rule declarations
# ---------------------------------------------------------------------------

# 1) RvR tool selection (iperf vs ixchariot).
CUSTOM_SIMPLE_UI_RULES.append(
    SimpleRuleSpec(
        trigger_field="rvr.tool",
        effects=[
            # IxChariot path editable only when tool is ixchariot.
            SimpleFieldEffect(
                target_field="rvr.ixchariot.path",
                action="enable",
                condition=lambda values: values.get("rvr.tool") == "ixchariot",
            ),
            SimpleFieldEffect(
                target_field="rvr.ixchariot.path",
                action="disable",
                condition=lambda values: values.get("rvr.tool") != "ixchariot",
            ),
        ],
    )
)


# 2) RF Solution model -> field visibility.
CUSTOM_SIMPLE_UI_RULES.append(
    SimpleRuleSpec(
        trigger_field="rf_solution.model",
        effects=[
            # RC4DAT-8G-95 fields
            SimpleFieldEffect(
                target_field="rf_solution.RC4DAT-8G-95.idVendor",
                action="show",
                condition=lambda values: values.get("rf_solution.model") == "RC4DAT-8G-95",
            ),
            SimpleFieldEffect(
                target_field="rf_solution.RC4DAT-8G-95.idVendor",
                action="hide",
                condition=lambda values: values.get("rf_solution.model") != "RC4DAT-8G-95",
            ),
            SimpleFieldEffect(
                target_field="rf_solution.RC4DAT-8G-95.idProduct",
                action="show",
                condition=lambda values: values.get("rf_solution.model") == "RC4DAT-8G-95",
            ),
            SimpleFieldEffect(
                target_field="rf_solution.RC4DAT-8G-95.idProduct",
                action="hide",
                condition=lambda values: values.get("rf_solution.model") != "RC4DAT-8G-95",
            ),
            SimpleFieldEffect(
                target_field="rf_solution.RC4DAT-8G-95.ip_address",
                action="show",
                condition=lambda values: values.get("rf_solution.model") == "RC4DAT-8G-95",
            ),
            SimpleFieldEffect(
                target_field="rf_solution.RC4DAT-8G-95.ip_address",
                action="hide",
                condition=lambda values: values.get("rf_solution.model") != "RC4DAT-8G-95",
            ),
            # RADIORACK-4-220 field
            SimpleFieldEffect(
                target_field="rf_solution.RADIORACK-4-220.ip_address",
                action="show",
                condition=lambda values: values.get("rf_solution.model") == "RADIORACK-4-220",
            ),
            SimpleFieldEffect(
                target_field="rf_solution.RADIORACK-4-220.ip_address",
                action="hide",
                condition=lambda values: values.get("rf_solution.model") != "RADIORACK-4-220",
            ),
            # LDA-908V-8 fields
            SimpleFieldEffect(
                target_field="rf_solution.LDA-908V-8.ip_address",
                action="show",
                condition=lambda values: values.get("rf_solution.model") == "LDA-908V-8",
            ),
            SimpleFieldEffect(
                target_field="rf_solution.LDA-908V-8.ip_address",
                action="hide",
                condition=lambda values: values.get("rf_solution.model") != "LDA-908V-8",
            ),
            SimpleFieldEffect(
                target_field="rf_solution.LDA-908V-8.channels",
                action="show",
                condition=lambda values: values.get("rf_solution.model") == "LDA-908V-8",
            ),
            SimpleFieldEffect(
                target_field="rf_solution.LDA-908V-8.channels",
                action="hide",
                condition=lambda values: values.get("rf_solution.model") != "LDA-908V-8",
            ),
        ],
    )
)


# 3) Turntable model -> IP visibility and enabled state.
CUSTOM_SIMPLE_UI_RULES.append(
    SimpleRuleSpec(
        trigger_field="Turntable.model",
        effects=[
            SimpleFieldEffect(
                target_field="Turntable.ip_address",
                action="show",
                condition=lambda values: values.get("Turntable.model") == TURN_TABLE_MODEL_OTHER,
            ),
            SimpleFieldEffect(
                target_field="Turntable.ip_address",
                action="enable",
                condition=lambda values: values.get("Turntable.model") == TURN_TABLE_MODEL_OTHER,
            ),
            SimpleFieldEffect(
                target_field="Turntable.ip_address",
                action="hide",
                condition=lambda values: values.get("Turntable.model") != TURN_TABLE_MODEL_OTHER,
            ),
            SimpleFieldEffect(
                target_field="Turntable.ip_address",
                action="disable",
                condition=lambda values: values.get("Turntable.model") != TURN_TABLE_MODEL_OTHER,
            ),
        ],
    )
)


# 4) Control Type (Android / Linux) driving connect_type.* and system.* fields.
CUSTOM_SIMPLE_UI_RULES.append(
    SimpleRuleSpec(
        trigger_field="connect_type.type",
        effects=[
            # Android branch
            SimpleFieldEffect(
                target_field="connect_type.Android.device",
                action="enable",
                condition=lambda values: normalize_connect_type_label(
                    str(values.get("connect_type.type") or "")
                )
                == "Android",
            ),
            SimpleFieldEffect(
                target_field="connect_type.Linux.ip",
                action="disable",
                condition=lambda values: normalize_connect_type_label(
                    str(values.get("connect_type.type") or "")
                )
                == "Android",
            ),
            SimpleFieldEffect(
                target_field="system.version",
                action="show",
                condition=lambda values: normalize_connect_type_label(
                    str(values.get("connect_type.type") or "")
                )
                == "Android",
            ),
            SimpleFieldEffect(
                target_field="system.version",
                action="enable",
                condition=lambda values: normalize_connect_type_label(
                    str(values.get("connect_type.type") or "")
                )
                == "Android",
            ),
            SimpleFieldEffect(
                target_field="system.kernel_version",
                action="show",
                condition=lambda values: normalize_connect_type_label(
                    str(values.get("connect_type.type") or "")
                )
                == "Android",
            ),
            SimpleFieldEffect(
                target_field="system.kernel_version",
                action="disable",
                condition=lambda values: normalize_connect_type_label(
                    str(values.get("connect_type.type") or "")
                )
                == "Android",
            ),
            # Linux branch
            SimpleFieldEffect(
                target_field="connect_type.Linux.ip",
                action="enable",
                condition=lambda values: normalize_connect_type_label(
                    str(values.get("connect_type.type") or "")
                )
                == "Linux",
            ),
            SimpleFieldEffect(
                target_field="connect_type.Android.device",
                action="disable",
                condition=lambda values: normalize_connect_type_label(
                    str(values.get("connect_type.type") or "")
                )
                == "Linux",
            ),
            SimpleFieldEffect(
                target_field="system.version",
                action="hide",
                condition=lambda values: normalize_connect_type_label(
                    str(values.get("connect_type.type") or "")
                )
                == "Linux",
            ),
            SimpleFieldEffect(
                target_field="system.kernel_version",
                action="show",
                condition=lambda values: normalize_connect_type_label(
                    str(values.get("connect_type.type") or "")
                )
                == "Linux",
            ),
            SimpleFieldEffect(
                target_field="system.kernel_version",
                action="enable",
                condition=lambda values: normalize_connect_type_label(
                    str(values.get("connect_type.type") or "")
                )
                == "Linux",
            ),
        ],
    )
)


# 5) Third-party checkbox -> Wait seconds.
CUSTOM_SIMPLE_UI_RULES.append(
    SimpleRuleSpec(
        trigger_field="connect_type.third_party.enabled",
        effects=[
            SimpleFieldEffect(
                target_field="connect_type.third_party.wait_seconds",
                action="enable",
                condition=lambda values: _value_as_bool(values, "connect_type.third_party.enabled"),
            ),
            SimpleFieldEffect(
                target_field="connect_type.third_party.wait_seconds",
                action="disable",
                condition=lambda values: not _value_as_bool(values, "connect_type.third_party.enabled"),
            ),
        ],
    )
)


# 6) Serial Enabled -> Port/Baud.
CUSTOM_SIMPLE_UI_RULES.append(
    SimpleRuleSpec(
        trigger_field="serial_port.status",
        effects=[
            SimpleFieldEffect(
                target_field="serial_port.port",
                action="enable",
                condition=lambda values: _value_as_bool(values, "serial_port.status"),
            ),
            SimpleFieldEffect(
                target_field="serial_port.baud",
                action="enable",
                condition=lambda values: _value_as_bool(values, "serial_port.status"),
            ),
            SimpleFieldEffect(
                target_field="serial_port.port",
                action="disable",
                condition=lambda values: not _value_as_bool(values, "serial_port.status"),
            ),
            SimpleFieldEffect(
                target_field="serial_port.baud",
                action="disable",
                condition=lambda values: not _value_as_bool(values, "serial_port.status"),
            ),
            # Populate port options from system serial enumeration when status is enabled.
            SimpleFieldEffect(
                target_field="serial_port.port",
                action="set_options",
                value=lambda values: _serial_port_option_labels(),
            ),
        ],
    )
)

# 7) Stability Duration: exitfirst -> Retry count editable.
# CUSTOM_SIMPLE_UI_RULES.append(
#     SimpleRuleSpec(
#         trigger_field="duration_control.exitfirst",
#         effects=[
#             SimpleFieldEffect(
#                 target_field="duration_control.retry_limit",
#                 action="enable",
#                 condition=lambda values: _value_as_bool(values, "duration_control.exitfirst"),
#             ),
#             SimpleFieldEffect(
#                 target_field="duration_control.retry_limit",
#                 action="disable",
#                 condition=lambda values: not _value_as_bool(values, "duration_control.exitfirst"),
#             ),
#         ],
#     )
# )


# 8) Stability Check Point: ping checkbox -> ping_targets editable.
CUSTOM_SIMPLE_UI_RULES.append(
    SimpleRuleSpec(
        trigger_field="check_point.ping",
        effects=[
            SimpleFieldEffect(
                target_field="check_point.ping_targets",
                action="enable",
                condition=lambda values: _value_as_bool(values, "check_point.ping"),
            ),
            SimpleFieldEffect(
                target_field="check_point.ping_targets",
                action="disable",
                condition=lambda values: not _value_as_bool(values, "check_point.ping"),
            ),
        ],
    )
)


# 9) Combined stability (test_switch_wifi_str): AC/STR section enabled flags.
CUSTOM_SIMPLE_UI_RULES.append(
    SimpleRuleSpec(
        trigger_field="stability.cases.test_switch_wifi_str.ac.enabled",
        effects=[
            # When AC is enabled, all AC fields are editable.
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.ac.on_duration",
                action="enable",
                condition=lambda values: _value_as_bool(values, "stability.cases.test_switch_wifi_str.ac.enabled"),
            ),
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.ac.off_duration",
                action="enable",
                condition=lambda values: _value_as_bool(values, "stability.cases.test_switch_wifi_str.ac.enabled"),
            ),
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.ac.relay_type",
                action="enable",
                condition=lambda values: _value_as_bool(values, "stability.cases.test_switch_wifi_str.ac.enabled"),
            ),
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.ac.port",
                action="enable",
                condition=lambda values: _value_as_bool(values, "stability.cases.test_switch_wifi_str.ac.enabled"),
            ),
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.ac.mode",
                action="enable",
                condition=lambda values: _value_as_bool(values, "stability.cases.test_switch_wifi_str.ac.enabled"),
            ),
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.ac.relay_params",
                action="enable",
                condition=lambda values: _value_as_bool(values, "stability.cases.test_switch_wifi_str.ac.enabled"),
            ),
            # When AC is disabled, all AC fields are disabled.
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.ac.on_duration",
                action="disable",
                condition=lambda values: not _value_as_bool(values, "stability.cases.test_switch_wifi_str.ac.enabled"),
            ),
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.ac.off_duration",
                action="disable",
                condition=lambda values: not _value_as_bool(values, "stability.cases.test_switch_wifi_str.ac.enabled"),
            ),
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.ac.relay_type",
                action="disable",
                condition=lambda values: not _value_as_bool(values, "stability.cases.test_switch_wifi_str.ac.enabled"),
            ),
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.ac.port",
                action="disable",
                condition=lambda values: not _value_as_bool(values, "stability.cases.test_switch_wifi_str.ac.enabled"),
            ),
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.ac.mode",
                action="disable",
                condition=lambda values: not _value_as_bool(values, "stability.cases.test_switch_wifi_str.ac.enabled"),
            ),
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.ac.relay_params",
                action="disable",
                condition=lambda values: not _value_as_bool(values, "stability.cases.test_switch_wifi_str.ac.enabled"),
            ),
        ],
    )
)

CUSTOM_SIMPLE_UI_RULES.append(
    SimpleRuleSpec(
        trigger_field="stability.cases.test_switch_wifi_str.str.enabled",
        effects=[
            # STR branch enabled -> STR fields editable.
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.str.on_duration",
                action="enable",
                condition=lambda values: _value_as_bool(values, "stability.cases.test_switch_wifi_str.str.enabled"),
            ),
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.str.off_duration",
                action="enable",
                condition=lambda values: _value_as_bool(values, "stability.cases.test_switch_wifi_str.str.enabled"),
            ),
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.str.relay_type",
                action="enable",
                condition=lambda values: _value_as_bool(values, "stability.cases.test_switch_wifi_str.str.enabled"),
            ),
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.str.port",
                action="enable",
                condition=lambda values: _value_as_bool(values, "stability.cases.test_switch_wifi_str.str.enabled"),
            ),
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.str.mode",
                action="enable",
                condition=lambda values: _value_as_bool(values, "stability.cases.test_switch_wifi_str.str.enabled"),
            ),
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.str.relay_params",
                action="enable",
                condition=lambda values: _value_as_bool(values, "stability.cases.test_switch_wifi_str.str.enabled"),
            ),
            # STR branch disabled -> STR fields disabled.
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.str.on_duration",
                action="disable",
                condition=lambda values: not _value_as_bool(values, "stability.cases.test_switch_wifi_str.str.enabled"),
            ),
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.str.off_duration",
                action="disable",
                condition=lambda values: not _value_as_bool(values, "stability.cases.test_switch_wifi_str.str.enabled"),
            ),
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.str.relay_type",
                action="disable",
                condition=lambda values: not _value_as_bool(values, "stability.cases.test_switch_wifi_str.str.enabled"),
            ),
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.str.port",
                action="disable",
                condition=lambda values: not _value_as_bool(values, "stability.cases.test_switch_wifi_str.str.enabled"),
            ),
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.str.mode",
                action="disable",
                condition=lambda values: not _value_as_bool(values, "stability.cases.test_switch_wifi_str.str.enabled"),
            ),
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.str.relay_params",
                action="disable",
                condition=lambda values: not _value_as_bool(values, "stability.cases.test_switch_wifi_str.str.enabled"),
            ),
        ],
    )
)


# 10) test_switch_wifi_str Relay Type -> USB vs relay params (AC and STR branches).
CUSTOM_SIMPLE_UI_RULES.append(
    SimpleRuleSpec(
        trigger_field="stability.cases.test_switch_wifi_str.ac.relay_type",
        effects=[
            # usb_relay -> enable port/mode, disable relay_params.
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.ac.port",
                action="enable",
                condition=lambda values: values.get("stability.cases.test_switch_wifi_str.ac.relay_type") == "usb_relay"
                and _value_as_bool(values, "stability.cases.test_switch_wifi_str.ac.enabled"),
            ),
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.ac.port",
                action="set_options",
                value=lambda values: _serial_port_option_labels(),
                condition=lambda values: values.get("stability.cases.test_switch_wifi_str.ac.relay_type") == "usb_relay"
                and _value_as_bool(values, "stability.cases.test_switch_wifi_str.ac.enabled"),
            ),
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.ac.mode",
                action="enable",
                condition=lambda values: values.get("stability.cases.test_switch_wifi_str.ac.relay_type") == "usb_relay"
                and _value_as_bool(values, "stability.cases.test_switch_wifi_str.ac.enabled"),
            ),
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.ac.relay_params",
                action="disable",
                condition=lambda values: values.get("stability.cases.test_switch_wifi_str.ac.relay_type") == "usb_relay"
                and _value_as_bool(values, "stability.cases.test_switch_wifi_str.ac.enabled"),
            ),
            # GWGJ-XC3012 -> disable port/mode, enable relay_params.
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.ac.port",
                action="disable",
                condition=lambda values: values.get("stability.cases.test_switch_wifi_str.ac.relay_type")
                == "GWGJ-XC3012",
            ),
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.ac.mode",
                action="disable",
                condition=lambda values: values.get("stability.cases.test_switch_wifi_str.ac.relay_type")
                == "GWGJ-XC3012",
            ),
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.ac.relay_params",
                action="enable",
                condition=lambda values: values.get("stability.cases.test_switch_wifi_str.ac.relay_type")
                == "GWGJ-XC3012"
                and _value_as_bool(values, "stability.cases.test_switch_wifi_str.ac.enabled"),
            ),
        ],
    )
)

CUSTOM_SIMPLE_UI_RULES.append(
    SimpleRuleSpec(
        trigger_field="stability.cases.test_switch_wifi_str.str.relay_type",
        effects=[
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.str.port",
                action="enable",
                condition=lambda values: values.get("stability.cases.test_switch_wifi_str.str.relay_type") == "usb_relay"
                and _value_as_bool(values, "stability.cases.test_switch_wifi_str.str.enabled"),
            ),
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.str.port",
                action="set_options",
                value=lambda values: _serial_port_option_labels(),
                condition=lambda values: values.get("stability.cases.test_switch_wifi_str.str.relay_type") == "usb_relay"
                and _value_as_bool(values, "stability.cases.test_switch_wifi_str.str.enabled"),
            ),
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.str.mode",
                action="enable",
                condition=lambda values: values.get("stability.cases.test_switch_wifi_str.str.relay_type") == "usb_relay"
                and _value_as_bool(values, "stability.cases.test_switch_wifi_str.str.enabled"),
            ),
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.str.relay_params",
                action="disable",
                condition=lambda values: values.get("stability.cases.test_switch_wifi_str.str.relay_type") == "usb_relay"
                and _value_as_bool(values, "stability.cases.test_switch_wifi_str.str.enabled"),
            ),
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.str.port",
                action="disable",
                condition=lambda values: values.get("stability.cases.test_switch_wifi_str.str.relay_type")
                == "GWGJ-XC3012",
            ),
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.str.mode",
                action="disable",
                condition=lambda values: values.get("stability.cases.test_switch_wifi_str.str.relay_type")
                == "GWGJ-XC3012",
            ),
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.str.relay_params",
                action="enable",
                condition=lambda values: values.get("stability.cases.test_switch_wifi_str.str.relay_type")
                == "GWGJ-XC3012"
                and _value_as_bool(values, "stability.cases.test_switch_wifi_str.str.enabled"),
            ),
        ],
    )
)


# ---------------------------------------------------------------------------
# Rule engine API
# ---------------------------------------------------------------------------

# Testcase-scoped rules: these rules use the injected ``testcase.*`` context
# (see ``evaluate_all_rules``) to enable/disable whole groups of fields based
# on the selected script.  This expresses the same behaviour that used to
# live in controller-side EditableInfo helpers.
CUSTOM_TESTCASE_UI_RULES.append(
    SimpleRuleSpec(
        trigger_field="testcase.selection",
        effects=[
            # Always-editable DUT fields: connect_type / router / serial / project / system.
            SimpleFieldEffect(
                target_field="connect_type.type",
                action="enable",
                condition=lambda values: not str(values.get("project.project") or "").strip(),
            ),
            SimpleFieldEffect(
                target_field="connect_type.Android.device",
                action="enable",
                condition=lambda values: normalize_connect_type_label(
                    str(values.get("connect_type.type") or "")
                )
                == "Android",
            ),
            SimpleFieldEffect(
                target_field="connect_type.Linux.ip",
                action="enable",
                condition=lambda values: normalize_connect_type_label(
                    str(values.get("connect_type.type") or "")
                )
                == "Linux",
            ),
            SimpleFieldEffect(
                target_field="connect_type.Linux.wildcard",
                action="enable",
                condition=lambda values: normalize_connect_type_label(
                    str(values.get("connect_type.type") or "")
                )
                == "Linux",
            ),
            SimpleFieldEffect(
                target_field="connect_type.third_party.enabled",
                action="enable",
                condition=lambda values: True,
            ),
            SimpleFieldEffect(
                target_field="connect_type.third_party.wait_seconds",
                action="enable",
                condition=lambda values: True,
            ),
            SimpleFieldEffect(
                target_field="project.customer",
                action="enable",
                condition=lambda values: True,
            ),
            SimpleFieldEffect(
                target_field="project.product_line",
                action="enable",
                condition=lambda values: True,
            ),
            SimpleFieldEffect(
                target_field="project.project",
                action="enable",
                condition=lambda values: True,
            ),
            SimpleFieldEffect(
                target_field="system.version",
                action="enable",
                condition=lambda values: True,
            ),
            SimpleFieldEffect(
                target_field="system.kernel_version",
                action="enable",
                condition=lambda values: True,
            ),
            SimpleFieldEffect(
                target_field="router.name",
                action="enable",
                condition=lambda values: True,
            ),
            SimpleFieldEffect(
                target_field="router.address",
                action="enable",
                condition=lambda values: True,
            ),
            SimpleFieldEffect(
                target_field="serial_port.status",
                action="enable",
                condition=lambda values: True,
            ),
            SimpleFieldEffect(
                target_field="serial_port.port",
                action="enable",
                condition=lambda values: True,
            ),
            SimpleFieldEffect(
                target_field="serial_port.baud",
                action="enable",
                condition=lambda values: True,
            ),
            # Debug Options: these checkboxes should always be user-editable.
            SimpleFieldEffect(
                target_field="debug.database_mode",
                action="enable",
                condition=lambda values: True,
            ),
            SimpleFieldEffect(
                target_field="debug.skip_router",
                action="enable",
                condition=lambda values: True,
            ),
            SimpleFieldEffect(
                target_field="debug.skip_connect",
                action="enable",
                condition=lambda values: True,
            ),
              SimpleFieldEffect(
                  target_field="debug.skip_corner_rf",
                  action="enable",
                  condition=lambda values: True,
              ),

              # `test_switch_wifi` controls should always be user-editable
              # when the script group is visible.
              SimpleFieldEffect(
                  target_field="stability.cases.test_switch_wifi_str.use_router",
                  action="enable",
                  condition=lambda values: True,
              ),
              SimpleFieldEffect(
                  target_field="stability.cases.test_switch_wifi_str.manual_entries",
                  action="enable",
                  condition=lambda values: True,
              ),
            # `test_str` AC/STR enable checkboxes should always be user-editable
            # when the group is visible; testcase rules must not lock them out.
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.ac.enabled",
                action="enable",
                condition=lambda values: True,
            ),
            SimpleFieldEffect(
                target_field="stability.cases.test_switch_wifi_str.str.enabled",
                action="enable",
                condition=lambda values: True,
            ),
            # ------------------------------------------------------------------
            # Always-disabled DUT detail fields (not part of the editable
            # surface in the original EditableInfo logic).
            # ------------------------------------------------------------------
            SimpleFieldEffect(
                target_field="software_info.software_version",
                action="disable",
                condition=lambda values: True,
            ),
            SimpleFieldEffect(
                target_field="software_info.driver_version",
                action="disable",
                condition=lambda values: True,
            ),
            SimpleFieldEffect(
                target_field="hardware_info.hardware_version",
                action="disable",
                condition=lambda values: True,
            ),
            SimpleFieldEffect(
                target_field="project.main_chip",
                action="disable",
                condition=lambda values: True,
            ),
            SimpleFieldEffect(
                target_field="project.wifi_module",
                action="disable",
                condition=lambda values: True,
            ),
            SimpleFieldEffect(
                target_field="project.interface",
                action="disable",
                condition=lambda values: True,
            ),
            # ------------------------------------------------------------------
            # Throughput generator fields shared across test types.
            # ------------------------------------------------------------------
            # RvR base controls (any testcase that needs throughput measurements).
            SimpleFieldEffect(
                target_field="rvr.tool",
                action="enable",
                condition=needs_throughput,
            ),
            SimpleFieldEffect(
                target_field="rvr.iperf.path",
                action="enable",
                condition=needs_throughput,
            ),
            SimpleFieldEffect(
                target_field="rvr.iperf.server_cmd",
                action="enable",
                condition=needs_throughput,
            ),
            SimpleFieldEffect(
                target_field="rvr.iperf.client_cmd",
                action="enable",
                condition=needs_throughput,
            ),
            SimpleFieldEffect(
                target_field="rvr.ixchariot.path",
                action="enable",
                condition=needs_throughput,
            ),
            SimpleFieldEffect(
                target_field="rvr.repeat",
                action="enable",
                condition=needs_throughput,
            ),
            # Throughput threshold: all performance cases.
            SimpleFieldEffect(
                target_field="rvr.throughput_threshold",
                action="enable",
                condition=lambda values: bool(values.get("testcase.is_performance")),
            ),
            # ------------------------------------------------------------------
            # Compatibility Settings fields.
            # ------------------------------------------------------------------
            # NIC selection and power‑relay configuration are only editable
            # for compatibility testcases; keep them disabled otherwise.
            SimpleFieldEffect(
                target_field="compatibility.nic",
                action="enable",
                condition=lambda values: bool(values.get("testcase.is_compatibility")),
            ),
            SimpleFieldEffect(
                target_field="compatibility.nic",
                action="disable",
                condition=lambda values: not bool(values.get("testcase.is_compatibility")),
            ),
            SimpleFieldEffect(
                target_field="compatibility.power_ctrl.relays",
                action="enable",
                condition=lambda values: bool(values.get("testcase.is_compatibility")),
            ),
            SimpleFieldEffect(
                target_field="compatibility.power_ctrl.relays",
                action="disable",
                condition=lambda values: not bool(values.get("testcase.is_compatibility")),
            ),
            # Disable RvR fields when throughput inputs are not required.
            SimpleFieldEffect(
                target_field="rvr.tool",
                action="disable",
                condition=lambda values: not needs_throughput(values),
            ),
            SimpleFieldEffect(
                target_field="rvr.iperf.path",
                action="disable",
                condition=lambda values: not needs_throughput(values),
            ),
            SimpleFieldEffect(
                target_field="rvr.iperf.server_cmd",
                action="disable",
                condition=lambda values: not needs_throughput(values),
            ),
            SimpleFieldEffect(
                target_field="rvr.iperf.client_cmd",
                action="disable",
                condition=lambda values: not needs_throughput(values),
            ),
            SimpleFieldEffect(
                target_field="rvr.ixchariot.path",
                action="disable",
                condition=lambda values: not needs_throughput(values),
            ),
            SimpleFieldEffect(
                target_field="rvr.repeat",
                action="disable",
                condition=lambda values: not needs_throughput(values),
            ),
            SimpleFieldEffect(
                target_field="rvr.throughput_threshold",
                action="disable",
                condition=lambda values: not bool(values.get("testcase.is_performance")),
            ),
            # ------------------------------------------------------------------
            # RF solution / Turntable fields: RvO and RvR cases.
            # ------------------------------------------------------------------
            # Turntable fields: only RvO cases.
            SimpleFieldEffect(
                target_field="Turntable.model",
                action="enable",
                condition=lambda values: bool(values.get("testcase.is_rvo")),
            ),
            SimpleFieldEffect(
                target_field="Turntable.ip_address",
                action="enable",
                condition=lambda values: bool(values.get("testcase.is_rvo")),
            ),
            SimpleFieldEffect(
                target_field="Turntable.step",
                action="enable",
                condition=lambda values: bool(values.get("testcase.is_rvo")),
            ),
            SimpleFieldEffect(
                target_field="Turntable.static_db",
                action="enable",
                condition=lambda values: bool(values.get("testcase.is_rvo")),
            ),
            SimpleFieldEffect(
                target_field="Turntable.target_rssi",
                action="enable",
                condition=lambda values: bool(values.get("testcase.is_rvo")),
            ),
            SimpleFieldEffect(
                target_field="Turntable.model",
                action="disable",
                condition=lambda values: not bool(values.get("testcase.is_rvo")),
            ),
            SimpleFieldEffect(
                target_field="Turntable.ip_address",
                action="disable",
                condition=lambda values: not bool(values.get("testcase.is_rvo")),
            ),
            SimpleFieldEffect(
                target_field="Turntable.step",
                action="disable",
                condition=lambda values: not bool(values.get("testcase.is_rvo")),
            ),
            SimpleFieldEffect(
                target_field="Turntable.static_db",
                action="disable",
                condition=lambda values: not bool(values.get("testcase.is_rvo")),
            ),
            SimpleFieldEffect(
                target_field="Turntable.target_rssi",
                action="disable",
                condition=lambda values: not bool(values.get("testcase.is_rvo")),
            ),
            # RF solution fields: RvO and RvR cases.
            SimpleFieldEffect(
                target_field="rf_solution.step",
                action="enable",
                condition=lambda values: bool(
                    values.get("testcase.is_rvo") or values.get("testcase.is_rvr")
                ),
            ),
            SimpleFieldEffect(
                target_field="rf_solution.model",
                action="enable",
                condition=lambda values: bool(
                    values.get("testcase.is_rvo") or values.get("testcase.is_rvr")
                ),
            ),
            SimpleFieldEffect(
                target_field="rf_solution.RC4DAT-8G-95.idVendor",
                action="enable",
                condition=lambda values: bool(
                    values.get("testcase.is_rvo") or values.get("testcase.is_rvr")
                ),
            ),
            SimpleFieldEffect(
                target_field="rf_solution.RC4DAT-8G-95.idProduct",
                action="enable",
                condition=lambda values: bool(
                    values.get("testcase.is_rvo") or values.get("testcase.is_rvr")
                ),
            ),
            SimpleFieldEffect(
                target_field="rf_solution.RC4DAT-8G-95.ip_address",
                action="enable",
                condition=lambda values: bool(
                    values.get("testcase.is_rvo") or values.get("testcase.is_rvr")
                ),
            ),
            SimpleFieldEffect(
                target_field="rf_solution.RADIORACK-4-220.ip_address",
                action="enable",
                condition=lambda values: bool(
                    values.get("testcase.is_rvo") or values.get("testcase.is_rvr")
                ),
            ),
            SimpleFieldEffect(
                target_field="rf_solution.LDA-908V-8.ip_address",
                action="enable",
                condition=lambda values: bool(
                    values.get("testcase.is_rvo") or values.get("testcase.is_rvr")
                ),
            ),
            SimpleFieldEffect(
                target_field="rf_solution.LDA-908V-8.channels",
                action="enable",
                condition=lambda values: bool(
                    values.get("testcase.is_rvo") or values.get("testcase.is_rvr")
                ),
            ),
            SimpleFieldEffect(
                target_field="rf_solution.step",
                action="disable",
                condition=lambda values: not bool(
                    values.get("testcase.is_rvo") or values.get("testcase.is_rvr")
                ),
            ),
            SimpleFieldEffect(
                target_field="rf_solution.model",
                action="disable",
                condition=lambda values: not bool(
                    values.get("testcase.is_rvo") or values.get("testcase.is_rvr")
                ),
            ),
            SimpleFieldEffect(
                target_field="rf_solution.RC4DAT-8G-95.idVendor",
                action="disable",
                condition=lambda values: not bool(
                    values.get("testcase.is_rvo") or values.get("testcase.is_rvr")
                ),
            ),
            SimpleFieldEffect(
                target_field="rf_solution.RC4DAT-8G-95.idProduct",
                action="disable",
                condition=lambda values: not bool(
                    values.get("testcase.is_rvo") or values.get("testcase.is_rvr")
                ),
            ),
            SimpleFieldEffect(
                target_field="rf_solution.RC4DAT-8G-95.ip_address",
                action="disable",
                condition=lambda values: not bool(
                    values.get("testcase.is_rvo") or values.get("testcase.is_rvr")
                ),
            ),
            SimpleFieldEffect(
                target_field="rf_solution.RADIORACK-4-220.ip_address",
                action="disable",
                condition=lambda values: not bool(
                    values.get("testcase.is_rvo") or values.get("testcase.is_rvr")
                ),
            ),
            SimpleFieldEffect(
                target_field="rf_solution.LDA-908V-8.ip_address",
                action="disable",
                condition=lambda values: not bool(
                    values.get("testcase.is_rvo") or values.get("testcase.is_rvr")
                ),
            ),
            SimpleFieldEffect(
                target_field="rf_solution.LDA-908V-8.channels",
                action="disable",
                condition=lambda values: not bool(
                    values.get("testcase.is_rvo") or values.get("testcase.is_rvr")
                ),
            ),
            # ------------------------------------------------------------------
            # Stability base fields (Duration Control & Check Point).
            # ------------------------------------------------------------------
            # SimpleFieldEffect(
            #     target_field="stability.duration_control.loop",
            #     action="enable",
            #     condition=lambda values: bool(values.get("testcase.is_stability")),
            # ),
            # SimpleFieldEffect(
            #     target_field="stability.duration_control.duration_hours",
            #     action="enable",
            #     condition=lambda values: bool(values.get("testcase.is_stability")),
            # ),
            # SimpleFieldEffect(
            #     target_field="stability.duration_control.exitfirst",
            #     action="enable",
            #     condition=lambda values: bool(values.get("testcase.is_stability")),
            # ),
            # SimpleFieldEffect(
            #     target_field="stability.duration_control.retry_limit",
            #     action="enable",
            #     condition=lambda values: bool(values.get("testcase.is_stability")),
            # ),
            SimpleFieldEffect(
                target_field="stability.check_point.ping",
                action="enable",
                condition=lambda values: bool(values.get("testcase.is_stability")),
            ),
            SimpleFieldEffect(
                target_field="stability.check_point.ping_targets",
                action="enable",
                condition=lambda values: bool(values.get("testcase.is_stability")),
            ),
            # SimpleFieldEffect(
            #     target_field="stability.duration_control.loop",
            #     action="disable",
            #     condition=lambda values: not bool(values.get("testcase.is_stability")),
            # ),
            # SimpleFieldEffect(
            #     target_field="stability.duration_control.duration_hours",
            #     action="disable",
            #     condition=lambda values: not bool(values.get("testcase.is_stability")),
            # ),
            # SimpleFieldEffect(
            #     target_field="stability.duration_control.exitfirst",
            #     action="disable",
            #     condition=lambda values: not bool(values.get("testcase.is_stability")),
            # ),
            # SimpleFieldEffect(
            #     target_field="stability.duration_control.retry_limit",
            #     action="disable",
            #     condition=lambda values: not bool(values.get("testcase.is_stability")),
            # ),
            SimpleFieldEffect(
                target_field="stability.check_point.ping",
                action="disable",
                condition=lambda values: not bool(values.get("testcase.is_stability")),
            ),
            SimpleFieldEffect(
                target_field="stability.check_point.ping_targets",
                action="disable",
                condition=lambda values: not bool(values.get("testcase.is_stability")),
            ),
        ],
    )
)

def apply_rules(
    trigger_field: str,
    values: Dict[str, Any],
    ui_adapter: Any,
    rules: Optional[List[SimpleRuleSpec]] = None,
) -> None:
    """
    Apply all matching simple UI rules for the given trigger field.

    Parameters
    ----------
    trigger_field:
        Name of the field that changed.
    values:
        Mapping of all known field keys to their current values.
    ui_adapter:
        An object implementing ``show``, ``hide``, ``enable``, ``disable``,
        ``set_value`` and ``set_options`` methods for field identifiers.
    """
    rule_source = rules if rules is not None else CUSTOM_SIMPLE_UI_RULES

    for rule in rule_source:
        if rule.trigger_field != trigger_field:
            continue
        for eff in rule.effects:
            if eff.condition is not None and not eff.condition(values):
                continue
            if eff.action == "show":
                ui_adapter.show(eff.target_field)
            elif eff.action == "hide":
                ui_adapter.hide(eff.target_field)
            elif eff.action == "enable":
                ui_adapter.enable(eff.target_field)
            elif eff.action == "disable":
                ui_adapter.disable(eff.target_field)
            elif eff.action == "set_value":
                val = eff.value(values) if callable(eff.value) else eff.value
                ui_adapter.set_value(eff.target_field, val)
            elif eff.action == "set_options":
                opts = eff.value(values) if callable(eff.value) else eff.value
                opts_list = list(opts) if opts is not None else []
                # Prefer adapter API when available.
                fn = getattr(ui_adapter, "set_options", None)
                if callable(fn):
                    try:
                        fn(eff.target_field, opts_list)
                    except Exception:
                        logging.debug("ui_adapter.set_options failed", exc_info=True)
                else:
                    # Fallback: try to update the underlying widget directly.
                    try:
                        field_widgets: Dict[str, Any] = getattr(ui_adapter, "field_widgets", {}) or {}
                        widget = field_widgets.get(eff.target_field)
                        if widget is not None and hasattr(widget, "clear") and hasattr(widget, "addItem"):
                            try:
                                widget.blockSignals(True)
                            except Exception:
                                pass
                            try:
                                widget.clear()
                                for opt in opts_list:
                                    widget.addItem(str(opt), str(opt))
                            finally:
                                try:
                                    widget.blockSignals(False)
                                except Exception:
                                    pass
                    except Exception:
                        logging.debug("Failed to apply set_options fallback", exc_info=True)


# ---------------------------------------------------------------------------
def evaluate_all_rules(
    page: Any,
    trigger_field: str | None = None,
    extra_rule_lists: Optional[List[List[SimpleRuleSpec]]] = None,
) -> None:
    """
    Evaluate all simple rules for the page.

    Parameters
    ----------
    page:
        The Config page instance (or adapter) exposing ``field_widgets`` and
        UIAdapter methods used by simple rules.
    trigger_field:
        Optional field identifier that has just changed.  When provided, only
        rules for that field are executed; when ``None``, rules for all
        trigger fields are evaluated using the current widget values.
    """
    field_widgets: Dict[str, Any] = getattr(page, "field_widgets", {}) or {}

    # Collect current values from widgets.
    # Order matters: treat combo-like widgets (currentText) first so that
    # checkable combo implementations do not get coerced via isChecked().
    values: Dict[str, Any] = {}
    for key, widget in field_widgets.items():
        try:
            # ComboBox (and similar) have currentText.
            if hasattr(widget, "currentText"):
                values[key] = str(widget.currentText())
            # QCheckBox has isChecked.
            elif hasattr(widget, "isChecked"):
                values[key] = bool(widget.isChecked())
            # QSpinBox / QDoubleSpinBox have value() but no currentText.
            elif hasattr(widget, "value") and not hasattr(widget, "currentText"):
                values[key] = widget.value()
            # LineEdit (and similar) have text.
            elif hasattr(widget, "text"):
                values[key] = str(widget.text())
        except Exception:
            values[key] = None

    # Normalise connect_type.type value so that rules can rely on a
    # consistent label (Android / Linux).  This mirrors the helper used
    # elsewhere in the UI layer.
    try:
        ct = current_connect_type(page)
        if ct:
            values["connect_type.type"] = ct
    except Exception:
        pass

    # Inject testcase context so that CUSTOM_TESTCASE_UI_RULES can express
    # conditions based on the selected script (basename, kind, etc.)
    case_path = ""
    try:
        case_path = getattr(page, "_current_case_path", "") or ""
    except Exception:
        case_path = ""
    basename = os.path.basename(case_path) if case_path else ""

    values["testcase.path"] = case_path
    values["testcase.basename"] = basename
    values["testcase.is_rvo"] = bool(basename and "rvo" in basename)
    values["testcase.is_rvr"] = bool(basename and "rvr" in basename)
    values["testcase.is_peak_throughput"] = basename == "test_wifi_peak_throughput.py"

    # Derive performance/stability/compatibility flags via the controller when available.
    is_performance = False
    is_stability = False
    is_compatibility = False
    config_ctl = getattr(page, "config_ctl", None)
    if config_ctl is not None:
        try:
            if hasattr(config_ctl, "is_performance_case"):
                is_performance = bool(config_ctl.is_performance_case(case_path))
        except Exception:
            logging.debug("evaluate_all_rules: is_performance_case failed", exc_info=True)
        try:
            if hasattr(config_ctl, "is_stability_case"):
                is_stability = bool(config_ctl.is_stability_case(case_path))
        except Exception:
            logging.debug("evaluate_all_rules: is_stability_case failed", exc_info=True)

    # Treat any testcase whose path contains a "compatibility" segment as a
    # compatibility case.  This mirrors the folder-based Settings layout
    # logic in the view/controller layer.
    try:
        norm_path = case_path.replace("\\", "/")
        is_compatibility = bool("/compatibility/" in norm_path)
    except Exception:
        is_compatibility = False

    values["testcase.is_performance"] = is_performance
    values["testcase.is_stability"] = is_stability
    values["testcase.is_compatibility"] = is_compatibility
    # Build combined ordered rule list(s): testcase-specific lists first,
    # followed by any extra lists and then the global rule list.  This
    # ordering lets testcase rules define the editable surface while
    # simple rules refine behaviour within that boundary.
    combined_rules: List[SimpleRuleSpec] = []
    combined_rules.extend(CUSTOM_TESTCASE_UI_RULES)
    if extra_rule_lists:
        for lst in extra_rule_lists:
            combined_rules.extend(lst or [])
    combined_rules.extend(CUSTOM_SIMPLE_UI_RULES)

    if trigger_field:
        apply_rules(trigger_field, values, page, rules=combined_rules)
        return

    # No specific trigger: evaluate rules for all known trigger fields.
    seen: set[str] = set()
    for rule in combined_rules:
        tf = rule.trigger_field
        if tf in seen:
            continue
        seen.add(tf)
        apply_rules(tf, values, page, rules=combined_rules)


__all__ = [
    "SimpleFieldEffect",
    "SimpleRuleSpec",
    "CUSTOM_SIMPLE_UI_RULES",
    "CUSTOM_TESTCASE_UI_RULES",
    "apply_rules",
    "evaluate_all_rules",
    "normalize_connect_type_label",
    "current_connect_type",
]
