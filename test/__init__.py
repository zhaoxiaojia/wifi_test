from tools.router_tool.Router import Router
from tools.Iperf import Iperf
from tools.connect_tool.adb import accompanying_dut
from tools.playback_tool.Youtube import Youtube
import pytest
import os
Router = Router
add_network = pytest.dut.add_network
enter_wifi_activity = pytest.dut.enter_wifi_activity
forget_network_cmd = pytest.dut.forget_wifi
kill_setting = pytest.dut.kill_setting
wait_for_wifi_address = pytest.dut.wait_for_wifi_address
connect_ssid = pytest.dut.connect_ssid
close_wifi = pytest.dut.close_wifi
open_wifi = pytest.dut.open_wifi
find_ssid = pytest.dut.find_ssid
wait_keyboard = pytest.dut.wait_keyboard
close_hotspot = pytest.dut.close_hotspot
open_hotspot = pytest.dut.open_hotspot
kill_moresetting = pytest.dut.kill_moresetting
accompanying_dut = accompanying_dut
wait_for_wifi_service = pytest.dut.wait_for_wifi_service
change_keyboard_language = pytest.dut.change_keyboard_language
reset_keyboard_language = pytest.dut.reset_keyboard_language
connect_save_ssid = pytest.dut.connect_save_ssid
get_hwaddr = pytest.dut.get_hwaddr
wait_router = pytest.dut.wait_router
forget_ssid = pytest.dut.forget_ssid

youtube = Youtube()
iperf =Iperf()

open_info = r'<node index="0" text="Hotspot name" resource-id="android:id/title" class="android.widget.TextView" package="com.(.*?).tv.settings" content-desc="" checkable="false" checked="false" clickable="false" enabled="true"'
close_info = r'<node index="0" text="Hotspot name" resource-id="android:id/title" class="android.widget.TextView" package="com.(.*?).tv.settings" content-desc="" checkable="false" checked="false" clickable="false" enabled="false"'
wifi_onoff_tag = 'Available networks'

config_yaml = pytest.config_yaml