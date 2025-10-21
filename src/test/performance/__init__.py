#!/usr/bin/env python
# encoding: utf-8
"""
通用性能测试工具
"""
import logging
import re
import time
from contextlib import contextmanager
from functools import lru_cache
from typing import Any, Optional

import pytest

from src.tools.config_loader import load_config
from src.tools.router_tool.Router import Router
from src.tools.router_tool.router_factory import get_router
from src.tools.connect_tool.lab_device_controller import LabDeviceController
from src.tools.rs_test import rs
from src.util.constants import (
    DEFAULT_RF_STEP_SPEC,
    IDENTIFIER_SANITIZE_PATTERN,
    RF_STEP_SPLIT_PATTERN,
    is_database_debug_enabled,
)


_SCENARIO_KEY_FIELDS = (
    ("band", "band"),
    ("ssid", "ssid"),
    ("mode", "wireless_mode"),
    ("channel", "channel"),
    ("bandwidth", "bandwidth"),
    ("security", "security_mode"),
)


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
    """No-op RF controller used when database debug mode is enabled."""

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
    """No-op corner controller used when database debug mode is enabled."""

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
    """Lightweight router placeholder used in database debug mode."""

    name = "debug-router"
    CHANNEL_2: tuple = ()
    CHANNEL_5: tuple = ()
    BANDWIDTH_2: tuple = ()
    BANDWIDTH_5: tuple = ()
    AUTHENTICATION_METHOD = ()
    AUTHENTICATION_METHOD_LEGCY = ()

    def __init__(self) -> None:
        logging.info("Database debug mode enabled, skip router controller instantiation")

    def __getattr__(self, item: str):
        raise AttributeError(f"_DebugRouterController has no attribute {item!r}")


@lru_cache(maxsize=1)
def get_cfg() -> Any:
    """返回最新的配置"""
    return load_config(refresh=True)


def init_rf():
    """根据配置初始化射频衰减器"""
    if is_database_debug_enabled():
        logging.info("Database debug mode enabled, skip RF attenuator initialization")
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
    if is_database_debug_enabled():
        logging.info("Database debug mode enabled, skip corner initialization")
        controller = _DebugCornerController()
        controller.set_turntable_zero()
        return controller
    cfg = get_cfg()
    corner_ip = cfg['corner_angle']['ip_address']
    corner_tool = rs() if corner_ip == '192.168.5.11' else LabDeviceController(corner_ip)
    logging.info(f'corner_ip {corner_ip}')
    logging.info('Reset corner')
    corner_tool.set_turntable_zero()
    logging.info(corner_tool.get_turntanle_current_angle())
    time.sleep(3)
    return corner_tool


def init_router() -> Any:
    """根据配置返回路由实例"""
    if is_database_debug_enabled():
        return _DebugRouterController()
    cfg = get_cfg()
    router = get_router(cfg['router']['name'])
    return router


def common_setup(router: Router, router_info: Router) -> bool:
    """通用的性能测试前置步骤"""
    logging.info("router setup start")

    pytest.dut.skip_tx = False
    pytest.dut.skip_rx = False

    if is_database_debug_enabled():
        logging.info("Database debug mode enabled, skip router setup steps")
        return True

    router.change_setting(router_info), "Can't set ap , pls check first"
    band = '5G' if '2' in router_info.band else '2.4G'
    ssid = router_info.ssid + "_bat"
    router.change_setting(Router(band=band, ssid=ssid))
    if pytest.connect_type == 'telnet':
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
    third_party_cfg = get_cfg().get("connect_type", {}).get("third_party", {}).get("enabled", {})
    if is_database_debug_enabled():
        logging.info(
            "Database debug mode enabled, skip Wi-Fi reconnection workflow (router=%s)",
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
        if pytest.connect_type == 'telnet':
            connect_status = True
            pytest.dut.wait_reconnect_sync(timeout=90)
        else:
            connect_status = False
            for _ in range(3):
                try:
                    wpa_type = 'wpa3' if 'WPA3' in router_info.security_mode else 'wpa2'
                    if router_info.security_mode.lower() == "open system":
                        logging.info('no passwd')
                        cmd = pytest.dut.CMD_WIFI_CONNECT.format(router_info.ssid, "open", "")
                    else:
                        cmd = pytest.dut.CMD_WIFI_CONNECT.format(
                            router_info.ssid, wpa_type, router_info.password
                        )
                    if router_info.hide_ssid == '是':
                        cmd += pytest.dut.CMD_WIFI_HIDE
                    pytest.dut.checkoutput(cmd)
                    time.sleep(5)
                    if pytest.dut.wait_for_wifi_address(
                            cmd=cmd,
                            target=re.findall(r'(\d+\.\d+\.\d+\.)', pytest.dut.pc_ip)[0],
                    ):
                        connect_status = True
                        break
                except Exception as e:
                    logging.info(e)
                    connect_status = False

    logging.info(f'dut_ip:{pytest.dut.dut_ip}')
    logging.info(f'pc_ip:{pytest.dut.pc_ip}')
    logging.info('dut connected')
    return connect_status


def _parse_optional_int(
        value: Any,
        *,
        field_name: str = "value",
        min_value: Optional[int] = None,
        max_value: Optional[int] = None,
) -> Optional[int]:
    """将配置中的数值安全地转换为 int。"""

    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None

    if isinstance(value, (list, tuple, set)):
        for item in value:
            parsed = _parse_optional_int(
                item,
                field_name=field_name,
                min_value=min_value,
                max_value=max_value,
            )
            if parsed is not None:
                return parsed
        return None

    if value is None:
        return None

    try:
        number = int(float(value))
    except (TypeError, ValueError):
        logging.warning("Invalid %s: %r", field_name, value)
        return None

    if min_value is not None and number < min_value:
        logging.warning(
            "%s %s lower than minimum %s, clamped.", field_name, number, min_value
        )
        number = min_value
    if max_value is not None and number > max_value:
        logging.warning(
            "%s %s higher than maximum %s, clamped.", field_name, number, max_value
        )
        number = max_value
    return number



def _is_scalar(value: Any) -> bool:
    return not isinstance(value, (list, tuple, set, dict))


def _collect_rf_step_segments(raw_step: Any) -> list[str]:
    segments: list[str] = []

    def _collect(value: Any) -> None:
        if value is None:
            return
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return
            normalized = (
                text.replace("；", ";")
                .replace("，", ",")
                .replace("：", ":")
            )
            for part in RF_STEP_SPLIT_PATTERN.split(normalized):
                part = part.strip()
                if part:
                    segments.append(part)
            return
        if isinstance(value, (list, tuple, set)):
            items = list(value)
            if len(items) == 2 and all(_is_scalar(i) for i in items):
                start = str(items[0]).strip()
                stop = str(items[1]).strip()
                if start and stop:
                    segments.append(f"{start},{stop}")
                return
            for item in items:
                _collect(item)
            return
        text = str(value).strip()
        if text:
            segments.append(text)

    _collect(raw_step)
    return segments


def _expand_rf_step_segments(segment_specs: list[str]) -> list[int]:
    values: list[int] = []
    seen: set[int] = set()

    for original in segment_specs:
        segment = original.strip()
        if not segment:
            continue

        normalized = (
            segment.replace("；", ";")
            .replace("，", ",")
            .replace("：", ":")
        )
        include_stop = ":" in normalized
        if include_stop:
            range_part, step_part = normalized.split(":", 1)
        else:
            range_part, step_part = normalized, None

        tokens = [tok for tok in re.split(r"[\s,]+", range_part.strip()) if tok]
        if not tokens:
            logging.warning("Empty rf_solution.step segment ignored: %r", original)
            continue
        if len(tokens) > 2:
            logging.warning(
                "rf_solution.step segment %r has too many bounds, only the first two values are used.",
                original,
            )

        start_token = tokens[0]
        stop_token = tokens[1] if len(tokens) >= 2 else tokens[0]

        start = _parse_optional_int(
            start_token,
            field_name="rf_solution.step.start",
        )
        stop = _parse_optional_int(
            stop_token,
            field_name="rf_solution.step.stop",
        )

        if start is None:
            continue
        if stop is None:
            stop = start

        if step_part is not None:
            step = _parse_optional_int(
                step_part,
                field_name="rf_solution.step.step",
                min_value=1,
            )
            if step is None:
                step = 1
        else:
            step = 1

        if step <= 0:
            logging.warning("rf_solution.step step %s <= 0, fallback to 1", step)
            step = 1

        if stop < start:
            logging.warning(
                "rf_solution.step stop %s lower than start %s, swapping.",
                stop,
                start,
            )
            start, stop = stop, start

        exclusive = step_part is None and len(tokens) >= 2 and start != stop
        current = start
        while current <= stop:
            if exclusive and current == stop:
                break
            if current not in seen:
                values.append(current)
                seen.add(current)
            current += step

    return values


def parse_rf_step_spec(raw_step: Any) -> list[int]:
    segments = _collect_rf_step_segments(raw_step)
    values = _expand_rf_step_segments(segments)
    if values:
        return values
    if raw_step not in (None, "", DEFAULT_RF_STEP_SPEC):
        logging.warning(
            "rf_solution.step is empty or invalid (%r), fallback to default %s",
            raw_step,
            DEFAULT_RF_STEP_SPEC,
        )
    default_values = _expand_rf_step_segments(_collect_rf_step_segments(DEFAULT_RF_STEP_SPEC))
    return default_values if default_values else [0]


@lru_cache(maxsize=1)
def get_rf_step_list():
    cfg = get_cfg()
    rf_solution = cfg.get('rf_solution', {}) if isinstance(cfg, dict) else {}
    raw_step = rf_solution.get('step') if isinstance(rf_solution, dict) else None
    return parse_rf_step_spec(raw_step)


@lru_cache(maxsize=1)
def get_corner_step_list():
    cfg = get_cfg()
    corner_step = cfg['corner_angle']['step']
    return [i for i in range(*corner_step)][::45]


def get_rvo_static_db_list():
    cfg = load_config(refresh=True)
    raw_value = cfg.get('corner_angle', {}).get('static_db', '')
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
            field_name='corner_angle.static_db',
            min_value=0,
            max_value=110,
        )
        if parsed is not None:
            parsed_values.append(parsed)

    return parsed_values if parsed_values else [None]


def get_rvo_target_rssi_list():
    cfg = load_config(refresh=True)
    raw_value = cfg.get('corner_angle', {}).get('target_rssi', '')
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
            field_name='corner_angle.target_rssi',
        )
        if parsed is not None:
            parsed_values.append(parsed)

    return parsed_values if parsed_values else [None]
