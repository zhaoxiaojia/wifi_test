"""Combined STR relay + Wi‑Fi BSS switching stability workflow."""

from __future__ import annotations

import csv
import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import pytest

from src.test.stability import (
    CheckpointConfig,
    STABILITY_COMPLETED_LOOPS_ENV,
    describe_iteration,
    extract_checkpoints,
    extract_stability_case,
    iterate_stability_loops,
    load_stability_plan,
    run_checkpoints,
)
from src.util.constants import load_config
from src.tools.relay_tool import Relay, get_relay_controller
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

WifiTarget = dict[str, str]
CycleConfig = dict[str, Any]


def _build_wifi_target(raw: Mapping[str, Any] | None) -> WifiTarget | None:
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
    return {"ssid": ssid, "security_mode": security, "password": password}


def _normalize_manual_targets(data: Iterable[Any] | None) -> tuple[WifiTarget, ...]:
    if data is None:
        return ()
    targets: list[WifiTarget] = []
    for item in data:
        mapping = item if isinstance(item, Mapping) else None
        target = _build_wifi_target(mapping)
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


def _load_router_targets(csv_path: Path | None) -> tuple[WifiTarget, ...]:
    if csv_path is None:
        return ()
    entries: list[WifiTarget] = []
    try:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                target = _build_wifi_target(row)
                if target is not None:
                    entries.append(target)
    except FileNotFoundError:
        logging.warning("Router CSV %s missing; falling back to manual entries", csv_path)
        return ()
    except Exception as exc:  # pragma: no cover - CSV corruption is rare
        logging.error("Failed to load Wi-Fi router CSV %s: %s", csv_path, exc)
        return ()
    return tuple(entries)


def _load_wifi_targets(case_cfg: Mapping[str, Any]) -> tuple[WifiTarget, ...]:
    data = case_cfg or {}
    use_router = bool(data.get(SWITCH_WIFI_USE_ROUTER_FIELD))
    router_csv = _resolve_router_csv_path(data.get(SWITCH_WIFI_ROUTER_CSV_FIELD))
    manual_targets = _normalize_manual_targets(data.get(SWITCH_WIFI_MANUAL_ENTRIES_FIELD))
    router_targets: tuple[WifiTarget, ...] = ()
    if use_router:
        router_targets = _load_router_targets(router_csv)
        if not router_targets and manual_targets:
            logging.info(
                "Router CSV produced no entries; defaulting to %s manual targets.",
                len(manual_targets),
            )
    targets: tuple[WifiTarget, ...] = router_targets or manual_targets
    if not targets:
        logging.warning("No Wi-Fi BSS targets configured for %s", SWITCH_WIFI_CASE_KEY)
    return targets


def _connect_wifi(target: WifiTarget) -> bool:
    if getattr(pytest, "connect_type", "").lower() != "android":
        logging.error(
            "Switch Wi-Fi stability currently supports Android DUT only (connect_type=%s)",
            getattr(pytest, "connect_type", None),
        )
        return False

    security_lower = target["security_mode"].strip().lower()
    if security_lower == "open system":
        security_token = "open"
        password = ""
    elif "wpa3" in security_lower:
        security_token = "wpa3"
        password = target["password"]
    else:
        security_token = "wpa2"
        password = target["password"]

    logging.info(
        "Connecting to SSID '%s' (security=%s)",
        target["ssid"],
        target["security_mode"],
    )
    try:
        return bool(
            pytest.dut.wifi_connect(target["ssid"], password, security_token, lan=False)
        )
    except Exception as exc:  # pragma: no cover - hardware dependent
        logging.error("Wi-Fi connect API failed for %s: %s", target["ssid"], exc)
        return False


def _cycle_targets(
    targets: Iterable[WifiTarget],
    checkpoints: CheckpointConfig | Mapping[str, Any] | None,
    failures: list[str],
    iteration_label: str,
) -> None:
    for target in targets:
        label = f"SSID {target['ssid']}"
        success = False
        try:
            success = _connect_wifi(target)
            if success:
                run_checkpoints(label, checkpoints)
        finally:
            pytest.dut.wifi_forget()

        if success:
            logging.info("Successfully cycled %s", label)
        else:
            message = f"{label} ({target['security_mode']})"
            logging.error("Failed to cycle %s", message)
            failures.append(f"{iteration_label}: {message}")


def _coerce_duration(raw: Any) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 0
    return max(0, value)


def _parse_relay_params(raw_params: Any) -> tuple[Any, ...]:
    if isinstance(raw_params, (list, tuple)):
        return tuple(raw_params)
    if isinstance(raw_params, Sequence) and not isinstance(
        raw_params, (str, bytes, bytearray)
    ):
        return tuple(raw_params)
    if isinstance(raw_params, str):
        return tuple(item.strip() for item in raw_params.split(",") if item.strip())
    return ()


def _build_cycle_config(data: Mapping[str, Any] | None) -> CycleConfig | None:
    if not isinstance(data, Mapping):
        return None

    enabled = bool(data.get("enabled"))
    if not enabled:
        return None

    port = str(data.get("port", "") or "").strip()
    mode = str(data.get("mode", "") or "NO").strip().upper() or "NO"
    relay_type = str(data.get("relay_type", "usb_relay") or "usb_relay").strip()
    relay_params = _parse_relay_params(data.get("relay_params"))
    relay = get_relay_controller(relay_type, relay_params, port=port, mode=mode)
    if relay is None:
        logging.warning("Relay controller unavailable for type %s; skipping cycle.", relay_type)
        return None

    return {
        "enabled": enabled,
        "on_duration": _coerce_duration(data.get("on_duration")),
        "off_duration": _coerce_duration(data.get("off_duration")),
        "port": port,
        "mode": mode,
        "relay_type": relay_type,
        "relay_params": relay_params,
        "relay": relay,
    }


def _run_cycle(label: str, cycle: CycleConfig | None) -> None:
    if not cycle or not cycle.get("enabled"):
        logging.info("[%s] cycle disabled or not configured; skipping", label)
        return

    controller = cycle.get("relay")
    if not isinstance(controller, Relay):
        logging.warning("[%s] relay controller unavailable; skipping", label)
        return

    logging.info(
        "[%s] cycle start: on=%ss off=%ss mode=%s port=%s",
        label,
        cycle["on_duration"],
        cycle["off_duration"],
        cycle["mode"],
        cycle["port"],
    )
    try:
        if cycle["on_duration"] > 0:
            time.sleep(cycle["on_duration"])
        controller.pulse("power_off")
        if cycle["off_duration"] > 0:
            time.sleep(cycle["off_duration"])
        controller.pulse("power_on")
    except Exception as exc:  # pragma: no cover - hardware dependent
        logging.error("[%s] relay operation failed: %s", label, exc)


def _load_switch_wifi_str_components() -> tuple[
    CycleConfig | None,
    CycleConfig | None,
    tuple[WifiTarget, ...],
    CheckpointConfig,
]:
    config = load_config(refresh=True)
    stability_cfg = config.get("stability") if isinstance(config, Mapping) else {}
    case_cfg = extract_stability_case(
        stability_cfg,
        SWITCH_WIFI_CASE_KEY,
        aliases=SWITCH_WIFI_CASE_ALIASES,
    )
    ac_cycle = _build_cycle_config(case_cfg.get("ac"))
    str_cycle = _build_cycle_config(case_cfg.get("str"))
    wifi_targets = _load_wifi_targets(case_cfg)
    checkpoints = extract_checkpoints(stability_cfg)
    return ac_cycle, str_cycle, wifi_targets, checkpoints


@pytest.fixture(scope="session")
def switch_wifi_str_components() -> dict[str, Any]:
    ac_cycle, str_cycle, wifi_targets, checkpoints = _load_switch_wifi_str_components()
    return {
        "ac_cycle": ac_cycle,
        "str_cycle": str_cycle,
        "wifi_targets": wifi_targets,
        "checkpoints": checkpoints,
    }


@pytest.fixture(scope="session")
def ac_control(switch_wifi_str_components: Mapping[str, Any]) -> Callable[[], None]:
    cycle: CycleConfig | None = switch_wifi_str_components.get("ac_cycle")
    checkpoints = switch_wifi_str_components.get("checkpoints")

    def _runner() -> None:
        if not cycle:
            return
        _run_cycle("AC", cycle)
        if checkpoints is not None:
            run_checkpoints("AC", checkpoints)

    return _runner


@pytest.fixture(scope="session")
def str_control(switch_wifi_str_components: Mapping[str, Any]) -> Callable[[], None]:
    cycle: CycleConfig | None = switch_wifi_str_components.get("str_cycle")
    checkpoints = switch_wifi_str_components.get("checkpoints")

    def _runner() -> None:
        if not cycle:
            return
        _run_cycle("STR", cycle)
        if checkpoints is not None:
            run_checkpoints("STR", checkpoints)

    return _runner


@pytest.fixture(scope="session")
def wifi_control(
    switch_wifi_str_components: Mapping[str, Any],
) -> Callable[[list[str], str], None]:
    targets: tuple[WifiTarget, ...] = switch_wifi_str_components.get("wifi_targets", ())
    checkpoints = switch_wifi_str_components.get("checkpoints")

    def _runner(failures: list[str], iteration_label: str) -> None:
        if not targets:
            return
        _cycle_targets(targets, checkpoints, failures, iteration_label)

    return _runner


def test_switch_wifi_str_workflow(
    switch_wifi_str_components: Mapping[str, Any],
    ac_control: Callable[[], None],
    str_control: Callable[[], None],
    wifi_control: Callable[[list[str], str], None],
) -> None:
    """Run AC/STR relay cycles and Wi‑Fi BSS switching in a single stability testcase."""
    plan = load_stability_plan()

    os.environ[STABILITY_COMPLETED_LOOPS_ENV] = "0"

    ac_cycle: CycleConfig | None = switch_wifi_str_components.get("ac_cycle")
    str_cycle: CycleConfig | None = switch_wifi_str_components.get("str_cycle")
    wifi_targets: tuple[WifiTarget, ...] = switch_wifi_str_components.get(
        "wifi_targets", ()
    )

    if not ac_cycle and not str_cycle and not wifi_targets:
        os.environ[STABILITY_COMPLETED_LOOPS_ENV] = "0"
        pytest.skip(
            "AC/STR cycles disabled and no Wi-Fi targets configured; nothing to execute."
        )

    if wifi_targets and getattr(pytest, "connect_type", "").lower() != "android":
        os.environ[STABILITY_COMPLETED_LOOPS_ENV] = "0"
        pytest.skip("Switch Wi-Fi stability currently supports Android DUT only")

    failures: list[str] = []

    for iteration, budget, report_completion in iterate_stability_loops(plan):
        iteration_label = describe_iteration(iteration, budget, plan.mode)
        logging.info("[Switch Wi-Fi STR] stability %s start", iteration_label)

        ac_control()
        str_control()
        wifi_control(failures, iteration_label)

        report_completion()
        logging.info("[Switch Wi-Fi STR] stability %s complete", iteration_label)

    if failures:
        logging.warning(
            "Switch Wi-Fi encountered %s failures:%s%s",
            len(failures),
            os.linesep,
            os.linesep.join(failures),
        )
