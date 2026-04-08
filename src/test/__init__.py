import csv
import logging
import os
import re
import time
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import pytest

from src.tools.connect_tool.lab_device_controller import LabDeviceController
from src.tools.performance_result import PerformanceResult
from src.tools.router_tool.Router import Router
from src.tools.router_tool.router_factory import get_router
from src.tools.rs_test import rs
from src.util.constants import get_config_base, load_config
from src.util.constants import (
    DEFAULT_RF_STEP_SPEC,
    IDENTIFIER_SANITIZE_PATTERN,
    RF_ATTENUATION_MAX_DB,
    RF_ATTENUATION_MIN_DB,
    RF_MODEL_CHOICES,
    RF_MODEL_RS232,
    TURN_TABLE_FIELD_IP_ADDRESS,
    TURN_TABLE_FIELD_MODEL,
    TURN_TABLE_FIELD_STATIC_DB,
    TURN_TABLE_FIELD_STEP,
    TURN_TABLE_FIELD_TARGET_RSSI,
    TURN_TABLE_MODEL_RS232,
    TURN_TABLE_SECTION_KEY,
    get_debug_flags,
)
from src.test.rf_steps import (
    collect_rf_step_segments as _collect_rf_step_segments,
    expand_rf_step_segments as _expand_rf_step_segments,
    parse_optional_int as _parse_optional_int,
    parse_rf_step_spec,
    parse_turntable_step_bounds as _parse_turntable_step_bounds,
)

_SCENARIO_KEY_FIELDS = (
    ("band", "band"),
    ("ssid", "ssid"),
    ("mode", "wireless_mode"),
    ("channel", "channel"),
    ("bandwidth", "bandwidth"),
    ("security", "security_mode"),
)


def get_testdata(router):
    config = load_config(refresh=True) or {}
    config_base = get_config_base()
    router_name = config.get("router", {}).get("name", "")
    csv_path = config.get("csv_path")

    if csv_path:
        csv_path = Path(csv_path)
        if not csv_path.is_absolute():
            csv_path = config_base / csv_path
    else:
        csv_path = config_base / "performance_test_csv" / "rvr_wifi_setup.csv"

    test_data = []
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = [j for j in reader]
            for i in rows[1:]:
                if not i:
                    continue
                stripped_i = [field.strip() for field in i]
                test_data.append(Router(*stripped_i))
    except FileNotFoundError:
        raise FileNotFoundError(
            f"CSV file not found at {csv_path}. Please check router name '{router_name}'."
        )
    return test_data


def _turntable_section_from_config(cfg: Any) -> dict[str, Any]:
    if not isinstance(cfg, dict):
        return {}
    section = cfg.get(TURN_TABLE_SECTION_KEY)
    return section if isinstance(section, dict) else {}


def _normalize_scenario_token(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    sanitized = IDENTIFIER_SANITIZE_PATTERN.sub("_", text)
    sanitized = sanitized.strip("_")
    if not sanitized:
        return ""
    return sanitized.upper()


def build_scenario_group_key(router_info: Router) -> str:
    parts: list[str] = []
    for label, attr in _SCENARIO_KEY_FIELDS:
        raw = getattr(router_info, attr, None)
        normalized = _normalize_scenario_token(raw)
        if normalized:
            parts.append(f"{label.upper()}={normalized}")
    for label in ("tx", "rx"):
        normalized = _normalize_scenario_token(getattr(router_info, label, None))
        if normalized:
            parts.append(f"{label.upper()}={normalized}")
    if not parts:
        return "SCENARIO|UNKNOWN"
    return "SCENARIO|" + "|".join(parts)


def ensure_performance_result() -> PerformanceResult:
    existing = getattr(pytest, "testResult", None)
    if isinstance(existing, PerformanceResult):
        return existing
    logdir = getattr(pytest, "_result_path", None) or os.getcwd()
    repeat_times = getattr(pytest, "_testresult_repeat_times", 0)
    result = PerformanceResult(logdir, [], repeat_times)
    pytest.testResult = result
    return result


@contextmanager
def scenario_group(router_info: Router):
    key = build_scenario_group_key(router_info)
    test_result = getattr(pytest, "testResult", None)
    if test_result is not None:
        test_result.set_scenario_group_key(key)
    try:
        yield key
    finally:
        if test_result is not None:
            test_result.clear_scenario_group_key()


class _DebugRFController:
    def __init__(self) -> None:
        self._current_value = 0

    def execute_rf_cmd(self, value) -> None:
        try:
            self._current_value = int(float(value))
        except Exception:
            self._current_value = 0
        logging.info("[Debug] Skip RF command, simulated attenuation: %s dB", self._current_value)

    def get_rf_current_value(self):
        return self._current_value


class _DebugCornerController:
    def __init__(self) -> None:
        self._angle = 0

    def set_turntable_zero(self) -> None:
        self._angle = 0
        logging.info("[Debug] Skip corner reset, simulated angle reset to 0°")

    def execute_turntable_cmd(self, command, angle="") -> None:
        if angle not in (None, ""):
            self._angle = angle
        logging.info(
            "[Debug] Skip corner command %s, simulated angle: %s",
            command,
            self._angle,
        )

    def get_turntanle_current_angle(self):
        return self._angle


class _DebugRouterController:
    name = "debug-router"
    CHANNEL_2: tuple = ()
    CHANNEL_5: tuple = ()
    BANDWIDTH_2: tuple = ()
    BANDWIDTH_5: tuple = ()
    AUTHENTICATION_METHOD = ()
    AUTHENTICATION_METHOD_LEGCY = ()

    def __init__(self, reason: str) -> None:
        logging.info(
            "Debug flag (%s) enabled, skip router controller instantiation",
            reason,
        )

    def set_wireless_mode(self, mode) -> None:
        logging.info("[Debug] Skip router set_wireless_mode(%s)", mode)

    def set_bandwidth(self, bandwidth) -> None:
        logging.info("[Debug] Skip router set_bandwidth(%s)", bandwidth)

    def set_channel(self, channel) -> None:
        logging.info("[Debug] Skip router set_channel(%s)", channel)

    def set_security(self, security_mode) -> None:
        logging.info("[Debug] Skip router set_security(%s)", security_mode)

    def set_ssid_password(self, ssid, password) -> None:
        logging.info("[Debug] Skip router set_ssid_password(ssid=%s)", ssid)

    def enable_tx_rx(self, tx, rx) -> None:
        logging.info("[Debug] Skip router enable_tx_rx(tx=%s, rx=%s)", tx, rx)

    def change_setting(self, router_info: Router) -> bool:
        logging.info("[Debug] Skip router change_setting(%s)", router_info)
        return True

    def __getattr__(self, item: str):
        raise AttributeError(f"_DebugRouterController has no attribute {item!r}")


@lru_cache(maxsize=1)
def get_cfg() -> Any:
    return load_config(refresh=True)


def describe_debug_reason(option_key: str) -> str:
    return f"debug option '{option_key}'"


def init_rf():
    flags = get_debug_flags()
    if flags.skip_corner_rf:
        reason = describe_debug_reason("skip_corner_rf")
        logging.info("Debug flag (%s) enabled, skip RF attenuator initialization", reason)
        return _DebugRFController()
    cfg = get_cfg()
    rf_solution = cfg["rf_solution"]
    model = rf_solution["model"]
    if model not in RF_MODEL_CHOICES:
        raise EnvironmentError("Doesn't support this model")
    if model == RF_MODEL_RS232:
        rf_tool = rs()
    else:
        rf_ip = rf_solution[model]["ip_address"]
        rf_tool = LabDeviceController(rf_ip)
        logging.info(f"rf_ip {rf_ip}")
    logging.info("Reset rf value")
    rf_tool.execute_rf_cmd(RF_ATTENUATION_MIN_DB)
    time.sleep(3)
    return rf_tool


def init_corner():
    flags = get_debug_flags()
    if flags.skip_corner_rf:
        reason = describe_debug_reason("skip_corner_rf")
        logging.info("Debug flag (%s) enabled, skip corner initialization", reason)
        controller = _DebugCornerController()
        controller.set_turntable_zero()
        return controller
    cfg = get_cfg()
    turntable_cfg = _turntable_section_from_config(cfg)
    model = str(turntable_cfg.get(TURN_TABLE_FIELD_MODEL, TURN_TABLE_MODEL_RS232)).strip()
    corner_ip = ""
    if model == TURN_TABLE_MODEL_RS232:
        corner_tool = rs()
    else:
        corner_ip = str(turntable_cfg.get(TURN_TABLE_FIELD_IP_ADDRESS, "")).strip()
        if not corner_ip:
            raise EnvironmentError(
                "Turntable IP address is required when using network-controlled models"
            )
        corner_tool = LabDeviceController(corner_ip)
    logging.info(f"corner model {model} ip {corner_ip}")
    logging.info("Reset corner")
    corner_tool.set_turntable_zero()
    logging.info(corner_tool.get_turntanle_current_angle())
    time.sleep(3)
    return corner_tool


def init_router() -> Any:
    flags = get_debug_flags()
    if flags.skip_router:
        reason = describe_debug_reason("skip_router")
        return _DebugRouterController(reason)
    cfg = get_cfg()
    router = get_router(cfg["router"]["name"])
    return router


def common_setup(router: Router, router_info: Router) -> bool:
    logging.info("router setup start")
    logging.info("router factory start")
    channel_text = str(getattr(router_info, "channel", "") or "").strip()
    if not channel_text or channel_text.lower() in {"none", "null"}:
        channel_text = "auto"
    router_config = Router(
        band=getattr(router_info, "band", None),
        ssid=getattr(router_info, "ssid", None),
        wireless_mode=getattr(router_info, "wireless_mode", None),
        channel=channel_text,
        bandwidth=getattr(router_info, "bandwidth", None),
        security_mode=getattr(router_info, "security_mode", None),
        password=getattr(router_info, "password", None),
        tx=getattr(router_info, "tx", None),
        rx=getattr(router_info, "rx", None),
        expected_rate=getattr(router_info, "expected_rate", None),
        wifi6=getattr(router_info, "wifi6", None),
        wep_encrypt=getattr(router_info, "wep_encrypt", None),
        hide_ssid=getattr(router_info, "hide_ssid", None),
        hide_type=getattr(router_info, "hide_type", None),
        wpa_encrypt=getattr(router_info, "wpa_encrypt", None),
        passwd_index=getattr(router_info, "passwd_index", None),
        protect_frame=getattr(router_info, "protect_frame", None),
        smart_connect=getattr(router_info, "smart_connect", None),
        country_code=getattr(router_info, "country_code", None),
    )

    if hasattr(router, "change_setting"):
        result = router.change_setting(router_config)
        logging.info("router setup end")
        return True if result is None else bool(result)

    # Compatibility fallback for legacy controllers that expose step-wise APIs.
    router.channel = router_config.channel
    router.bandwidth = router_config.bandwidth
    router.wireless_mode = router_config.wireless_mode
    router.security_mode = router_config.security_mode
    router.tx = router_config.tx
    router.rx = router_config.rx
    router.ssid = router_config.ssid
    router.password = router_config.password

    router.set_wireless_mode(router.wireless_mode)
    router.set_bandwidth(router.bandwidth)
    router.set_channel(router.channel)
    router.set_security(router.security_mode)
    router.set_ssid_password(router.ssid, router.password)
    router.enable_tx_rx(router.tx, router.rx)

    logging.info("router setup end")
    return True


def _parse_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def wait_connect(router_info: Router) -> bool:
    flags = get_debug_flags()
    cfg = get_cfg()
    third_party_cfg = cfg.get("connect_type", {}).get("third_party", {}) if isinstance(cfg, dict) else {}
    if flags.skip_connect:
        reason = describe_debug_reason("skip_connect")
        logging.info(
            "Debug flag (%s) enabled, skip Wi-Fi reconnection workflow (router=%s)",
            reason,
            getattr(router_info, "ssid", "<unknown>"),
        )
        return True
    if third_party_cfg == "true":
        wait_seconds = _parse_optional_int(
            third_party_cfg.get("wait_seconds"),
            field_name="connect_type.third_party.wait_seconds",
            min_value=1,
        )
        actual_wait_seconds = wait_seconds if third_party_cfg.get("enabled") and wait_seconds else 3
        logging.info(
            "router setup waiting for %s seconds (enabled=%s, wait_seconds=%s)",
            actual_wait_seconds,
            third_party_cfg.get("enabled"),
            wait_seconds,
        )
        time.sleep(actual_wait_seconds)
        connect_status = True
    else:
        logging.info(f"dut try to connect {router_info.ssid}")
        security_mode = getattr(router_info, "security_mode", "") or ""
        security_lower = security_mode.lower()
        if security_lower == "open system":
            security_token = "open"
            password = ""
        elif "wpa3" in security_lower:
            security_token = "wpa3"
            password = getattr(router_info, "password", "") or ""
        else:
            security_token = "wpa2"
            password = getattr(router_info, "password", "") or ""

        connect_status = pytest.dut.wifi_connect(
            router_info.ssid,
            password,
            security_token,
            hidden=getattr(router_info, "hide_ssid", "") == "是",
        )

    logging.info(f"dut_ip:{pytest.dut.dut_ip}")
    logging.info(f"pc_ip:{pytest.dut.pc_ip}")
    logging.info("dut connected")
    return connect_status


@lru_cache(maxsize=1)
def get_rf_step_list():
    cfg = get_cfg()
    rf_solution = cfg.get("rf_solution", {}) if isinstance(cfg, dict) else {}
    raw_step = rf_solution.get("step") if isinstance(rf_solution, dict) else None
    return parse_rf_step_spec(raw_step)


@lru_cache(maxsize=1)
def get_corner_step_list():
    cfg = get_cfg()
    turntable_cfg = _turntable_section_from_config(cfg)
    raw_step = turntable_cfg.get(TURN_TABLE_FIELD_STEP, "")
    bounds_part, sep, step_part = str(raw_step).replace("-", ",", 1).partition(":")
    step = int(step_part.strip()) if sep else 45
    bounds = _parse_turntable_step_bounds(bounds_part.strip())
    if bounds is None:
        logging.warning("Turntable step configuration %r is invalid", raw_step)
        return []
    start, stop = bounds
    if start == stop:
        return [start]
    if start > stop:
        start, stop = stop, start
    return list(range(start, stop + 1, step))


def get_rvo_static_db_list():
    cfg = load_config(refresh=True)
    turntable_cfg = _turntable_section_from_config(cfg)
    raw_value = turntable_cfg.get(TURN_TABLE_FIELD_STATIC_DB, "")
    candidates = []

    if isinstance(raw_value, str):
        segments = [segment.strip() for segment in re.split(r"[,，]", raw_value)]
        candidates.extend(segment for segment in segments if segment)
    elif isinstance(raw_value, (list, tuple, set)):
        candidates.extend(raw_value)
    else:
        candidates.append(raw_value)

    parsed_values = []
    for item in candidates:
        parsed = _parse_optional_int(
            item,
            field_name=f"{TURN_TABLE_SECTION_KEY}.{TURN_TABLE_FIELD_STATIC_DB}",
            min_value=0,
            max_value=RF_ATTENUATION_MAX_DB,
        )
        if parsed is not None:
            parsed_values.append(parsed)

    return parsed_values if parsed_values else [None]


def get_rvo_target_rssi_list():
    return get_target_rssi_list()


def get_target_rssi_list():
    cfg = load_config(refresh=True)
    turntable_cfg = _turntable_section_from_config(cfg)
    raw_value = turntable_cfg.get(TURN_TABLE_FIELD_TARGET_RSSI, "")
    candidates = []

    if isinstance(raw_value, str):
        segments = [segment.strip() for segment in re.split(r"[,，]", raw_value)]
        candidates.extend(segment for segment in segments if segment)
    elif isinstance(raw_value, (list, tuple, set)):
        candidates.extend(raw_value)
    else:
        candidates.append(raw_value)

    parsed_values = []
    for item in candidates:
        parsed = _parse_optional_int(
            item,
            field_name=f"{TURN_TABLE_SECTION_KEY}.{TURN_TABLE_FIELD_TARGET_RSSI}",
        )
        if parsed is not None:
            normalized = parsed if parsed <= 0 else -abs(parsed)
            if normalized != parsed:
                logging.debug(
                    "%s.%s %s converted to %s dBm to match RSSI sign convention",
                    TURN_TABLE_SECTION_KEY,
                    TURN_TABLE_FIELD_TARGET_RSSI,
                    parsed,
                    normalized,
                )
            parsed_values.append(normalized)

    return parsed_values if parsed_values else [None]


def _safe_int(value: Any) -> Optional[int]:
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        try:
            return int(float(value))
        except ValueError:
            return None
    if isinstance(value, (list, tuple, set)):
        for item in value:
            parsed = _safe_int(item)
            if parsed is not None:
                return parsed
        return None
    if isinstance(value, (int, float)):
        return int(value)
    return None


def _get_current_attenuation(rf_tool: Any) -> int:
    try:
        value = rf_tool.get_rf_current_value()
    except Exception as exc:
        logging.warning("Failed to get rf current value: %s", exc)
        return 0
    parsed = _safe_int(value)
    return parsed if parsed is not None else 0


def _clamp_db(value: Optional[int]) -> int:
    parsed = _safe_int(value)
    if parsed is None:
        return 0
    return max(0, min(RF_ATTENUATION_MAX_DB, parsed))


def _initial_rssi_adjust_step() -> int:
    try:
        candidates = sorted(set(get_rf_step_list()))
    except Exception as exc:
        logging.warning("Failed to load RF step list: %s; fallback to step=1", exc)
        return 1

    max_gap = 0
    previous = None
    for value in candidates:
        if previous is not None and value > previous:
            gap = value - previous
            if gap > max_gap:
                max_gap = gap
        previous = value

    return max_gap or 1


def adjust_rssi_to_target(
    rf_tool: Any,
    target_rssi: int,
    base_db: Optional[int] = None,
) -> tuple[int, Optional[int]]:
    flags = get_debug_flags()
    if flags.skip_corner_rf:
        simulated_rssi = pytest.dut.get_rssi()
        reason = describe_debug_reason("skip_corner_rf")
        logging.info(
            "Debug flag (%s) enabled, skip RSSI adjustment and return simulated RSSI %s dBm",
            reason,
            simulated_rssi,
        )
        return simulated_rssi, _clamp_db(
            base_db if base_db is not None else _get_current_attenuation(rf_tool)
        )

    applied_db = _clamp_db(
        base_db if base_db is not None else _get_current_attenuation(rf_tool)
    )
    step = _initial_rssi_adjust_step()
    current_rssi = pytest.dut.get_rssi()
    logging.info(
        "Start adjusting attenuation to %s dB for target RSSI %s dBm",
        applied_db,
        target_rssi,
    )
    if current_rssi == -1:
        return current_rssi, applied_db

    for attempt in range(30):
        diff = current_rssi - target_rssi
        logging.info("current rssi %s target rssi %s", current_rssi, target_rssi)
        if diff == 0:
            break

        direction = 1 if diff > 0 else -1
        next_db = max(0, min(RF_ATTENUATION_MAX_DB, applied_db + direction * step))
        if next_db == applied_db:
            if step > 1:
                step = 1
                continue
            logging.info(
                "Attenuation locked at %s dB while RSSI diff=%s dB; boundary reached.",
                applied_db,
                diff,
            )
            break

        logging.info(
            "Adjust attenuation to %s dB (attempt %s) for RSSI diff=%s dB (target %s dBm)",
            next_db,
            attempt + 1,
            diff,
            target_rssi,
        )
        try:
            rf_tool.execute_rf_cmd(next_db)
        except Exception as exc:
            logging.warning("Failed to execute rf command %s: %s", next_db, exc)
            break

        time.sleep(3)
        measured = pytest.dut.get_rssi()
        applied_db = next_db
        current_rssi = measured
        if measured == -1:
            break

        new_diff = measured - target_rssi
        logging.info(
            "Measured RSSI %s dBm (diff %s dB) after attenuation %s dB",
            measured,
            new_diff,
            next_db,
        )
        if new_diff == 0:
            break
        if abs(new_diff) >= abs(diff) and step > 1:
            step = max(1, step // 2)
        elif step > 1 and abs(new_diff) <= 1:
            step = 1

    logging.info("Final RSSI %s dBm with attenuation %s dB", current_rssi, applied_db)
    return current_rssi, applied_db


def _merge_rf_step_defaults(raw_value: Any) -> str:
    if raw_value is None:
        return DEFAULT_RF_STEP_SPEC
    text = str(raw_value).strip()
    if not text:
        return DEFAULT_RF_STEP_SPEC
    if re.fullmatch(r"\\d+", text):
        return f"0,{text}:3"
    return text


@lru_cache(maxsize=1)
def collect_rf_step_segments():
    cfg = load_config(refresh=True)
    rf_solution = cfg.get("rf_solution", {}) if isinstance(cfg, dict) else {}
    raw_step = rf_solution.get("step") if isinstance(rf_solution, dict) else None
    return _collect_rf_step_segments(_merge_rf_step_defaults(raw_step))


@lru_cache(maxsize=1)
def expand_rf_step_segments():
    segments = collect_rf_step_segments()
    return _expand_rf_step_segments(segments)


def get_rf_step_segments() -> str:
    segments = collect_rf_step_segments()
    return ",".join(str(seg) for seg in segments)


def get_rf_step_list() -> list[int]:
    return expand_rf_step_segments()


__all__ = [
    "Router",
    "build_scenario_group_key",
    "collect_rf_step_segments",
    "common_setup",
    "adjust_rssi_to_target",
    "ensure_performance_result",
    "expand_rf_step_segments",
    "get_cfg",
    "get_corner_step_list",
    "get_rf_step_list",
    "get_rf_step_segments",
    "get_target_rssi_list",
    "get_rvo_static_db_list",
    "get_rvo_target_rssi_list",
    "get_testdata",
    "init_corner",
    "init_rf",
    "init_router",
    "scenario_group",
    "wait_connect",
]
