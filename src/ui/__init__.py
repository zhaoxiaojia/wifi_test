#!/usr/bin/env python
# encoding: utf-8
"""
Common UI helpers and exports for the wifi_test application.
"""

from __future__ import annotations

from typing import Tuple

from PyQt5.QtWidgets import QGroupBox, QLayout, QVBoxLayout, QWidget

__all__ = ["build_groupbox"]


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
