import os
import sys
import shutil
import tempfile
import signal
import atexit
from pathlib import Path
from typing import Final
from contextlib import suppress


def get_config_base() -> Path:
    """获取配置目录路径。

    优先返回可执行文件同目录下的 ``config`` 目录；若不存在，
        则回退到源码目录 ``Path(__file__).resolve().parents[2] / 'config'``。
    """
    exe_dir = Path(sys.argv[0]).resolve().parent
    candidate = exe_dir / "config"
    if candidate.exists():
        return candidate
    return Path(__file__).resolve().parents[2] / "config"


_SRC_TEMP_DIR: Path | None = None


def get_src_base() -> Path:
    """获取 src 解压后的目录。

    打包后会将 ``src`` 目录解压到系统临时目录，
    在开发环境下直接返回源码目录。
    """
    global _SRC_TEMP_DIR
    if getattr(sys, "frozen", False):
        if _SRC_TEMP_DIR is None:
            tmp_root = Path(tempfile.mkdtemp(prefix="wifi_src_"))
            shutil.copytree(Path(sys._MEIPASS) / "src", tmp_root / "src", dirs_exist_ok=True)
            if str(tmp_root) not in sys.path:
                sys.path.insert(0, str(tmp_root))

            def _cleanup():
                shutil.rmtree(tmp_root, ignore_errors=True)

            atexit.register(_cleanup)
            for sig in (signal.SIGTERM, signal.SIGINT):
                with suppress(Exception):
                    signal.signal(sig, lambda s, f: (_cleanup(), sys.exit(0)))
            _SRC_TEMP_DIR = tmp_root / "src"
        return _SRC_TEMP_DIR
    return Path(__file__).resolve().parents[2] / "src"


def cleanup_temp_dir() -> None:
    """手动清理临时 src 目录"""
    global _SRC_TEMP_DIR
    if _SRC_TEMP_DIR and _SRC_TEMP_DIR.exists():
        shutil.rmtree(_SRC_TEMP_DIR.parent, ignore_errors=True)
        _SRC_TEMP_DIR = None


class Paths:
    """项目路径常量"""
    if getattr(sys, "frozen", False):
        # sys.executable 指向临时 _MEI 目录，改用 sys.argv[0] 获取真实 exe 路径
        BASE_DIR: Final[str] = os.path.dirname(os.path.abspath(sys.argv[0]))
    else:
        BASE_DIR: Final[str] = str(Path(__file__).resolve().parents[2])
    CONFIG_DIR: Final[str] = os.path.join(BASE_DIR, "config")
    RES_DIR: Final[str] = os.path.join(BASE_DIR, "res")
    SRC_DIR: Final[str] = str(get_src_base())


class RouterConst:
    """路由器相关常量"""
    RUN_SETTING_ACTIVITY: Final[str] = 'am start -n com.android.tv.settings/.MainSettings'
    fields: Final[list[str]] = [
        'band', 'ssid', 'wireless_mode', 'channel', 'bandwidth', 'security_protocol',
        'password', 'tx', 'rx', 'data_row', 'expected_rate', 'wifi6', 'wep_encrypt',
        'hide_ssid', 'hide_type', 'wpa_encrypt', 'passwd_index', 'protect_frame',
        'smart_connect', 'country_code'
    ]
    FPGA_CONFIG: Final[dict] = {
        'W1': {'mimo': '1X1', '2.4G': '11N', '5G': '11AC'},
        'W1U': {'mimo': '1X1', '2.4G': '11N', '5G': '11AC'},
        'W2': {'mimo': '2X2', '2.4G': '11AX', '5G': '11AX'},
        'W2U': {'mimo': '2X2', '2.4G': '11AX', '5G': '11AX'},
        'W2L': {'mimo': '2X2', '2.4G': '11AX', '5G': '11AX'}
    }
    INTERFACE_CONFIG = ['SDIO','PCIE','USB']
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
