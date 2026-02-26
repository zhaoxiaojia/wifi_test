# test_wifi_same_ssid_roaming.py
import pytest
import allure
import time, logging
from src.tools.router_tool.router_factory import get_router
from src.conftest import record_test_step
from src.tools.connect_tool.mixins.ui_mixin import UiAutomationMixin
from src.tools.router_tool.router_telnet_control import (
    configure_ap_channel,
    restore_ap_default_wireless
)


TCID = "WiFi-STA-FSSID0002"

@allure.title("Wi-Fi Same SSID Roaming Between 2.4G & 5G")
@allure.description("""
1. Set 2.4G & 5G to same SSID/password via Telnet
2. Connect DUT
3. Change channels (2.4G: 1/6/11; 5G: 36/149)
4. Reboot DUT → auto reconnect
5. Reboot router → auto reconnect
6. Toggle Wi-Fi → auto reconnect
""")
def test_wifi_same_ssid_roaming(wifi_adb_device):
    dut, serial, logdir, cfg = wifi_adb_device

    # === 从配置中提取路由器参数 ===
    wifi_config = cfg.get("router", {})
    ssid = wifi_config.get("24g_ssid")          # 使用 2.4G SSID 作为统一名称
    password = wifi_config.get("password", "88888888")
    security = wifi_config.get("security_mode", "WPA2-Personal")
    router_ip = wifi_config.get("address")
    router_name = wifi_config.get("name")

    if not all([ssid, router_ip, router_name]):
        raise ValueError(f"Missing config: ssid={ssid}, ip={router_ip}, name={router_name}")

    # --- Step 0: clear currect connected and save SSID ---
    UiAutomationMixin._clear_saved_wifi_networks(serial)
    dut._forget_wifi_via_ui(serial, ssid)
    time.sleep(2)

    try:
        # === Step 1: 通过 Telnet 配置同名 SSID ===
        with allure.step("Configure AP via Telnet: same SSID for 2.4G and 5G"):
            router = get_router(router_name=router_name, address=router_ip)
            try:
                # 2.4G Setting
                configure_ap_channel(router, band='2g', channel=1, ssid=ssid, password=password)

                # 5G Setting（Same SSID）
                configure_ap_channel(router, band='5g', channel=36, ssid=ssid, password=password)

            finally:
                router.quit()

        time.sleep(10)  # 等待 AP 生效

        # === Step 2: DUT 连接（弱信号）===
        with allure.step("Connect DUT to AP"):
            # 假设已处于弱信号环境（物理隔墙）
            success = UiAutomationMixin._connect_to_wifi_via_ui(
                serial=serial,
                ssid=ssid,
                password=password,
                logdir=logdir
            )
            #assert success, "Failed to connect to same-SSID network"
            current_ssid = dut.get_connected_ssid_via_cli_adb(serial)
            logging.info(f"Connected SSID after add network: {current_ssid}")
            if current_ssid == ssid:
                success = True
            else:
                success = False
            rssi = dut.get_rssi()
            record_test_step(TCID, "DUT connected {current_ssid}", "PASS" if success else "FAIL", f"RSSI={rssi} dBm")

        # === Step 3: 信道切换测试 ===
        channel_tests = [
            ("2.4G", "6"),
            ("2.4G", "11"),
            ("5G", "36"),
        ]
        for band, ch in channel_tests:
            with allure.step(f"Change {band} channel to {ch} via Telnet"):
                router = get_router(router_name=router_name, address=router_ip)
                try:
                    if band == "2.4G":
                        router.set_2g_channel(ch)
                    else:
                        bw = wifi_config.get("5g_bandwidth", "80MHZ")
                        router.set_5g_channel_bandwidth(channel=ch, bandwidth=bw)
                    router.commit()
                finally:
                    router.quit()

                time.sleep(8)  # 等待 DUT 重连

                current_ssid = dut.get_connected_ssid_via_cli_adb(serial)
                if current_ssid == ssid:
                    success = True
                else:
                    success = False
                #assert current_ssid == ssid, f"Disconnected after {band} CH{ch}! Got: {current_ssid}"
                record_test_step(TCID, f"{current_ssid} {band} CH{ch} switch",  "PASS" if success else "FAIL", "Auto-reconnected")

        # === Step 4: 重启 DUT ===
        with allure.step("Reboot DUT and verify auto-reconnect"):
            booted, boot_debug = dut.wait_for_device_boot(serial, timeout=150)
            details = f"Reboot and boot: {'SUCCESS' if booted else 'FAILED'}\n{boot_debug}"
            passed = "PASS" if booted else "FAIL"
            time.sleep(15)

            current_ssid = dut.get_connected_ssid_via_cli_adb(serial)
            if current_ssid == ssid:
                success = True
            else:
                success = False
            #assert current_ssid == ssid, "DUT failed to reconnect after reboot"
            record_test_step(TCID, "DUT reboot recovery", "PASS" if success else "FAIL", "Auto-reconnected")

        # === Step 5: 重启路由器 ===
        with allure.step("Reboot router via Telnet"):
            router = get_router(router_name=router_name, address=router_ip)
            try:
                router.telnet_write("reboot", wait_prompt=False)
            finally:
                router.quit()

            time.sleep(45)  # 路由器启动 + DUT 重连

            current_ssid = dut.get_connected_ssid_via_cli_adb(serial)
            if current_ssid == ssid:
                success = True
            else:
                success = False
            #assert current_ssid == ssid, "DUT failed to reconnect after router reboot"
            record_test_step(TCID, "{current_ssid} Connection Restored After Router reboot", "PASS" if success else "FAIL", "Auto-reconnected")

        # === Step 6: Toggle Wi-Fi 开关 ===
        with allure.step("Toggle Wi-Fi OFF/ON and verify reconnect"):
            # 关闭
            UiAutomationMixin._disable_wifi_adb(serial)
            time.sleep(3)
            assert not dut.get_connected_ssid_via_cli_adb(serial), "Still connected after Wi-Fi off"

            # 打开
            UiAutomationMixin._enable_wifi_adb(serial)
            time.sleep(10)

            current_ssid = dut.get_connected_ssid_via_cli_adb(serial)
            if current_ssid == ssid:
                success = True
            else:
                success = False
            #assert current_ssid == ssid, "Failed to reconnect after Wi-Fi toggle"
            record_test_step(TCID, "{current_ssid} Connection Restored After Wi-Fi toggle recovery", "PASS" if success else "FAIL", "Auto-reconnected")

    finally:
        # === Step 5: 恢复 AP 默认设置 ===
        with allure.step("Restore AP to default"):
            restore_ap_default_wireless(
                router, band='5g',
                original_ssid=wifi_config.get("5g_ssid"),
                original_password=wifi_config.get("password")
            )
            record_test_step(TCID, "Restore AP to default", "PASS", "Environment cleaned up")
            router.quit()