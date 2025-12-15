"""Centralised option sources for Config page dropdowns.

This module belongs to the *model* layer for the UI.  It exposes
field-level choice lists that can be consumed by the schema-driven
builder and controllers instead of hard-coding options in views or
utility modules.
"""

from __future__ import annotations

from typing import Callable, Iterable, Sequence

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
    """Return known FPGA customer names from the Wi‑Fi project map."""

    return _sorted_unique(WIFI_PRODUCT_PROJECT_MAP.keys())


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
