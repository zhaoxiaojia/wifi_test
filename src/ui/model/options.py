"""Centralised option sources for Config page dropdowns.

This module belongs to the *model* layer for the UI.  It exposes
field-level choice lists that can be consumed by the schema-driven
builder and controllers instead of hard-coding options in views or
utility modules.
"""

from __future__ import annotations

from typing import Callable, Iterable, Sequence
import socket
import subprocess

from src.util.constants import (
    AP_MODEL_CHOICES,
    AP_REGION_CHOICES,
    ATTENUATOR_CHOICES,
    BT_DEVICE_CHOICES,
    BT_REMOTE_CHOICES,
    BT_TYPE_CHOICES,
    DEFAULT_ANDROID_VERSION_CHOICES,
    DEFAULT_KERNEL_VERSION_CHOICES,
    DUT_OS_CHOICES,
    LAB_ENV_COEX_MODE_CHOICES,
    HW_PHASE_CHOICES,
    LAB_ENV_CONNECT_TYPE_CHOICES,
    LAB_NAME_CHOICES,
    PROJECT_TYPES,
    TURN_TABLE_MODEL_CHOICES,
    WIFI_PRODUCT_PROJECT_MAP,
)


def _sorted_unique(values: Iterable[str]) -> list[str]:
    """Return a sorted list of unique string values."""

    seen: dict[str, None] = {}
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        if text not in seen:
            seen[text] = None
    return sorted(seen.keys())


def _router_name_choices() -> Sequence[str]:
    """Return supported AP models from the shared constants enum."""

    return list(AP_MODEL_CHOICES)


def _android_version_choices() -> Sequence[str]:
    """Return default Android version choices."""

    return list(DEFAULT_ANDROID_VERSION_CHOICES)


def _kernel_version_choices() -> Sequence[str]:
    """Return default kernel version choices."""

    return list(DEFAULT_KERNEL_VERSION_CHOICES)


def _turntable_model_choices() -> Sequence[str]:
    """Return available turntable model identifiers."""

    return list(TURN_TABLE_MODEL_CHOICES)

def _rf_model_choices() -> Sequence[str]:
    """Return available RF solution model identifiers."""

    return list(ATTENUATOR_CHOICES)


def _fpga_customer_choices() -> Sequence[str]:
    """Return known ODM names from the Wi-Fi project map."""

    values: list[str] = []
    for odm_map in WIFI_PRODUCT_PROJECT_MAP.values():
        for odm_name in odm_map.keys():
            values.append(odm_name)
    return _sorted_unique(values)

def _project_type_choices() -> Sequence[str]:
    return list(PROJECT_TYPES)

def _lab_name_choices() -> Sequence[str]:
    """Return known lab names from the lab catalog."""

    return list(LAB_NAME_CHOICES)


def _hw_phase_choices() -> Sequence[str]:
    return list(HW_PHASE_CHOICES)

def _dut_os_choices() -> Sequence[str]:
    return list(DUT_OS_CHOICES)

def _bt_remote_choices() -> Sequence[str]:
    return list(BT_REMOTE_CHOICES)

def _bt_device_choices() -> Sequence[str]:
    return list(BT_DEVICE_CHOICES)

def _bt_type_choices() -> Sequence[str]:
    return list(BT_TYPE_CHOICES)

def _lab_env_connect_type_choices() -> Sequence[str]:
    return list(LAB_ENV_CONNECT_TYPE_CHOICES)

def _lab_env_coex_mode_choices() -> Sequence[str]:
    return list(LAB_ENV_COEX_MODE_CHOICES)

def _ap_region_choices() -> Sequence[str]:
    return list(AP_REGION_CHOICES)


def _adb_device_choices() -> Sequence[str]:
    """Return connected ADB device serials from `adb devices` output."""

    try:
        proc = subprocess.run(
            ["adb", "devices"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=3,
        )
    except Exception:
        return ["No devices"]
    if proc.returncode != 0:
        return ["No devices"]
    devices: list[str] = []
    for line in (proc.stdout or "").splitlines()[1:]:
        parts = line.strip().split()
        if len(parts) >= 2 and parts[1] == "device":
            devices.append(parts[0])
    choices = _sorted_unique(devices)
    return choices if choices else ["No devices"]


def _iter_ipv4_prefixes() -> list[str]:
    prefixes: set[str] = set()
    try:
        import psutil  # type: ignore

        addrs_by_name = psutil.net_if_addrs()
        stats_by_name = psutil.net_if_stats()
        for name, addrs in addrs_by_name.items():
            stats = stats_by_name.get(name)
            if stats is not None and not getattr(stats, "isup", False):
                continue
            for addr in addrs:
                if getattr(addr, "family", None) != socket.AF_INET:
                    continue
                ip = str(getattr(addr, "address", "") or "")
                if not ip or ip.startswith("127."):
                    continue
                parts = ip.split(".")
                if len(parts) == 4:
                    prefixes.add(".".join(parts[:3]))
    except Exception:
        return []
    return sorted(prefixes)


def _linux_ip_choices() -> Sequence[str]:
    """Return fast local /24 candidates (no ping scan)."""

    prefixes = _iter_ipv4_prefixes()
    if not prefixes:
        return ["No devices"]

    candidates: list[str] = []
    for prefix in prefixes:
        for suffix in (2, 10, 11, 12, 100, 101, 166, 200):
            candidates.append(f"{prefix}.{suffix}")

    choices = _sorted_unique(candidates)
    return choices if choices else ["No devices"]


_FIELD_CHOICE_SOURCES: dict[str, Callable[[], Sequence[str]]] = {
    # Android / kernel system fields (support both legacy and new keys)
    "android_system.version": _android_version_choices,
    "android_system.kernel_version": _kernel_version_choices,
    "system.version": _android_version_choices,
    "system.kernel_version": _kernel_version_choices,
    # Turntable models
    "Turntable.model": _turntable_model_choices,
    # Lab selection
    "lab.name": _lab_name_choices,
    # RF solution models
    "rf_solution.model": _rf_model_choices,
    # Router selection
    "router.name": _router_name_choices,
    # Project / Wi-Fi chipset customer selection (product line / project
    # remain driven by WIFI_PRODUCT_PROJECT_MAP).
    "project.customer": _fpga_customer_choices,
    "project.project_type": _project_type_choices,
    "dut.hw_phase": _hw_phase_choices,
    "dut.os": _dut_os_choices,
    # Android / Linux connect targets
    "connect_type.Android.device": _adb_device_choices,
    "connect_type.Linux.ip": _linux_ip_choices,
    # Lab environment Bluetooth options
    "lab_enviroment.ap_name": _router_name_choices,
    "lab_enviroment.ap_region": _ap_region_choices,
    "lab_enviroment.bt_remote": _bt_remote_choices,
    "lab_enviroment.bt_device": _bt_device_choices,
    "lab_enviroment.bt_type": _bt_type_choices,
    "lab_enviroment.connect_type": _lab_env_connect_type_choices,
    "lab_enviroment.coex_mode": _lab_env_coex_mode_choices,
}


def get_field_choices(field_key: str) -> list[str]:
    """Return centralised choices for a given config field key.

    If no choices are registered for ``field_key``, an empty list is
    returned and the caller is free to fall back to config values or
    dynamic sources.
    """

    supplier = _FIELD_CHOICE_SOURCES.get(str(field_key).strip())
    if supplier is None:
        return []
    try:
        raw = supplier() or []
    except Exception:
        return []
    return [str(value) for value in raw if str(value).strip()]


__all__ = ["get_field_choices"]
