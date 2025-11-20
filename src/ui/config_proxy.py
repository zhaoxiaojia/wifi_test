from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Optional

from PyQt5.QtCore import QTimer
from qfluentwidgets import InfoBar, InfoBarPosition

from src.tools.config_loader import load_config, save_config
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
)
from src.ui.view.config.config_switch_wifi import normalize_switch_wifi_manual_entries

if TYPE_CHECKING:  # pragma: no cover - circular import guard
    from .case_config_page import CaseConfigPage


class ConfigProxy:
    """Encapsulate configuration lifecycle operations for the case page."""

    def __init__(self, page: "CaseConfigPage") -> None:
        """Store the owning page for subsequent configuration work."""
        self.page = page

    def load_config(self) -> dict:
        """Load configuration data from disk and normalise persisted paths."""
        page = self.page
        try:
            config = load_config(refresh=True) or {}

            # Delegate application base lookup to controller
            app_base = page.config_ctl.get_application_base() if hasattr(page, 'config_ctl') else None
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
            return config
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
            return {}

    def save_config(self) -> None:
        """Persist the active configuration and refresh cached state."""
        page = self.page
        logging.debug("[save] data=%s", page.config)
        try:
            save_config(page.config)
            logging.info("Configuration saved")
            refreshed = self.load_config()
            if hasattr(page, "_config_tool_snapshot"):
                page._config_tool_snapshot = copy.deepcopy(
                    refreshed.get(TOOL_SECTION_KEY, {})
                )
            page._load_csv_selection_from_config()
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
            entry[
                SWITCH_WIFI_MANUAL_ENTRIES_FIELD
            ] = page._normalize_switch_wifi_manual_entries(manual_entries)
            cases_section[case_key] = entry
            for legacy_key in SWITCH_WIFI_CASE_ALIASES:
                if legacy_key in cases_section:
                    cases_section.pop(legacy_key, None)  # safe-to-remove: migrated to canonical key
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

    def normalize_fpga_token(self, value: Any) -> str:
        """Coerce FPGA metadata tokens into normalised uppercase strings."""
        if value is None:
            return ""
        return str(value).strip().upper()

    def _split_legacy_fpga_value(self, raw: str) -> tuple[str, str]:
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
