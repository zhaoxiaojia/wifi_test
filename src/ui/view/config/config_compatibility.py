"""Compatibility Settings view helpers.

This module provides the :class:`CompatibilityConfigPage` which is a
pure-view component responsible for visualising the compatibility router
table and power‑control selections.

The page is intentionally UI‑only:

- It loads the static router catalogue from ``config/compatibility_router.json``.
- It exposes a checkable :class:`FormListPage` table so controllers can
  drive which routers are enabled for a given test.
- It does *not* know how to persist any configuration; controllers are
  expected to map the selection into ``config_compatibility.yaml``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping
import json

from PyQt5.QtCore import Qt, pyqtSignal, QSignalBlocker
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
    QFormLayout,
    QGroupBox,
)
from qfluentwidgets import CardWidget, ComboBox, LineEdit, PushButton

from src.util.constants import Paths
from src.ui.view.theme import apply_theme
from src.ui.view import FormListPage, FormListBinder


@dataclass(frozen=True)
class CompatibilityRouterRow:
    """Flattened representation of a single compatibility router entry."""

    key: str
    ip: str
    port: str
    brand: str
    model: str
    mode_24g: str
    sec_24g: str
    bw_24g: str
    mode_5g: str
    sec_5g: str
    bw_5g: str

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "CompatibilityRouterRow":
        ip = str(data.get("ip", "") or "")
        port = str(data.get("port", "") or "")
        brand = str(data.get("brand", "") or "")
        model = str(data.get("model", "") or "")
        b24 = data.get("2.4G") if isinstance(data.get("2.4G"), Mapping) else {}
        b5 = data.get("5G") if isinstance(data.get("5G"), Mapping) else {}
        mode_24g = str(b24.get("mode", "") or "")
        sec_24g = str(b24.get("security_mode", "") or "")
        bw_24g = str(b24.get("bandwidth", "") or "")
        mode_5g = str(b5.get("mode", "") or "")
        sec_5g = str(b5.get("security_mode", "") or "")
        bw_5g = str(b5.get("bandwidth", "") or "")
        key = f"{ip}:{port}" if ip or port else model
        return cls(
            key=key,
            ip=ip,
            port=port,
            brand=brand,
            model=model,
            mode_24g=mode_24g,
            sec_24g=sec_24g,
            bw_24g=bw_24g,
            mode_5g=mode_5g,
            sec_5g=sec_5g,
            bw_5g=bw_5g,
        )

    def to_row(self) -> dict[str, str]:
        return {
            "ip": self.ip,
            "port": self.port,
            "brand": self.brand,
            "model": self.model,
            "2.4G mode": self.mode_24g,
            "2.4G security": self.sec_24g,
            "2.4G bandwidth": self.bw_24g,
            "5G mode": self.mode_5g,
            "5G security": self.sec_5g,
            "5G bandwidth": self.bw_5g,
        }


def load_compatibility_router_catalog() -> tuple[list[str], list[CompatibilityRouterRow]]:
    """Load and normalise router entries from ``config/compatibility_router.json``."""
    config_dir = Path(Paths.CONFIG_DIR)
    path = config_dir / "compatibility_router.json"
    try:
        text = path.read_text(encoding="utf-8")
        raw = json.loads(text)
    except Exception:
        raw = []
    rows: list[CompatibilityRouterRow] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, Mapping):
                rows.append(CompatibilityRouterRow.from_mapping(item))
    headers = [
        "ip",
        "port",
        "brand",
        "model",
        "2.4G mode",
        "2.4G security",
        "2.4G bandwidth",
        "5G mode",
        "5G security",
        "5G bandwidth",
    ]
    return headers, rows


class CompatibilityConfigPage(CardWidget):
    """Compatibility Settings view (router list + checkboxes).

    This widget owns a single :class:`FormListPage` that presents all entries
    from ``compatibility_router.json`` with a checkbox column.  Controllers
    can:

    - query :meth:`selected_keys` to obtain the current selection as a set
      of router identifiers (``ip:port``).
    - call :meth:`set_selected_keys` to reflect persisted state from
      ``config_compatibility.yaml``.
    """

    selectionChanged = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        apply_theme(self)
        self.setObjectName("compatibilityConfigPage")

        headers, catalog = load_compatibility_router_catalog()
        self._catalog: list[CompatibilityRouterRow] = catalog
        self._header_labels: list[str] = headers

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        content = QWidget(self)
        layout = QHBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        outer.addWidget(content, 1)

        rows = [row.to_row() for row in self._catalog]
        self.list = FormListPage(headers=self._header_labels, rows=rows, checkable=True, parent=content)
        # Show fewer visible rows when embedded in narrow layouts.
        size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setSizePolicy(size_policy)
        layout.addWidget(self.list, 1)

        self.list.checkToggled.connect(self._on_check_toggled)

    # ------------------------------------------------------------------
    # Public API used by controllers
    # ------------------------------------------------------------------

    def selected_keys(self) -> set[str]:
        """Return the set of currently checked router keys (``ip:port``)."""
        selected: set[str] = set()
        for index, row in enumerate(self.list.rows):
            checked = bool(row.get("_checked"))
            if not checked:
                continue
            if 0 <= index < len(self._catalog):
                selected.add(self._catalog[index].key)
        return selected

    def set_selected_keys(self, keys: Iterable[str]) -> None:
        """Update checkboxes based on persisted selection keys."""
        key_set = {str(k) for k in keys}
        changed = False
        for index, row in enumerate(self.list.rows):
            target = False
            if 0 <= index < len(self._catalog):
                target = self._catalog[index].key in key_set
            if bool(row.get("_checked")) != target:
                row["_checked"] = target
                changed = True
        if changed:
            self.list.set_rows(self.list.rows)
            self.selectionChanged.emit()

    # ------------------------------------------------------------------
    # Internal callbacks
    # ------------------------------------------------------------------

    def _on_check_toggled(self, index: int, checked: bool) -> None:  # noqa: ARG002
        self.selectionChanged.emit()


class CompatibilityRelayEditor(QWidget):
    """Composite editor for multiple power relays (IP + ports)."""

    entriesChanged = pyqtSignal()
    rowChanged = pyqtSignal(dict)
    addRequested = pyqtSignal(dict)
    deleteRequested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        apply_theme(self, recursive=True)

        self._rows: list[dict[str, Any]] = []

        self._loading = False

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        # Left: simple form for single relay.
        form_box = QGroupBox("Relay", self)
        apply_theme(form_box, recursive=True)
        form_layout = QFormLayout(form_box)

        self.ip_edit = LineEdit(form_box)
        self.ip_edit.setPlaceholderText("192.168.200.x")
        form_layout.addRow("IP", self.ip_edit)

        self.ports_edit = LineEdit(form_box)
        self.ports_edit.setPlaceholderText("1,2,3,4,5,6,7,8")
        form_layout.addRow("Ports", self.ports_edit)

        btn_row = QWidget(form_box)
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        self.del_btn = PushButton("Del", btn_row)
        self.add_btn = PushButton("Add", btn_row)
        btn_layout.addWidget(self.del_btn)
        btn_layout.addWidget(self.add_btn)
        form_layout.addRow(btn_row)

        outer.addWidget(form_box, 2)

        # Right: table of configured relays.
        self.list = FormListPage(headers=["ip", "ports"], rows=[], checkable=False, parent=self)
        size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.list.setSizePolicy(size_policy)
        outer.addWidget(self.list, 5)

        self.add_btn.clicked.connect(self._on_add_clicked)
        self.del_btn.clicked.connect(self._on_del_clicked)

        # Emit rowChanged whenever IP/Ports edits change so that the
        # shared FormListBinder can update the active row.
        self.ip_edit.textChanged.connect(self._emit_row_changed)
        self.ports_edit.textChanged.connect(self._emit_row_changed)

        # Shared binder for form/list synchronisation.
        self._binder = FormListBinder(
            form=self,
            list_widget=self.list,
            rows=self._rows,
            on_rows_changed=lambda _rows: self.entriesChanged.emit(),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_relays(self, relays: Iterable[Mapping[str, Any]] | None) -> None:

        rows: list[dict[str, Any]] = []
        if relays is not None:
            for item in relays:
                if not isinstance(item, Mapping):
                    continue
                ip = str(item.get("ip", "") or "").strip()
                ports_val = item.get("ports", [])
                if isinstance(ports_val, list):
                    ports_str = ",".join(str(int(p)) for p in ports_val if str(p).isdigit())
                else:
                    ports_str = str(ports_val or "").strip()
                if not ip and not ports_str:
                    continue
                rows.append({"ip": ip, "ports": ports_str})
        # Important: mutate in-place so that the shared rows list used by
        # FormListBinder stays in sync. Rebinding self._rows would leave
        # the binder holding an outdated list reference.
        self._rows[:] = rows
        self.list.set_rows(self._rows)
        if self._rows:
            self.list.set_current_row(0)
        self.entriesChanged.emit()

    def relays(self) -> list[dict[str, Any]]:
        """Return configuration-friendly relay entries."""
        result: list[dict[str, Any]] = []
        for row in self._rows:
            ip = str(row.get("ip", "") or "").strip()
            ports_str = str(row.get("ports", "") or "").strip()
            if not ip:
                continue
            ports: list[int] = []
            for token in ports_str.split(","):
                token = token.strip()
                if not token:
                    continue
                if token.isdigit():
                    ports.append(int(token))
            result.append({"ip": ip, "ports": ports})
        return result

    # ------------------------------------------------------------------
    # Internal slots
    # ------------------------------------------------------------------

    def load_row(self, row: Mapping[str, Any]) -> None:
        """Populate the relay form from a row mapping."""
        self._loading = True
        try:
            with QSignalBlocker(self.ip_edit), QSignalBlocker(self.ports_edit):
                self.ip_edit.setText(str(row.get("ip", "") or ""))
                self.ports_edit.setText(str(row.get("ports", "") or ""))
        finally:
            self._loading = False

    def _emit_row_changed(self) -> None:
        if self._loading:
            return
        data = {
            "ip": self.ip_edit.text().strip(),
            "ports": self.ports_edit.text().strip(),
        }
        self.rowChanged.emit(data)

    def _on_add_clicked(self) -> None:
        ip = self.ip_edit.text().strip()
        ports = self.ports_edit.text().strip()
        if not ip:
            return
        row = {"ip": ip, "ports": ports}
        self.addRequested.emit(row)

    def _on_del_clicked(self) -> None:
        self.deleteRequested.emit()

    # Backwards-compatible helpers used by FormListBinder --------------------

    def _on_current_row_changed(self, index: int) -> None:
        if not (0 <= index < len(self._rows)):
            return
        row = self._rows[index]
        self.ip_edit.setText(str(row.get("ip", "") or ""))
        self.ports_edit.setText(str(row.get("ports", "") or ""))
