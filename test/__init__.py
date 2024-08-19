from tools.router_tool.Router import Router
from tools.Iperf import Iperf
from tools.connect_tool.adb import accompanying_dut
from tools.playback_tool.Youtube import Youtube
import pytest
import os
Router = Router
add_network = pytest.executer.add_network
enter_wifi_activity = pytest.enter_wifi_activity
forget_network_cmd = pytest.forget_network_cmd
kill_setting = pytest.executer.kill_setting
wait_for_wifi_address = pytest.executer.wait_for_wifi_address
connect_ssid = pytest.executer.connect_ssid
close_wifi = pytest.executer.close_wifi
open_wifi = pytest.executer.open_wifi
find_ssid = pytest.executer.find_ssid
wait_keyboard = pytest.executer.wait_keyboard
close_hotspot = pytest.executer.close_hotspot
open_hotspot = pytest.executer.open_hotspot
kill_moresetting = pytest.executer.kill_moresetting
accompanying_dut = accompanying_dut
wait_for_wifi_service = pytest.executer.wait_for_wifi_service
change_keyboard_language = pytest.executer.change_keyboard_language
reset_keyboard_language = pytest.executer.reset_keyboard_language
connect_save_ssid = pytest.executer.connect_save_ssid
get_hwaddr = pytest.executer.get_hwaddr
wait_router = pytest.executer.wait_router
forget_ssid = pytest.executer.forget_ssid

youtube = Youtube()
iperf =Iperf()

open_info = r'<node index="0" text="Hotspot name" resource-id="android:id/title" class="android.widget.TextView" package="com.(.*?).tv.settings" content-desc="" checkable="false" checked="false" clickable="false" enabled="true"'
close_info = r'<node index="0" text="Hotspot name" resource-id="android:id/title" class="android.widget.TextView" package="com.(.*?).tv.settings" content-desc="" checkable="false" checked="false" clickable="false" enabled="false"'
wifi_onoff_tag = 'Available networks'

config_yaml = pytest.config_yaml