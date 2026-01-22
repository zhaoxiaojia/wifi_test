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
import logging
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
    QLabel,
    QCheckBox,
    QSpacerItem
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
            "key": self.key,
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


def derive_selected_router_keys(relays: Iterable[Mapping[str, Any]] | None) -> list[str]:
    """
    Derive ``ip:port`` selection keys from configured relay entries.

    The result is filtered against the router catalogue so we only return
    entries that exist in ``compatibility_router.json``.  Ports are coerced
    to integers to normalise values like ``\"1\"`` and ``1``.
    """
    try:
        _, catalog = load_compatibility_router_catalog()
        valid_keys = {row.key for row in catalog}
    except Exception:
        valid_keys = set()

    selected: set[str] = set()
    if relays is None:
        return []

    for item in relays:
        if not isinstance(item, Mapping):
            continue
        ip = str(item.get("ip", "") or "").strip()
        ports_val = item.get("ports") or []
        if isinstance(ports_val, str):
            ports_iter = [p.strip() for p in ports_val.split(",") if p.strip()]
        elif isinstance(ports_val, Iterable):
            ports_iter = ports_val
        else:
            ports_iter = []
        for port in ports_iter:
            try:
                port_str = str(int(port))
            except Exception:
                continue
            key_str = f"{ip}:{port_str}"
            if valid_keys and key_str not in valid_keys:
                continue
            selected.add(key_str)
    return sorted(selected)


def apply_selected_keys_to_relays(
    selected_keys: Iterable[str],
    existing_relays: Iterable[Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    Return a relay list that mirrors ``selected_keys`` while preserving
    non-catalog ports from ``existing_relays``.

    - Ports represented by the router catalogue are controlled solely by
      ``selected_keys`` (checked rows on the Case page).
    - Ports that are not part of the catalogue remain untouched so users
      can keep custom relay wiring outside the compatibility list.
    """
    try:
        _, catalog = load_compatibility_router_catalog()
        valid_keys = {row.key for row in catalog}
    except Exception:
        valid_keys = set()

    # Normalise selected keys -> ip -> {ports}
    selected_map: dict[str, set[int]] = {}
    for key in selected_keys or []:
        if not isinstance(key, str) or ":" not in key:
            continue
        ip, port_str = key.split(":", 1)
        try:
            port = int(port_str)
        except Exception:
            continue
        if valid_keys and key not in valid_keys:
            continue
        selected_map.setdefault(ip.strip(), set()).add(port)

    # Start with any non-catalog ports from existing relays so we do not
    # drop user-entered data that the compatibility table does not know about.
    preserved_map: dict[str, set[int]] = {}
    ordered_ips: list[str] = []

    def _touch_ip(ip_val: str) -> None:
        if ip_val not in ordered_ips:
            ordered_ips.append(ip_val)

    for entry in existing_relays or []:
        if not isinstance(entry, Mapping):
            continue
        ip = str(entry.get("ip", "") or "").strip()
        if not ip:
            continue
        _touch_ip(ip)
        ports_val = entry.get("ports") or []
        ports_iter = ports_val if isinstance(ports_val, Iterable) else []
        for port in ports_iter:
            try:
                port_int = int(port)
            except Exception:
                continue
            key = f"{ip}:{port_int}"
            if valid_keys and key in valid_keys:
                # Catalog-backed ports will be overridden by selected_map.
                continue
            preserved_map.setdefault(ip, set()).add(port_int)

    # Ensure IP order includes any newly selected IPs.
    for ip in selected_map:
        _touch_ip(ip)

    result: list[dict[str, Any]] = []
    for ip in ordered_ips:
        ports: set[int] = set()
        ports.update(preserved_map.get(ip, set()))
        ports.update(selected_map.get(ip, set()))
        if not ports:
            continue
        result.append({"ip": ip, "ports": sorted(ports)})

    return result


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
        # Let the router list occupy all available space on the Case
        # page when used for compatibility testcases.
        size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setSizePolicy(size_policy)

        headers, catalog = load_compatibility_router_catalog()
        self._catalog: list[CompatibilityRouterRow] = catalog
        self._header_labels: list[str] = headers
        self._global_checked = {row.key: True for row in self._catalog}
        self._has_initialized_selection = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        #self._select_all_mode = True
        rows = []
        for row in self._catalog:
            r = row.to_row()
            r["_checked"] = True  # default all selected
            rows.append(r)
        self.list = FormListPage(headers=headers, rows=rows, checkable=True, parent=self)

        # ===== Filter bar =====
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(8)
        filter_layout.setContentsMargins(0, 10, 0, 10)

        filter_label = QLabel("Filter", self)
        filter_label.setFixedWidth(60)
        LABEL_STYLE = """
            font-weight: bold;
            color: #cccccc;
            font-size: 10pt;
        """
        filter_label.setStyleSheet(LABEL_STYLE)
        filter_layout.addWidget(filter_label)

        spacer1 = QSpacerItem(20, 0, QSizePolicy.Fixed, QSizePolicy.Minimum)
        filter_layout.addItem(spacer1)

        # Relay IP filter (ComboBox with all unique IPs, placed before Brand)
        relay_ip_label = QLabel("Relay IP:", self)
        relay_ip_label.setFixedWidth(80)
        #relay_ip_label.setStyleSheet(LABEL_STYLE)
        filter_layout.addWidget(relay_ip_label)

        self.relay_ip_combo = ComboBox(self)
        unique_ips = sorted({row.ip for row in self._catalog if row.ip.strip()})
        self.relay_ip_combo.addItems(["All"] + unique_ips)
        self.relay_ip_combo.setFixedWidth(180)
        filter_layout.addWidget(self.relay_ip_combo)

        # Brand filter
        brand_label = QLabel("Brand:", self)
        brand_label.setFixedWidth(80)
        #brand_label.setStyleSheet(LABEL_STYLE)
        filter_layout.addWidget(brand_label)

        self.brand_combo = ComboBox(self)
        brand_items = ["All"] + sorted({row.brand for row in self._catalog if row.brand})
        self.brand_combo.addItems(brand_items)
        self.brand_combo.setFixedWidth(180)
        filter_layout.addWidget(self.brand_combo)

        spacer2 = QSpacerItem(20, 0, QSizePolicy.Fixed, QSizePolicy.Minimum)
        filter_layout.addItem(spacer2)

        self.select_all_checkbox = QCheckBox("Select All", self)
        self.select_all_checkbox.setChecked(True)
        filter_layout.addWidget(self.select_all_checkbox)

        COMBO_STYLE = """
            background-color: #2a2a2a;
            border: 1px solid #555;
            border-radius: 4px;
            padding: 3px;
            color: white;
            font-size: 9pt;
        """
        self.relay_ip_combo.setStyleSheet(COMBO_STYLE)
        self.brand_combo.setStyleSheet(COMBO_STYLE)

        filter_layout.addStretch(1)
        outer.addLayout(filter_layout)
        # =============================================================

        #self.list = FormListPage(headers=self._header_labels, rows=rows, checkable=True, parent=self)
        self.list.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))
        outer.addWidget(self.list, 1)

        self.list.checkToggled.connect(self._on_check_toggled)

        self.select_all_checkbox.stateChanged.connect(self._on_select_all_changed)
        self.relay_ip_combo.currentTextChanged.connect(self._apply_filters)
        self.brand_combo.currentTextChanged.connect(self._apply_filters)


        # Initial load
        self._apply_filters()
        self.select_all_checkbox.setChecked(True)
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

    # def set_selected_keys(self, keys: Iterable[str]) -> None:
    #     """Update checkboxes based on persisted selection keys."""
    #     key_set = {str(k) for k in keys}
    #     logging.debug("compat set_selected_keys: %s", key_set)
    #     changed = False
    #     for index, row in enumerate(self.list.rows):
    #         target = False
    #         if 0 <= index < len(self._catalog):
    #             target = self._catalog[index].key in key_set
    #         if bool(row.get("_checked")) != target:
    #             row["_checked"] = target
    #             changed = True
    #     if changed:
    #         self.list.set_rows(self.list.rows)
    #         logging.debug("compat rows updated with _checked flags")
    #         self.selectionChanged.emit()
    def set_selected_keys(self, keys: Iterable[str]) -> None:
        """Restore selection from persisted config."""
        """Restore selection from persisted config."""
        keys = list(keys) if keys is not None else []

        if not self._has_initialized_selection:
            # 首次初始化：空输入 → 默认全选
            if not keys:
                key_set = set(self._global_checked.keys())
            else:
                key_set = {str(k) for k in keys}
            self._has_initialized_selection = True  # 标记已完成初始化
        else:
            key_set = {str(k) for k in keys}

        # 更新全局状态
        for key in self._global_checked:
            self._global_checked[key] = (key in key_set)

        # 刷新视图
        self._apply_filters()

        # 更新 Select All checkbox 状态
        all_checked = all(self._global_checked.values())
        self.select_all_checkbox.setChecked(all_checked)

        self.selectionChanged.emit()
    # ------------------------------------------------------------------
    # Internal callbacks
    # ------------------------------------------------------------------

    def _on_check_toggled(self, index: int, checked: bool) -> None:  # noqa: ARG002
        self.selectionChanged.emit()

    def _apply_filters(self):
        selected_ip = self.relay_ip_combo.currentText()
        selected_brand = self.brand_combo.currentText()

        # ===== 修正：通过内部 table 获取滚动条 =====
        table_widget = getattr(self.list, 'table', None)  # 假设内部叫 table
        if table_widget is None:
            # 如果找不到，尝试其他常见命名
            table_widget = getattr(self.list, '_table', None)

        scroll_pos = 0
        if table_widget and hasattr(table_widget, 'verticalScrollBar'):
            vbar = table_widget.verticalScrollBar()
            if vbar:
                scroll_pos = vbar.value()

        filtered_rows = []
        for row in self._catalog:
            if selected_ip != "All" and row.ip != selected_ip:
                continue
            if selected_brand != "All" and row.brand != selected_brand:
                continue

            r = row.to_row()
            # 从全局状态读取，不修改！
            r["_checked"] = self._global_checked.get(row.key, False)
            filtered_rows.append(r)

        self.list.set_rows(filtered_rows)
        if table_widget and hasattr(table_widget, 'verticalScrollBar'):
            vbar = table_widget.verticalScrollBar()
            if vbar and vbar.maximum() > 0:
                vbar.setValue(min(scroll_pos, vbar.maximum()))

    def _on_select_all_changed(self, state):
        check_state = (state == Qt.Checked)

        # 更新全局状态
        for key in self._global_checked:
            self._global_checked[key] = check_state

        # refresh UI
        self._apply_filters()

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
