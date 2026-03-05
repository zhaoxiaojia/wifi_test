"""Config auto-save helpers for the Config page.

This module lives in the *model* layer so that configuration persistence
is decoupled from any particular view implementation.  It exposes a
decorator that can be applied to event handlers (such as
``handle_config_event``) to automatically flush widget state into the
merged config dictionary and write the YAML files when certain events
occur.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable, Iterable
import logging


# Events that should trigger a config auto-save when routed through
# the unified Config-page event handler.  ``field_changed`` is used by
# the generic field-change wiring in the Config view so that *any*
# widget edit on the Config page results in a persisted configuration.
AUTOSAVE_EVENTS: set[str] = {
    "field_changed",
    "case_clicked",
    "connect_type_changed",
    "third_party_toggled",
    "serial_status_changed",
    "rf_model_changed",
    "rvr_tool_changed",
    "router_name_changed",
    "router_address_changed",
    "csv_index_changed",
    "switch_wifi_use_router_changed",
    "switch_wifi_router_csv_changed",
    "stability_exitfirst_changed",
    "stability_ping_changed",
    "stability_script_section_toggled",
    "stability_relay_type_changed",
}


def should_autosave(event: str) -> bool:
    """Return True when the given event name should trigger auto-save."""
    return str(event or "").strip() in AUTOSAVE_EVENTS


def autosave_config(handler: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator that auto-saves Config-page state after certain events.

    The wrapped function must accept ``page`` as its first argument and
    an ``event`` string as its second (matching the signature of
    :func:`handle_config_event`).  After the handler returns, this
    decorator invokes ``page.config_ctl.sync_widgets_to_config`` and
    ``page.config_ctl.save_config`` when:

    - the event name is listed in :data:`AUTOSAVE_EVENTS`, and
    - the page exposes a ConfigController via ``page.config_ctl``, and
    - the page is not currently in a refresh pass (``page._refreshing``).
    """

    @wraps(handler)
    def wrapper(page: Any, event: str, *args: Any, **kwargs: Any) -> Any:
        result = handler(page, event, *args, **kwargs)

        evt = str(event or "").strip() if event is not None else ""
        if not should_autosave(evt):
            return result

        config_ctl = getattr(page, "config_ctl", None)
        if config_ctl is None or getattr(page, "_refreshing", False):
            return result

        try:
            config_ctl.sync_widgets_to_config()
            config_ctl.save_config()
        except Exception:
            logging.debug(
                "autosave_config failed for event=%s", evt, exc_info=True
            )
        return result

    return wrapper


__all__ = ["AUTOSAVE_EVENTS", "should_autosave", "autosave_config"]
