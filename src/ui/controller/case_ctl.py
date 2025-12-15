from __future__ import annotations

"""Controller-side helpers for the RvR Wi‑Fi case page.

This module hosts the non-UI logic that was previously split across
``src.ui.rvr_wifi_config`` and ``src.ui.rvrwifi_proxy``:

- CSV discovery and normalisation for performance_test_csv files.
- Synchronisation of CSV combo boxes across the Config and Case pages.
- Loading switch‑Wi‑Fi entries from CSV and updating previews.
- Enabling/disabling the RVR navigation button based on configuration.
"""

from typing import TYPE_CHECKING, Any, Mapping, Sequence
from pathlib import Path
import csv
import logging

from PyQt5.QtCore import QObject, QSignalBlocker
from qfluentwidgets import ComboBox

from src.util.constants import (
    get_config_base,
    SWITCH_WIFI_ENTRY_SSID_FIELD,
    SWITCH_WIFI_ENTRY_SECURITY_FIELD,
    SWITCH_WIFI_ENTRY_PASSWORD_FIELD,
    AUTH_OPTIONS,
)

if TYPE_CHECKING:  # pragma: no cover - circular import guard
    from src.ui.view.case import RvrWifiConfigPage as CaseConfigPage


def _register_switch_wifi_csv_combo(page: "CaseConfigPage", combo: ComboBox) -> None:
    """Track CSV combos so selections stay in sync across the UI."""
    if combo in page._switch_wifi_csv_combos:
        return
    if combo.property("switch_wifi_include_placeholder") is None:
        combo.setProperty("switch_wifi_include_placeholder", True)
    page._switch_wifi_csv_combos.append(combo)

    def _cleanup(_obj: QObject | None = None, *, target: ComboBox = combo) -> None:
        _unregister_switch_wifi_csv_combo(page, target)

    combo.destroyed.connect(_cleanup)  # type: ignore[arg-type]


def _unregister_switch_wifi_csv_combo(page: "CaseConfigPage", combo: ComboBox) -> None:
    """Stop tracking a CSV combo when it is removed."""
    try:
        page._switch_wifi_csv_combos.remove(combo)
    except ValueError:
        return


def _list_available_csv_files() -> list[tuple[str, str]]:
    """Discover available CSV files under the configured directory."""
    csv_dir = get_config_base() / "performance_test_csv"
    entries: list[tuple[str, str]] = []
    if csv_dir.exists():
        for csv_file in sorted(csv_dir.glob("*.csv")):
            try:
                entries.append((csv_file.name, str(csv_file.resolve())))
            except Exception:
                continue
    return entries


def _resolve_csv_config_path(value: Any) -> str | None:
    """Return the absolute CSV path derived from persisted configuration."""
    if not value:
        return None
    try:
        candidate = Path(value)
    except (TypeError, ValueError):
        return None
    try:
        if not candidate.is_absolute():
            candidate = (get_config_base() / candidate).resolve()
        else:
            candidate = candidate.resolve()
    except Exception:
        return None
    return str(candidate)


def _load_csv_selection_from_config(page: "CaseConfigPage") -> None:
    """Initialise the cached CSV selection from stored configuration."""
    stored = None
    if isinstance(page.config, dict):
        stored = _resolve_csv_config_path(page.config.get("csv_path"))
    config_ctl = getattr(page, "config_ctl", None)
    if config_ctl is not None:
        config_ctl.set_selected_csv(stored, sync_combo=False)
    else:
        _set_selected_csv(page, stored, sync_combo=False)


def _update_csv_options(page: "CaseConfigPage") -> None:
    """Refresh CSV drop-downs to reflect router availability."""
    if hasattr(page, "csv_combo"):
        _populate_csv_combo(page, page.csv_combo, page.selected_csv_path)
    _refresh_registered_csv_combos(page)


def _capture_preselected_csv(page: "CaseConfigPage") -> None:
    """Cache the combo selection when no CSV has been recorded yet."""
    combo = getattr(page, "csv_combo", None)
    if combo is None or page.selected_csv_path:
        return
    index = combo.currentIndex()
    if index < 0:
        return
    data = combo.itemData(index)
    normalized = _normalize_csv_path(data) if data else None
    if not normalized:
        normalized = _normalize_csv_path(combo.itemText(index))
    if normalized:
        config_ctl = getattr(page, "config_ctl", None)
        if config_ctl is not None:
            config_ctl.set_selected_csv(normalized, sync_combo=False)
        else:
            _set_selected_csv(page, normalized, sync_combo=False)


def _normalize_csv_path(path: Any) -> str | None:
    """Normalise CSV paths to absolute strings for reliable comparisons."""
    if not path:
        return None
    try:
        return str(Path(path).resolve())
    except Exception:
        return str(path)


def _relativize_config_path(path: Any) -> str:
    """Convert CSV paths into config-relative strings for persistence."""
    if path in (None, ""):
        return ""
    try:
        candidate = Path(str(path)).resolve()
    except Exception:
        return str(path)
    base_cfg = get_config_base()
    try:
        rel = candidate.relative_to(base_cfg)
    except ValueError:
        return candidate.as_posix()
    return rel.as_posix()


def _find_csv_index(
    page: "CaseConfigPage", normalized_path: str | None, combo: ComboBox | None = None
) -> int:
    """Return the combo index for a normalized CSV path."""
    if not normalized_path:
        return -1
    normalized = _normalize_csv_path(normalized_path)
    if not normalized:
        return -1
    if combo is None:
        combo = getattr(page, "csv_combo", None)
    if combo is None:
        return -1
    for idx in range(combo.count()):
        data = combo.itemData(idx)
        text = combo.itemText(idx)
        if _normalize_csv_path(data) == normalized or _normalize_csv_path(text) == normalized:
            return idx
    return -1


def _set_selected_csv(
    page: "CaseConfigPage", csv_path: str | None, *, sync_combo: bool = True
) -> bool:
    """Update page.selected_csv_path and optionally sync the page combo."""
    normalized = _normalize_csv_path(csv_path)
    changed = normalized != getattr(page, "selected_csv_path", None)
    page.selected_csv_path = normalized
    if sync_combo and hasattr(page, "csv_combo") and page.csv_combo is not None:
        index = _find_csv_index(page, normalized, page.csv_combo)
        if index < 0 and page.csv_combo.count():
            index = 0
        with QSignalBlocker(page.csv_combo):
            page.csv_combo.setCurrentIndex(index)
    _update_rvr_nav_button(page)
    return changed


def _populate_csv_combo(
    page: "CaseConfigPage",
    combo: ComboBox,
    selected_path: str | None,
    *,
    include_placeholder: bool = False,
) -> None:
    """Populate a combo box with available CSV files."""
    entries = _list_available_csv_files()
    normalized_selected = _normalize_csv_path(selected_path)
    with QSignalBlocker(combo):
        combo.clear()
        if include_placeholder:
            combo.addItem("Select config csv file", "")
        for display, path in entries:
            combo.addItem(display)
            idx = combo.count() - 1
            combo.setItemData(idx, path)
        index = -1
        if normalized_selected:
            index = _find_csv_index(page, normalized_selected, combo)
            if index < 0:
                combo.addItem(Path(normalized_selected).name)
                idx = combo.count() - 1
                combo.setItemData(idx, normalized_selected)
                index = idx
        elif include_placeholder:
            index = combo.findData("")
        if index < 0 and combo.count():
            index = 0
        combo.setCurrentIndex(index)


def _refresh_registered_csv_combos(page: "CaseConfigPage") -> None:
    """Refresh registered CSV combos to ensure the UI is up to date."""
    for combo in list(getattr(page, "_switch_wifi_csv_combos", [])):
        if combo is None:
            continue
        try:
            data = combo.currentData()
        except RuntimeError:
            _unregister_switch_wifi_csv_combo(page, combo)
            continue
        selected = data if isinstance(data, str) and data else combo.currentText()
        include_placeholder = combo.property("switch_wifi_include_placeholder")
        use_placeholder = True if include_placeholder is None else bool(include_placeholder)
        _populate_csv_combo(page, combo, selected, include_placeholder=use_placeholder)


def _load_switch_wifi_entries(
    page: "CaseConfigPage", csv_path: str | None
) -> list[dict[str, str]]:
    """Load switch Wi-Fi entries from a CSV file."""
    normalized = _normalize_csv_path(csv_path)
    if not normalized:
        return []
    entries: list[dict[str, str]] = []
    try:
        with open(normalized, "r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if not isinstance(row, dict):
                    continue
                ssid = str(row.get(SWITCH_WIFI_ENTRY_SSID_FIELD, "") or "").strip()
                if not ssid:
                    continue
                mode = (
                    str(row.get(SWITCH_WIFI_ENTRY_SECURITY_FIELD, "") or "").strip()
                    or AUTH_OPTIONS[0]
                )
                password = str(row.get(SWITCH_WIFI_ENTRY_PASSWORD_FIELD, "") or "")
                entries.append(
                    {
                        SWITCH_WIFI_ENTRY_SSID_FIELD: ssid,
                        SWITCH_WIFI_ENTRY_SECURITY_FIELD: mode,
                        SWITCH_WIFI_ENTRY_PASSWORD_FIELD: password,
                    }
                )
    except Exception as exc:
        logging.debug("Failed to load Wi-Fi CSV %s: %s", csv_path, exc)
    return entries


def _update_switch_wifi_preview(
    page: "CaseConfigPage",
    preview: Any,
    csv_path: str | None,
) -> None:
    """Update preview widgets when CSV selections change."""
    if preview is None:
        return
    entries = _load_switch_wifi_entries(page, csv_path)
    preview.update_entries(entries)


def _update_rvr_nav_button(page: "CaseConfigPage") -> None:
    """Ensure the RVR navigation button is available.

    The Case button itself stays enabled once the user is logged in;
    CSV/router state only affects what the Case page shows, not whether
    the sidebar entry is clickable.
    """
    main_window = page.window()
    if hasattr(main_window, "rvr_nav_button"):
        btn = getattr(main_window, "rvr_nav_button", None)
        if btn is not None:
            try:
                btn.setEnabled(True)
            except Exception:
                logging.debug("Failed to enable RVR nav button", exc_info=True)


def _open_rvr_wifi_config(page: "CaseConfigPage") -> None:
    """Open the RVR Wi-Fi configuration page when supported."""
    main_window = page.window()
    if main_window is None:
        return
    if hasattr(main_window, "show_rvr_wifi_config"):
        try:
            main_window.show_rvr_wifi_config()
        except Exception as exc:  # pragma: no cover - defensive log only
            logging.debug("show_rvr_wifi_config failed: %s", exc)


__all__ = [
    "_register_switch_wifi_csv_combo",
    "_load_csv_selection_from_config",
    "_resolve_csv_config_path",
    "_update_csv_options",
    "_capture_preselected_csv",
    "_normalize_csv_path",
    "_relativize_config_path",
    "_find_csv_index",
    "_set_selected_csv",
    "_populate_csv_combo",
    "_refresh_registered_csv_combos",
    "_load_switch_wifi_entries",
    "_update_switch_wifi_preview",
    "_update_rvr_nav_button",
    "_open_rvr_wifi_config",
]
