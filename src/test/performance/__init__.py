#!/usr/bin/env python
# encoding: utf-8
"""
通用性能测试工具
"""
import logging
import os
import re
import time
from contextlib import contextmanager
from functools import lru_cache
from typing import Any, Optional

import pytest

from src.util.constants import load_config
from src.tools.performance_result import PerformanceResult
from src.tools.router_tool.Router import Router
from src.tools.router_tool.router_factory import get_router
from src.tools.connect_tool.lab_device_controller import LabDeviceController
from src.tools.rs_test import rs
from src.util.constants import (
    DEFAULT_RF_STEP_SPEC,
    IDENTIFIER_SANITIZE_PATTERN,
    get_debug_flags,
    TURN_TABLE_FIELD_IP_ADDRESS,
    TURN_TABLE_FIELD_MODEL,
    TURN_TABLE_FIELD_STATIC_DB,
    TURN_TABLE_FIELD_STEP,
    TURN_TABLE_FIELD_TARGET_RSSI,
    TURN_TABLE_MODEL_RS232,
    TURN_TABLE_SECTION_KEY,
)
from src.test.performance.rf_steps import (
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
    """根据 ``rvr_wifi_setup`` 的行数据生成场景分组键。"""

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
    """Return the shared PerformanceResult instance, creating it on first use."""
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
    """在测试执行期间临时设置 ``scenario_group_key``。"""

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
    """No-op RF controller used when RF operations are skipped."""

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
    """No-op corner controller used when corner operations are skipped."""

    def __init__(self) -> None:
        self._angle = 0

    def set_turntable_zero(self) -> None:
        self._angle = 0
        logging.info("[Debug] Skip corner reset, simulated angle reset to 0°")

    def execute_turntable_cmd(self, command, angle='') -> None:
        if angle not in (None, ''):
            self._angle = angle
        logging.info(
            "[Debug] Skip corner command %s, simulated angle: %s",
            command,
            self._angle,
        )

    def get_turntanle_current_angle(self):
        return self._angle


class _DebugRouterController:
    """Lightweight router placeholder used when router operations are skipped."""

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

    def __getattr__(self, item: str):
        raise AttributeError(f"_DebugRouterController has no attribute {item!r}")


@lru_cache(maxsize=1)
def get_cfg() -> Any:
    """返回最新的配置"""
    return load_config(refresh=True)


def describe_debug_reason(option_key: str, *, database_mode: bool) -> str:
    return "database debug mode" if database_mode else f"debug option '{option_key}'"


def init_rf():
    """根据配置初始化射频衰减器"""
    flags = get_debug_flags()
    if flags.skip_corner_rf:
        reason = describe_debug_reason("skip_corner_rf", database_mode=flags.database_mode)
        logging.info("Debug flag (%s) enabled, skip RF attenuator initialization", reason)
        return _DebugRFController()
    cfg = get_cfg()
    rf_solution = cfg['rf_solution']
    model = rf_solution['model']
    if model not in ['RADIORACK-4-220', 'RC4DAT-8G-95', 'RS232Board5', 'LDA-908V-8']:
        raise EnvironmentError("Doesn't support this model")
    if model == 'RS232Board5':
        rf_tool = rs()
    else:
        rf_ip = rf_solution[model]['ip_address']
        rf_tool = LabDeviceController(rf_ip)
        logging.info(f'rf_ip {rf_ip}')
    logging.info('Reset rf value')
    rf_tool.execute_rf_cmd(0)
    time.sleep(3)
    return rf_tool


def init_corner():
    """根据配置初始化转台"""
    flags = get_debug_flags()
    if flags.skip_corner_rf:
        reason = describe_debug_reason("skip_corner_rf", database_mode=flags.database_mode)
        logging.info("Debug flag (%s) enabled, skip corner initialization", reason)
        controller = _DebugCornerController()
        controller.set_turntable_zero()
        return controller
    cfg = get_cfg()
    turntable_cfg = _turntable_section_from_config(cfg)
    model = str(turntable_cfg.get(TURN_TABLE_FIELD_MODEL, TURN_TABLE_MODEL_RS232)).strip()
    corner_ip = ''
    if model == TURN_TABLE_MODEL_RS232:
        corner_tool = rs()
    else:
        corner_ip = str(turntable_cfg.get(TURN_TABLE_FIELD_IP_ADDRESS, "")).strip()
        if not corner_ip:
            raise EnvironmentError(
                "Turntable IP address is required when using network-controlled models"
            )
        corner_tool = LabDeviceController(corner_ip)
    logging.info(f'corner model {model} ip {corner_ip}')
    logging.info('Reset corner')
    corner_tool.set_turntable_zero()
    logging.info(corner_tool.get_turntanle_current_angle())
    time.sleep(3)
    return corner_tool


def init_router() -> Any:
    """根据配置返回路由实例"""
    flags = get_debug_flags()
    if flags.skip_router:
        reason = describe_debug_reason("skip_router", database_mode=flags.database_mode)
        return _DebugRouterController(reason)
    cfg = get_cfg()
    router = get_router(cfg['router']['name'])
    return router


def common_setup(router: Router, router_info: Router) -> bool:
    """通用的性能测试前置步骤"""
    logging.info("router setup start")

    pytest.dut.skip_tx = False
    pytest.dut.skip_rx = False

    flags = get_debug_flags()
    if flags.skip_router:
        reason = describe_debug_reason("skip_router", database_mode=flags.database_mode)
        logging.info("Debug flag (%s) enabled, skip router setup steps", reason)
        return True

    router.change_setting(router_info), "Can't set ap , pls check first"
git    band = "5G" if "2" in router_info.band else "2.4G"
    ssid = router_info.ssid + "_bat"
    router.change_setting(Router(band=band, ssid=ssid))
    if pytest.connect_type == 'Linux':
        if router_info.band == "2.4G":
            router.change_country("欧洲")
        else:
            router.change_country("美国")
        router.driver.quit()
    logging.info('router set done')
    cfg = load_config(refresh=True)
    rvr_tool = cfg['rvr']['tool']
    if rvr_tool == 'ixchariot':
        script = (
            'set script "$ixchariot_installation_dir/Scripts/High_Performance_Throughput.scr"\n'
            if '5' in router_info.band
            else 'set script "$ixchariot_installation_dir/Scripts/Throughput.scr"\n'
        )
        pytest.dut.ix.modify_tcl_script("set script ", script)
        pytest.dut.checkoutput(pytest.dut.IX_ENDPOINT_COMMAND)
        time.sleep(3)


def wait_connect(router_info: Router):
    third_party_cfg = get_cfg().get("connect_type", {}).get("third_party", {})
    flags = get_debug_flags()
    if flags.skip_router:
        reason = describe_debug_reason("skip_router", database_mode=flags.database_mode)
        logging.info(
            "Debug flag (%s) enabled, skip Wi-Fi reconnection workflow (router=%s)",
            reason,
            getattr(router_info, "ssid", "<unknown>"),
        )
        return True
    if third_party_cfg == 'true':
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
        logging.info(f'dut try to connect {router_info.ssid}')
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

        connect_status = pytest.dut.connect_wifi(
            router_info.ssid,
            password,
            security_token,
            hide=getattr(router_info, "hide_ssid", "") == '是',
        )

    logging.info(f'dut_ip:{pytest.dut.dut_ip}')
    logging.info(f'pc_ip:{pytest.dut.pc_ip}')
    logging.info('dut connected')
    return connect_status


@lru_cache(maxsize=1)
def get_rf_step_list():
    cfg = get_cfg()
    rf_solution = cfg.get('rf_solution', {}) if isinstance(cfg, dict) else {}
    raw_step = rf_solution.get('step') if isinstance(rf_solution, dict) else None
    return parse_rf_step_spec(raw_step)


@lru_cache(maxsize=1)
def get_corner_step_list():
    cfg = get_cfg()
    turntable_cfg = _turntable_section_from_config(cfg)
    raw_step = turntable_cfg.get(TURN_TABLE_FIELD_STEP, "")
    bounds = _parse_turntable_step_bounds(raw_step)
    if bounds is None:
        logging.warning("Turntable step configuration %r is invalid", raw_step)
        return []
    start, stop = bounds
    if start == stop:
        return [start]
    if start > stop:
        start, stop = stop, start
    return [i for i in range(start, stop)][::45]


def get_rvo_static_db_list():
    cfg = load_config(refresh=True)
    turntable_cfg = _turntable_section_from_config(cfg)
    raw_value = turntable_cfg.get(TURN_TABLE_FIELD_STATIC_DB, '')
    candidates = []

    if isinstance(raw_value, str):
        segments = [segment.strip() for segment in re.split(r'[,，]', raw_value)]
        candidates.extend(segment for segment in segments if segment)
    elif isinstance(raw_value, (list, tuple, set)):
        candidates.extend(raw_value)
    else:
        candidates.append(raw_value)

    parsed_values = []
    for item in candidates:
        parsed = _parse_optional_int(
            item,
            field_name=f'{TURN_TABLE_SECTION_KEY}.{TURN_TABLE_FIELD_STATIC_DB}',
            min_value=0,
            max_value=110,
        )
        if parsed is not None:
            parsed_values.append(parsed)

    return parsed_values if parsed_values else [None]


def get_rvo_target_rssi_list():
    cfg = load_config(refresh=True)
    turntable_cfg = _turntable_section_from_config(cfg)
    raw_value = turntable_cfg.get(TURN_TABLE_FIELD_TARGET_RSSI, '')
    candidates = []

    if isinstance(raw_value, str):
        segments = [segment.strip() for segment in re.split(r'[,，]', raw_value)]
        candidates.extend(segment for segment in segments if segment)
    elif isinstance(raw_value, (list, tuple, set)):
        candidates.extend(raw_value)
    else:
        candidates.append(raw_value)

    parsed_values = []
    for item in candidates:
        parsed = _parse_optional_int(
            item,
            field_name=f'{TURN_TABLE_SECTION_KEY}.{TURN_TABLE_FIELD_TARGET_RSSI}',
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
