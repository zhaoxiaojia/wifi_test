# test_wifi_hidden_ssid_security_modes.py
import pytest
import allure
import time, logging
from src.tools.router_tool.router_factory import get_router
from src.conftest import record_test_step
from src.tools.connect_tool.mixins.ui_mixin import UiAutomationMixin

from src.tools.router_tool.router_telnet_control import (
    restore_ap_default_wireless
)

TCID = "WiFi-STA-FSSID0004"

# 安全模式映射：测试用例名 -> 路由器配置值 & UI 选择项
SECURITY_MODES = [
    {
        "name": "Open",
        "router_auth": "Open System",
        "ui_security": "None",
        "password": "",
        "use_password": False,
    },
     {
         "name": "WEP", # adb device un-support WEP mode
         "router_auth": "WEP",
         "ui_security": "WEP",
         "password": "1234567890",
         "use_password": True,
     },
     {
        "name": "WPA/WPA2",
        "router_auth": "WPA/WPA2-Personal",
        "ui_security": "WPA/WPA2",
        "password": "88888888",
        "use_password": True,
    },
    # {
    #     "name": "WPA2/WPA3",  # adb device un-support WPA2/WPA3 mode
    #     "router_auth": "WPA2/WPA3-Personal",
    #     "ui_security": "WPA2/WPA3",
    #     "password": "88888888",
    #     "use_password": True,
    # },
    {
        "name": "WPA3",
        "router_auth": "WPA3-Personal",
        "ui_security": "WPA3",
        "password": "88888888",
        "use_password": True,
    },
]

@allure.title("Wi-Fi Hidden SSID with Security Mode Cycling")
@allure.description("""
1. Use fixed SSID from config (e.g., 'MyTestNet'), set as hidden (non-broadcast) on both 2.4G/5G.
2. For each security mode: Open, WEP, WPA/WPA2, WPA2/WPA3, WPA3:
   - Reconfigure AP with new auth/password (same hidden SSID)
   - On DUT: Settings → Add network manually → input SSID + select security + password
   - Connect and verify internet access
   - Reboot DUT → auto-reconnect to hidden AP
""")
@pytest.mark.parametrize("sec_mode", SECURITY_MODES, ids=[m["name"] for m in SECURITY_MODES])
def test_wifi_hidden_ssid_security_modes(wifi_adb_device, sec_mode):
    dut, serial, logdir, cfg = wifi_adb_device

    # === 从配置中提取固定 SSID 和路由器参数 ===
    wifi_config = cfg.get("router", {})
    ssid = wifi_config.get("24g_ssid")  # ← 固定 SSID，来自配置（如 testbed.yaml）
    if not ssid:
        raise ValueError("Missing 'ssid' in router config")

    password = sec_mode["password"]
    router_auth = sec_mode["router_auth"]
    ui_security = sec_mode["ui_security"]
    use_password = sec_mode["use_password"]

    router_ip = wifi_config.get("address")
    router_name = wifi_config.get("name")
    if not all([router_ip, router_name]):
        raise ValueError(f"Missing router config: ip={router_ip}, name={router_name}")

    # --- Step 0: 清除已保存网络（确保干净状态）---
    UiAutomationMixin._clear_saved_wifi_networks(serial)
    logging.info(f"DEBUG: sec_mode = {sec_mode}")

    # === Step 1: 配置路由器（双频合一 + 隐藏 SSID + 当前安全模式）===
    with allure.step(f"Configure AP: hidden SSID '{ssid}', security={sec_mode['name']}"):
        router = get_router(router_name=router_name, address=router_ip)
        dut._forget_wifi_via_ui(serial, ssid)

        try:
            # 2.4G 设置
            router.set_2g_ssid(ssid)
           #router.set_hidden_ssid(hide_2g=True, hide_5g=False)
            if sec_mode['name'] == 'WEP':
                # Use new dedicated WEP function
                router.set_wep_mode_dual_band(key_type='64-bit', wep_key=sec_mode['password'], bands=['2g'])
            else:
                # Keep original logic for other security modes
                router.set_2g_authentication(router_auth)
                if use_password:
                    router.set_2g_password(password)
            router.set_2g_channel("6")

            # 5G 设置（同名 + 隐藏）
            router.set_5g_ssid(ssid)
            if sec_mode['name'] == 'WEP':
                # Use new dedicated WEP function
                router.set_wep_mode_dual_band(key_type='64-bit', wep_key=sec_mode['password'], bands=['5g'])
            else:
                # Keep original logic for other security modes
                router.set_5g_authentication(router_auth)
                if use_password:
                    router.set_5g_password(password)

            router.set_hidden_ssid(hide_2g=True, hide_5g=True)
            router.set_5g_channel_bandwidth(channel="36", bandwidth="80MHZ")
            router.commit()
            #record_test_step(TCID, f"AP configured: {sec_mode['name']}", "PASS", f"SSID={ssid} (hidden)")

            time.sleep(12)  # 等待 AP 生效（隐藏网络需更长时间稳定)

        finally:
            router.quit()

        # === Step 2: 手动添加网络并连接（即使 SSID 隐藏也能连）===
        try:
            with allure.step(f"Add network manually: {ssid} ({sec_mode['name']})"):
                success = UiAutomationMixin._add_manual_wifi_network(
                    serial=serial,
                    ssid=ssid,
                    security=ui_security,
                    password=password if use_password else None,
                    logdir=logdir
                )

                current_ssid = dut.get_connected_ssid_via_cli_adb(serial)
                # assert current_ssid == ssid, f"Auto-reconnect failed! Expected: {ssid}, Got: '{current_ssid}'"
                logging.info(f"Connected SSID after add network: {current_ssid}")
                if current_ssid == ssid:
                    success = True
                else:
                    success = False

                record_test_step(TCID, f"Manual connect: {sec_mode['name']}",  "PASS" if success else "FAIL", "Connected via UI")
                img = dut._capture_screenshot(logdir, "step2_hiddle_connect")
                if img and img.exists():
                    allure.attach.file(str(img), name="Hiddle Connect", attachment_type=allure.attachment_type.PNG)
                time.sleep(10)
                assert success, f"Failed to connect to hidden {ssid} with {sec_mode['name']}"


            # === Step 3: 验证在线视频播放（简化为网络连通性）===
            with allure.step("Verify internet connectivity (video playback)"):
                success = dut.launch_youtube_tv_and_search(serial, logdir)
                passed = success
                details = "YouTube playable after recovery" if passed else "YouTube not playable"
                record_test_step(TCID, "Post-Recovery Playback", "PASS" if passed else "FAIL", details)
                if not passed:
                    pytest.fail("YouTube cannot be played after Watchdog recovery")

                img2 = dut._capture_screenshot(logdir, "step3_video")
                if img2 and img2.exists():
                    allure.attach.file(str(img2), name="Recovered Playback", attachment_type=allure.attachment_type.PNG)

            # === Step 4: 重启 DUT 并验证自动重连到隐藏 AP ===
            with allure.step("Reboot DUT and verify auto-reconnect to hidden AP"):
                booted, _ = dut.wait_for_device_boot(serial, timeout=150)
                assert booted, "DUT failed to boot"
                time.sleep(15)

                current_ssid2 = dut.get_connected_ssid_via_cli_adb(serial)
                logging.info(f"Connected SSID after reboot: {current_ssid2}")
                if current_ssid2 == ssid:
                    success = True
                else:
                    success = False
                assert current_ssid2 == ssid, f"Auto-reconnect failed! Expected: {ssid}, Got: '{current_ssid2}'"
                record_test_step(TCID, f"Reboot recovery: {sec_mode['name']}", "PASS" if success else "FAIL", "Auto-reconnected to hidden AP")

        finally:
            logging.info("🔧 Restoring SSID broadcast (unhiding SSID)...")
            try:
                restore_ap_default_wireless(
                    router,
                    band="5g",
                    original_ssid=wifi_config.get("5g_ssid"),
                    original_password=password
                )
                restore_ap_default_wireless(
                    router,
                    band="2g",
                    original_ssid=wifi_config.get("24g_ssid"),
                    original_password=password
                )

                router.set_hidden_ssid(hide_2g=False, hide_5g=False)
                router.commit()
                time.sleep(3)  # 给 AP 时间生效
                logging.info("✅ SSID broadcast restored.")
            except Exception as e:
                logging.error(f"⚠️ Failed to restore SSID broadcast: {e}")