import logging
import os
import time
from typing import Mapping
import sys

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from src.dut_control.roku_ctrl import roku_ctrl
from src.tools.connect_tool.telnet_tool import telnet_tool
from src.util.constants import load_config


def _create_device_connection(device_info: dict):
    control_type = device_info.get("control_type", "").lower()
    ip = device_info.get("ip")
    logging.info(f"Establishing device connection (type: {control_type})")
    if control_type == "roku":
        return roku_ctrl(ip)
    elif control_type == "linux":
        return telnet_tool(ip)
    else:
        raise ValueError(f"Unsupported control_type: {control_type}")


def _reboot_dut(dut, control_type: str):
    logging.info("Sending soft reboot command")
    output = dut.checkoutput('reboot')
    logging.info(f"Reboot shell output: {output}")


def _check_network_status(dut, router_ip: str):
    logging.info("Executing ifconfig to check network interface")
    if_output = dut.checkoutput("ifconfig")
    logging.info(f"ifconfig output:\n{if_output}")
    if "eth0" not in if_output or "inet" not in if_output:
        raise AssertionError("eth0 interface or IP address not found")
    logging.info(f"Pinging router ({router_ip}) to verify connectivity")
    ping_output = dut.checkoutput(f"ping -c 4 {router_ip}")
    logging.info(f"Ping result:\n{ping_output}")
    if "0% packet loss" not in ping_output and "4 received" not in ping_output:
        raise AssertionError("Failed to ping router")


def test_soft_reboot_str():
    # === 1. 加载全局配置（来自 UI）===
    base_config = load_config(refresh=True)
    logging.info(f"Loaded base_config keys: {list(base_config.keys())}")

    # === 2. 提取测试参数 ===
    basic_test_duration = base_config.get("duration_control", {})
    loop_count = int(basic_test_duration.get("loop", "1"))

    basic_router = base_config.get("router", {})
    router_ip = basic_router.get("address") or basic_router.get("ip")
    ssid_24g = basic_router.get("24g_ssid")
    ssid_5g = basic_router.get("5g_ssid")

    # === 3. 构造 device_info 从 connect_type ===
    connect_type_cfg = base_config.get("connect_type", {})
    ctrl_type_raw = connect_type_cfg.get("type", "Unknown")
    control_type = ctrl_type_raw.lower()

    device_info = {"control_type": control_type}
    if control_type == "linux":
        linux_cfg = connect_type_cfg.get("Linux", {})
        device_info["ip"] = linux_cfg.get("ip", "")
        device_info["wildcard"] = linux_cfg.get("wildcard", "None")
    elif control_type == "android":
        android_cfg = connect_type_cfg.get("Android", {})
        device_info["device"] = android_cfg.get("device", "Unknown")

    # === 4. 参数校验 ===
    if not all([router_ip, ssid_24g, ssid_5g]):
        raise RuntimeError("Basic Router configuration incomplete")

    if control_type not in ("linux", "roku"):
        raise RuntimeError(f"Unsupported control_type: {control_type}")

    if not device_info.get("ip"):
        raise RuntimeError("Device IP is required for Linux-type DUT")

    # === 5. 开始测试 ===
    logging.info(f"Starting Soft Reboot Stability Test - {loop_count} Loops")
    logging.info(f"Router: {router_ip}, DUT IP: {device_info['ip']}")

    dut = None
    total_failures = 0

    try:
        logging.info("Initializing device connection")
        dut = _create_device_connection(device_info)

        for current_loop in range(1, loop_count + 1):
            logging.info(f"\n===== Starting Loop {current_loop}/{loop_count} =====")
            try:
                _reboot_dut(dut, control_type)
                time.sleep(60)

                # Reconnect after reboot
                if hasattr(dut, 'close'):
                    dut.close()
                dut = _create_device_connection(device_info)
                time.sleep(5)

                _check_network_status(dut, router_ip)
                time.sleep(60)

                os.environ["SOFT_REBOOT_COMPLETED_LOOPS"] = str(current_loop)
                logging.info(f"✅ Loop {current_loop} completed successfully")

            except Exception as e:
                total_failures += 1
                logging.error(f"Loop {current_loop} failed: {e}", exc_info=True)
                # Recovery attempt
                try:
                    if dut and hasattr(dut, 'close'):
                        dut.close()
                    dut = _create_device_connection(device_info)
                except Exception:
                    pass

        summary = f"Total loops: {loop_count}\nTotal failures: {total_failures}"
        logging.info(f"\n===== Test Completed =====\n{summary}")
        if total_failures > 0:
            raise RuntimeError(f"Test completed with {total_failures} failure(s)")

    finally:
        if dut and hasattr(dut, 'close'):
            dut.close()