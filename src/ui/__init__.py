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

from typing import Any, Dict, Optional, Tuple
from pathlib import Path
import logging

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QGroupBox, QLayout, QVBoxLayout, QWidget
from qfluentwidgets import InfoBar, InfoBarPosition

from src.tools.config_loader import load_config, save_config
from src.util.constants import get_src_base

__all__ = [
    "SIDEBAR_PAGE_KEYS",
    "SIDEBAR_PAGE_LABELS",
    "load_config",
    "save_config",
    "load_page_config",
    "save_page_config",
]

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


def load_page_config(page: QWidget) -> dict[str, Any]:
    """
    Load configuration data for a UI page and normalise paths.

    This is a UI-friendly wrapper around :func:`load_config` that:
    - refreshes the cached YAML content from disk
    - normalises the ``text_case`` path relative to the source base
    - persists the normalised config back to disk when it changes
    - shows an InfoBar on errors

    The resulting configuration dictionary is stored on ``page.config``
    and also returned.
    """
    try:
        config = load_config(refresh=True) or {}

        app_base = Path(get_src_base()).resolve()
        changed = False
        path = config.get("text_case", "")
        if path:
            abs_path = Path(path)
            if not abs_path.is_absolute():
                abs_path = app_base / abs_path
            abs_path = abs_path.resolve()
            if abs_path.exists():
                try:
                    rel_path = abs_path.relative_to(app_base)
                except ValueError:
                    config["text_case"] = ""
                    changed = True
                else:
                    rel_str = rel_path.as_posix()
                    if rel_str != path:
                        config["text_case"] = rel_str
                        changed = True
            else:
                config["text_case"] = ""
                changed = True
        else:
            config["text_case"] = ""

        if changed:
            try:
                save_config(config)
            except Exception as exc:  # pragma: no cover - UI only feedback
                logging.error("Failed to normalize and persist config: %s", exc)
                QTimer.singleShot(
                    0,
                    lambda exc=exc: InfoBar.error(
                        title="Error",
                        content=f"Failed to write config: {exc}",
                        parent=page,
                        position=InfoBarPosition.TOP,
                    ),
                )
        page.config = config  # type: ignore[attr-defined]
    except Exception as exc:  # pragma: no cover - UI only feedback
        QTimer.singleShot(
            0,
            lambda exc=exc: InfoBar.error(
                title="Error",
                content=f"Failed to load config : {exc}",
                parent=page,
                position=InfoBarPosition.TOP,
            ),
        )
        page.config = {}  # type: ignore[attr-defined]

    return page.config  # type: ignore[attr-defined]


def save_page_config(page: QWidget) -> dict[str, Any]:
    """
    Persist the active configuration for a UI page and reload it.

    This function wraps :func:`save_config` and :func:`load_page_config`
    with logging and InfoBar-based error reporting.
    """
    data = getattr(page, "config", None)
    logging.debug("[save] data=%s", data)
    try:
        save_config(data)
        logging.info("Configuration saved")
        refreshed = load_page_config(page)
        logging.info("Configuration saved")
        return refreshed
    except Exception as exc:  # pragma: no cover - UI only feedback
        logging.error("[save] failed: %s", exc)
        QTimer.singleShot(
            0,
            lambda exc=exc: InfoBar.error(
                title="Error",
                content=f"Failed to save config: {exc}",
                parent=page,
                position=InfoBarPosition.TOP,
            ),
        )
        return getattr(page, "config", {}) or {}
