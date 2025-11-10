"""RVR Wi-Fi configuration page (PyQt5 + qfluentwidgets).

Responsibilities:
- Provide a visual editor for Wi-Fi test parameters (band/mode/channel/bandwidth/security/credentials/tx-rx).
- Load/write table data from/to CSV and sync with the form.
- Load router object by model/address to drive allowed options (band/channel/bandwidth).
- Listen to router/CSV change signals from the upstream Case config page.

Side effects:
- Read/write a CSV file (path resolved from Paths.CONFIG_DIR/performance_test_csv/rvr_wifi_setup.csv).
- Operate PyQt widgets/signals and show InfoBar error messages.
- Log load/save/errors.

When triggered:
- On page initialization, user changes on form/table, or router/csv change signals from upstream.
"""
from __future__ import annotations
import csv
from pathlib import Path
import logging
from contextlib import ExitStack
from PyQt5.QtCore import Qt, QSignalBlocker
from src.util.constants import AUTH_OPTIONS, OPEN_AUTH, Paths, RouterConst
from PyQt5.QtWidgets import QHBoxLayout, QTableWidgetItem, QGroupBox, QVBoxLayout, QAbstractItemView, QFormLayout, QCheckBox, QHeaderView, QWidget
from qfluentwidgets import TableWidget, CardWidget, ComboBox, LineEdit, PushButton, InfoBar, InfoBarPosition
from src.tools.router_tool.router_factory import get_router
from .theme import apply_theme, apply_font_and_selection

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .windows_case_config import CaseConfigPage


class WifiTableWidget(TableWidget):
    """Wi-Fi parameter table widget.

    Behavior:
    - Enforces single row selection to cooperate with the checkbox column.
    - Clicking on an empty area clears selection and asks the parent page to reset the form.

    Notes:
    - Signals interact with the outer RvrWifiConfigPage; the widget does not write CSV directly.
    """

    def __init__(self, page: "RvrWifiConfigPage"):
        """Initialize table properties and bind to the outer page."""
        super().__init__(page)
        self.page = page
        # Enforce single row selection to avoid conflicts with the checkbox column
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)

    def mousePressEvent(self, event):
        """Custom mouse press behavior.

        Behavior:
            - If clicking on an empty area: clear selection and ask the page to reset the form.
            - Otherwise: keep default selection.

        Args:
            event (QMouseEvent): mouse event.

        Side effects:
            - Calls self.page.reset_form() (UI only).
        """
        super().mousePressEvent(event)
        if self.itemAt(event.pos()) is None:
            self.clearSelection()
            self.page.reset_form()


class RvrWifiConfigPage(CardWidget):
    """RVR Wi-Fi test parameter configuration page.

    Main duties:
        - Display and edit a set of Wi-Fi configuration rows with two-way sync (form <-> table).
        - Read/write configurations from/to CSV.
        - Populate selectable band/channel/bandwidth according to router capability.
        - React to Router/CSV change signals from the upper Case page.

    External deps:
        - src.util.constants provides Paths/AUTH_OPTIONS.
        - get_router() provides a router object capability table.
        - qfluentwidgets handles UI components and InfoBar.
    """

    def __init__(self, case_config_page: "CaseConfigPage"):
        """Initialize the config page, build the form and table, load router/CSV, and connect signals.

        Notes:
            - Uses a loading guard (_loading) to prevent signal loops while initializing.
        """
        super().__init__()
        # Object name is used for styling/debugging only
        self.setObjectName("rvrWifiConfigPage")
        self.case_config_page = case_config_page

        combo = getattr(self.case_config_page, "router_name_combo", None)
        router_name = combo.currentText().lower() if combo is not None else ""
        self.csv_path = self._compute_csv_path(router_name)

        addr_edit = getattr(self.case_config_page, "router_addr_edit", None)
        addr = addr_edit.text() if addr_edit is not None else None

        self.router, self.router_name = self._load_router(router_name, addr)
        self.headers, self.rows = self._load_csv()

        # Guard flag to avoid signal recursion
        self._loading = False

        main_layout = QHBoxLayout(self)

        # -----------------------------
        # Left-side form (single-row editor)
        # -----------------------------
        form_box = QGroupBox(self)
        apply_theme(form_box, recursive=True)
        form_layout = QFormLayout(form_box)

        self.band_combo = ComboBox(form_box)
        band_list = getattr(self.router, "BAND_LIST", ["2.4G", "5G"])
        self.band_combo.addItems(band_list)
        self.band_combo.currentTextChanged.connect(self._on_band_changed)
        form_layout.addRow("band", self.band_combo)

        self.wireless_combo = ComboBox(form_box)
        form_layout.addRow("wireless mode", self.wireless_combo)

        self.channel_combo = ComboBox(form_box)
        form_layout.addRow("channel", self.channel_combo)

        self.bandwidth_combo = ComboBox(form_box)
        form_layout.addRow("bandwidth", self.bandwidth_combo)

        self.auth_combo = ComboBox(form_box)
        self.auth_combo.addItems(AUTH_OPTIONS)
        form_layout.addRow("security", self.auth_combo)

        self.ssid_edit = LineEdit(form_box)
        form_layout.addRow("ssid", self.ssid_edit)

        self.passwd_edit = LineEdit(form_box)
        self.passwd_edit.setEchoMode(LineEdit.Password)
        form_layout.addRow("password", self.passwd_edit)
        self.auth_combo.currentTextChanged.connect(self._on_auth_changed)

        test_widget = QWidget(form_box)
        test_layout = QHBoxLayout(test_widget)
        test_layout.setContentsMargins(0, 0, 0, 0)
        self.tx_check = QCheckBox("tx", test_widget)
        self.rx_check = QCheckBox("rx", test_widget)
        test_layout.addWidget(self.tx_check)
        test_layout.addWidget(self.rx_check)
        self.tx_check.stateChanged.connect(self._update_tx_rx)
        self.rx_check.stateChanged.connect(self._update_tx_rx)
        form_layout.addRow("direction", test_widget)

        btn_widget = QWidget(form_box)
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        self.del_btn = PushButton("Del", btn_widget)
        self.del_btn.clicked.connect(self.delete_row)
        btn_layout.addWidget(self.del_btn)
        self.add_btn = PushButton("Add", btn_widget)
        self.add_btn.clicked.connect(self.add_row)
        btn_layout.addWidget(self.add_btn)
        form_layout.addRow(btn_widget)

        main_layout.addWidget(form_box, 2)

        self.table = WifiTableWidget(self)

        # Turn off alternating row colors and keep stylesheets from turning them back on
        # Reason: we unify styling explicitly via apply_font_and_selection below
        self.table.setAlternatingRowColors(False)
        self.table.setSortingEnabled(False)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.cellClicked.connect(self._on_table_cell_clicked)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setMinimumSectionSize(100)

        main_layout.addWidget(self.table, 5)

        apply_theme(header)
        # Unify fonts/selection colors for this page only; no global stylesheet changes
        apply_font_and_selection(
            self.table,
            family="Verdana",
            size_px=12,
            sel_text="#A6E3FF",  # selected text
            sel_bg="#2B2B2B",  # selected background
            grid="#3F3F46",  # grid line color
            header_bg="#0B0B0C",
            header_fg="#D0D0D0",
        )

        # Form/table field sync
        self.band_combo.currentTextChanged.connect(self._update_current_row)
        self.wireless_combo.currentTextChanged.connect(self._update_current_row)
        self.channel_combo.currentTextChanged.connect(self._update_current_row)
        self.bandwidth_combo.currentTextChanged.connect(self._update_current_row)
        self.auth_combo.currentTextChanged.connect(self._on_auth_changed)
        self.auth_combo.currentTextChanged.connect(self._update_current_row)
        self.passwd_edit.textChanged.connect(self._update_current_row)
        self.ssid_edit.textChanged.connect(self._update_current_row)
        self._update_band_options(self.band_combo.currentText())
        self._update_auth_options(self.wireless_combo.currentText())
        self._on_auth_changed(self.auth_combo.currentText())
        self.refresh_table()

        # Listen to signals from the main Case config page
        self.case_config_page.routerInfoChanged.connect(self.reload_router)
        self.case_config_page.csvFileChanged.connect(self.on_csv_file_changed)

    def _get_base_dir(self) -> Path:
        """Return the project base directory (Paths.BASE_DIR)."""
        return Path(Paths.BASE_DIR)

    def _compute_csv_path(self, router_name: str) -> Path:
        """Compute CSV path for the given router name.

        Notes:
            - Currently returns performance_test_csv/rvr_wifi_setup.csv.
            - Can be extended to split CSV per router model.
        """
        csv_base = Path(Paths.CONFIG_DIR) / "performance_test_csv"
        return (csv_base / "rvr_wifi_setup.csv").resolve()

    def set_router_credentials(self, ssid: str, passwd: str) -> None:
        """Set router credentials and fill UI controls.

        Args:
            ssid: SSID text.
            passwd: password. Disabled when using open network.

        Side effects:
            - Update UI text fields only.
        """
        self.ssid_edit.setText(ssid)
        self.passwd_edit.setText(passwd)

    def get_router_credentials(self) -> tuple[str, str]:
        """Get (ssid, password) from current UI values."""
        return (self.ssid_edit.text(), self.passwd_edit.text())

    def set_readonly(self, readonly: bool) -> None:
        """Toggle read-only state for all interactive widgets.

        Args:
            readonly: True to disable controls.

        Side effects:
            - UI enable/disable; no I/O.
        """
        widgets = (self.table, self.band_combo, self.wireless_combo, self.channel_combo, self.bandwidth_combo, self.auth_combo, self.ssid_edit, self.passwd_edit, self.tx_check, self.rx_check, self.add_btn, self.del_btn)
        for w in widgets:
            w.setEnabled(not readonly)

    def _load_router(self, name: str | None = None, address: str | None = None):
        """Load router object and name.

        Behavior:
            - Prefer explicit name/address; otherwise read from global config.
            - Fallback to default model on failure.

        Returns:
            - (router_obj, router_name)

        Logs:
            - Errors are logged.
        """
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

    def _load_csv(self):
        """Read CSV into (headers, rows).

        Returns:
            - headers: list[str]
            - rows: list[dict[str, str]] (missing keys filled with empty string)

        Logs:
            - Debug information with path and row count.
        """
        default_headers = ["band", "ssid", "wireless_mode", "channel", "bandwidth", "security_mode", "password", "tx", "rx"]
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
        return (headers, rows)

    def reload_csv(self):
        """Reload current CSV and refresh the table.

        Side effects:
            - UI refresh only.
        """
        logging.info("Reloading CSV from %s", self.csv_path)
        (self.headers, self.rows) = self._load_csv()
        self.refresh_table()

    def reload_router(self):
        """Reload router info and refresh band-related options.

        Behavior:
            - Read router name/address from the upstream page.
            - Recreate router object.
            - Refresh band/mode/channel/bandwidth options.
            - Initialize the form if there is no row.

        Logs:
            - Errors are logged.
        """
        combo = getattr(self.case_config_page, "router_name_combo", None)
        name = combo.currentText().lower() if combo is not None else self.router_name
        self.csv_path = self._compute_csv_path(name)
        try:
            addr_edit = getattr(self.case_config_page, "router_addr_edit", None)
            addr = addr_edit.text() if addr_edit is not None else None
            (self.router, self.router_name) = self._load_router(name, addr)
        except Exception as e:
            logging.error("reload router failed: %s", e)
            return
        # Refresh options based on current band
        self._update_band_options(self.band_combo.currentText())
        self._update_auth_options(self.wireless_combo.currentText())
        # Initialize form if needed
        if not self.rows:
            self.reset_form()
        else:
            self._load_row_to_form(ensure_checked=True)

    def on_csv_file_changed(self, path: str) -> None:
        """Handle CSV file path change from the upstream page.

        Args:
            path: new CSV path (possibly relative).

        Behavior:
            - Resolve to absolute path, reload and refresh the table and form.
        """
        if not path:
            return
        logging.debug("CSV file changed: %s", path)
        self.csv_path = Path(path).resolve()
        logging.debug("Resolved CSV path: %s", self.csv_path)
        self.reload_csv()
        self._loading = True
        try:
            self._load_row_to_form(ensure_checked=True)
        finally:
            self._loading = False

    def _update_band_options(self, band: str):
        """Refresh wireless mode/channel/bandwidth options according to band.

        Args:
            band: "2.4G" or "5G".

        Notes:
            - Uses QSignalBlocker to avoid write-back loops.
        """
        wireless = RouterConst.DEFAULT_WIRELESS_MODES[band]
        channel = {"2.4G": getattr(self.router, "CHANNEL_2", []), "5G": getattr(self.router, "CHANNEL_5", [])}[band]
        bandwidth = {"2.4G": getattr(self.router, "BANDWIDTH_2", []), "5G": getattr(self.router, "BANDWIDTH_5", [])}[band]
        with QSignalBlocker(self.wireless_combo), QSignalBlocker(self.channel_combo), QSignalBlocker(self.bandwidth_combo):
            self.wireless_combo.clear()
            self.wireless_combo.addItems(wireless)
            self.channel_combo.clear()
            self.channel_combo.addItems(channel)
            self.bandwidth_combo.clear()
            self.bandwidth_combo.addItems(bandwidth)
        if not self._loading:
            self._update_auth_options(self.wireless_combo.currentText())

    def _on_band_changed(self, band: str):
        """After band changes, refresh options and try to write back the current row."""
        self._update_band_options(band)
        self._update_current_row()

    def _update_auth_options(self, wireless: str):
        """Update authentication options according to wireless mode (currently a fixed preset).

        Args:
            wireless: wireless mode string.
        """
        with QSignalBlocker(self.auth_combo):
            self.auth_combo.clear()
            self.auth_combo.addItems(AUTH_OPTIONS)
        if not self._loading:
            self._on_auth_changed(self.auth_combo.currentText())

    def _on_auth_changed(self, auth: str):
        """Enable/disable password field according to authentication method.

        Args:
            auth: selected auth method.

        Logs:
            - Warns when an unsupported method is seen.
        """
        if auth not in AUTH_OPTIONS:
            logging.warning("Unsupported auth method: %s", auth)
            return
        no_password = auth in OPEN_AUTH
        self.passwd_edit.setEnabled(not no_password)
        if no_password:
            self.passwd_edit.clear()

    def refresh_table(self):
        """Rebuild the table from self.headers/self.rows.

        Behavior:
            - Create a checkbox column, set resize policies, clear selection and load the current row into the form.

        Side effects:
            - UI only; no external I/O.
        """
        self.table.clear()
        self.table.setRowCount(len(self.rows))
        # First column is the checkbox column
        self.table.setColumnCount(len(self.headers) + 1)
        self.table.setHorizontalHeaderLabels([" ", *self.headers])

        for r, row in enumerate(self.rows):
            # checkbox column
            checkbox = QTableWidgetItem()
            checkbox.setFlags(checkbox.flags() | Qt.ItemIsUserCheckable)
            checkbox.setCheckState(Qt.Checked if row.get("tx", "0") == "1" or row.get("rx", "0") == "1" else Qt.Unchecked)
            self.table.setItem(r, 0, checkbox)
            # data columns
            for c, h in enumerate(self.headers):
                item = QTableWidgetItem(row.get(h, ""))
                self.table.setItem(r, c + 1, item)

        self.table.clearSelection()
        self._load_row_to_form(ensure_checked=True)

    def _sync_rows(self):
        """Synchronize self.rows from the table (wrapper of _collect_table_data)."""
        self._collect_table_data()

    def _collect_table_data(self):
        """Collect table data back to self.rows.

        Notes:
            - Only text columns are synced; the checkbox column is handled elsewhere.

        Side effects:
            - Update in-memory structures only.
        """
        data: list[dict[str, str]] = []
        for r in range(self.table.rowCount()):
            row: dict[str, str] = {}
            for c, h in enumerate(self.headers):
                item = self.table.item(r, c + 1)
                row[h] = item.text().strip() if item else ""
            data.append(row)
        self.rows = data

    def reset_form(self) -> None:
        """Reset form widgets to defaults.

        Behavior:
            - If rows exist: use the last row as a template.
            - Else: initialize using current band defaults.
            - Signals are blocked to avoid write-back.

        Side effects:
            - UI updates only.
        """
        self._loading = True
        try:
            with ExitStack() as stack:
                widgets = (self.band_combo, self.wireless_combo, self.channel_combo, self.bandwidth_combo, self.auth_combo, self.passwd_edit, self.ssid_edit, self.tx_check, self.rx_check)
                for w in widgets:
                    stack.enter_context(QSignalBlocker(w))
                if self.rows:
                    data = self.rows[-1]
                    band = data.get("band", "")
                    self.band_combo.setCurrentText(band)
                    self._update_band_options(band)
                    self.wireless_combo.setCurrentText(data.get("wireless_mode", ""))
                    self.channel_combo.setCurrentText(data.get("channel", ""))
                    self.bandwidth_combo.setCurrentText(data.get("bandwidth", ""))
                    self._update_auth_options(self.wireless_combo.currentText())
                    self.auth_combo.setCurrentText(data.get("security_mode", ""))
                    self._on_auth_changed(self.auth_combo.currentText())
                    self.passwd_edit.setText(data.get("password", ""))
                    self.ssid_edit.setText(data.get("ssid", ""))
                    self.tx_check.setChecked(data.get("tx", "0") == "1")
                    self.rx_check.setChecked(data.get("rx", "0") == "1")
                else:
                    if self.band_combo.count():
                        self.band_combo.setCurrentIndex(0)
                    self._update_band_options(self.band_combo.currentText())
                    if self.wireless_combo.count():
                        self.wireless_combo.setCurrentIndex(0)
                    if self.channel_combo.count():
                        self.channel_combo.setCurrentIndex(0)
                    if self.bandwidth_combo.count():
                        self.bandwidth_combo.setCurrentIndex(0)
                    if self.auth_combo.count():
                        self.auth_combo.setCurrentIndex(0)
                    self._on_auth_changed(self.auth_combo.currentText())
                    self.passwd_edit.clear()
                    self.ssid_edit.clear()
                    self.tx_check.setChecked(False)
                    self.rx_check.setChecked(False)
        finally:
            self._loading = False

    def _on_table_cell_clicked(self, row: int, column: int) -> None:
        """Handle table cell click: sync form and checkbox state.

        Behavior:
            - Clicking the checkbox column toggles the check state.
            - Clicking other columns ensures the row is checked, then loads it into the form.

        Args:
            row: row index.
            column: column index.

        Side effects:
            - Update UI state; no direct I/O.
        """
        item = self.table.item(row, 0) if 0 <= row < self.table.rowCount() else None
        if item is None:
            self._load_row_to_form(ensure_checked=False)
            return
        clicked_checkbox = column == 0
        ensure_checked = not clicked_checkbox
        if clicked_checkbox and (item.flags() & Qt.ItemIsUserCheckable):
            item.setCheckState(Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked)
        else:
            self._ensure_row_checked(row)
        self._load_row_to_form(ensure_checked=ensure_checked)

    def _ensure_row_checked(self, row: int) -> None:
        """Ensure a row is checked if it's checkable."""
        item = self.table.item(row, 0) if 0 <= row < self.table.rowCount() else None
        if item is not None and item.flags() & Qt.ItemIsUserCheckable:
            if item.checkState() != Qt.Checked:
                item.setCheckState(Qt.Checked)

    def _load_row_to_form(self, ensure_checked: bool = False):
        """Load the current table row into the left form.

        Args:
            ensure_checked: ensure the current row is checked.

        Notes:
            - Uses QSignalBlocker to prevent a write-back loop.

        Side effects:
            - UI updates only.
        """
        self._loading = True
        try:
            row_index = self.table.currentRow()
            if not (0 <= row_index < len(self.rows)):
                return
            data = self.rows[row_index]
            band = data.get("band", "")
            if ensure_checked:
                item = self.table.item(row_index, 0)
                if item is not None and item.flags() & Qt.ItemIsUserCheckable and item.checkState() != Qt.Checked:
                    item.setCheckState(Qt.Checked)

            # Block signals while filling back the form
            with ExitStack() as stack:
                for w in (self.band_combo, self.wireless_combo, self.channel_combo, self.bandwidth_combo, self.auth_combo, self.passwd_edit, self.ssid_edit):
                    stack.enter_context(QSignalBlocker(w))
                self._update_band_options(band)

            with QSignalBlocker(self.wireless_combo):
                self.wireless_combo.setCurrentText(data.get("wireless_mode", ""))
            with ExitStack() as stack:
                stack.enter_context(QSignalBlocker(self.auth_combo))
                stack.enter_context(QSignalBlocker(self.passwd_edit))
                self._update_auth_options(self.wireless_combo.currentText())
                self._on_auth_changed(self.auth_combo.currentText())
            with QSignalBlocker(self.channel_combo):
                self.channel_combo.setCurrentText(data.get("channel", ""))
            with QSignalBlocker(self.bandwidth_combo):
                self.bandwidth_combo.setCurrentText(data.get("bandwidth", ""))
            with QSignalBlocker(self.auth_combo):
                self.auth_combo.setCurrentText(data.get("security_mode", ""))
            with QSignalBlocker(self.passwd_edit):
                self._on_auth_changed(self.auth_combo.currentText())
            with QSignalBlocker(self.passwd_edit):
                self.passwd_edit.setText(data.get("password", ""))
            with QSignalBlocker(self.ssid_edit):
                self.ssid_edit.setText(data.get("ssid", ""))
            with QSignalBlocker(self.tx_check):
                self.tx_check.setChecked(data.get("tx", "0") == "1")
            with QSignalBlocker(self.rx_check):
                self.rx_check.setChecked(data.get("rx", "0") == "1")
        finally:
            self._loading = False

    def _update_tx_rx(self, state: int):
        """Update current row when TX/RX checkboxes change and write back to the table.

        Args:
            state: Qt.Checked / Qt.Unchecked.

        Side effects:
            - Modify in-memory data and table view, then call save_csv() to persist.
        """
        row = self.table.currentRow()
        if not (0 <= row < len(self.rows)):
            return
        sender = self.sender()
        if sender not in (self.tx_check, self.rx_check):
            return

        is_tx = sender is self.tx_check
        value = "1" if sender.isChecked() else "0"
        self.rows[row]["tx" if is_tx else "rx"] = value
        item = self.table.item(row, 1 + self.headers.index("tx" if is_tx else "rx"))
        if item is None:
            item = QTableWidgetItem(value)
            self.table.setItem(row, 1 + self.headers.index("tx" if is_tx else "rx"), item)
        else:
            item.setText(value)
        self.save_csv()

    def _update_current_row(self, *args):
        """Write current form values back to the current row (excluding tx/rx).

        Notes:
            - Does nothing during _loading to avoid meaningless saves during initialization.

        Side effects:
            - Update table display and call save_csv().
        """
        if self._loading:
            return
        row = self.table.currentRow()
        if not (0 <= row < len(self.rows)):
            return
        mapping = {
            "band": self.band_combo.currentText(),
            "wireless_mode": self.wireless_combo.currentText(),
            "channel": self.channel_combo.currentText(),
            "bandwidth": self.bandwidth_combo.currentText(),
            "security_mode": self.auth_combo.currentText(),
            "password": self.passwd_edit.text(),
            "ssid": self.ssid_edit.text(),
        }
        for k, value in mapping.items():
            self.rows[row][k] = value
            item = self.table.item(row, 1 + self.headers.index(k))
            if item is None:
                item = QTableWidgetItem(value)
                self.table.setItem(row, 1 + self.headers.index(k), item)
            else:
                item.setText(value)
        self.save_csv()

    def add_row(self):
        """Append a new row using current form values and save.

        Validation:
            - SSID is required.
            - Password is required when the password field is enabled.

        Side effects:
            - Update self.rows, refresh the table, and write the CSV.
            - May show InfoBar error messages.
        """
        band = self.band_combo.currentText()
        if not self.ssid_edit.text():
            InfoBar.error(title="Error", content="Pls input ssid", parent=self, position=InfoBarPosition.TOP)
            return
        if self.passwd_edit.isEnabled() and not self.passwd_edit.text():
            InfoBar.error(title="Error", content="Pls input password", parent=self, position=InfoBarPosition.TOP)
            return
        ssid = self.ssid_edit.text()
        row = {
            "band": band,
            "wireless_mode": self.wireless_combo.currentText(),
            "channel": self.channel_combo.currentText(),
            "bandwidth": self.bandwidth_combo.currentText(),
            "security_mode": self.auth_combo.currentText(),
            "ssid": ssid,
            "password": self.passwd_edit.text(),
            "tx": "1" if self.tx_check.isChecked() else "0",
            "rx": "1" if self.rx_check.isChecked() else "0",
        }
        self.rows.append(row)
        self.refresh_table()
        self.save_csv()

    def delete_row(self):
        """Delete all checked rows and save.

        Side effects:
            - Refresh the table and write the CSV.
        """
        new_rows: list[dict[str, str]] = []
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item and item.checkState() == Qt.Checked:
                continue
            row_data: dict[str, str] = {}
            for c, h in enumerate(self.headers):
                cell = self.table.item(r, c + 1)
                row_data[h] = cell.text().strip() if cell else ""
            new_rows.append(row_data)
        self.rows = new_rows
        self.refresh_table()
        self.save_csv()

    def save_csv(self):
        """Validate and write self.rows to the CSV.

        Validation:
            - If password field is enabled, password must be provided.
            - SSID must be provided for every row.

        Side effects:
            - Write to CSV, log success/failure, and show InfoBar on error.
        """
        if self.passwd_edit.isEnabled() and not self.passwd_edit.text():
            InfoBar.error(title="Error", content="Pls input password", parent=self, position=InfoBarPosition.TOP)
            return
        self._collect_table_data()
        if any(not row.get("ssid") for row in self.rows):
            InfoBar.error(title="Error", content="Pls input ssid", parent=self, position=InfoBarPosition.TOP)
            return
        try:
            with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.headers)
                writer.writeheader()
                writer.writerows(self.rows)
            logging.info("CSV saved to %s", self.csv_path)
        except Exception as e:
            InfoBar.error(title="Error", content=str(e), parent=self, position=InfoBarPosition.TOP)
