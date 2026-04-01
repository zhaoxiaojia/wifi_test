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
    LAB_CATALOG,
    RF_MODEL_CHOICES,
    TURN_TABLE_MODEL_CHOICES,
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


def _turntable_model_choices() -> Sequence[str]:
    """Return available turntable model identifiers."""

    return list(TURN_TABLE_MODEL_CHOICES)

def _rf_model_choices() -> Sequence[str]:
    """Return available RF solution model identifiers."""

    return list(RF_MODEL_CHOICES)


def _lab_name_choices() -> Sequence[str]:
    """Return known lab names from the lab catalog."""

    return _sorted_unique(LAB_CATALOG.keys())


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


_FIELD_CHOICE_SOURCES: dict[str, Callable[[], Sequence[str]]] = {
    # Turntable models
    "Turntable.model": _turntable_model_choices,
    # Lab selection
    "lab.name": _lab_name_choices,
    # RF solution models
    "rf_solution.model": _rf_model_choices,
    # Router selection
    "router.name": _router_name_choices,
    # Android connect targets
    "connect_type.Android.device": _adb_device_choices,
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
