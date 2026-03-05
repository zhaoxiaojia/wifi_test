import logging
import os
import sys
import time
from typing import Dict, Any

import allure  # ← Allure 核心模块

# 添加项目根路径（兼容 PyInstaller 打包）
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from src.tools.connect_tool.transports.telnet_tool import telnet_tool
from src.util.constants import load_config


@allure.step("创建 DUT 连接 [类型: {control_type}, IP: {ip}]")
def _create_device_connection(control_type: str, ip: str):
    """建立 Telnet 连接到 DUT"""
    logging.info(f"Establishing {control_type} connection to {ip}")
    if control_type in ("roku", "linux"):
        return telnet_tool(ip)
    else:
        raise ValueError(f"Unsupported control_type: {control_type}")


@allure.step("发送软重启命令")
def _send_reboot_command(dut) -> str:
    """向 DUT 发送 reboot 命令"""
    output = dut.checkoutput('reboot')
    logging.info(f"Reboot command output:\n{output}")
    return output


@allure.step("验证网络连通性 [路由器 IP: {router_ip}]")
def _verify_network_connectivity(dut, router_ip: str):
    """检查 eth0 是否有 IP，并 ping 路由器"""
    # 检查接口
    ifconfig_output = dut.checkoutput("ifconfig")
    logging.info(f"ifconfig output:\n{ifconfig_output}")

    if "eth0" not in ifconfig_output or "inet " not in ifconfig_output:
        raise AssertionError("eth0 interface or IP address missing")

    # Ping 路由器
    ping_output = dut.checkoutput(f"ping -c 4 {router_ip}")
    logging.info(f"Ping result:\n{ping_output}")

    if "0% packet loss" not in ping_output and "4 received" not in ping_output:
        raise AssertionError("Ping to router failed")


@allure.title("Wi-Fi Check Wi-Fi Status")
@allure.description("Check Wi-Fi Status after Reboot")
def test_check_wifi_status():
    """
    主测试用例：软重启 + 网络验证
    """
    # === 1. 加载配置 ===
    base_config: Dict[str, Any] = load_config(refresh=True)
    logging.info(f"Loaded config keys: {list(base_config.keys())}")

    # === 2. 提取参数 ===
    duration_cfg = base_config.get("duration_control", {})
    loop_count = int(duration_cfg.get("loop", "1") or "1")  # 防空字符串

    router_cfg = base_config.get("router", {})
    router_ip = router_cfg.get("address") or router_cfg.get("ip")
    ssid_24g = router_cfg.get("24g_ssid")
    ssid_5g = router_cfg.get("5g_ssid")

    connect_cfg = base_config.get("connect_type", {})
    control_type_raw = connect_cfg.get("type", "Unknown")
    control_type = control_type_raw.lower()

    # 构造 device_info
    if control_type == "linux":
        linux_cfg = connect_cfg.get("Linux", {})
        dut_ip = linux_cfg.get("ip", "")
    elif control_type == "roku":
        roku_cfg = connect_cfg.get("Roku", {})
        dut_ip = roku_cfg.get("ip", "")
    else:
        raise RuntimeError(f"Unsupported DUT type: {control_type}")

    # === 3. 参数校验 ===
    if not all([router_ip, ssid_24g, ssid_5g, dut_ip]):
        missing = [k for k, v in {
            "router_ip": router_ip,
            "ssid_24g": ssid_24g,
            "ssid_5g": ssid_5g,
            "dut_ip": dut_ip
        }.items() if not v]
        raise RuntimeError(f"Missing required config: {missing}")

    logging.info(f"Starting test: {loop_count} loops | DUT={dut_ip} | Router={router_ip}")

    dut = None
    total_failures = 0

    try:
        with allure.step("Init DUT Connected"):
            dut = _create_device_connection(control_type, dut_ip)

        for current_loop in range(1, loop_count + 1):
            with allure.step(f" {current_loop}/{loop_count} testing"):

                # 执行软重启
                _send_reboot_command(dut)
                time.sleep(60)  # 等待重启

                # 重新连接
                with allure.step("Re-Connect after Reboot"):
                    if hasattr(dut, 'close'):
                        dut.close()
                    dut = _create_device_connection(control_type, dut_ip)
                    time.sleep(5)

                # 验证网络
                _verify_network_connectivity(dut, router_ip)
                time.sleep(60)

                # 记录成功轮次（可用于恢复）
                os.environ["SOFT_REBOOT_COMPLETED_LOOPS"] = str(current_loop)
                logging.info(f"✅ Loop {current_loop} passed")

    except Exception as e:
        total_failures += 1
        logging.error(f"Test failed at loop {current_loop}: {e}", exc_info=True)

        # 附加错误到 Allure 报告
        allure.attach(
            str(e),
            name="Exception Details",
            attachment_type=allure.attachment_type.TEXT
        )
        raise

    finally:
        if dut and hasattr(dut, 'close'):
            with allure.step("Close DUT Connection"):
                dut.close()

    # 最终断言
    if total_failures > 0:
        raise AssertionError(f"Test completed with {total_failures} failure(s)")