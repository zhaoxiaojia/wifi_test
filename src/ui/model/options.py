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

from src.tools.router_tool.router_factory import router_list
from src.util.constants import (
    DEFAULT_ANDROID_VERSION_CHOICES,
    DEFAULT_KERNEL_VERSION_CHOICES,
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
    """Return available router names derived from the router factory."""

    return _sorted_unique(router_list.keys())


def _android_version_choices() -> Sequence[str]:
    """Return default Android version choices."""

    return list(DEFAULT_ANDROID_VERSION_CHOICES)


def _kernel_version_choices() -> Sequence[str]:
    """Return default kernel version choices."""

    return list(DEFAULT_KERNEL_VERSION_CHOICES)


def _turntable_model_choices() -> Sequence[str]:
    """Return available turntable model identifiers."""

    return list(TURN_TABLE_MODEL_CHOICES)


def _fpga_customer_choices() -> Sequence[str]:
    """Return known FPGA customer names from the Wi-Fi project map."""

    return _sorted_unique(WIFI_PRODUCT_PROJECT_MAP.keys())


def _mass_production_status_choices() -> Sequence[str]:
    values: list[str] = []
    for product_lines in WIFI_PRODUCT_PROJECT_MAP.values():
        for projects in product_lines.values():
            for info in projects.values():
                entries = info.get("mass_production_status") or []
                for entry in entries:
                    values.append(str(entry))
    return _sorted_unique(values)


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
        return []
    if proc.returncode != 0:
        return []
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
    # Router selection
    "router.name": _router_name_choices,
    # Project / Wi-Fi chipset customer selection (product line / project
    # remain driven by WIFI_PRODUCT_PROJECT_MAP).
    "project.customer": _fpga_customer_choices,
    "project.mass_production_status": _mass_production_status_choices,
    # Android / Linux connect targets
    "connect_type.Android.device": _adb_device_choices,
    "connect_type.Linux.ip": _linux_ip_choices,
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
