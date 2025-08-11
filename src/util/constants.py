import os
import sys
from pathlib import Path


class Paths:
    """Common path constants."""
    BASE_DIR = (
        os.path.dirname(sys.executable)
        if getattr(sys, "frozen", False)
        else str(Path(__file__).resolve().parents[2])
    )
    CONFIG_DIR = os.path.join(BASE_DIR, "config")
    RES_DIR = os.path.join(BASE_DIR, "res")


class RouterConst:
    """Constants used by router related utilities."""
    RUN_SETTING_ACTIVITY = "am start -n com.android.tv.settings/.MainSettings"
    fields = [
        "band",
        "ssid",
        "wireless_mode",
        "channel",
        "bandwidth",
        "authentication",
        "password",
        "tx",
        "rx",
        "data_row",
        "expected_rate",
        "wifi6",
        "wep_encrypt",
        "hide_ssid",
        "hide_type",
        "wpa_encrypt",
        "passwd_index",
        "protect_frame",
        "smart_connect",
        "country_code",
    ]
    FPGA_CONFIG = {
        "W1": {"mimo": "1X1", "2.4G": "11N", "5G": "11AC"},
        "W1L": {"mimo": "1X1", "2.4G": "11N", "5G": "11AC"},
        "W2": {"mimo": "2X2", "2.4G": "11AX", "5G": "11AX"},
        "W2U": {"mimo": "2X2", "2.4G": "11AX", "5G": "11AX"},
        "W2L": {"mimo": "2X2", "2.4G": "11AX", "5G": "11AX"},
    }
    dut_wifichip = "w2_sdio"


class RokuConst:
    """Constants for Roku control."""
    COMMANDS = {
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
    SENSORS = ("acceleration", "magnetic", "orientation", "rotation")


__all__ = ["Paths", "RouterConst", "RokuConst"]
