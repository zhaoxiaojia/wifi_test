"""View layer helpers for UI pages.

This package hosts individual modules for each top-level sidebar page
(account, config, case, run, report, about).  Common helpers for wiring
view events live here so that controllers can keep their logic separate
from Qt signal/slot plumbing.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, Mapping, Sequence
from contextlib import ExitStack

import yaml

from PyQt5.QtCore import Qt, QSignalBlocker, pyqtSignal, QObject
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import CardWidget, ComboBox, LineEdit, PushButton, TableWidget

from src.util.constants import AUTH_OPTIONS, OPEN_AUTH
from src.ui.view.theme import apply_theme, apply_font_and_selection


def _load_view_event_table() -> Dict[str, Any]:
    """Load the global view-event table from the view layer.

    The table is defined in ``view_events.yaml`` next to this module and
    maps high-level view keys (\"config\", \"run\", …) to a list of event
    specifications.  Each specification describes which widget should
    trigger which logical event on the controller side.
    """
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
        Logical view name (\"config\", \"run\", etc.) used as a top-level
        key in ``view_events.yaml``.
    event_handler:
        Callable ``event_handler(page, event: str, **payload)`` that will
        be invoked when a configured event fires.  For the Config page
        this is typically
        :func:`src.ui.view.config.actions.handle_config_event`.
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
            def _handler(*_args: Any) -> None:
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


def _extract_category_from_parts(parts: Sequence[str]) -> str | None:
    """Return the test category (folder under ``test``) from path parts."""
    for index, part in enumerate(parts):
        if part == "test" and index + 1 < len(parts):
            return parts[index + 1].lower()
    return None


def determine_case_category(case_path: str | None = None, display_path: str | None = None) -> str | None:
    """Best-effort category detection for a testcase path.

    The category is defined as the first directory immediately under
    ``test`` within the relative path, for example:

    - ``src/test/stability/test_str.py`` -> ``stability``
    - ``test/compatibility/test_compatibility.py`` -> ``compatibility``
    """
    candidate_paths: list[str] = []
    if display_path:
        candidate_paths.append(str(display_path))
    if case_path:
        candidate_paths.append(str(case_path))

    for raw in candidate_paths:
        normalized = raw.replace("\\", "/")
        parts = PurePosixPath(normalized).parts
        category = _extract_category_from_parts(parts)
        if category:
            return category
    return None


class FormListPage(CardWidget):
    """
    Simple read-only table view for CSV-like data with an optional
    checkbox column.

    This widget does not know anything about routers or specific header
    semantics; callers provide ``headers`` and ``rows`` and handle
    persistence themselves.
    """

    rowsChanged = pyqtSignal()
    currentRowChanged = pyqtSignal(int)
    checkToggled = pyqtSignal(int, bool)

    def __init__(
        self,
        headers: Sequence[str],
        rows: Sequence[Mapping[str, Any]] | None = None,
        *,
        checkable: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        apply_theme(self)
        self.setObjectName("caseListPage")

        self.headers: list[str] = [str(h).strip() for h in headers]
        self.rows: list[dict[str, Any]] = [dict(r) for r in (rows or [])]
        self.checkable = bool(checkable)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.table = TableWidget(self)
        self.table.setAlternatingRowColors(False)
        self.table.setSortingEnabled(False)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setMinimumSectionSize(100)
        layout.addWidget(self.table, 1)

        apply_theme(header)
        apply_font_and_selection(self.table)

        self.table.cellClicked.connect(self._on_cell_clicked)

        self._refresh_table()

    # ------------------------------------------------------------------
    # Data API
    # ------------------------------------------------------------------

    def set_data(self, headers: Sequence[str], rows: Sequence[Mapping[str, Any]] | None) -> None:
        self.headers = [str(h).strip() for h in headers]
        self.rows = [dict(r) for r in (rows or [])]
        self._refresh_table()
        self.rowsChanged.emit()

    def data(self) -> tuple[list[str], list[dict[str, Any]]]:
        return list(self.headers), [dict(r) for r in self.rows]

    def current_row(self) -> int:
        return self.table.currentRow()

    def set_current_row(self, index: int) -> None:
        if not self.rows:
            return
        index = max(0, min(index, len(self.rows) - 1))
        self.table.setCurrentCell(index, 0)
        self.currentRowChanged.emit(index)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _refresh_table(self) -> None:
        self.table.clear()
        if not self.headers:
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            return

        self.table.setRowCount(len(self.rows))
        if self.checkable:
            self.table.setColumnCount(len(self.headers) + 1)
            self.table.setHorizontalHeaderLabels([" ", *self.headers])
        else:
            self.table.setColumnCount(len(self.headers))
            self.table.setHorizontalHeaderLabels([str(h) for h in self.headers])

        for r, row in enumerate(self.rows):
            col_offset = 0
            if self.checkable:
                checkbox = QTableWidgetItem()
                checkbox.setFlags(checkbox.flags() | Qt.ItemIsUserCheckable)
                checkbox.setCheckState(Qt.Checked if row.get("_checked") else Qt.Unchecked)
                self.table.setItem(r, 0, checkbox)
                col_offset = 1
            for c, h in enumerate(self.headers):
                item = QTableWidgetItem(str(row.get(h, "")))
                self.table.setItem(r, c + col_offset, item)

        self.table.clearSelection()
        if self.rows:
            self.table.setCurrentCell(0, 0)
            self.currentRowChanged.emit(0)

    def _on_cell_clicked(self, row: int, column: int) -> None:  # noqa: ARG002
        if not (0 <= row < len(self.rows)):
            return
        self.table.selectRow(row)
        self.currentRowChanged.emit(row)
        item = self.table.item(row, 0)
        if not self.checkable or item is None or not (item.flags() & Qt.ItemIsUserCheckable):
            return
        new_state = Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked
        item.setCheckState(new_state)
        checked = new_state == Qt.Checked
        # Store lightweight flag so that refresh_table can restore state.
        self.rows[row]["_checked"] = checked
        self.checkToggled.emit(row, checked)
        self.rowsChanged.emit()

    # ------------------------------------------------------------------
    # Row-level helpers (for orchestration pages)
    # ------------------------------------------------------------------

    def set_rows(self, rows: Sequence[Mapping[str, Any]] | None) -> None:
        """Replace the underlying rows and refresh the table."""
        self.rows = [dict(r) for r in (rows or [])]
        self._refresh_table()
        self.rowsChanged.emit()

    def update_row(self, index: int, row: Mapping[str, Any]) -> None:
        """Update a single row in-place and refresh its cells."""
        if not (0 <= index < len(self.rows)):
            return
        self.rows[index] = dict(row)
        if not self.headers:
            return
        col_offset = 1 if self.checkable else 0
        # Checkbox column
        if self.checkable:
            checkbox = self.table.item(index, 0)
            if checkbox is None:
                checkbox = QTableWidgetItem()
                checkbox.setFlags(checkbox.flags() | Qt.ItemIsUserCheckable)
                self.table.setItem(index, 0, checkbox)
            checked = bool(self.rows[index].get("_checked"))
            checkbox.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        # Data columns
        for c, h in enumerate(self.headers):
            item = self.table.item(index, c + col_offset)
            if item is None:
                item = QTableWidgetItem()
                self.table.setItem(index, c + col_offset, item)
            item.setText(str(self.rows[index].get(h, "")))


class RouterConfigForm(CardWidget):
    """
    Left-side form used to edit a single router Wi‑Fi row (band/SSID/etc.).

    The form emits high-level signals when the row changes or when the
    user requests to add/delete a row; it does not manage any table
    widgets or CSV persistence itself.
    """

    rowChanged = pyqtSignal(dict)
    addRequested = pyqtSignal(dict)
    deleteRequested = pyqtSignal()

    def __init__(
        self,
        router: Any | None,
        *,
        fields: Sequence[str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        apply_theme(self)

        self.router = router
        self._loading = False
        self._all_fields: tuple[str, ...] = (
            "band",
            "wireless_mode",
            "channel",
            "bandwidth",
            "security_mode",
            "password",
            "ssid",
            "tx",
            "rx",
        )
        if fields is None:
            self.fields: list[str] = list(self._all_fields)
        else:
            self.fields = [f for f in fields if f in self._all_fields]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        form_box = QGroupBox(self)
        apply_theme(form_box, recursive=True)
        form_layout = QFormLayout(form_box)

        self.band_combo = ComboBox(form_box)
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

        test_widget = QWidget(form_box)
        test_layout = QHBoxLayout(test_widget)
        test_layout.setContentsMargins(0, 0, 0, 0)
        self.tx_check = QCheckBox("tx", test_widget)
        self.rx_check = QCheckBox("rx", test_widget)
        test_layout.addWidget(self.tx_check)
        test_layout.addWidget(self.rx_check)
        form_layout.addRow("direction", test_widget)

        btn_widget = QWidget(form_box)
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        self.del_btn = PushButton("Del", btn_widget)
        btn_layout.addWidget(self.del_btn)
        self.add_btn = PushButton("Add", btn_widget)
        btn_layout.addWidget(self.add_btn)
        form_layout.addRow(btn_widget)

        layout.addWidget(form_box, 1)
        # 根据 fields 隐藏不需要展示的行（仅影响 UI，不改变内部数据结构）。
        field_widget_map: dict[str, QWidget] = {
            "band": self.band_combo,
            "wireless_mode": self.wireless_combo,
            "channel": self.channel_combo,
            "bandwidth": self.bandwidth_combo,
            "security_mode": self.auth_combo,
            "password": self.passwd_edit,
            "ssid": self.ssid_edit,
            "tx": self.tx_check,
            "rx": self.rx_check,
        }
        visible_fields = set(self.fields)
        for name, widget in field_widget_map.items():
            if name in visible_fields:
                continue
            label = form_layout.labelForField(widget)
            if label is not None:
                label.hide()
            widget.hide()

        # Populate band choices based on router when available.
        band_list = getattr(self.router, "BAND_LIST", ["2.4G", "5G"])
        self.band_combo.addItems(band_list)

        # Wire up interactions.
        self.band_combo.currentTextChanged.connect(self._on_band_changed)
        self.auth_combo.currentTextChanged.connect(self._on_auth_changed)

        for widget in (
            self.wireless_combo,
            self.channel_combo,
            self.bandwidth_combo,
            self.ssid_edit,
            self.passwd_edit,
            self.tx_check,
            self.rx_check,
        ):
            if isinstance(widget, ComboBox):
                widget.currentTextChanged.connect(self._emit_row_changed)
            elif isinstance(widget, LineEdit):
                widget.textChanged.connect(self._emit_row_changed)
            elif isinstance(widget, QCheckBox):
                widget.stateChanged.connect(lambda _state, w=widget: self._emit_row_changed())

        self.add_btn.clicked.connect(self._on_add_clicked)
        self.del_btn.clicked.connect(self._on_delete_clicked)

        # Initialise dependent combos based on the default band.
        if self.band_combo.count():
            self._update_band_options(self.band_combo.currentText())
            self.reset_form()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_router(self, router: Any | None) -> None:
        self.router = router
        # Re-populate mode/channel/bandwidth combos for the current band.
        self._update_band_options(self.band_combo.currentText())

    def load_row(self, data: Mapping[str, Any] | None) -> None:
        """Populate form fields from ``data`` (may be empty)."""
        data = data or {}
        self._loading = True
        try:
            band = str(data.get("band", "") or "")
            with ExitStack() as stack:
                for w in (
                    self.band_combo,
                    self.wireless_combo,
                    self.channel_combo,
                    self.bandwidth_combo,
                    self.auth_combo,
                    self.passwd_edit,
                    self.ssid_edit,
                ):
                    stack.enter_context(QSignalBlocker(w))
                self._update_band_options(band)
                if band:
                    self.band_combo.setCurrentText(band)

            with QSignalBlocker(self.wireless_combo):
                self.wireless_combo.setCurrentText(str(data.get("wireless_mode", "") or ""))

            with ExitStack() as stack:
                stack.enter_context(QSignalBlocker(self.auth_combo))
                stack.enter_context(QSignalBlocker(self.passwd_edit))
                self._update_auth_options(self.wireless_combo.currentText())
                self._on_auth_changed(self.auth_combo.currentText())

            with QSignalBlocker(self.channel_combo):
                self.channel_combo.setCurrentText(str(data.get("channel", "") or ""))
            with QSignalBlocker(self.bandwidth_combo):
                self.bandwidth_combo.setCurrentText(str(data.get("bandwidth", "") or ""))
            with QSignalBlocker(self.auth_combo):
                self.auth_combo.setCurrentText(str(data.get("security_mode", "") or ""))
            with QSignalBlocker(self.passwd_edit):
                self.passwd_edit.setText(str(data.get("password", "") or ""))
            with QSignalBlocker(self.ssid_edit):
                self.ssid_edit.setText(str(data.get("ssid", "") or ""))
            with QSignalBlocker(self.tx_check):
                self.tx_check.setChecked(str(data.get("tx", "0") or "0") == "1")
            with QSignalBlocker(self.rx_check):
                self.rx_check.setChecked(str(data.get("rx", "0") or "0") == "1")
        finally:
            self._loading = False

    def reset_form(self) -> None:
        self._loading = True
        try:
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

    def current_row_data(self) -> dict[str, str]:
        data = {
            "band": self.band_combo.currentText().strip(),
            "wireless_mode": self.wireless_combo.currentText().strip(),
            "channel": self.channel_combo.currentText().strip(),
            "bandwidth": self.bandwidth_combo.currentText().strip(),
            "security_mode": self.auth_combo.currentText().strip(),
            "password": self.passwd_edit.text(),
            "ssid": self.ssid_edit.text(),
            "tx": "1" if self.tx_check.isChecked() else "0",
            "rx": "1" if self.rx_check.isChecked() else "0",
        }
        # When a field subset is configured, only expose those keys.
        if getattr(self, "fields", None):
            return {k: v for k, v in data.items() if k in self.fields}
        return data

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _emit_row_changed(self) -> None:
        if self._loading:
            return
        self.rowChanged.emit(self.current_row_data())

    def _update_band_options(self, band: str) -> None:
        from src.util.constants import RouterConst  # local import to avoid heavy deps at module import time

        wireless = RouterConst.DEFAULT_WIRELESS_MODES.get(band, [])
        router = self.router
        if band == "2.4G":
            channel = getattr(router, "CHANNEL_2", []) if router is not None else []
            bandwidth = getattr(router, "BANDWIDTH_2", []) if router is not None else []
        elif band == "5G":
            channel = getattr(router, "CHANNEL_5", []) if router is not None else []
            bandwidth = getattr(router, "BANDWIDTH_5", []) if router is not None else []
        else:
            channel = []
            bandwidth = []
        with QSignalBlocker(self.wireless_combo), QSignalBlocker(self.channel_combo), QSignalBlocker(
            self.bandwidth_combo
        ):
            self.wireless_combo.clear()
            self.wireless_combo.addItems(list(wireless))
            self.channel_combo.clear()
            self.channel_combo.addItems(list(channel))
            self.bandwidth_combo.clear()
            self.bandwidth_combo.addItems(list(bandwidth))
        if not self._loading:
            self._update_auth_options(self.wireless_combo.currentText())

    def _on_band_changed(self, band: str) -> None:
        self._update_band_options(band)
        self._emit_row_changed()

    def _update_auth_options(self, wireless: str) -> None:  # noqa: ARG002
        with QSignalBlocker(self.auth_combo):
            self.auth_combo.clear()
            self.auth_combo.addItems(AUTH_OPTIONS)
        if not self._loading:
            self._on_auth_changed(self.auth_combo.currentText())

    def _on_auth_changed(self, auth: str) -> None:
        if auth not in AUTH_OPTIONS:
            return
        no_password = auth in OPEN_AUTH
        self.passwd_edit.setEnabled(not no_password)
        if no_password:
            self.passwd_edit.clear()

    def _on_add_clicked(self) -> None:
        self.addRequested.emit(self.current_row_data())

    def _on_delete_clicked(self) -> None:
        self.deleteRequested.emit()


class FormListBinder(QObject):
    """
    Lightweight helper that keeps a form widget and a FormListPage
    synchronised via a shared list of row dictionaries.

    The binder assumes:

    - ``form`` exposes ``rowChanged(dict)``, ``addRequested(dict)`` and
      ``deleteRequested()`` signals plus a ``load_row(mapping)`` method.
    - ``list_widget`` is a :class:`FormListPage` (or compatible) with
      ``currentRowChanged(int)``, ``current_row()``, ``set_rows()`` and
      ``update_row()`` helpers.

    Callers supply the shared ``rows`` list and optional callbacks:

    - ``on_row_updated(index, row)`` is invoked after a row is merged with
      form data but before the list widget is refreshed, allowing callers
      to adjust fields such as ``_checked`` flags.
    - ``on_rows_changed(rows)`` runs after rows have been added/removed or
      updated, so controllers can trigger persistence (CSV/YAML) or emit
      higher-level signals.
    """

    def __init__(
        self,
        form: QObject,
        list_widget: Any,
        rows: list[dict[str, Any]],
        *,
        on_row_updated: Any | None = None,
        on_rows_changed: Any | None = None,
        bind_add: bool = True,
        bind_delete: bool = True,
    ) -> None:
        super().__init__(form)
        self._form = form
        self._list = list_widget
        self._rows = rows
        self._on_row_updated = on_row_updated
        self._on_rows_changed = on_rows_changed

        # Selection changes: populate form from the active row.
        if hasattr(self._list, "currentRowChanged"):
            self._list.currentRowChanged.connect(self._on_list_row_changed)

        # Form edits: merge into current row and refresh list.
        if hasattr(self._form, "rowChanged"):
            self._form.rowChanged.connect(self._on_form_row_changed)

        # Optional add/delete wiring.
        if bind_add and hasattr(self._form, "addRequested"):
            self._form.addRequested.connect(self._on_form_add_requested)
        if bind_delete and hasattr(self._form, "deleteRequested"):
            self._form.deleteRequested.connect(self._on_form_delete_requested)

    # ------------------------------------------------------------------
    # Internal slots
    # ------------------------------------------------------------------

    def _on_list_row_changed(self, index: int) -> None:
        if not (0 <= index < len(self._rows)):
            return
        row = self._rows[index]
        load = getattr(self._form, "load_row", None)
        if callable(load):
            load(row)

    def _current_index(self) -> int:
        getter = getattr(self._list, "current_row", None)
        if callable(getter):
            try:
                return int(getter())
            except Exception:
                return -1
        return -1

    def _on_form_row_changed(self, data: Mapping[str, Any]) -> None:
        index = self._current_index()
        if not (0 <= index < len(self._rows)):
            return
        row = dict(self._rows[index])
        row.update(dict(data))
        if callable(self._on_row_updated):
            self._on_row_updated(index, row)
        self._rows[index] = row
        if hasattr(self._list, "update_row"):
            self._list.update_row(index, row)
        if callable(self._on_rows_changed):
            self._on_rows_changed(self._rows)

    def _on_form_add_requested(self, data: Mapping[str, Any]) -> None:
        row = dict(data)
        self._rows.append(row)
        if hasattr(self._list, "set_rows"):
            self._list.set_rows(self._rows)
        # Move selection to the new row if helper is available.
        setter = getattr(self._list, "set_current_row", None)
        if callable(setter) and self._rows:
            setter(len(self._rows) - 1)
        if callable(self._on_rows_changed):
            self._on_rows_changed(self._rows)

    def _on_form_delete_requested(self) -> None:
        index = self._current_index()
        if not (0 <= index < len(self._rows)):
            return
        del self._rows[index]
        if hasattr(self._list, "set_rows"):
            self._list.set_rows(self._rows)
        if self._rows:
            setter = getattr(self._list, "set_current_row", None)
            if callable(setter):
                setter(min(index, len(self._rows) - 1))
        if callable(self._on_rows_changed):
            self._on_rows_changed(self._rows)

# Backwards-compatible alias for existing imports.


__all__ = [
    "bind_view_events",
    "FormListPage",
    "RouterConfigForm",
    "determine_case_category",
    "FormListBinder",
]
