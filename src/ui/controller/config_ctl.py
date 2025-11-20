from __future__ import annotations

import copy
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Optional,Sequence

from PyQt5.QtCore import QTimer, QSignalBlocker,QSortFilterProxyModel
from PyQt5.QtWidgets import QCheckBox, QSpinBox, QDoubleSpinBox
from qfluentwidgets import InfoBar, InfoBarPosition, ComboBox, LineEdit

from src.ui.view.config.actions import compute_editable_info, apply_config_ui_rules
from src.ui.view.common import EditableInfo
from src.tools.config_loader import load_config, save_config
from src import display_to_case_path
from src.util.constants import (
    SWITCH_WIFI_CASE_ALIASES,
    SWITCH_WIFI_CASE_KEY,
    SWITCH_WIFI_CASE_KEYS,
    SWITCH_WIFI_ENTRY_PASSWORD_FIELD,
    SWITCH_WIFI_ENTRY_SECURITY_FIELD,
    SWITCH_WIFI_ENTRY_SSID_FIELD,
    SWITCH_WIFI_MANUAL_ENTRIES_FIELD,
    SWITCH_WIFI_ROUTER_CSV_FIELD,
    SWITCH_WIFI_USE_ROUTER_FIELD,
    TOOL_SECTION_KEY,
    WIFI_PRODUCT_PROJECT_MAP,
    TURN_TABLE_SECTION_KEY,
    TURN_TABLE_FIELD_MODEL,
    TURN_TABLE_FIELD_IP_ADDRESS,
    TURN_TABLE_FIELD_STEP,
    TURN_TABLE_FIELD_STATIC_DB,
    TURN_TABLE_FIELD_TARGET_RSSI,
    TURN_TABLE_MODEL_CHOICES,
    TURN_TABLE_MODEL_RS232,
    TURN_TABLE_MODEL_OTHER,
    get_config_base,
    get_src_base,
)
from src.ui.rvrwifi_proxy import (
    _load_csv_selection_from_config as _proxy_load_csv_selection_from_config,
    _resolve_csv_config_path as _proxy_resolve_csv_config_path,
    _update_csv_options as _proxy_update_csv_options,
    _capture_preselected_csv as _proxy_capture_preselected_csv,
    _normalize_csv_path as _proxy_normalize_csv_path,
    _relativize_config_path as _proxy_relativize_config_path,
    _find_csv_index as _proxy_find_csv_index,
    _set_selected_csv as _proxy_set_selected_csv,
    _populate_csv_combo as _proxy_populate_csv_combo,
    _refresh_registered_csv_combos as _proxy_refresh_registered_csv_combos,
    _load_switch_wifi_entries as _proxy_load_switch_wifi_entries,
    _update_switch_wifi_preview as _proxy_update_switch_wifi_preview,
    _update_rvr_nav_button as _proxy_update_rvr_nav_button,
    _open_rvr_wifi_config as _proxy_open_rvr_wifi_config,
)
from src.ui.view.common import ScriptConfigEntry, TestFileFilterModel
from src.ui.view.config import RfStepSegmentsWidget, SwitchWifiManualEditor
from src.ui.view.config.config_switch_wifi import normalize_switch_wifi_manual_entries
from src.ui.view.config.config_str import script_field_key
from src.ui.controller import show_info_bar

if TYPE_CHECKING:  # pragma: no cover - circular import guard
    from src.ui.case_config_page import CaseConfigPage


class ConfigController:
    """
    Controller responsible for configuration lifecycle and normalisation
    for the Config page.

    This keeps all config I/O and structural cleanup out of the Qt widget
    class so that CaseConfigPage can focus on wiring UI and delegating
    business logic.
    """

    def __init__(self, page: "CaseConfigPage") -> None:
        self.page = page

    def get_application_base(self) -> Path:
        """Return the application source base path (was CaseConfigPage._get_application_base)."""
        return Path(get_src_base()).resolve()

    def init_case_tree(self, root_dir: Path) -> None:
        """Initialize the case tree model + proxy (migrated from CaseConfigPage).

        This constructs a QFileSystemModel rooted at `root_dir` and attaches a
        TestFileFilterModel proxy so that only test_*.py files (and directories)
        are visible. The tree widget on the page is configured accordingly.
        """
        page = self.page
        try:
            from PyQt5.QtWidgets import QFileSystemModel
        except Exception:
            return
        # create/replace models on the page
        page.fs_model = QFileSystemModel(page.case_tree)
        root_index = page.fs_model.setRootPath(str(root_dir))
        page.fs_model.setNameFilters(["test_*.py"])
        page.fs_model.setNameFilterDisables(True)
        from PyQt5.QtCore import QDir

        page.fs_model.setFilter(QDir.Filter.AllDirs | QDir.Filter.NoDotAndDotDot | QDir.Filter.Files)
        page.proxy_model = TestFileFilterModel()
        page.proxy_model.setSourceModel(page.fs_model)
        page.case_tree.setModel(page.proxy_model)
        page.case_tree.setRootIndex(page.proxy_model.mapFromSource(root_index))
        # hide non-name columns
        try:
            page.case_tree.header().hide()
            for col in range(1, page.fs_model.columnCount()):
                page.case_tree.hideColumn(col)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def load_initial_config(self) -> dict:
        """
        Load configuration data from disk and normalise persisted paths.

        - Populates page.config
        - Captures the TOOL_SECTION snapshot for change detection
        - Restores CSV selection into page.selected_csv_path if supported
        """
        page = self.page
        try:
            config = load_config(refresh=True) or {}

            app_base = self.get_application_base()
            changed = False
            path = config.get("text_case", "")
            if path:
                abs_path = Path(path)
                if not abs_path.is_absolute():
                    abs_path = app_base / abs_path
                abs_path = abs_path.resolve()
                if abs_path.exists():
                    try:
                        rel_path = abs_path.relative_to(app_base)
                    except ValueError:
                        config["text_case"] = ""
                        changed = True
                    else:
                        rel_str = rel_path.as_posix()
                        if rel_str != path:
                            config["text_case"] = rel_str
                            changed = True
                else:
                    config["text_case"] = ""
                    changed = True
            else:
                config["text_case"] = ""

            if changed:
                try:
                    save_config(config)
                except Exception as exc:  # pragma: no cover - UI only feedback
                    logging.error("Failed to normalize and persist config: %s", exc)
                    QTimer.singleShot(
                        0,
                        lambda exc=exc: InfoBar.error(
                            title="Error",
                            content=f"Failed to write config: {exc}",
                            parent=page,
                            position=InfoBarPosition.TOP,
                        ),
                    )
            page.config = config
        except Exception as exc:  # pragma: no cover - UI only feedback
            QTimer.singleShot(
                0,
                lambda exc=exc: InfoBar.error(
                    title="Error",
                    content=f"Failed to load config : {exc}",
                    parent=page,
                    position=InfoBarPosition.TOP,
                ),
            )
            page.config = {}

        # Capture snapshot for tool section and restore CSV selection.
        snapshot = copy.deepcopy(page.config.get(TOOL_SECTION_KEY, {}))
        setattr(page, "_config_tool_snapshot", snapshot)

        try:
            _proxy_load_csv_selection_from_config(page)
        except Exception:
            pass

        return page.config

    def save_config(self) -> None:
        """Persist the active configuration and refresh cached state."""
        page = self.page
        logging.debug("[save] data=%s", page.config)
        try:
            save_config(page.config)
            logging.info("Configuration saved")
            refreshed = self.load_initial_config()
            if hasattr(page, "_config_tool_snapshot"):
                page._config_tool_snapshot = copy.deepcopy(
                    refreshed.get(TOOL_SECTION_KEY, {})
                )
            logging.info("Configuration saved")
        except Exception as exc:  # pragma: no cover - UI only feedback
            logging.error("[save] failed: %s", exc)
            QTimer.singleShot(
                0,
                lambda exc=exc: InfoBar.error(
                    title="Error",
                    content=f"Failed to save config: {exc}",
                    parent=page,
                    position=InfoBarPosition.TOP,
                ),
            )

    # ------------------------------------------------------------------
    # Stability case defaults
    # ------------------------------------------------------------------

    def ensure_script_case_defaults(self, case_key: str, case_path: str) -> dict[str, Any]:
        """Ensure stability case defaults exist, handling legacy aliases."""
        page = self.page
        stability_cfg = page.config.setdefault("stability", {})
        cases_section = stability_cfg.setdefault("cases", {})
        entry = cases_section.get(case_key)
        if not isinstance(entry, dict):
            entry = None
        if case_key == SWITCH_WIFI_CASE_KEY and entry is None:
            for legacy_key in SWITCH_WIFI_CASE_ALIASES:
                legacy_entry = cases_section.get(legacy_key)
                if isinstance(legacy_entry, dict):
                    entry = dict(legacy_entry)
                    break
        if entry is None:
            entry = {}

        if case_key == SWITCH_WIFI_CASE_KEY:
            entry.setdefault(SWITCH_WIFI_USE_ROUTER_FIELD, False)
            router_csv = entry.get(SWITCH_WIFI_ROUTER_CSV_FIELD)
            entry[SWITCH_WIFI_ROUTER_CSV_FIELD] = str(router_csv or "").strip()
            manual_entries = entry.get(SWITCH_WIFI_MANUAL_ENTRIES_FIELD)
            entry[SWITCH_WIFI_MANUAL_ENTRIES_FIELD] = normalize_switch_wifi_manual_entries(
                manual_entries
            )
            cases_section[case_key] = entry
            for legacy_key in SWITCH_WIFI_CASE_ALIASES:
                if legacy_key in cases_section:
                    cases_section.pop(legacy_key, None)
            return entry

        def _ensure_branch(name: str) -> None:
            branch = entry.get(name)
            if not isinstance(branch, dict):
                branch = {}
            branch.setdefault("enabled", False)
            branch.setdefault("on_duration", 0)
            branch.setdefault("off_duration", 0)
            branch.setdefault("port", "")
            branch.setdefault("mode", "NO")
            entry[name] = branch

        _ensure_branch("ac")
        _ensure_branch("str")
        cases_section[case_key] = entry
        return entry

    # ------------------------------------------------------------------
    # FPGA helpers
    # ------------------------------------------------------------------

    @staticmethod
    def normalize_fpga_token(value: Any) -> str:
        """Coerce FPGA metadata tokens into normalised uppercase strings."""
        if value is None:
            return ""
        return str(value).strip().upper()

    @staticmethod
    def _split_legacy_fpga_value(raw: str) -> tuple[str, str]:
        """Split legacy `wifi_module_interface` values for compatibility."""
        parts = raw.split("_", 1)
        wifi_module = parts[0] if parts and parts[0] else ""
        interface = parts[1] if len(parts) > 1 and parts[1] else ""
        return wifi_module.upper(), interface.upper()

    def _guess_fpga_project(
        self,
        wifi_module: str,
        interface: str,
        main_chip: str = "",
        *,
        customer: str = "",
        product_line: str = "",
        project: str = "",
    ) -> tuple[str, str, str, Optional[dict[str, str]]]:
        """Match FPGA selections against known customer/product/project data."""
        wifi_upper = wifi_module.strip().upper()
        interface_upper = interface.strip().upper()
        chip_upper = main_chip.strip().upper()
        customer_upper = customer.strip().upper()
        product_upper = product_line.strip().upper()
        project_upper = project.strip().upper()
        for customer_name, product_lines in WIFI_PRODUCT_PROJECT_MAP.items():
            customer_name_upper = self.normalize_fpga_token(customer_name)
            if customer_upper and customer_name_upper != customer_upper:
                continue
            for product_name, projects in product_lines.items():
                product_name_upper = self.normalize_fpga_token(product_name)
                if product_upper and product_name_upper != product_upper:
                    continue
                for project_name, info in projects.items():
                    project_name_upper = self.normalize_fpga_token(project_name)
                    if project_upper and project_name_upper != project_upper:
                        continue
                    info_wifi = self.normalize_fpga_token(info.get("wifi_module"))
                    info_if = self.normalize_fpga_token(info.get("interface"))
                    info_chip = self.normalize_fpga_token(info.get("main_chip"))
                    if wifi_upper and info_wifi and info_wifi != wifi_upper:
                        continue
                    if interface_upper and info_if and info_if != interface_upper:
                        continue
                    if chip_upper and info_chip and info_chip != chip_upper:
                        continue
                    return customer_name, product_name, project_name, info
        return "", "", "", None

    def normalize_fpga_section(self, raw_value: Any) -> dict[str, str]:
        """Normalise FPGA configuration into structured token fields."""
        normalized = {
            "customer": "",
            "product_line": "",
            "project": "",
            "main_chip": "",
            "wifi_module": "",
            "interface": "",
        }
        if isinstance(raw_value, Mapping):
            customer = self.normalize_fpga_token(raw_value.get("customer"))
            product_line = self.normalize_fpga_token(raw_value.get("product_line"))
            project = self.normalize_fpga_token(raw_value.get("project"))
            main_chip = self.normalize_fpga_token(raw_value.get("main_chip"))
            wifi_module = raw_value.get("wifi_module") or raw_value.get("series") or ""
            interface = raw_value.get("interface") or ""
            normalized.update(
                {
                    "customer": customer,
                    "product_line": product_line,
                    "project": project,
                    "main_chip": main_chip,
                    "wifi_module": self.normalize_fpga_token(wifi_module),
                    "interface": self.normalize_fpga_token(interface),
                }
            )
            guessed_customer, guessed_product, guessed_project, info = self._guess_fpga_project(
                normalized["wifi_module"],
                normalized["interface"],
                main_chip,
                customer=customer,
                product_line=product_line,
                project=project,
            )
            if guessed_customer:
                normalized["customer"] = guessed_customer
            if guessed_product:
                normalized["product_line"] = guessed_product
            if guessed_project:
                normalized["project"] = guessed_project
            if info:
                if not normalized["main_chip"]:
                    normalized["main_chip"] = self.normalize_fpga_token(info.get("main_chip"))
                if not normalized["wifi_module"]:
                    normalized["wifi_module"] = self.normalize_fpga_token(info.get("wifi_module"))
                if not normalized["interface"]:
                    normalized["interface"] = self.normalize_fpga_token(info.get("interface"))
        elif isinstance(raw_value, str):
            wifi_module, interface = self._split_legacy_fpga_value(raw_value)
            normalized["wifi_module"] = wifi_module
            normalized["interface"] = interface
            customer, product, project, info = self._guess_fpga_project(wifi_module, interface)
            if customer:
                normalized["customer"] = customer
            if product:
                normalized["product_line"] = product
            if project:
                normalized["project"] = project
            if info:
                normalized["main_chip"] = self.normalize_fpga_token(info.get("main_chip"))
                normalized["wifi_module"] = self.normalize_fpga_token(info.get("wifi_module"))
                normalized["interface"] = self.normalize_fpga_token(info.get("interface"))
        return normalized

    # ------------------------------------------------------------------
    # Connect-type / stability normalisation
    # ------------------------------------------------------------------

    def normalize_connect_type_section(self, raw_value: Any) -> dict[str, Any]:
        """Normalise connect-type data, supporting legacy adb/telnet fields."""
        normalized: dict[str, Any] = {}
        if isinstance(raw_value, Mapping):
            normalized.update(raw_value)

        type_value = normalized.get("type", "Android")
        if isinstance(type_value, str):
            type_value = type_value.strip() or "Android"
        else:
            type_value = str(type_value).strip() or "Android"
        lowered_type = type_value.lower()
        if lowered_type in {"android", "adb"}:
            type_value = "Android"
        elif lowered_type in {"linux", "telnet"}:
            type_value = "Linux"
        normalized["type"] = type_value

        android_cfg = normalized.get("Android")
        if not isinstance(android_cfg, Mapping):
            legacy_adb = normalized.get("adb")
            if isinstance(legacy_adb, Mapping):
                android_cfg = legacy_adb
            else:
                android_cfg = legacy_adb
        if isinstance(android_cfg, Mapping):
            android_dict = dict(android_cfg)
        else:
            android_dict = {}
            if android_cfg not in (None, ""):
                android_dict["device"] = str(android_cfg)
        device = android_dict.get("device", "")
        android_dict["device"] = str(device).strip() if device is not None else ""
        normalized["Android"] = android_dict
        normalized.pop("adb", None)

        linux_cfg = normalized.get("Linux")
        if not isinstance(linux_cfg, Mapping):
            legacy_telnet = normalized.get("telnet")
            if isinstance(legacy_telnet, Mapping):
                linux_cfg = legacy_telnet
            else:
                linux_cfg = legacy_telnet
        if isinstance(linux_cfg, Mapping):
            linux_dict = dict(linux_cfg)
        else:
            linux_dict = {}
            if isinstance(linux_cfg, str) and linux_cfg.strip():
                linux_dict["ip"] = linux_cfg.strip()
        telnet_ip = linux_dict.get("ip", "")
        linux_dict["ip"] = str(telnet_ip).strip() if telnet_ip is not None else ""
        wildcard = linux_dict.get("wildcard", "")
        linux_dict["wildcard"] = str(wildcard).strip() if wildcard is not None else ""
        normalized["Linux"] = linux_dict
        normalized.pop("telnet", None)

        third_cfg = normalized.get("third_party")
        if isinstance(third_cfg, Mapping):
            third_dict = dict(third_cfg)
        else:
            third_dict = {}
        enabled_val = third_dict.get("enabled", False)
        if isinstance(enabled_val, str):
            enabled_bool = enabled_val.strip().lower() in {"1", "true", "yes", "on"}
        else:
            enabled_bool = bool(enabled_val)
        third_dict["enabled"] = enabled_bool
        wait_val = third_dict.get("wait_seconds")
        wait_seconds: Optional[int]
        if wait_val in (None, ""):
            wait_seconds = None
        else:
            try:
                wait_seconds = int(str(wait_val).strip())
            except (TypeError, ValueError):
                wait_seconds = None
        if wait_seconds is not None and wait_seconds < 0:
            wait_seconds = None
        third_dict["wait_seconds"] = wait_seconds
        normalized["third_party"] = third_dict

        return normalized

    def normalize_stability_settings(self, raw_value: Any) -> dict[str, Any]:
        """Normalise stability settings including duration, checkpoints, cases."""

        def _coerce_positive_int(value: Any) -> int | None:
            try:
                candidate = int(value)
            except (TypeError, ValueError):
                return None
            return candidate if candidate > 0 else None

        def _coerce_positive_float(value: Any) -> float | None:
            try:
                candidate = float(value)
            except (TypeError, ValueError):
                return None
            return candidate if candidate > 0 else None

        def _normalize_cycle(value: Any) -> dict[str, Any]:
            mapping = value if isinstance(value, Mapping) else {}
            result = {
                "enabled": bool(mapping.get("enabled")),
                "on_duration": max(0, int(mapping.get("on_duration", 0) or 0)),
                "off_duration": max(0, int(mapping.get("off_duration", 0) or 0)),
                "port": str(mapping.get("port", "") or "").strip(),
                "mode": str(mapping.get("mode", "") or "NO").strip().upper() or "NO",
            }
            return result

        page = self.page
        source = raw_value if isinstance(raw_value, Mapping) else {}

        duration_cfg = source.get("duration_control")
        if isinstance(duration_cfg, Mapping):
            loop_value = _coerce_positive_int(duration_cfg.get("loop"))
            duration_value = _coerce_positive_float(duration_cfg.get("duration_hours"))
            exitfirst_flag = bool(duration_cfg.get("exitfirst"))
            retry_limit = _coerce_positive_int(duration_cfg.get("retry_limit")) or 0
        else:
            loop_value = None
            duration_value = None
            exitfirst_flag = False
            retry_limit = 0

        check_point_cfg = source.get("check_point")
        if isinstance(check_point_cfg, Mapping):
            check_point = {key: bool(value) for key, value in check_point_cfg.items()}
        else:
            check_point = {"ping": False}
        check_point.setdefault("ping", False)
        ping_targets = (
            str(check_point_cfg.get("ping_targets", "")).strip()
            if isinstance(check_point_cfg, Mapping)
            else ""
        )
        check_point["ping_targets"] = ping_targets

        cases_cfg = source.get("cases")
        cases: dict[str, dict[str, Any]] = {}
        if isinstance(cases_cfg, Mapping):
            for name, case_value in cases_cfg.items():
                if not isinstance(case_value, Mapping):
                    continue
                normalized_name = (
                    SWITCH_WIFI_CASE_KEY
                    if name in SWITCH_WIFI_CASE_KEYS
                    else name
                )
                if normalized_name == SWITCH_WIFI_CASE_KEY:
                    manual_entries = case_value.get(SWITCH_WIFI_MANUAL_ENTRIES_FIELD)
                    from src.ui.view.config.config_switch_wifi import normalize_switch_wifi_manual_entries

                    cases[SWITCH_WIFI_CASE_KEY] = {
                        SWITCH_WIFI_USE_ROUTER_FIELD: bool(
                            case_value.get(SWITCH_WIFI_USE_ROUTER_FIELD)
                        ),
                        SWITCH_WIFI_ROUTER_CSV_FIELD: str(
                            case_value.get(SWITCH_WIFI_ROUTER_CSV_FIELD, "") or ""
                        ).strip(),
                        SWITCH_WIFI_MANUAL_ENTRIES_FIELD: normalize_switch_wifi_manual_entries(
                            manual_entries
                        ),
                    }
                else:
                    cases[normalized_name] = {
                        "ac": _normalize_cycle(case_value.get("ac")),
                        "str": _normalize_cycle(case_value.get("str")),
                    }

        return {
            "duration_control": {
                "loop": loop_value,
                "duration_hours": duration_value,
                "exitfirst": exitfirst_flag,
                "retry_limit": retry_limit,
            },
            "check_point": check_point,
            "cases": cases,
        }

    # ------------------------------------------------------------------
    # CSV / RvR Wi-Fi helpers
    # ------------------------------------------------------------------

    def resolve_csv_config_path(self, value: Any) -> str | None:
        """Resolve persisted CSV paths to absolute path strings."""
        return _proxy_resolve_csv_config_path(value)

    def normalize_csv_path(self, path: Any) -> str | None:
        """Normalise CSV paths to absolute strings for reliable comparisons."""
        return _proxy_normalize_csv_path(path)

    def relativize_config_path(self, path: Any) -> str:
        """Convert CSV paths into config-relative strings for persistence."""
        return _proxy_relativize_config_path(path)

    def find_csv_index(self, normalized_path: str | None, combo=None) -> int:
        """Locate CSV indices using the RvR Wi-Fi proxy helper."""
        return _proxy_find_csv_index(self.page, normalized_path, combo)

    def set_selected_csv(self, path: str | None, *, sync_combo: bool = True) -> bool:
        """Update CSV selection via the RvR Wi-Fi proxy implementation."""
        return _proxy_set_selected_csv(self.page, path, sync_combo=sync_combo)

    def update_csv_options(self) -> None:
        """Refresh CSV drop-downs via the RvR Wi-Fi proxy."""
        _proxy_update_csv_options(self.page)

    def capture_preselected_csv(self) -> None:
        """Cache CSV selections using the RvR Wi-Fi proxy helper."""
        _proxy_capture_preselected_csv(self.page)

    def populate_csv_combo(
        self,
        combo,
        selected_path: str | None,
        *,
        include_placeholder: bool = False,
    ) -> None:
        """Populate CSV combos via the RvR Wi-Fi proxy helper."""
        _proxy_populate_csv_combo(
            self.page,
            combo,
            selected_path,
            include_placeholder=include_placeholder,
        )

    def refresh_registered_csv_combos(self) -> None:
        """Refresh CSV combo registrations via the RvR Wi-Fi proxy."""
        _proxy_refresh_registered_csv_combos(self.page)

    def load_switch_wifi_entries(self, csv_path: str | None) -> list[dict[str, str]]:
        """Load Wi-Fi CSV rows through the RvR Wi-Fi proxy implementation."""
        return _proxy_load_switch_wifi_entries(self.page, csv_path)

    def update_switch_wifi_preview(self, preview, csv_path: str | None) -> None:
        """Update Wi-Fi preview widgets via the RvR Wi-Fi proxy."""
        _proxy_update_switch_wifi_preview(self.page, preview, csv_path)

    def update_rvr_nav_button(self) -> None:
        """Update the RVR navigation button using the proxy helper."""
        _proxy_update_rvr_nav_button(self.page)

    def open_rvr_wifi_config(self) -> None:
        """Open the RVR Wi-Fi configuration page via the proxy helper."""
        _proxy_open_rvr_wifi_config(self.page)

    # ------------------------------------------------------------------
    # Router helpers
    # ------------------------------------------------------------------

    def handle_router_name_changed(self, name: str) -> None:
        """Handle router combo changes: update router_obj, address widget, and signal."""
        page = self.page
        try:
            from src.tools.router_tool.router_factory import get_router  # type: ignore
        except Exception:
            return
        cfg = getattr(page, "config", {}) or {}
        router_cfg = cfg.get("router", {}) if isinstance(cfg, dict) else {}
        addr = router_cfg.get("address") if router_cfg.get("name") == name else None
        try:
            router_obj = get_router(name, addr)
        except Exception:
            return
        setattr(page, "router_obj", router_obj)

        # Keep field widget in sync.
        field_widgets = getattr(page, "field_widgets", {}) or {}
        router_addr_widget = field_widgets.get("router.address")
        if router_addr_widget is not None and hasattr(router_addr_widget, "setText"):
            try:
                router_addr_widget.setText(router_obj.address)
            except Exception:
                pass

        # Emit routerInfoChanged for dependent UI (CSV combos, etc.).
        signal = getattr(page, "routerInfoChanged", None)
        if signal is not None and hasattr(signal, "emit"):
            signal.emit()

    def handle_router_address_changed(self, address: str) -> None:
        """Handle manual edits to the router address field."""
        page = self.page
        router_obj = getattr(page, "router_obj", None)
        if router_obj is not None:
            router_obj.address = address
        signal = getattr(page, "routerInfoChanged", None)
        if signal is not None and hasattr(signal, "emit"):
            signal.emit()

    # ------------------------------------------------------------------
    # Stability script config glue
    # ------------------------------------------------------------------

    def load_script_config_into_widgets(
        self,
        entry: ScriptConfigEntry,
        data: Mapping[str, Any] | None,
    ) -> None:
        """
        Load stability script config into widgets from persistent storage.

        Handles both ``test_switch_wifi`` (router/manual Wi-Fi list) and
        ``test_str`` AC/STR timing + relay controls.
        """
        # Delegate to the view-layer helper so the UI-side implementation
        # lives with other visual logic. Keep this thin wrapper to avoid
        # breaking callers that expect the controller API.
        try:
            from src.ui.view.config.actions import load_script_config_into_widgets as _view_load

            _view_load(self.page, entry, data)
            return
        except Exception:
            logging.debug("Controller fallback to view-layer loader failed", exc_info=True)

    def sync_widgets_to_config(self) -> None:
        """Read all widgets into page.config, including stability settings."""
        page = self.page
        if not isinstance(page.config, dict):
            page.config = {}
        if hasattr(page, "_config_tool_snapshot"):
            page.config[TOOL_SECTION_KEY] = copy.deepcopy(
                page._config_tool_snapshot
            )
        for key, widget in page.field_widgets.items():
            parts = key.split(".")
            ref = page.config
            for part in parts[:-1]:
                child = ref.get(part)
                if not isinstance(child, dict):
                    child = {}
                    ref[part] = child
                ref = child
            leaf = parts[-1]
            if isinstance(widget, LineEdit):
                val = widget.text()
                if key == "connect_type.third_party.wait_seconds":
                    val = val.strip()
                    ref[leaf] = int(val) if val else 0
                    continue
                if key == "rf_solution.step":
                    ref[leaf] = val.strip()
                    continue
                if key == f"{TURN_TABLE_SECTION_KEY}.{TURN_TABLE_FIELD_STEP}":
                    ref[leaf] = val.strip()
                    continue
                if key == f"{TURN_TABLE_SECTION_KEY}.{TURN_TABLE_FIELD_STATIC_DB}":
                    ref[leaf] = val.strip()
                    continue
                if key == f"{TURN_TABLE_SECTION_KEY}.{TURN_TABLE_FIELD_TARGET_RSSI}":
                    ref[leaf] = val.strip()
                    continue
                if key == f"{TURN_TABLE_SECTION_KEY}.{TURN_TABLE_FIELD_IP_ADDRESS}":
                    ref[leaf] = val.strip()
                    continue
                if leaf == "relay_params":
                    items = [item.strip() for item in val.split(",") if item.strip()]
                    normalized = []
                    for item in items:
                        normalized.append(int(item) if item.isdigit() else item)
                    ref[leaf] = normalized
                    continue
                old_val = ref.get(leaf)
                if isinstance(old_val, list):
                    items = [x.strip() for x in val.split(",") if x.strip()]
                    if all(i.isdigit() for i in items):
                        ref[leaf] = [int(i) for i in items]
                    else:
                        ref[leaf] = items
                else:
                    val = val.strip()
                    if len(parts) >= 2 and parts[-2] == "router" and leaf.startswith("passwd") and not val:
                        ref[leaf] = ""
                    else:
                        ref[leaf] = val
            elif isinstance(widget, RfStepSegmentsWidget):
                ref[leaf] = widget.serialize()
            elif isinstance(widget, SwitchWifiManualEditor):
                ref[leaf] = widget.serialize()
            elif isinstance(widget, ComboBox):
                data_val = widget.currentData()
                if data_val not in (None, "", widget.currentText()):
                    value = data_val
                else:
                    text = widget.currentText().strip()
                    if text.lower() == "select port":
                        text = ""
                    value = True if text == "True" else False if text == "False" else text
                if key == script_field_key(
                    SWITCH_WIFI_CASE_KEY, SWITCH_WIFI_ROUTER_CSV_FIELD
                ):
                    value = self.relativize_config_path(value)
                ref[leaf] = value
            elif isinstance(widget, QSpinBox):
                ref[leaf] = widget.value()
            elif isinstance(widget, QDoubleSpinBox):
                ref[leaf] = float(widget.value())
            elif isinstance(widget, QCheckBox):
                ref[leaf] = widget.isChecked()
        if hasattr(page, "_fpga_details"):
            page.config["fpga"] = dict(page._fpga_details)
        base = Path(self.get_application_base())
        case_display = page.field_widgets.get("text_case")
        display_text = case_display.text().strip() if isinstance(case_display, LineEdit) else ""
        storage_path = page._current_case_path or display_to_case_path(display_text)
        case_path = Path(storage_path).as_posix() if storage_path else ""
        page._current_case_path = case_path
        if case_path:
            abs_case_path = (base / case_path).resolve().as_posix()
        else:
            abs_case_path = ""
        page.config["text_case"] = case_path
        if page.selected_csv_path:
            base_cfg = get_config_base()
            try:
                rel_csv = os.path.relpath(Path(page.selected_csv_path).resolve(), base_cfg)
            except ValueError:
                rel_csv = Path(page.selected_csv_path).resolve().as_posix()
            page.config["csv_path"] = Path(rel_csv).as_posix()
        else:
            page.config.pop("csv_path", None)
        proxy_idx = page.case_tree.currentIndex()
        model = page.case_tree.model()
        src_idx = (
            model.mapToSource(proxy_idx)
            if isinstance(model, QSortFilterProxyModel)
            else proxy_idx
        )
        selected_path = page.fs_model.filePath(src_idx)
        if os.path.isfile(selected_path) and selected_path.endswith(".py"):
            abs_path = Path(selected_path).resolve()
            display_path = os.path.relpath(abs_path, base)
            case_path = Path(display_path).as_posix()
            page._current_case_path = case_path
            page.config["text_case"] = case_path

        stability_cfg = page.config.get("stability")
        if isinstance(stability_cfg, dict):
            duration_cfg = stability_cfg.get("duration_control")
            if isinstance(duration_cfg, dict):
                loop_value = duration_cfg.get("loop")
                if not isinstance(loop_value, int) or loop_value <= 0:
                    duration_cfg["loop"] = None
                duration_value = duration_cfg.get("duration_hours")
                try:
                    duration_float = float(duration_value)
                except (TypeError, ValueError):
                    duration_float = 0.0
                duration_cfg["duration_hours"] = duration_float if duration_float > 0 else None
                duration_cfg["exitfirst"] = bool(duration_cfg.get("exitfirst"))
                try:
                    retry_int = int(duration_cfg.get("retry_limit") or 0)
                except (TypeError, ValueError):
                    retry_int = 0
                duration_cfg["retry_limit"] = max(0, retry_int)
            checkpoint_cfg = stability_cfg.get("check_point")
            if isinstance(checkpoint_cfg, dict):
                checkpoint_cfg["ping"] = bool(checkpoint_cfg.get("ping"))
                checkpoint_cfg["ping_targets"] = str(
                    checkpoint_cfg.get("ping_targets", "") or ""
                ).strip()

    def validate_test_str_requirements(self) -> bool:
        """Ensure test_str stability settings require port/mode when AC/STR enabled."""
        page = self.page
        config = page.config if isinstance(page.config, dict) else {}
        case_path = config.get("text_case", "")
        case_key = self.script_case_key(case_path)
        if case_key != "test_str":
            return True

        stability_cfg = config.get("stability") if isinstance(config, dict) else {}
        cases_cfg = stability_cfg.get("cases") if isinstance(stability_cfg, dict) else {}
        case_cfg = cases_cfg.get(case_key) if isinstance(cases_cfg, dict) else {}

        errors: list[str] = []
        focus_widget = None

        def _require(branch: str, label: str) -> None:
            nonlocal focus_widget
            branch_cfg = case_cfg.get(branch) if isinstance(case_cfg, dict) else {}
            if not isinstance(branch_cfg, dict) or not branch_cfg.get("enabled"):
                return
            relay_type = str(branch_cfg.get("relay_type") or "usb_relay").strip() or "usb_relay"
            relay_key = relay_type.lower()
            if relay_key == "usb_relay":
                port_value = str(branch_cfg.get("port") or "").strip()
                mode_value = str(branch_cfg.get("mode") or "").strip()
                if not port_value:
                    errors.append(f"{label}: USB power relay port is required.")
                    focus_widget = focus_widget or page.field_widgets.get(
                        f"stability.cases.{case_key}.{branch}.port"
                    )
                if not mode_value:
                    errors.append(f"{label}: Wiring mode is required.")
                    focus_widget = focus_widget or page.field_widgets.get(
                        f"stability.cases.{case_key}.{branch}.mode"
                    )
            elif relay_key == "gwgj-xc3012":
                params = branch_cfg.get("relay_params")
                if isinstance(params, (list, tuple)):
                    items = list(params)
                elif isinstance(params, str):
                    items = [item.strip() for item in params.split(",") if item.strip()]
                else:
                    items = []
                ip_value = str(items[0]).strip() if items else ""
                port_value = None
                if len(items) > 1:
                    try:
                        port_value = int(str(items[1]).strip())
                    except (TypeError, ValueError):
                        port_value = None
                if not ip_value or port_value is None:
                    errors.append(
                        f"{label}: Relay params must include IP and port for GWGJ-XC3012."
                    )
                    focus_widget = focus_widget or page.field_widgets.get(
                        f"stability.cases.{case_key}.{branch}.relay_params"
                    )

        _require("ac", "AC cycle")
        _require("str", "STR cycle")
        if not errors:
            return True

        message = "\n".join(errors)
        try:
            bar = show_info_bar(
                page,
                "warning",
                "Configuration error",
                message,
                duration=4000,
            )
            if bar is None:
                raise RuntimeError("InfoBar unavailable")
        except Exception:
            from PyQt5.QtWidgets import QMessageBox  # local import

            QMessageBox.warning(page, "Configuration error", message)
        if focus_widget is not None and hasattr(focus_widget, "setFocus"):
            focus_widget.setFocus()
            if hasattr(focus_widget, "selectAll"):
                focus_widget.selectAll()
        return False

    def validate_first_page(self) -> bool:
        """Validate DUT page before running or navigating to subsequent pages."""
        from src.ui.view.config.actions import current_connect_type  # local import

        page = self.page
        errors: list[str] = []
        connect_type = ""
        focus_widget = None
        if hasattr(page, "connect_type_combo"):
            connect_type = current_connect_type(page)
            if not connect_type:
                errors.append("Connect type is required.")
                focus_widget = focus_widget or getattr(page, "connect_type_combo", None)
            elif connect_type == "Android" and hasattr(page, "adb_device_edit"):
                if not page.adb_device_edit.text().strip():
                    errors.append("ADB device is required.")
                    focus_widget = focus_widget or page.adb_device_edit
            elif connect_type == "Linux" and hasattr(page, "telnet_ip_edit"):
                if not page.telnet_ip_edit.text().strip():
                    errors.append("Linux IP is required.")
                    focus_widget = focus_widget or page.telnet_ip_edit
                kernel_text = ""
                if hasattr(page, "kernel_version_combo"):
                    kernel_text = page.kernel_version_combo.currentText().strip()
                if not kernel_text:
                    errors.append("Kernel version is required for Linux access.")
                    focus_widget = focus_widget or getattr(page, "kernel_version_combo", None)
            if (
                hasattr(page, "third_party_checkbox")
                and page.third_party_checkbox.isChecked()
            ):
                wait_text = (
                    page.third_party_wait_edit.text().strip()
                    if hasattr(page, "third_party_wait_edit")
                    else ""
                )
                if not wait_text or not wait_text.isdigit() or int(wait_text) <= 0:
                    errors.append("Third-party wait time must be a positive integer.")
                    if hasattr(page, "third_party_wait_edit"):
                        focus_widget = focus_widget or page.third_party_wait_edit
        else:
            errors.append("Connect type widget missing.")

        if (
            hasattr(page, "android_version_combo")
            and connect_type == "Android"
            and not page.android_version_combo.currentText().strip()
        ):
            errors.append("Android version is required.")
            focus_widget = focus_widget or getattr(page, "android_version_combo", None)

        fpga_valid = (
            hasattr(page, "fpga_customer_combo")
            and hasattr(page, "fpga_product_combo")
            and hasattr(page, "fpga_project_combo")
        )
        customer_text = (
            page.fpga_customer_combo.currentText().strip() if fpga_valid else ""
        )
        product_text = (
            page.fpga_product_combo.currentText().strip() if fpga_valid else ""
        )
        project_text = (
            page.fpga_project_combo.currentText().strip() if fpga_valid else ""
        )
        if not fpga_valid or not customer_text or not product_text or not project_text:
            errors.append(
                "Wi-Fi chipset customer, product line and project are required."
            )
            if fpga_valid:
                focus_widget = focus_widget or (
                    page.fpga_customer_combo
                    if not customer_text
                    else page.fpga_product_combo
                    if not product_text
                    else page.fpga_project_combo
                )

        if errors:
            show_info_bar(
                page,
                "warning",
                "Validation",
                "\n".join(errors),
                duration=3000,
            )
            if focus_widget is not None:
                focus_widget.setFocus()
                if hasattr(focus_widget, "selectAll"):
                    focus_widget.selectAll()
            return False
        return True

    # ------------------------------------------------------------------
    # Case classification / page selection
    # ------------------------------------------------------------------

    def is_performance_case(self, abs_case_path: str | Path | None) -> bool:
        """
        Determine whether abs_case_path is under the test/performance directory at any level.

        Does not rely on project root path; only checks path segments.
        """
        logging.debug("Checking performance case path: %s", abs_case_path)
        if not abs_case_path:
            logging.debug("is_performance_case: empty path -> False")
            return False
        try:
            p = Path(abs_case_path).resolve()
            for node in (p, *p.parents):
                if node.name == "performance" and node.parent.name == "test":
                    logging.debug("is_performance_case: True")
                    return True
                logging.debug("is_performance_case: False")
            return False
        except Exception as exc:
            logging.error("is_performance_case exception: %s", exc)
            return False

    def is_stability_case(self, case_path: str | Path | None) -> bool:
        """Return True when the case resides under ``test/stability``."""

        if not case_path:
            return False
        try:
            path_obj = case_path if isinstance(case_path, Path) else Path(case_path)
        except (TypeError, ValueError):
            return False
        try:
            resolved = path_obj.resolve()
        except OSError:
            resolved = path_obj
        candidates = [path_obj, resolved]
        for candidate in candidates:
            normalized = candidate.as_posix().replace("\\", "/")
            segments = [seg.lower() for seg in normalized.split("/") if seg]
            for idx in range(len(segments) - 1):
                if segments[idx] == "test" and segments[idx + 1] == "stability":
                    return True
            if normalized.lower().startswith("test/stability/"):
                return True
        return False

    def script_case_key(self, case_path: str | Path) -> str:
        """Return the logical script key used by stability config for the given case path."""
        if not case_path:
            return ""
        path_obj = case_path if isinstance(case_path, Path) else Path(case_path)
        if path_obj.is_absolute():
            try:
                from src.util.constants import get_src_base

                path_obj = path_obj.resolve().relative_to(Path(get_src_base()).resolve())
            except ValueError:
                path_obj = path_obj.resolve()
        stem = path_obj.stem.lower()
        if stem in SWITCH_WIFI_CASE_KEYS:
            return SWITCH_WIFI_CASE_KEY
        return stem

    def determine_pages_for_case(self, case_path: str, info: "EditableInfo") -> list[str]:
        """Return which logical pages (dut/execution/stability) should be visible for the case."""
        if not case_path:
            return ["dut"]
        keys = ["dut"]
        if self.is_performance_case(case_path) or getattr(info, "enable_csv", False):
            if "execution" not in keys:
                keys.append("execution")
        else:
            case_key = self.script_case_key(case_path)
            script_groups = getattr(self.page, "_script_groups", {})
            if case_key in script_groups:
                keys.append("stability")
        return keys

    # ------------------------------------------------------------------
    # Editable state / rules bridge
    # ------------------------------------------------------------------

    def get_field_value(self, field_key: str) -> Any:
        """Return a Python value representing the current state of a field widget."""
        page = self.page
        widget = page.field_widgets.get(field_key)
        if widget is None:
            return None
        from qfluentwidgets import ComboBox, LineEdit, TextEdit  # local import

        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        if isinstance(widget, ComboBox):
            data = widget.currentData()
            if data not in (None, ""):
                return data
            return widget.currentText()
        if isinstance(widget, LineEdit):
            return widget.text()
        if isinstance(widget, TextEdit):
            return widget.toPlainText()
        if isinstance(widget, QSpinBox):
            return widget.value()
        if isinstance(widget, QDoubleSpinBox):
            return float(widget.value())
        return None

    def eval_case_type_flag(self, flag: str) -> bool:
        """Return True/False for high level case-type flags used by rules."""
        page = self.page
        if not flag:
            return True
        case_path = getattr(page, "_current_case_path", "") or ""
        basename = os.path.basename(case_path) if case_path else ""
        abs_path = case_path
        try:
            path_obj = Path(case_path)
            if not path_obj.is_absolute():
                abs_path = (Path(self.get_application_base()) / path_obj).as_posix()
            else:
                abs_path = path_obj.as_posix()
        except Exception:
            pass

        if flag == "performance_or_enable_csv":
            info = getattr(page, "_last_editable_info", None)
            enable_csv = bool(getattr(info, "enable_csv", False))
            return bool(self.is_performance_case(abs_path) or enable_csv)
        if flag == "execution_panel_visible":
            keys = getattr(page, "_current_page_keys", [])
            return "execution" in keys
        if flag == "stability_case":
            return self.is_stability_case(abs_path or case_path)
        if flag == "rvr_case":
            return "rvr" in basename.lower()
        if flag == "rvo_case":
            return "rvo" in basename.lower()
        if flag == "performance_case_with_rvr_wifi":
            is_perf = self.is_performance_case(abs_path)
            has_rvr = bool(
                getattr(page, "_enable_rvr_wifi", False)
                and getattr(page, "selected_csv_path", None)
            )
            return bool(is_perf and has_rvr)
        return False

    def apply_sidebar_rules(self) -> None:
        """Evaluate sidebar rules that depend on the active case."""
        from src.ui.model.rules import SIDEBAR_RULES, RuleSpec  # local import

        page = self.page
        main_window = page.window()
        if not main_window:
            return
        try:
            rules: dict[str, RuleSpec] = SIDEBAR_RULES
        except Exception:
            return

        spec = rules.get("S11_case_button_for_performance")
        if not spec:
            return
        sidebar_key = spec.get("trigger_sidebar_key") or "case"
        sidebar_enabled = self.eval_case_type_flag(
            spec.get("trigger_case_type") or ""
        )

        btn = None
        sidebar_map = getattr(main_window, "sidebar_nav_buttons", None)
        if isinstance(sidebar_map, dict):
            btn = sidebar_map.get(sidebar_key)
        if btn is None:
            btn = getattr(main_window, "rvr_nav_button", None)
        if btn is None:
            return
        try:
            import sip  # local import to avoid top-level dependency

            if sip.isdeleted(btn):
                return
        except Exception:
            pass
        btn.setEnabled(bool(sidebar_enabled))

    def apply_editable_info(self, info: "EditableInfo | None") -> None:
        """Apply EditableInfo to model flags and UI."""
        from src.ui.view.config.actions import apply_config_ui_rules  # local import

        page = self.page
        if info is None:
            fields: set[str] = set()
            enable_csv = False
            enable_rvr_wifi = False
        else:
            fields = set(info.fields)
            enable_csv = info.enable_csv
            enable_rvr_wifi = info.enable_rvr_wifi
        snapshot = EditableInfo(
            fields=fields,
            enable_csv=enable_csv,
            enable_rvr_wifi=enable_rvr_wifi,
        )
        page._last_editable_info = snapshot
        self._apply_editable_model_state(snapshot)
        self._apply_editable_ui_state(snapshot)
        apply_config_ui_rules(page)

    def _apply_editable_model_state(self, snapshot: "EditableInfo") -> None:
        """Update internal flags and CSV selection from EditableInfo (no direct UI)."""
        page = self.page
        page._enable_rvr_wifi = snapshot.enable_rvr_wifi
        if not snapshot.enable_rvr_wifi:
            page._router_config_active = False
        if snapshot.enable_csv:
            # Ensure selected CSV is applied and combo synced when CSV is enabled.
            self.set_selected_csv(getattr(page, "selected_csv_path", None), sync_combo=True)
        else:
            # Clear CSV selection when CSV usage is disabled.
            self.set_selected_csv(None, sync_combo=False)

    def _apply_editable_ui_state(self, snapshot: "EditableInfo") -> None:
        """Apply UI-related changes for EditableInfo (widgets only)."""
        from src.ui.view.config.actions import set_fields_editable  # local import

        page = self.page
        set_fields_editable(page, snapshot.fields)
        if hasattr(page, "csv_combo"):
            page.csv_combo.setEnabled(True)
        self.update_rvr_nav_button()

    def restore_editable_state(self) -> None:
        """Re-apply last EditableInfo snapshot."""
        page = self.page
        info = getattr(page, "_last_editable_info", None)
        self.apply_editable_info(info)

    def get_editable_fields(self, case_path: str) -> "EditableInfo":
        """Control field editability after selecting a test case and return related info."""
        from src.ui.view.config.actions import apply_config_ui_rules, update_script_config_ui
        from src.ui.view.common import EditableInfo as EditableInfoType

        page = self.page
        logging.debug("get_editable_fields case_path=%s", case_path)
        if page._refreshing:
            logging.debug("get_editable_fields: refreshing, return empty")
            return EditableInfoType()

        page._refreshing = True
        from src.ui.view.config.actions import set_refresh_ui_locked, set_fields_editable

        set_refresh_ui_locked(page, True)

        try:
            update_script_config_ui(page, case_path)
            info = compute_editable_info(page, case_path)
            logging.debug("get_editable_fields enable_csv=%s", info.enable_csv)
            if info.enable_csv and not hasattr(page, "csv_combo"):
                info.enable_csv = False
            self.apply_editable_info(info)
            page_keys = self.determine_pages_for_case(case_path, info)
            from src.ui.view.config.actions import set_available_pages

            set_available_pages(page, page_keys)
            apply_config_ui_rules(page)
        finally:
            set_refresh_ui_locked(page, False)
            page._refreshing = False

        main_window = page.window()
        if hasattr(main_window, "setCurrentIndex"):
            logging.debug("get_editable_fields: before switch to case_config_page")
            main_window.setCurrentIndex(main_window.case_config_page)
            logging.debug("get_editable_fields: after switch to case_config_page")
        if not hasattr(page, "csv_combo"):
            logging.debug("csv_combo disabled")
        if page._pending_path:
            path = page._pending_path
            page._pending_path = None
            QTimer.singleShot(0, lambda: self.get_editable_fields(path))
        return info

    # ------------------------------------------------------------------
    # Second-page (Execution) reset helpers
    # ------------------------------------------------------------------

    def reset_second_page_inputs(self) -> None:
        """Reset Execution-page inputs (CSV selection + enabled state) after a run."""
        page = self.page
        if hasattr(page, "csv_combo"):
            self.reset_second_page_model_state()
            self.reset_second_page_ui_state()
        else:
            # When there is no CSV combo, clear selection via controller helper.
            try:
                self.set_selected_csv(None, sync_combo=False)
            except Exception:
                pass

    def reset_second_page_model_state(self) -> None:
        """Restore CSV selection to the last pre-run value."""
        page = self.page
        selected = getattr(page, "selected_csv_path", None)
        try:
            self.set_selected_csv(selected, sync_combo=True)
        except Exception:
            pass

    def reset_second_page_ui_state(self) -> None:
        """Restore CSV combo enabled state based on RvR Wi-Fi toggle."""
        page = self.page
        if hasattr(page, "csv_combo"):
            try:
                page.csv_combo.setEnabled(bool(getattr(page, "_enable_rvr_wifi", False)))
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Run / lock state
    # ------------------------------------------------------------------

    def sync_run_buttons_enabled(self) -> None:
        """Enable/disable all Run buttons based on _run_locked flag."""
        page = self.page
        enabled = not getattr(page, "_run_locked", False)
        for btn in getattr(page, "_run_buttons", []) or []:
            try:
                btn.setEnabled(enabled)
            except Exception:
                logging.debug("Failed to update run button enabled state", exc_info=True)

    def lock_for_running(self, locked: bool) -> None:
        """Update model + UI when a run starts or finishes."""
        from src.ui.view.config.actions import apply_run_lock_ui_state  # local import

        page = self.page
        page._run_locked = bool(locked)
        apply_run_lock_ui_state(page, locked)
        self.sync_run_buttons_enabled()

    def on_run(self) -> None:
        """Main entry for running the currently selected case from the Config page."""
        from PyQt5.QtWidgets import QMessageBox  # local import

        page = self.page
        if not self.validate_first_page():
            page.stack.setCurrentIndex(0)
            return

        # Reload config to latest on-disk state, then sync widgets -> config.
        page.config = self.load_initial_config()
        self.capture_preselected_csv()
        self.sync_widgets_to_config()
        if not self.validate_test_str_requirements():
            return

        logging.info(
            "[on_run] start case=%s csv=%s config=%s",
            page.field_widgets["text_case"].text().strip()
            if "text_case" in page.field_widgets
            else "",
            getattr(page, "selected_csv_path", None),
            page.config,
        )

        base = Path(self.get_application_base())
        case_path = page.config.get("text_case", "")
        abs_case_path = (base / case_path).resolve().as_posix() if case_path else ""

        proxy_idx = page.case_tree.currentIndex()
        model = page.case_tree.model()
        src_idx = (
            model.mapToSource(proxy_idx)
            if isinstance(model, QSortFilterProxyModel)
            else proxy_idx
        )
        selected_path = page.fs_model.filePath(src_idx)
        if os.path.isfile(selected_path) and selected_path.endswith(".py"):
            abs_path = Path(selected_path).resolve()
            display_path = os.path.relpath(abs_path, base)
            case_path = Path(display_path).as_posix()
            abs_case_path = abs_path.as_posix()
            page.config["text_case"] = case_path

        # Persist config before running.
        self.save_config()

        # Performance case must have CSV selected.
        try:
            if self.is_performance_case(abs_case_path) and not getattr(
                page, "selected_csv_path", None
            ):
                try:
                    bar = show_info_bar(
                        page,
                        "warning",
                        "Hint",
                        "This is a performance test. Please select a CSV file before running.",
                        duration=3000,
                    )
                    if bar is None:
                        raise RuntimeError("InfoBar unavailable")
                except Exception:
                    QMessageBox.warning(
                        page,
                        "Hint",
                        "This is a performance test.\nPlease select a CSV file before running.",
                    )
                return
        except Exception:
            # Fall through and let the normal missing-case handling show an error.
            pass

        from src.ui.controller.run_ctl import reset_wizard_after_run

        if os.path.isfile(abs_case_path) and abs_case_path.endswith(".py"):
            try:
                page.on_run_callback(abs_case_path, case_path, page.config)
            except Exception as exc:  # pragma: no cover - callback logging only
                logging.exception("Run callback failed: %s", exc)
            else:
                reset_wizard_after_run(page)
        else:
            show_info_bar(
                page,
                "warning",
                "Hint",
                "Pls select a test case before test",
                duration=1800,
            )



__all__ = ["ConfigController"]
