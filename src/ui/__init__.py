#!/usr/bin/env python
# encoding: utf-8
"""
Common UI helpers and exports for the wifi_test application.

This module defines logical identifiers and label mappings for the
sidebar pages and provides convenience wrappers for loading/saving the
global YAML configuration used by the UI pages.

It also re-exports a small set of shared view-layer widgets so callers
can import them from ``src.ui`` without reaching into subpackages.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
from pathlib import Path
import logging
import copy

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QWidget
from qfluentwidgets import InfoBar, InfoBarPosition

from src.util.constants import load_config, save_config
from src.util.constants import get_src_base, TOOL_SECTION_KEY

__all__ = [
    "SIDEBAR_PAGE_KEYS",
    "SIDEBAR_PAGE_LABELS",
    "load_config",
    "save_config",
    "load_page_config",
    "save_page_config",
    "load_config_page_state",
    "save_config_page_state",
    "FormListPage",
    "RouterConfigForm",
]


# ---------------------------------------------------------------------------
# Sidebar page identifiers and labels
# ---------------------------------------------------------------------------

SIDEBAR_PAGE_KEYS: Tuple[str, ...] = (
    "account",
    "config",
    "case",
    "run",
    "report",
    "about",
)

SIDEBAR_PAGE_LABELS: Dict[str, Tuple[str, Optional[str]]] = {
    "account": ("Login", None),
    "config": ("Config Setup", "Case Config"),
    "case": ("RVR Scenario Config", "RVR Wi-Fi Config"),
    "run": ("Test", None),
    "report": ("Reports", None),
    "about": ("About", None),
}


def load_page_config(page: QWidget) -> dict[str, Any]:
    """
    Load configuration data for a UI page and normalise paths.

    - Refreshes the cached YAML content from disk.
    - Normalises ``text_case`` relative to the source base.
    - Persists the normalised config back to disk when it changes.
    - Shows an InfoBar on errors.

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

    This wraps :func:`save_config` and :func:`load_page_config` with
    logging and InfoBar-based error reporting.
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


def load_config_page_state(page: QWidget) -> dict[str, Any]:
    """
    Load and initialise configuration state for the Config page.

    This wraps :func:`load_page_config` with additional state used by
    ConfigController and related helpers:

    - sets ``page._current_case_path`` from ``text_case`` when available,
    - captures a snapshot of the tool section on ``page._config_tool_snapshot``,
    - restores CSV selection using the shared case controller helpers.
    """
    config = load_page_config(page)

    text_case = str(config.get("text_case", "") or "").strip()
    if text_case:
        base = Path(get_src_base()).resolve()
        abs_path = (base / text_case).resolve()
        page._current_case_path = abs_path.as_posix()  # type: ignore[attr-defined]

    page._config_tool_snapshot = copy.deepcopy(  # type: ignore[attr-defined]
        config.get(TOOL_SECTION_KEY, {})
    )

    from src.ui.controller.case_ctl import (  # local import to avoid cycles
        _load_csv_selection_from_config as _proxy_load_csv_selection_from_config,
    )

    _proxy_load_csv_selection_from_config(page)
    return config


def save_config_page_state(page: QWidget) -> dict[str, Any]:
    """
    Persist and refresh Config page configuration state.

    This wraps :func:`save_page_config` and updates the tool snapshot so
    controller logic can compare TOOL_SECTION changes efficiently.
    """
    refreshed = save_page_config(page)
    page._config_tool_snapshot = copy.deepcopy(  # type: ignore[attr-defined]
        refreshed.get(TOOL_SECTION_KEY, {})
    )
    return refreshed


# Re-export shared view widgets so callers can use ``src.ui`` as a stable
# entry point without depending on the view package structure.
