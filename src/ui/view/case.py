"""Case (RvR Wi-Fi) configuration view and page.

This module now defines three widgets:

* :class:`CasePage` – generic, read‑only CSV/list table with an optional
  checkbox column that can be reused by other features (such as the
  switch‑Wi‑Fi stability editor).
* :class:`RouterConfigForm` – left‑hand form used to edit a single Wi‑Fi
  row (band, channel, security, SSID, password, tx/rx flags).
* :class:`RvrWifiConfigPage` – the actual Case page shown in the
  application, implemented as a composition of ``RouterConfigForm`` and
  ``CasePage`` plus router/CSV persistence logic.
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
from src.ui import CasePage, RouterConfigForm


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

        # Outer layout holds a single content widget so that the Case page
        # itself stays present in the navigation stack even when the
        # RvR-specific UI should be hidden for non-Performance testcases.
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

        self.list = CasePage(self.headers, self.rows, parent=self._content, checkable=True)
        layout.addWidget(self.list, 5)

        # Wiring between form, list and persistence.
        self.form.rowChanged.connect(self._on_form_row_changed)
        self.form.addRequested.connect(self._on_form_add_requested)
        self.form.deleteRequested.connect(self._on_form_delete_requested)
        self.list.currentRowChanged.connect(self._on_list_row_changed)
        self.list.checkToggled.connect(self._on_list_check_toggled)
        self.dataChanged.connect(self._save_csv)

        # Initialise selection/form from first row when available.
        if self.rows:
            self.list.set_current_row(0)
            self.form.load_row(self.rows[0])

        # Hidden by default until Config page enables it.
        self._content.setVisible(False)

    def set_case_content_visible(self, visible: bool) -> None:
        """Show or hide the RvR Wi-Fi UI for the current case."""
        self._content.setVisible(bool(visible))

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
        self.list.set_data(self.headers, self.rows)
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
        if not self.rows:
            self.form.reset_form()
        else:
            self.form.load_row(self.rows[0])
            self.list.set_data(self.headers, self.rows)

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

    def _on_list_row_changed(self, row_index: int) -> None:
        if not (0 <= row_index < len(self.rows)):
            return
        self.form.load_row(self.rows[row_index])

    def _on_list_check_toggled(self, row_index: int, checked: bool) -> None:
        if not (0 <= row_index < len(self.rows)):
            return
        row = self.rows[row_index]
        row["tx"] = "1" if checked else "0"
        row["rx"] = "1" if checked else "0"
        self.dataChanged.emit()

    def _on_form_row_changed(self, data: dict[str, str]) -> None:
        row_index = self.list.current_row()
        if not (0 <= row_index < len(self.rows)):
            return
        self.rows[row_index].update(data)
        # Keep checkbox in sync with tx/rx fields via the _checked flag.
        checked = data.get("tx") == "1" or data.get("rx") == "1"
        self.rows[row_index]["_checked"] = checked
        # Let the FormListPage handle cell updates.
        self.list.update_row(row_index, self.rows[row_index])
        self.dataChanged.emit()

    def _on_form_add_requested(self, data: dict[str, str]) -> None:
        self.rows.append(dict(data))
        self.list.set_data(self.headers, self.rows)
        new_index = len(self.rows) - 1
        if new_index >= 0:
            self.list.set_current_row(new_index)
        self.dataChanged.emit()

    def _on_form_delete_requested(self) -> None:
        row_index = self.list.current_row()
        if not (0 <= row_index < len(self.rows)):
            return
        del self.rows[row_index]
        self.list.set_data(self.headers, self.rows)
        if self.rows:
            new_index = min(row_index, len(self.rows) - 1)
            self.list.set_current_row(new_index)
            self.form.load_row(self.rows[new_index])
        else:
            self.form.reset_form()
        self.dataChanged.emit()

    # --- router / CSV helpers -------------------------------------------------
