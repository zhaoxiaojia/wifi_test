"""Wi-Fi BSS switching stability workflow."""

from __future__ import annotations

import csv
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

import pytest

from src.test.stability import (
    STABILITY_COMPLETED_LOOPS_ENV,
    extract_checkpoints,
    extract_stability_case,
    iterate_stability_loops,
    load_stability_plan,
)
from src.tools.config_loader import load_config
from src.util.constants import (
    AUTH_OPTIONS,
    SWITCH_WIFI_CASE_ALIASES,
    SWITCH_WIFI_CASE_KEY,
    SWITCH_WIFI_ENTRY_PASSWORD_FIELD,
    SWITCH_WIFI_ENTRY_SECURITY_FIELD,
    SWITCH_WIFI_ENTRY_SSID_FIELD,
    SWITCH_WIFI_MANUAL_ENTRIES_FIELD,
    SWITCH_WIFI_ROUTER_CSV_FIELD,
    SWITCH_WIFI_USE_ROUTER_FIELD,
    get_config_base,
)


@dataclass(frozen=True)
class BssTarget:
    """Normalized Wi-Fi connection target."""

    ssid: str
    security_mode: str
    password: str

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None) -> "BssTarget | None":
        if not isinstance(raw, Mapping):
            return None

        ssid = str(raw.get(SWITCH_WIFI_ENTRY_SSID_FIELD, "") or "").strip()
        if not ssid:
            return None

        security = str(
            raw.get(SWITCH_WIFI_ENTRY_SECURITY_FIELD, AUTH_OPTIONS[0]) or AUTH_OPTIONS[0]
        ).strip()
        if not security:
            security = AUTH_OPTIONS[0]

        password = str(raw.get(SWITCH_WIFI_ENTRY_PASSWORD_FIELD, "") or "")
        return cls(ssid=ssid, security_mode=security, password=password)


@dataclass(frozen=True)
class SwitchWifiSettings:
    """Persisted configuration for ``test_switch_wifi``."""

    use_router: bool
    router_path: Path | None
    router_targets: tuple[BssTarget, ...]
    manual_targets: tuple[BssTarget, ...]

    def iter_targets(self) -> Iterator[BssTarget]:
        """Yield connection targets according to configuration priority."""

        if self.use_router and self.router_targets:
            yield from self.router_targets
            return
        if self.manual_targets:
            yield from self.manual_targets


def _normalize_manual_targets(data: Iterable[Any] | None) -> tuple[BssTarget, ...]:
    if data is None:
        return ()
    targets: list[BssTarget] = []
    for item in data:
        target = BssTarget.from_mapping(item if isinstance(item, Mapping) else None)
        if target is not None:
            targets.append(target)
    return tuple(targets)


def _resolve_router_csv_path(raw_value: Any) -> Path | None:
    if not raw_value:
        return None
    try:
        candidate = Path(str(raw_value))
    except (TypeError, ValueError):
        return None
    if not candidate.is_absolute():
        candidate = (get_config_base() / candidate).resolve()
    else:
        try:
            candidate = candidate.resolve()
        except OSError:
            return None
    return candidate if candidate.exists() else None


def _load_router_targets(csv_path: Path | None) -> tuple[BssTarget, ...]:
    if csv_path is None:
        return ()
    entries: list[BssTarget] = []
    try:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                target = BssTarget.from_mapping(row)
                if target is not None:
                    entries.append(target)
    except FileNotFoundError:
        logging.warning("Router CSV %s missing; falling back to manual entries", csv_path)
        return ()
    except Exception as exc:  # pragma: no cover - CSV corruption is rare
        logging.error("Failed to load Wi-Fi router CSV %s: %s", csv_path, exc)
        return ()
    return tuple(entries)


def _parse_switch_wifi_settings(data: Mapping[str, Any] | None) -> SwitchWifiSettings:
    data = data or {}
    use_router = bool(data.get(SWITCH_WIFI_USE_ROUTER_FIELD))
    router_csv = _resolve_router_csv_path(data.get(SWITCH_WIFI_ROUTER_CSV_FIELD))
    manual_targets = _normalize_manual_targets(data.get(SWITCH_WIFI_MANUAL_ENTRIES_FIELD))
    router_targets: tuple[BssTarget, ...] = ()
    if use_router:
        router_targets = _load_router_targets(router_csv)
        if not router_targets and manual_targets:
            logging.info(
                "Router CSV produced no entries; defaulting to %s manual targets.",
                len(manual_targets),
            )
    return SwitchWifiSettings(
        use_router=use_router,
        router_path=router_csv,
        router_targets=router_targets,
        manual_targets=manual_targets,
    )


def _load_switch_settings() -> tuple[SwitchWifiSettings, tuple[BssTarget, ...], Mapping[str, bool]]:
    config = load_config(refresh=True)
    stability_cfg = config.get("stability") if isinstance(config, Mapping) else {}
    case_cfg = extract_stability_case(
        stability_cfg,
        SWITCH_WIFI_CASE_KEY,
        aliases=SWITCH_WIFI_CASE_ALIASES,
    )
    settings = _parse_switch_wifi_settings(case_cfg)
    targets = _load_planned_targets(settings)
    checkpoints = extract_checkpoints(stability_cfg)
    return settings, targets, checkpoints


def _load_planned_targets(settings: SwitchWifiSettings) -> tuple[BssTarget, ...]:
    targets = tuple(settings.iter_targets())
    if not targets:
        logging.warning("No Wi-Fi BSS targets configured for %s", SWITCH_WIFI_CASE_KEY)
    return targets


def _disconnect_wifi() -> None:
    forget = getattr(pytest.dut, "forget_wifi", None)
    if callable(forget):
        try:
            forget()
        except Exception as exc:  # pragma: no cover - hardware dependent
            logging.debug("Failed to forget Wi-Fi network: %s", exc)

    disable = getattr(pytest.dut, "set_wifi_disabled", None)
    enable = getattr(pytest.dut, "set_wifi_enabled", None)
    if callable(disable) and callable(enable):
        try:
            disable()
            time.sleep(2)
            enable()
            time.sleep(2)
        except Exception as exc:  # pragma: no cover - hardware dependent
            logging.debug("Failed to toggle Wi-Fi interface: %s", exc)


def _connect_wifi(target: BssTarget) -> bool:
    if getattr(pytest, "connect_type", "").lower() != "android":
        logging.error(
            "Switch Wi-Fi stability currently supports Android DUT only (connect_type=%s)",
            getattr(pytest, "connect_type", None),
        )
        return False


    security_lower = target.security_mode.strip().lower()
    if security_lower == "open system":
        security_token = "open"
        password = ""
    elif "wpa3" in security_lower:
        security_token = "wpa3"
        password = target.password
    else:
        security_token = "wpa2"
        password = target.password

    logging.info(
        "Connecting to SSID '%s' (security=%s)",
        target.ssid,
        target.security_mode,
    )
    try:
        return bool(pytest.dut.connect_wifi(target.ssid, password, security_token,lan=False))
    except Exception as exc:  # pragma: no cover - hardware dependent
        logging.error("Wi-Fi connect API failed for %s: %s", target.ssid, exc)
        return False


def _describe_iteration(iteration: int, loops: int | None, mode: str) -> str:
    if loops is not None:
        return f"loop {iteration}/{loops}"
    if mode == "duration":
        return f"loop {iteration} (duration mode)"
    if mode == "limit":
        return f"loop {iteration} (limit mode)"
    return f"loop {iteration}"


def _cycle_targets(targets: Iterable[BssTarget], checkpoints: Mapping[str, bool], failures: list[str], iteration_label: str) -> None:
    for target in targets:
        label = f"SSID {target.ssid}"
        success = False
        try:
            success = _connect_wifi(target)
            if success:
                _run_check_points(label, checkpoints)
        finally:
            _disconnect_wifi()

        if success:
            logging.info("Successfully cycled %s", label)
        else:
            message = f"{label} ({target.security_mode})"
            logging.error("Failed to cycle %s", message)
            failures.append(f"{iteration_label}: {message}")


def _run_check_points(label: str, checkpoints: Mapping[str, bool]) -> None:
    if checkpoints.get("ping"):
        logging.info("[Ping] Placeholder verification for %s", label)


def test_swtich_wifi_workflow() -> None:
    plan = load_stability_plan()

    os.environ[STABILITY_COMPLETED_LOOPS_ENV] = "0"

    _, targets, checkpoints = _load_switch_settings()
    if not targets:
        os.environ[STABILITY_COMPLETED_LOOPS_ENV] = "0"
        pytest.skip("No Wi-Fi targets configured for test_switch_wifi")

    if getattr(pytest, "connect_type", "").lower() != "android":
        os.environ[STABILITY_COMPLETED_LOOPS_ENV] = "0"
        pytest.skip("Switch Wi-Fi stability currently supports Android DUT only")

    failures: list[str] = []

    for iteration, budget, report_completion in iterate_stability_loops(plan):
        iteration_label = _describe_iteration(iteration, budget.total_loops, plan.mode)
        logging.info("[Switch Wi-Fi] %s start", iteration_label)

        _cycle_targets(targets, checkpoints, failures, iteration_label)

        report_completion()
        logging.info("[Switch Wi-Fi] %s complete", iteration_label)

    if failures:
        logging.warning(
            "Switch Wi-Fi encountered %s failures:%s%s",
            len(failures),
            os.linesep,
            os.linesep.join(failures),
        )
