import os
import sys
from pathlib import Path
from typing import Final


class Paths:
    """项目路径常量"""
    if getattr(sys, "frozen", False):
        BASE_DIR: Final[str] = os.path.dirname(sys.executable)
    else:
        BASE_DIR: Final[str] = str(Path(__file__).resolve().parents[2])
    CONFIG_DIR: Final[str] = os.path.join(BASE_DIR, "config")
    RES_DIR: Final[str] = os.path.join(BASE_DIR, "res")


class RouterConst:
    """路由器相关常量"""
    RUN_SETTING_ACTIVITY: Final[str] = 'am start -n com.android.tv.settings/.MainSettings'
    fields: Final[list[str]] = [
        'band', 'ssid', 'wireless_mode', 'channel', 'bandwidth', 'authentication',
        'password', 'tx', 'rx', 'data_row', 'expected_rate', 'wifi6', 'wep_encrypt',
        'hide_ssid', 'hide_type', 'wpa_encrypt', 'passwd_index', 'protect_frame',
        'smart_connect', 'country_code'
    ]
    FPGA_CONFIG: Final[dict] = {
        'W1': {'mimo': '1X1', '2.4G': '11N', '5G': '11AC'},
        'W1L': {'mimo': '1X1', '2.4G': '11N', '5G': '11AC'},
        'W2': {'mimo': '2X2', '2.4G': '11AX', '5G': '11AX'},
        'W2U': {'mimo': '2X2', '2.4G': '11AX', '5G': '11AX'},
        'W2L': {'mimo': '2X2', '2.4G': '11AX', '5G': '11AX'}
    }
    dut_wifichip: Final[str] = 'w2_sdio'


class RokuConst:
    """Roku 控制常量"""
    COMMANDS: Final[dict[str, str]] = {
        # Standard Keys
        "home": "Home",
        "reverse": "Rev",
        "forward": "Fwd",
        "play": "Play",
        "select": "Select",
        "left": "Left",
        "right": "Right",
        "down": "Down",
        "up": "Up",
        "back": "Back",
        "replay": "InstantReplay",
        "info": "Info",
        "backspace": "Backspace",
        "search": "Search",
        "enter": "Enter",
        "literal": "Lit",
        # For devices that support "Find Remote"
        "find_remote": "FindRemote",
        # For Roku TV
        "volume_down": "VolumeDown",
        "volume_up": "VolumeUp",
        "volume_mute": "VolumeMute",
        # For Roku TV while on TV tuner channel
        "channel_up": "ChannelUp",
        "channel_down": "ChannelDown",
        # For Roku TV current input
        "input_tuner": "InputTuner",
        "input_hdmi1": "InputHDMI1",
        "input_hdmi2": "InputHDMI2",
        "input_hdmi3": "InputHDMI3",
        "input_hdmi4": "InputHDMI4",
        "input_av1": "InputAV1",
        # For devices that support being turned on/off
        "power": "Power",
        "poweroff": "PowerOff",
        "poweron": "PowerOn",
    }
    SENSORS: Final[tuple[str, ...]] = (
        "acceleration", "magnetic", "orientation", "rotation"
    )
