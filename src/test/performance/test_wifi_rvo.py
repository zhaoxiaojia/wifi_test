#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""RVO performance test flow with streamlined fixture handling."""

import logging
import time
from collections import namedtuple
from typing import Optional, Tuple

import pytest
from src.tools.router_tool.Router import router_str
from src.util.constants import (
    TURN_TABLE_FIELD_STATIC_DB,
    TURN_TABLE_FIELD_TARGET_RSSI,
    TURN_TABLE_SECTION_KEY,
    get_debug_flags,
)

from src.test import get_testdata
from src.test.pyqt_log import log_fixture_params, update_fixture_params
from src.test.performance import (
    common_setup,
    describe_debug_reason,
    ensure_performance_result,
    get_corner_step_list,
    get_rf_step_list,  # 确保已导入
    # get_rvo_static_db_list, # 不再需要这个函数
    get_rvo_target_rssi_list,
    init_corner,
    init_rf,
    init_router,
    scenario_group,
    wait_connect,
)


def _safe_int(value) -> Optional[int]:
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

def _clamp_db(value: Optional[int]) -> int:
    parsed = _safe_int(value)
    if parsed is None:
        return 0
    return max(0, min(110, parsed))


def _initial_step_size() -> int:
    try:
        # 注意：这里也需要根据频段获取step list，但为了简化，我们先用全局的
        candidates = sorted(set(get_rf_step_list()))
    except Exception as exc:
        logging.warning('Failed to load RF step list: %s; fallback to step=1', exc)
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


def _resolve_target_rssi(base_db: Optional[int], rf_tool) -> Tuple[int, int, int]:
    max_retries = 1
    applied_db = 0  # 默认值
    for attempt in range(max_retries + 1):
        try:
            current_attenuation = rf_tool.get_rf_current_value()
            logging.debug(f"[DEBUG_RF] _resolve_target_rssi attempt {attempt + 1}, raw value: {current_attenuation}")
            # 尝试解析值，假设所有通道值一致，取第一个
            if isinstance(current_attenuation, list) and len(current_attenuation) > 0:
                parsed_db = _clamp_db(_safe_int(current_attenuation[0]))
                if parsed_db > 0 or attempt == max_retries:  # 如果读到有效值或已是最后一次尝试
                    applied_db = parsed_db
                    break
            else:
                # 如果返回的不是列表，尝试直接解析
                parsed_db = _clamp_db(_safe_int(current_attenuation))
                if parsed_db > 0 or attempt == max_retries:
                    applied_db = parsed_db
                    break

            logging.warning(
                f"_resolve_target_rssi got unexpected value {current_attenuation} on attempt {attempt + 1}, retrying...")
            time.sleep(1.0)

        except Exception as exc:
            logging.warning('Failed to get rf current value on attempt %s: %s; will retry.', attempt + 1, exc)
            if attempt < max_retries:
                time.sleep(1.0)
            else:
                # 所有重试失败，回退到 base_db 或 0
                applied_db = _clamp_db(base_db if base_db is not None else 0)

    step = _initial_step_size()
    current_rssi = pytest.dut.get_rssi()
    return current_rssi, applied_db, step


def _step_att_db(applied_db: int, diff: int, attempt: int, target_rssi: int, rf_tool) -> Tuple[int, bool]:
    """
    Adjust attenuation with a dynamic step size based on the current RSSI difference.

    Args:
        applied_db: The currently applied attenuation in dB.
        diff: The difference between current RSSI and target RSSI (current - target).
        attempt: The current adjustment attempt number.
        target_rssi: The target RSSI value in dBm.
        rf_tool: The RF tool instance for sending commands.

    Returns:
        A tuple of (new_applied_db, command_was_successful).
    """
    # --- 新增：动态计算步长 ---
    if diff > 6:
        step = 5
    elif diff > 3:
        step = 2
    else:
        step = 1
    # --- 动态步长计算结束 ---

    direction = 1 if diff > 0 else -1
    next_db = max(0, min(110, applied_db + direction * step))
    if next_db == applied_db:
        return applied_db, False

    logging.info(
        'Adjust attenuation to %s dB (attempt %s, step=%s dB) for RSSI diff=%s dB (target %s dBm)',
        next_db,
        attempt + 1,
        step,  # 记录使用的步长
        diff,
        target_rssi,
    )

    # --- 保留原有的命令执行和重试逻辑 ---
    cmd_success = False
    max_cmd_retries = 1
    for cmd_attempt in range(max_cmd_retries + 1):
        try:
            rf_tool.execute_rf_cmd(next_db)
            # 短暂等待并验证
            time.sleep(0.5)
            verified_value = rf_tool.get_rf_current_value()
            if (isinstance(verified_value, list) and len(verified_value) > 0) or verified_value is True:
                verified_db = _safe_int(verified_value[0])
                if verified_db == next_db:
                    cmd_success = True
                    break
        except Exception as exc:
            logging.warning('Failed to execute/verify rf command %s on cmd attempt %s: %s', next_db, cmd_attempt + 1,
                            exc)

        if not cmd_success and cmd_attempt < max_cmd_retries:
            time.sleep(1.0)

    if not cmd_success:
        logging.error("All attempts to set attenuation to %s dB failed.", next_db)
        return applied_db, False

    return next_db, True


def _record_adjustment(next_db: int, target_rssi: int) -> Tuple[int, Optional[int]]:
    time.sleep(3)
    measured = pytest.dut.get_rssi()
    if measured == -1:
        return measured, None
    new_diff = measured - target_rssi
    logging.info(
        'Measured RSSI %s dBm (diff %s dB) after attenuation %s dB',
        measured,
        new_diff,
        next_db,
    )
    return measured, new_diff

def _adjust_rssi_to_target(target_rssi: int, base_db: Optional[int], rf_tool) -> Tuple[int, Optional[int]]:
    flags = get_debug_flags()
    if flags.skip_corner_rf:
        simulated_rssi = pytest.dut.get_rssi()
        reason = describe_debug_reason("skip_corner_rf", database_mode=flags.database_mode)
        logging.info(
            "Debug flag (%s) enabled, skip RSSI adjustment and return simulated RSSI %s dBm",
            reason,
            simulated_rssi,
        )
        try:
            current_att = rf_tool.get_rf_current_value()
            applied_db = _clamp_db(_safe_int(current_att))
        except:
            applied_db = _clamp_db(base_db if base_db is not None else 0)
        return simulated_rssi, applied_db

    current_rssi, applied_db, _ = _resolve_target_rssi(base_db, rf_tool)
    logging.info(
        'Start adjusting attenuation to %s dB for target RSSI %s dBm',
        applied_db,
        target_rssi,
    )
    if current_rssi == -1:
        return current_rssi, applied_db

    max_iterations = 30
    for attempt in range(max_iterations):
        diff = current_rssi - target_rssi
        logging.info('current rssi %s target rssi %s', current_rssi, target_rssi)
        if diff == 0:
            break

        next_db, changed = _step_att_db(applied_db, diff, attempt, target_rssi, rf_tool)
        if not changed:
            logging.info(
                'Attenuation locked at %s dB while RSSI diff=%s dB; boundary reached.',
                applied_db,
                diff,
            )
            break

        measured, new_diff = _record_adjustment(next_db, target_rssi)
        applied_db = next_db
        current_rssi = measured

        if measured == -1:
            break
        if new_diff == 0:
            break

    logging.info('Final RSSI %s dBm with attenuation %s dB', current_rssi, applied_db)

    try:
        final_attenuation = rf_tool.get_rf_current_value()
        logging.info('Final RSSI %s dBm with attenuation %s dB (RF tool reports: %s)', current_rssi, applied_db,
                     final_attenuation)
    except Exception as e:
        logging.warning('Could not read final attenuation from RF tool: %s', e)
        logging.info('Final RSSI %s dBm with attenuation %s dB', current_rssi, applied_db)
    return current_rssi, applied_db


RVOProfile = namedtuple("RVOProfile", "mode value")
RVOCase = namedtuple("RVOCase", "router_info profile corner")

_MODE_DEFAULT = "default"
_MODE_STATIC = "static"
_MODE_TARGET = "target"


def _profile_id(profile: RVOProfile) -> str:
    if profile.mode == _MODE_STATIC:
        return f'static-{profile.value}'
    if profile.mode == _MODE_TARGET:
        return f'target-{profile.value}'
    return _MODE_DEFAULT


def _case_id(case: RVOCase) -> str:
    router_id = router_str(case.router_info)
    return f'{router_id}|{_profile_id(case.profile)}|corner-{case.corner}'


def _get_rvo_profiles_for_band(current_band: str) -> list[RVOProfile]:
    """Get RVO profiles for a specific band."""
    logging.info(f"[RVO] Determining profiles for band: {current_band}")

    VALID_TARGET_RSSI_MIN = -90
    VALID_TARGET_RSSI_MAX = -11

    target_values = [value for value in get_rvo_target_rssi_list(current_band) if value is not None]
    if target_values:
        logging.info(f"[RVO] Found target RSSI values: {target_values}. Validating them.")
        valid_targets = []
        invalid_targets = []
        for val in target_values:
            if VALID_TARGET_RSSI_MIN <= val <= VALID_TARGET_RSSI_MAX:
                valid_targets.append(val)
            else:
                invalid_targets.append(val)

        if invalid_targets:
            logging.warning(
                f"[RVO] Invalid target RSSI values found (must be between {VALID_TARGET_RSSI_MIN} and {VALID_TARGET_RSSI_MAX}): {invalid_targets}")

        if valid_targets:
            logging.info(f"[RVO] Using valid target RSSI values: {valid_targets}.")
            return [RVOProfile(_MODE_TARGET, value) for value in valid_targets]
        else:
            logging.warning("[RVO] No valid target RSSI values found.")

    static_values_from_rf = get_rf_step_list(band=current_band)
    static_values = [v for v in static_values_from_rf if v is not None]

    if static_values:
        logging.info(f"[RVO] Found static DB values from RF step list for {current_band}: {static_values}")
        return [RVOProfile(_MODE_STATIC, value) for value in static_values]
    else:
        logging.warning(f"[RVO] No static DB values found for band {current_band}. Falling back to default.")
        return [RVOProfile(_MODE_DEFAULT, None)]


def _build_rvo_cases_for_router(router_info) -> list[RVOCase]:
    """Build RVO cases for a single router."""
    current_band = getattr(router_info, 'band', '2.4G')
    profiles = _get_rvo_profiles_for_band(current_band)
    corners = get_corner_step_list() or [0]
    return [RVOCase(router_info, profile, corner) for profile in profiles for corner in corners]


# class NoOpCornerTool:
#     def __getattr__(self, name):
#         """任何方法调用都返回一个什么都不做的函数"""
#         return lambda *args, **kwargs: None


# Generator RVO test case ---
router = init_router()
_test_data = get_testdata(router)

ALL_RVO_CASES = []
for router_info in _test_data:
    ALL_RVO_CASES.extend(_build_rvo_cases_for_router(router_info))

ALL_RVO_CASE_IDS = [_case_id(case) for case in ALL_RVO_CASES]
logging.info(f"[MODULE TOP LEVEL] Generated a total of {len(ALL_RVO_CASES)} RVO cases.")

#corner_tool = NoOpCornerTool()
corner_tool = init_corner()


def _apply_static_attenuation(static_db: Optional[int], rf_tool) -> Tuple[int, Optional[int]]:
    if static_db is None:
        measured = pytest.dut.get_rssi()
        return measured, None
    logging.info('Set static attenuation to %s dB before RVO test.', static_db)
    flags = get_debug_flags()
    if flags.skip_corner_rf:
        reason = describe_debug_reason("skip_corner_rf", database_mode=flags.database_mode)
        logging.info(
            'Debug flag (%s) enabled, skip applying static attenuation %s dB.',
            reason,
            static_db,
        )
        measured = pytest.dut.get_rssi()
        return measured, static_db

    max_retries = 1  # 失败后重试2次
    for attempt in range(max_retries + 1):  # +1 是为了包含初始尝试
        try:
            # 执行设置命令
            rf_tool.execute_rf_cmd(static_db)

            # 获取当前值
            current_value = rf_tool.get_rf_current_value()
            logging.info(
                f"[DEBUG_RF] Attempt {attempt + 1}: setup_attenuation db_set={static_db} current={current_value}")

            # 检查读取到的值是否符合预期
            # 注意: current_value 是一个列表 [ch1, ch2, ch3, ch4]
            # 我们假设所有通道都应该被设置为 static_db
            if (isinstance(current_value, list) and all(att == static_db for att in current_value)) or current_value:
                logging.info("Current attenuation verified as %s dB on all channels.", static_db)
                break  # 验证成功，跳出循环
            else:
                logging.warning(
                    "Verification failed on attempt %s. Expected all channels to be %s dB, but got %s.",
                    attempt + 1, static_db, current_value
                )
                if attempt < max_retries:  # 不是最后一次尝试
                    time.sleep(1.0)  # 等待1秒再重试
                    continue
                else:
                    # 最后一次尝试也失败了，记录警告但继续流程
                    logging.error(
                        "All %s attempts to set and verify attenuation failed. Proceeding with potentially incorrect value: %s.",
                        max_retries + 1, current_value
                    )
        except Exception as exc:
            logging.exception("Exception occurred while setting/verifying attenuation on attempt %s: %s",
                              attempt + 1, exc)
            if attempt < max_retries:
                time.sleep(1.0)
                continue
            else:
                logging.error("All attempts failed due to exceptions. Proceeding.")
                # 如果发生异常，current_value 可能未定义，这里需要处理
                # 为了保持函数返回值一致，我们假设设置失败，返回 static_db 作为名义上的设置值
                # 但实际硬件状态未知
                current_value = [0, 0, 0, 0]  # 或者根据实际情况处理
    measured = pytest.dut.get_rssi()
    return measured, static_db


def _apply_profile(profile: RVOProfile, rf_tool) -> Tuple[int, Optional[int]]:
    if profile.mode == _MODE_STATIC:
        return _apply_static_attenuation(profile.value, rf_tool)
    if profile.mode == _MODE_TARGET:
        return _adjust_rssi_to_target(profile.value, None, rf_tool)
    measured = pytest.dut.get_rssi()
    return measured, None


@pytest.fixture(scope='session', params=_test_data, ids=[router_str(i) for i in _test_data])
@log_fixture_params()
def setup_router(request):
    router_info = request.param
    common_setup(router, router_info)
    try:
        pre_connect_rf_tool = init_rf()
        # 尝试将衰减器设置为0，并增加简单的重试
        for _ in range(2):
            pre_connect_rf_tool.execute_rf_cmd(0)
            time.sleep(0.5)
            current_val = pre_connect_rf_tool.get_rf_current_value()
            if (isinstance(current_val, list) and all(att == 0 for att in current_val)) or current_val:
                logging.info("[SETUP_ROUTER] Successfully set attenuation to 0 dB before connecting.")
                break
            time.sleep(1.0)
        else:
            logging.warning("[SETUP_ROUTER] Could not verify attenuation is 0 dB, but proceeding with connection.")
    except Exception as e:
        logging.error(f"[SETUP_ROUTER] Failed to reset attenuation before connect: {e}. Proceeding anyway.")

    connect_status = wait_connect(router_info)
    yield connect_status, router_info
    pytest.dut.kill_iperf()
    corner_tool.set_turntable_zero()


# --- setup_rvo_case 直接使用顶层生成的 ALL_RVO_CASES ---
@pytest.fixture(scope='function', params=ALL_RVO_CASES, ids=ALL_RVO_CASE_IDS)
@log_fixture_params()
def setup_rvo_case(request, setup_router):
    # 从参数中获取完整的 case 信息
    case: RVOCase = request.param
    expected_router_info = case.router_info
    # 验证当前 session 的 router_info 是否与 case 匹配
    _, actual_router_info = setup_router
    if router_str(expected_router_info) != router_str(actual_router_info):
        raise RuntimeError(f"Router mismatch! Expected {expected_router_info}, got {actual_router_info}")

    profile = case.profile
    corner_angle = case.corner

    # --- 关键修改：在 fixture 内部初始化 rf_tool ---
    local_rf_tool = init_rf()

    corner_tool.execute_turntable_cmd('rt', angle=corner_angle)
    corner_tool.get_turntanle_current_angle()
    measured_rssi, attenuation_db = _apply_profile(profile, local_rf_tool)

    try:
        yield setup_router[0], expected_router_info, corner_angle, attenuation_db, measured_rssi, profile, local_rf_tool
    finally:
        pytest.dut.kill_iperf()


def test_rvo(request, setup_rvo_case, performance_sync_manager):
    connect_status, router_info, corner_angle, attenuation_db, rssi_num, profile, rf_tool = setup_rvo_case
    test_result = ensure_performance_result()
    if not hasattr(request.node, 'extra'):
        request.node.extra = {}

        # 清空或覆盖旧值（防止重复）
    request.node.extra.update({
        'corner': corner_angle,
        'mode': profile.mode,
        'value': profile.value,
        'attenuation_db': attenuation_db,
        'rssi': rssi_num,
        'band': router_info.band,
        'channel': getattr(router_info, 'channel', '1'),
        'wireless_mode': router_info.wireless_mode,
        'bandwidth': router_info.bandwidth,
    })

    with scenario_group(router_info):
        test_result.ensure_log_file_prefix("RVO")
        if not connect_status:
            logging.info("Can't connect wifi ,input 0")
            return

        logging.info('RVO profile %s', _profile_id(profile))
        logging.info('corner angle set to %s', corner_angle)
        logging.info('start test iperf tx %s rx %s', router_info.tx, router_info.rx)

        # --- 新增：构建基础日志消息 ---
        band = router_info.band
        mode = router_info.wireless_mode
        bandwidth = router_info.bandwidth
        channel = getattr(router_info, 'channel', '1')

        # 推导 phy_mode
        if '2.4G' in band:
            band_name = '2G'
            if '11n' in mode:
                phy_mode = 'HT20' if '20M' in bandwidth else 'HT40'
            else:  # Assume 11ax or others
                phy_mode = 'HE20' if '20M' in bandwidth else 'HE40'
        elif '5G' in band:
            band_name = band
            if '11ac' in mode:
                phy_mode = 'VHT80'
            elif '11ax' in mode:
                phy_mode = 'HE80'
            else:
                phy_mode = 'HE80'
        else:
            phy_mode = 'UNKNOWN'

        if int(channel) <= 6:
            channel_name = f"{channel}l"
        elif int(channel) <= 13:
            channel_name = f"{channel}u"
        else:
            channel_name = channel

        db_for_log = str(attenuation_db) if attenuation_db is not None else '0'
        #new_log_message = f"{band}_{phy_mode}_CH{channel}_{corner_angle}°_{db_for_log}db"
        new_log_message = f"{band_name}_{phy_mode}_CH{channel_name}_RX_Angle:{corner_angle} Att:{db_for_log}db"
        # --- 新增部分结束 ---

        test_result.set_active_profile(profile.mode, profile.value)
        try:
            if int(router_info.tx):
                # --- 新增：TX 日志 ---
                #tx_log_message = f"{new_log_message}_TX"
                tx_log_message = f"{new_log_message.replace('_RX', '_TX')}"
                logging.info("Starting RVO test %s", tx_log_message)
                # --- 新增部分结束 ---
                logging.info('rssi : %s', rssi_num)
                pytest.dut.get_tx_rate(
                    router_info,
                    'TCP',
                    corner_tool=corner_tool,
                    db_set=attenuation_db if attenuation_db is not None else 0,
                )
            if int(router_info.rx):
                # --- 新增：RX 日志 ---
                rx_log_message = new_log_message
                logging.info("Starting RVO test %s", rx_log_message)
                # --- 新增部分结束 ---
                logging.info('rssi : %s', rssi_num)
                pytest.dut.get_rx_rate(
                    router_info,
                    'TCP',
                    corner_tool=corner_tool,
                    db_set=attenuation_db if attenuation_db is not None else 0,
                )
        finally:
            test_result.clear_active_profile()

    performance_sync_manager(
        "RVO",
        test_result.log_file,
        message="RVO data rows stored in database",
    )