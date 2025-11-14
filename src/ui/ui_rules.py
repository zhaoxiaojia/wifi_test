#!/usr/bin/env python
# encoding: utf-8
"""
Declarative UI interaction rules for the Config page and sidebar.

This module only records rules; it does not modify widgets directly.
Later, CaseConfigPage or MainWindow can consume these rules to replace
scattered if/else logic.

Conventions
-----------
- Field names use keys from ``CaseConfigPage.field_widgets``, for example
  ``"connect_type.type"`` or ``"stability.duration_control.exitfirst"``.
- Sidebar items use logical keys: ``"account"|"config"|"case"|"run"|"report"|"about"``.
- All text is ASCII only (no Chinese characters or punctuation).
"""

from __future__ import annotations

from typing import Any, Dict, List, TypedDict


class FieldEffect(TypedDict, total=False):
    """Describe how a set of fields is affected by a rule."""

    enable_fields: List[str]
    disable_fields: List[str]
    show_fields: List[str]
    hide_fields: List[str]


class RuleSpec(TypedDict, total=False):
    """High level description of a single UI rule."""

    number: int
    description: str
    # Triggers: by field value, case type, script key or sidebar key.
    trigger_field: str
    trigger_sidebar_key: str
    trigger_case_type: str
    trigger_script_key: str
    # Mapping from trigger value (True/False, "Android"/"Linux", etc.) to effects.
    cases: Dict[Any, FieldEffect]
    # Optional global effects when the rule is active.
    effects: FieldEffect
    # Helper lists for navigation and documentation.
    related_fields: List[str]
    related_sidebar_keys: List[str]


# ---------------------------------------------------------------------------
# Config page interaction rules (user items 1–4, 7, 9–10, 12–18).
# These rules describe relationships between widgets only.
# ---------------------------------------------------------------------------

CONFIG_UI_RULES: Dict[str, RuleSpec] = {
    # 1) Control type Android / Linux
    "R01_control_type_android_linux": {
        "number": 1,
        "description": (
            "Control Type is Android or Linux; when Android is selected the "
            "Android Device field must be editable, when Linux is selected the "
            "Linux IP field must be editable."
        ),
        "trigger_field": "connect_type.type",
        "cases": {
            "Android": {
                "enable_fields": [
                    "connect_type.Android.device",
                ],
                "disable_fields": [
                    "connect_type.Linux.ip",
                ],
            },
            "Linux": {
                "enable_fields": [
                    "connect_type.Linux.ip",
                ],
                "disable_fields": [
                    "connect_type.Android.device",
                ],
            },
        },
        "related_fields": [
            "connect_type.type",
            "connect_type.Android.device",
            "connect_type.Linux.ip",
        ],
    },

    # 2) Enable third_party control -> Wait seconds
    "R02_third_party_wait_seconds": {
        "number": 2,
        "description": (
            "When the Enable third-party control checkbox is checked, the "
            "Wait seconds field is editable; when unchecked it is disabled."
        ),
        "trigger_field": "connect_type.third_party.enabled",
        "cases": {
            True: {
                "enable_fields": [
                    "connect_type.third_party.wait_seconds",
                ],
            },
            False: {
                "disable_fields": [
                    "connect_type.third_party.wait_seconds",
                ],
            },
        },
        "related_fields": [
            "connect_type.third_party.enabled",
            "connect_type.third_party.wait_seconds",
        ],
    },

    # 3) Serial Port enabled -> Port/Baud
    "R03_serial_port_enable": {
        "number": 3,
        "description": (
            "In the Serial Port group, when Enable is True the Port and Baud "
            "fields are visible and editable; when False they are hidden or disabled."
        ),
        "trigger_field": "serial_port.status",
        "cases": {
            "True": {
                "enable_fields": [
                    "serial_port.port",
                    "serial_port.baud",
                ],
            },
            "False": {
                "disable_fields": [
                    "serial_port.port",
                    "serial_port.baud",
                ],
            },
        },
        "related_fields": [
            "serial_port.status",
            "serial_port.port",
            "serial_port.baud",
        ],
    },

    # 4) Android / Linux -> System (Android Version / Kernel Version)
    "R04_android_system_visibility": {
        "number": 4,
        "description": (
            "When Control Type is Android, both Android Version and Kernel "
            "Version fields are visible; when Linux is selected only Kernel "
            "Version is shown."
        ),
        "trigger_field": "connect_type.type",
        "cases": {
            "Android": {
                "show_fields": [
                    "android_system.version",
                    "android_system.kernel_version",
                ],
            },
            "Linux": {
                "hide_fields": [
                    "android_system.version",
                ],
                "show_fields": [
                    "android_system.kernel_version",
                ],
            },
        },
        "related_fields": [
            "connect_type.type",
            "android_system.version",
            "android_system.kernel_version",
        ],
    },

    # 7) test_case field is always read-only
    "R07_test_case_always_readonly": {
        "number": 7,
        "description": (
            "The test_case display field shows the selected case path and is "
            "always read-only (never editable by the user)."
        ),
        "effects": {
            "disable_fields": [
                "text_case",
            ],
        },
        "related_fields": [
            "text_case",
        ],
    },

    # 9) RVO case -> Attenuator and Turntable editable
    "R09_rvo_uses_attenuator_and_turntable": {
        "number": 9,
        "description": (
            "For RVO cases (file name contains 'rvo'), both Attenuator and "
            "Turntable related fields are editable."
        ),
        "trigger_case_type": "rvo_case",
        "effects": {
            "enable_fields": [
                # Turntable
                "turn_table.model",
                "turn_table.ip_address",
                "turn_table.step",
                "turn_table.static_db",
                "turn_table.target_rssi",
                # Attenuator
                "rf_solution.model",
                "rf_solution.RC4DAT-8G-95.idVendor",
                "rf_solution.RC4DAT-8G-95.idProduct",
                "rf_solution.RC4DAT-8G-95.ip_address",
                "rf_solution.RADIORACK-4-220.ip_address",
                "rf_solution.LDA-908V-8.ip_address",
                "rf_solution.LDA-908V-8.channels",
                "rf_solution.step",
            ],
        },
        "related_fields": [
            "rf_solution.model",
            "rf_solution.step",
            "turn_table.model",
            "turn_table.ip_address",
            "turn_table.step",
            "turn_table.static_db",
            "turn_table.target_rssi",
        ],
    },

    # 10) RVR case -> Attenuator editable
    "R10_rvr_uses_attenuator_only": {
        "number": 10,
        "description": (
            "For RVR cases (file name contains 'rvr'), Attenuator related "
            "fields are editable; otherwise they are read-only or disabled."
        ),
        "trigger_case_type": "rvr_case",
        "effects": {
            "enable_fields": [
                "rf_solution.step",
                "rf_solution.model",
                "rf_solution.RC4DAT-8G-95.idVendor",
                "rf_solution.RC4DAT-8G-95.idProduct",
                "rf_solution.RC4DAT-8G-95.ip_address",
                "rf_solution.RADIORACK-4-220.ip_address",
                "rf_solution.LDA-908V-8.ip_address",
                "rf_solution.LDA-908V-8.channels",
            ],
        },
        "related_fields": [
            "rf_solution.step",
            "rf_solution.model",
            "rf_solution.RC4DAT-8G-95.idVendor",
            "rf_solution.RC4DAT-8G-95.idProduct",
            "rf_solution.RC4DAT-8G-95.ip_address",
            "rf_solution.RADIORACK-4-220.ip_address",
            "rf_solution.LDA-908V-8.ip_address",
            "rf_solution.LDA-908V-8.channels",
        ],
    },

    # 12) Stability case -> show Stability Settings panel
    "R12_stability_panel_visible": {
        "number": 12,
        "description": (
            "For stability cases (path under test/stability or mapped by "
            "script key), the Stability Settings panel should be visible."
        ),
        "trigger_case_type": "stability_case",
        "effects": {},
        "related_fields": [],
    },

    # 13) Stability case -> Duration control and Check point editable
    "R13_stability_duration_and_checkpoint": {
        "number": 13,
        "description": (
            "For stability cases, Duration control and Check point fields "
            "under 'stability.duration_control.*' and 'stability.check_point.*' "
            "are always editable."
        ),
        "trigger_case_type": "stability_case",
        "effects": {
            "enable_fields": [
                "stability.duration_control.loop",
                "stability.duration_control.duration_hours",
                "stability.duration_control.exitfirst",
                "stability.duration_control.retry_limit",
                "stability.check_point.ping",
                "stability.check_point.ping_targets",
            ],
        },
        "related_fields": [
            "stability.duration_control.loop",
            "stability.duration_control.duration_hours",
            "stability.duration_control.exitfirst",
            "stability.duration_control.retry_limit",
            "stability.check_point.ping",
            "stability.check_point.ping_targets",
        ],
    },

    # 14) test_str script -> AC/STR groups controlled by their checkboxes
    "R14_test_str_section_toggles": {
        "number": 14,
        "description": (
            "In the stability case test_str, controls in the AC and STR groups "
            "are only effective when their corresponding 'enabled' checkboxes "
            "are checked."
        ),
        "trigger_script_key": "test_str",
        "effects": {
            "enable_fields": [
                "stability.cases.test_str.ac.enabled",
                "stability.cases.test_str.ac.on_duration",
                "stability.cases.test_str.ac.off_duration",
                "stability.cases.test_str.ac.port",
                "stability.cases.test_str.ac.mode",
                "stability.cases.test_str.ac.relay_type",
                "stability.cases.test_str.ac.relay_params",
                "stability.cases.test_str.str.enabled",
                "stability.cases.test_str.str.on_duration",
                "stability.cases.test_str.str.off_duration",
                "stability.cases.test_str.str.port",
                "stability.cases.test_str.str.mode",
                "stability.cases.test_str.str.relay_type",
                "stability.cases.test_str.str.relay_params",
            ],
        },
        "related_fields": [
            "stability.cases.test_str.ac.enabled",
            "stability.cases.test_str.str.enabled",
        ],
    },

    # 15) test_str relay type -> USB relay vs SNMP
    "R15_test_str_relay_type_usb_vs_snmp": {
        "number": 15,
        "description": (
            "In test_str stability configuration, when Relay type is USB Relay "
            "the USB relay port and Wiring mode fields are editable and the "
            "Relay params field is read-only; when Relay type is a SNMP-style "
            "value, USB controls are disabled and Relay params is editable."
        ),
        "trigger_script_key": "test_str",
        "related_fields": [
            "stability.cases.test_str.ac.relay_type",
            "stability.cases.test_str.ac.relay_params",
            "stability.cases.test_str.str.relay_type",
            "stability.cases.test_str.str.relay_params",
        ],
    },

    # 16) test_switch_wifi script -> router CSV vs manual entries
    "R16_test_switch_wifi_router_vs_manual": {
        "number": 16,
        "description": (
            "In test_switch_wifi stability cases: when 'Use router configuration' "
            "is checked, show the Router CSV group (CSV selector, router model, "
            "preview) and hide manual SSID entries; when unchecked, hide the "
            "Router CSV group and show manual SSID/Security/Password with "
            "Add/Remove controls."
        ),
        "trigger_script_key": "switch_wifi",
        "related_fields": [
            "stability.cases.switch_wifi.use_router_configuration",
            "stability.cases.switch_wifi.csv_path",
            "stability.cases.switch_wifi.manual_entries",
        ],
    },

    # 17) Duration: exitfirst -> Retry count editable
    "R17_duration_exitfirst_retry": {
        "number": 17,
        "description": (
            "Within Duration control, when 'Stop immediately on failure "
            "(exitfirst)' is checked, the Retry count field is editable; "
            "otherwise Retry count is disabled."
        ),
        "trigger_field": "stability.duration_control.exitfirst",
        "cases": {
            True: {
                "enable_fields": [
                    "stability.duration_control.retry_limit",
                ],
            },
            False: {
                "disable_fields": [
                    "stability.duration_control.retry_limit",
                ],
            },
        },
        "related_fields": [
            "stability.duration_control.exitfirst",
            "stability.duration_control.retry_limit",
        ],
    },

    # 18) Check Point: Ping after each step -> Ping targets editable
    "R18_checkpoint_ping_targets": {
        "number": 18,
        "description": (
            "Within Check point, when 'Ping after each step' is checked, the "
            "Ping targets field is editable; otherwise it is disabled."
        ),
        "trigger_field": "stability.check_point.ping",
        "cases": {
            True: {
                "enable_fields": [
                    "stability.check_point.ping_targets",
                ],
            },
            False: {
                "disable_fields": [
                    "stability.check_point.ping_targets",
                ],
            },
        },
        "related_fields": [
            "stability.check_point.ping",
            "stability.check_point.ping_targets",
        ],
    },
}


# ---------------------------------------------------------------------------
# Cross-cutting case-type rules (user items 5, 6, 8, 11).
# These affect panels, debug options, RvR config and sidebar state.
# ---------------------------------------------------------------------------

CONFIG_UI_RULES.update(
    {
        # 5) Performance case -> Execution Settings panel
        "R05_performance_execution_panel": {
            "number": 5,
            "description": (
                "When the selected case is a performance case (or CSV based "
                "performance), the Execution Settings panel should be part of "
                "the active page set (dut + execution)."
            ),
            "trigger_case_type": "performance_or_enable_csv",
            "effects": {},
            "related_fields": [],
        },

        # 6) Execution Settings visible -> Debug Options always editable
        "R06_debug_always_enabled_with_execution": {
            "number": 6,
            "description": (
                "When the Execution Settings panel is visible, Debug Options "
                "checkboxes under 'debug.*' remain editable regardless of "
                "the concrete case."
            ),
            "trigger_case_type": "execution_panel_visible",
            "effects": {
                "enable_fields": [
                    "debug.database_mode",
                    "debug.skip_router",
                    "debug.skip_corner_rf",
                ],
            },
            "related_fields": [
                "debug.database_mode",
                "debug.skip_router",
                "debug.skip_corner_rf",
            ],
        },

        # 8) Execution Settings visible -> Router and RvR Config always editable
        "R08_execution_router_rvr_enabled": {
            "number": 8,
            "description": (
                "When the Execution Settings panel is visible, Router "
                "(router.*) and RvR Config (rvr.*) related fields are always "
                "editable."
            ),
            "trigger_case_type": "execution_panel_visible",
            "effects": {
                "enable_fields": [
                    "router.name",
                    "router.address",
                    "rvr",
                    "rvr.tool",
                    "rvr.iperf.path",
                    "rvr.iperf.server_cmd",
                    "rvr.iperf.client_cmd",
                    "rvr.ixchariot.path",
                    "rvr.repeat",
                    "rvr.throughput_threshold",
                ],
            },
            "related_fields": [
                "router.name",
                "router.address",
                "rvr.tool",
                "rvr.iperf.path",
                "rvr.iperf.server_cmd",
                "rvr.iperf.client_cmd",
                "rvr.ixchariot.path",
                "rvr.repeat",
                "rvr.throughput_threshold",
            ],
        },
    }
)


# ---------------------------------------------------------------------------
# Sidebar rules (currently only the "case" button behaviour).
# ---------------------------------------------------------------------------

SIDEBAR_RULES: Dict[str, RuleSpec] = {
    # 11) Sidebar "case" button for performance cases with RvR Wi-Fi
    "S11_case_button_for_performance": {
        "number": 11,
        "description": (
            "When the selected case is a performance case and RvR Wi-Fi is "
            "enabled with a valid CSV, the sidebar 'case' button is enabled; "
            "in other situations it is disabled by default."
        ),
        "trigger_case_type": "performance_case_with_rvr_wifi",
        "trigger_sidebar_key": "case",
        "effects": {},
        "related_sidebar_keys": ["case"],
    },
}


__all__ = [
    "FieldEffect",
    "RuleSpec",
    "CONFIG_UI_RULES",
    "SIDEBAR_RULES",
]

