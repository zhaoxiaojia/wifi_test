"""Case (RvR Wi-Fi) configuration view and page.

This module now defines three widgets:

* :class:`FormListPage` – generic, read‑only CSV/list table with an optional
  checkbox column that can be reused by other features (such as the
  switch‑Wi‑Fi stability editor).
* :class:`RouterConfigForm` – left‑hand form used to edit a single Wi‑Fi
  row (band, channel, security, SSID, password, tx/rx flags).
* :class:`RvrWifiConfigPage` – the actual Case page shown in the
  application, implemented as a composition of ``RouterConfigForm`` and
  ``FormListPage`` plus router/CSV persistence logic.
"""

from __future__ import annotations

import logging
from contextlib import ExitStack, suppress
import csv
from pathlib import Path
from typing import Any, Mapping, Sequence

from PyQt5.QtCore import Qt, QSignalBlocker, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QVBoxLayout,
    QWidget,
    QTableWidgetItem,
)
from qfluentwidgets import CardWidget, ComboBox, LineEdit, PushButton, TableWidget, InfoBar, InfoBarPosition

from src.util.constants import AUTH_OPTIONS, OPEN_AUTH, Paths, RouterConst
from src.tools.router_tool.router_factory import get_router
from src.ui.view.theme import apply_theme, apply_font_and_selection
from src.ui.view import FormListPage, RouterConfigForm, FormListBinder
from src.ui.view.config.config_compatibility import (
    CompatibilityConfigPage,
    derive_selected_router_keys,
)


class RvrWifiConfigPage(CardWidget):
    """RVR Wi-Fi test parameter configuration page (form + list + behaviour)."""

    dataChanged = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        apply_theme(self)
        self.setObjectName("rvrWifiConfigPage")

        # Compute CSV path and load router/rows.
        self.csv_path = self._compute_csv_path()
        self.router, self.router_name = self._load_router()
        self.headers, self.rows = self._load_csv()

        # Outer layout holds both the RvR Wi‑Fi editor and, for
        # compatibility testcases, a CompatibilityConfigPage that shows
        # router entries from compatibility_router.json.  Only one of
        # these child widgets is visible at a time; the Config page
        # controller decides which mode to use for the active testcase.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._content = QWidget(self)
        layout = QHBoxLayout(self._content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        outer.addWidget(self._content, 1)

        self.form = RouterConfigForm(self.router, parent=self._content)
        layout.addWidget(self.form, 2)

        self.list = FormListPage(self.headers, self.rows, parent=self._content, checkable=True)
        layout.addWidget(self.list, 5)

        # Wiring between form, list and persistence.
        self._binder = FormListBinder(
            form=self.form,
            list_widget=self.list,
            rows=self.rows,
            on_row_updated=self._on_row_updated,
            on_rows_changed=self._on_rows_changed,
        )
        self.list.checkToggled.connect(self._on_list_check_toggled)
        self.dataChanged.connect(self._save_csv)

        # Initialise selection/form from first row when available.
        if self.rows:
            self.list.set_current_row(0)
            self.form.load_row(self.rows[0])

        # Compatibility router list: hidden by default and only shown
        # for compatibility testcases.
        self.compat_page = CompatibilityConfigPage(self)
        outer.addWidget(self.compat_page, 1)
        self.compat_page.setVisible(False)
        self._compat_loading = False
        self.compat_page.selectionChanged.connect(self._on_compat_selection_changed)

        # Hidden by default until the Config page decides which mode
        # should be active for the selected testcase.
        self._content.setVisible(False)

    def set_case_content_visible(self, visible: bool) -> None:
        """Show or hide the RvR Wi-Fi UI for the current case."""
        self._content.setVisible(bool(visible))

    def set_case_mode(self, mode: str) -> None:
        """
        Select which Case-page content is visible.

        Modes
        -----
        - ``\"performance\"`` – show RvR Wi‑Fi CSV editor.
        - ``\"compatibility\"`` – show compatibility router list driven
          by ``config_compatibility.yaml``.
        - anything else – hide both, leaving the Case page empty.
        """
        mode = str(mode or "").lower()
        show_rvr = mode == "performance"
        show_compat = mode == "compatibility"
        logging.debug("compat mode=%s show_rvr=%s show_compat=%s", mode, show_rvr, show_compat)

        self._content.setVisible(show_rvr)
        self.compat_page.setVisible(show_compat)

        if show_compat:
            # Refresh router selection from the merged configuration so
            # that Case page checkboxes mirror the Config-page
            # Compatibility Settings (selected_routers).
            try:
                from src.tools.config_loader import load_config  # local import to avoid cycles

                cfg = load_config(refresh=True) or {}
                compat_cfg = cfg.get("compatibility", {}) or {}
                relays = (compat_cfg.get("power_ctrl") or {}).get("relays")
                selected = derive_selected_router_keys(relays)
                if not selected:
                    # Legacy fallback: honour selected_routers only if relays
                    # do not describe any catalogue-backed entries.
                    selected = compat_cfg.get("selected_routers") or []
                logging.debug("compat selected_routers for case page: %s", selected)
                self._compat_loading = True
                try:
                    self.compat_page.set_selected_keys(selected)
                finally:
                    self._compat_loading = False
            except Exception:
                logging.debug("Failed to refresh Compatibility router selection", exc_info=True)

    def _on_compat_selection_changed(self) -> None:
        """Persist Case-page compatibility selection back to config YAML."""
        if self._compat_loading:
            return
        try:
            selected = sorted(self.compat_page.selected_keys())
            logging.debug("compat CasePage selection changed -> %s", selected)
            from src.tools.config_loader import load_config, save_config
            from src.ui.view.config.config_compatibility import apply_selected_keys_to_relays

            cfg = load_config(refresh=True) or {}
            compat_cfg = cfg.setdefault("compatibility", {})
            power_cfg = compat_cfg.setdefault("power_ctrl", {})
            relays = power_cfg.get("relays") or []
            power_cfg["relays"] = apply_selected_keys_to_relays(selected, relays)
            compat_cfg.pop("selected_routers", None)
            save_config(cfg)
            # Keep the Config page Compatibility panel in sync so the user
            # immediately sees Case-page edits reflected in Config.
            self._sync_config_page_relays(power_cfg["relays"])
        except Exception:
            logging.debug("Failed to persist Case-page compatibility selection", exc_info=True)

    def _sync_config_page_relays(self, relays: list[dict[str, Any]]) -> None:
        """Apply updated relays into the Config page widget and model."""
        main_window = self.window()
        cfg_page = main_window.caseConfigPage
        field_widgets = cfg_page.field_widgets
        editor = field_widgets.get("compatibility.power_ctrl.relays")
        if editor is None:
            return
        try:
            # Avoid autosave during programmatic refresh.
            setattr(cfg_page, "_refreshing", True)
            if hasattr(editor, "set_relays"):
                editor.set_relays(relays)
            compat_cfg = cfg_page.config.setdefault("compatibility", {})
            power_cfg = compat_cfg.setdefault("power_ctrl", {})
            power_cfg["relays"] = relays
            compat_cfg.pop("selected_routers", None)
        except Exception:
            logging.debug("Failed to sync Config page relays from Case selection", exc_info=True)
        finally:
            try:
                setattr(cfg_page, "_refreshing", False)
            except Exception:
                pass

    # --- router / CSV helpers -------------------------------------------------

    def _compute_csv_path(self, router_name: str | None = None) -> Path:
        csv_dir = Path(Paths.CONFIG_DIR) / "performance_test_csv"
        csv_dir.mkdir(parents=True, exist_ok=True)
        name = router_name or "rvr_wifi_setup"
        return (csv_dir / f"{name}.csv").resolve()

    def _load_router(self, name: str | None = None, address: str | None = None):
        from src.tools.config_loader import load_config

        try:
            cfg = load_config(refresh=True) or {}
            router_name = name or cfg.get("router", {}).get("name", "asusax86u")
            if address is None and cfg.get("router", {}).get("name") == router_name:
                address = cfg.get("router", {}).get("address")
            router = get_router(router_name, address)
        except Exception as e:
            logging.error("load router error: %s", e)
            router_name = name or "asusax86u"
            router = get_router(router_name, address)
        return (router, router_name)

    def _load_csv(self) -> tuple[list[str], list[dict[str, str]]]:
        default_headers = [
            "band",
            "ssid",
            "wireless_mode",
            "channel",
            "bandwidth",
            "security_mode",
            "password",
            "tx",
            "rx",
        ]
        headers: list[str] = default_headers
        rows: list[dict[str, str]] = []
        try:
            with open(self.csv_path, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if reader.fieldnames:
                    headers = [h.strip() for h in reader.fieldnames]
                for row in reader:
                    data = {h: (row.get(h) or "").strip() for h in headers}
                    rows.append(data)
        except FileNotFoundError:
            logging.warning("CSV not found: %s. Creating a new one with default headers.", self.csv_path)
            try:
                self.csv_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=default_headers)
                    writer.writeheader()
            except Exception as e:
                logging.error("Create CSV failed: %s", e)
        except Exception as e:
            InfoBar.error(title="Error", content=str(e), parent=self, position=InfoBarPosition.TOP)
            logging.exception("CSV load error: %s", e)
        logging.debug("Loaded headers %s with %d rows", headers, len(rows))
        return headers, rows

    def reload_csv(self) -> None:
        logging.info("Reloading CSV from %s", self.csv_path)
        self.headers, self.rows = self._load_csv()
        # Keep FormListBinder and FormListPage in sync with the new rows
        # list so that subsequent edits update the correct CSV data.
        if hasattr(self.list, "set_rows"):
            self.list.set_data(self.headers, self.rows)
        # Rebind binder's internal row reference to the freshly loaded list.
        try:
            self._binder._rows = self.rows  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - defensive
            logging.debug("Failed to rebind binder rows after CSV reload", exc_info=True)
        self.dataChanged.emit()

    def _save_csv(self) -> None:
        """Persist current rows back to the CSV file."""
        if not self.csv_path:
            return
        try:
            fieldnames = list(self.headers)
            with open(self.csv_path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                for row in self.rows:
                    writer.writerow({h: row.get(h, "") for h in fieldnames})
        except Exception:
            logging.exception("Failed to save Wi-Fi CSV to %s", self.csv_path)

    def reload_router(self) -> None:
        try:
            (self.router, self.router_name) = self._load_router()
            self.csv_path = self._compute_csv_path(self.router_name)
        except Exception as e:
            logging.error("reload router failed: %s", e)
            return
        self.form.set_router(self.router)
        # When router changes, reload CSV for the new router so that the
        # form/list/binder all operate on the same row list.
        self.headers, self.rows = self._load_csv()
        self.list.set_data(self.headers, self.rows)
        try:
            self._binder._rows = self.rows  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - defensive
            logging.debug("Failed to rebind binder rows after router reload", exc_info=True)
        if not self.rows:
            self.form.reset_form()
        else:
            self.form.load_row(self.rows[0])

    def on_csv_file_changed(self, path: str) -> None:
        if not path:
            return
        logging.debug("CSV file changed: %s", path)
        self.csv_path = Path(path).resolve()
        logging.debug("Resolved CSV path: %s", self.csv_path)
        self.reload_csv()
        if self.rows:
            self.list.set_current_row(0)
            self.form.load_row(self.rows[0])

    # --- form/list sync -------------------------------------------------------

    def _on_list_check_toggled(self, row_index: int, checked: bool) -> None:
        if not (0 <= row_index < len(self.rows)):
            return
        row = self.rows[row_index]
        # List checkbox只表示“该行是否启用”，不再强制把 tx/rx
        # 都改为 1，保留表单中用户单独勾选的方向设置。
        row["_checked"] = bool(checked)
        self.dataChanged.emit()

    def _on_row_updated(self, index: int, row: dict[str, str]) -> None:
        # Keep checkbox in sync with tx/rx fields via the _checked flag.
        _ = index
        checked = row.get("tx") == "1" or row.get("rx") == "1"
        row["_checked"] = checked

    def _on_rows_changed(self, rows: list[dict[str, str]]) -> None:  # noqa: ARG002
        self.dataChanged.emit()

    # --- router / CSV helpers -------------------------------------------------
