"""View layer package for UI pages.

Each top-level sidebar page (account, config, case, run, report, about)
has a corresponding module under this package.  Common builder helpers for
schema‑driven UI construction live in ``view.builder``.

This module also provides a small helper to bind view events from a
declarative "event table" defined in ``src/ui/model/view_events.yaml``.
The goal is to keep signal/slot wiring data-driven so that new pages can
add behaviour without growing ad-hoc code in the view layer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable

import yaml


def _load_view_event_table() -> Dict[str, Any]:
    """Load the global view-event table from the view layer."""
    path = Path(__file__).resolve().parent / "view_events.yaml"
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return {}
    try:
        data = yaml.safe_load(text) or {}
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def bind_view_events(page: Any, view_key: str, event_handler: Any) -> None:
    """
    Bind UI events for ``view_key`` using the declarative event table.

    Parameters
    ----------
    page:
        View/page instance that owns the widgets.
    view_key:
        Logical view name ("config", "run", etc.) used as a top-level key in
        ``view_events.yaml``.
    event_handler:
        Callable ``event_handler(page, event: str, **payload)`` that will be
        invoked when a configured event fires.  For the Config page this is
        typically :func:`src.ui.view.config.actions.handle_config_event`.
    """
    table = _load_view_event_table()
    spec = table.get(view_key) or {}
    events: Iterable[Dict[str, Any]] = spec.get("events") or []

    field_widgets = getattr(page, "field_widgets", {}) or {}

    for ev in events:
        field_key = str(ev.get("field") or "").strip()
        if not field_key:
            continue
        widget = field_widgets.get(field_key)
        if widget is None:
            continue

        trigger = str(ev.get("trigger") or "text").strip()
        payload_spec: Dict[str, str] = ev.get("payload") or {}
        event_name = str(ev.get("event") or "").strip()
        if not event_name:
            continue
        initial = bool(ev.get("initial", False))

        def _make_handler(w: Any, payload: Dict[str, str], name: str):
            def _handler(*args: Any) -> None:
                data: Dict[str, Any] = {}
                for key, source in payload.items():
                    if source == "text":
                        if hasattr(w, "currentText"):
                            data[key] = str(w.currentText())
                        elif hasattr(w, "text"):
                            data[key] = str(w.text())
                    elif source == "checked":
                        if hasattr(w, "isChecked"):
                            data[key] = bool(w.isChecked())
                    elif source == "bool_text":
                        if hasattr(w, "isChecked"):
                            data[key] = "True" if w.isChecked() else "False"
                event_handler(page, name, **data)

            return _handler

        handler = _make_handler(widget, payload_spec, event_name)

        # Connect appropriate Qt signal based on the declared trigger.
        if trigger == "toggled" and hasattr(widget, "toggled"):
            widget.toggled.connect(lambda *_a, h=handler: h(*_a))
        elif trigger == "text":
            if hasattr(widget, "currentTextChanged"):
                widget.currentTextChanged.connect(lambda *_a, h=handler: h(*_a))
            elif hasattr(widget, "textChanged"):
                widget.textChanged.connect(lambda *_a, h=handler: h(*_a))
            elif hasattr(widget, "currentIndexChanged"):
                widget.currentIndexChanged.connect(lambda *_a, h=handler: h(*_a))

        if initial:
            handler()


__all__ = ["bind_view_events"]
