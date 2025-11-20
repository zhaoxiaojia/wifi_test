from __future__ import annotations

import logging
from typing import Any, List, Tuple

from PyQt5.QtWidgets import QWidget
from qfluentwidgets import InfoBar, InfoBarPosition


def info_bar_parent(page: Any) -> QWidget:
    """Return the preferred parent widget for InfoBar dialogs."""
    window = getattr(page, "window", None)
    parent = window() if callable(window) else None
    if isinstance(parent, QWidget):
        return parent
    # Fallback to the page itself when no top-level window is available.
    return page  # type: ignore[return-value]


def show_info_bar(
    page: Any,
    level: str,
    title: str,
    content: str,
    **kwargs: Any,
):
    """Unified helper to show a qfluentwidgets.InfoBar attached to the Config UI."""
    bar_fn = getattr(InfoBar, level, None)
    if not callable(bar_fn):
        logging.debug("InfoBar level %s unavailable", level)
        return None

    parent = info_bar_parent(page)
    params = {
        "title": title,
        "content": content,
        "parent": parent,
        "position": InfoBarPosition.TOP,
    }
    params.update(kwargs)

    try:
        bar = bar_fn(**params)
    except Exception as exc:  # pragma: no cover - defensive logging only
        logging.debug("InfoBar.%s failed: %s", level, exc)
        return None

    # Scroll to top so the InfoBar is visible if page is inside a ScrollArea.
    scroll = getattr(page, "scroll_area", None)
    if scroll is not None:
        try:
            scrollbar = scroll.verticalScrollBar()
            if scrollbar is not None:
                scrollbar.setValue(scrollbar.minimum())
        except Exception as exc:  # pragma: no cover - best-effort only
            logging.debug("Failed to reset scroll position: %s", exc)

    # Raise both the InfoBar and the window so the user notices the message.
    if hasattr(bar, "raise_"):
        bar.raise_()
    if hasattr(parent, "raise_"):
        parent.raise_()
    if hasattr(parent, "activateWindow"):
        parent.activateWindow()

    return bar


def list_serial_ports() -> List[Tuple[str, str]]:
    """Enumerate available serial ports as (device, label) pairs."""
    ports: List[Tuple[str, str]] = []
    try:
        from serial.tools import list_ports  # type: ignore
    except Exception:
        logging.debug("serial.tools.list_ports unavailable", exc_info=True)
        return ports

    try:
        for info in list_ports.comports():
            label = info.device
            description = getattr(info, "description", "") or ""
            if description and description != info.device:
                label = f"{info.device} ({description})"
            ports.append((info.device, label))
    except Exception as exc:
        logging.debug("Failed to enumerate serial ports: %s", exc)
        return []
    return ports


__all__ = ["info_bar_parent", "show_info_bar", "list_serial_ports"]
