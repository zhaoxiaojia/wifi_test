#!/usr/bin/env python
# encoding: utf-8
"""
Common UI helpers and exports for the wifi_test application.

This module also defines logical identifiers and label mappings for the
sidebar pages.  These identifiers are used as stable, code-friendly keys
(`account`, `config`, `case`, `run`, `report`, `about`) while
``SIDEBAR_PAGE_LABELS`` records the human‑readable text shown in the UI.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from PyQt5.QtWidgets import QGroupBox, QLayout, QVBoxLayout, QWidget

__all__ = ["build_groupbox", "SIDEBAR_PAGE_KEYS", "SIDEBAR_PAGE_LABELS"]


def build_groupbox(
    title: str,
    *,
    parent: QWidget | None = None,
    layout_cls: type[QLayout] = QVBoxLayout,
    margins: Tuple[int, int, int, int] | None = None,
    spacing: int | None = None,
) -> tuple[QGroupBox, QLayout]:
    """Create a group box with a layout and optional spacing tweaks."""
    group = QGroupBox(title, parent)
    layout = layout_cls(group)
    if margins is not None:
        left, top, right, bottom = margins
        layout.setContentsMargins(left, top, right, bottom)
    if spacing is not None:
        layout.setSpacing(spacing)
    return group, layout


# ---------------------------------------------------------------------------
# Sidebar page identifiers and labels
# ---------------------------------------------------------------------------

# Logical sidebar page identifiers from top to bottom.  These are the
# canonical, code‑level names that other modules should use when referring
# to a top‑level page hosted in the FluentWindow navigation bar.
SIDEBAR_PAGE_KEYS: Tuple[str, ...] = (
    "account",
    "config",
    "case",
    "run",
    "report",
    "about",
)

# Mapping from internal page keys to the text (and optional sub‑text)
# presented in the navigation bar.  Keeping this centralised makes it easy
# to adjust wording for end users without touching the rest of the UI
# wiring.
SIDEBAR_PAGE_LABELS: Dict[str, Tuple[str, Optional[str]]] = {
    # Account / sign‑in area
    "account": ("Login", None),
    # Main configuration for test cases
    "config": ("Config Setup", "Case Config"),
    # RVR Wi‑Fi / scenario‑level configuration
    "case": ("RVR Scenario Config", "RVR Wi-Fi Config"),
    # Test execution
    "run": ("Test", None),
    # Report browser
    "report": ("Reports", None),
    # About / help
    "about": ("About", None),
}
