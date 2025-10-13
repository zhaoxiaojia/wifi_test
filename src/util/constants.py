import os
import sys
import json
import shutil
import signal
import tempfile
import subprocess
import atexit
from datetime import datetime
from pathlib import Path
from typing import Final
from contextlib import suppress

# 默认的 RF 衰减配置（start,stop:step 格式）。
# 供 UI 与性能测试模块共享，避免魔法字符串散落各处。
DEFAULT_RF_STEP_SPEC: Final[str] = "0,75:3"


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


_DEFAULT_METADATA = {
    "package_name": "未知",
    "version": "未知",
    "build_time": "未知",
    "branch": "未知",
    "commit_hash": "未知",
    "commit_short": "未知",
    "commit_author": "未知",
    "commit_date": "未知",
}


def _format_timestamp(ts: float | int | None) -> str:
    if not ts:
        return "未知"
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "未知"


def _parse_build_spec(spec_path: Path) -> tuple[dict[str, str], list[str]]:
    info: dict[str, str] = {}
    sources: list[str] = []
    if not spec_path.exists():
        return info, sources
    sources.append("build.spec")
    try:
        content = spec_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        content = ""
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "version" in line and "=" in line:
            key, value = line.split("=", 1)
            key = key.strip().lower()
            value = value.strip().strip(",")
            if key in {"version", "app_version", "build_version"}:
                info["version"] = value.strip("'\"")
        if line.startswith("name="):
            info["package_name"] = line.split("=", 1)[1].strip().strip(",'")
    try:
        info.setdefault("build_time", _format_timestamp(spec_path.stat().st_mtime))
    except Exception:
        pass
    return info, sources


def _run_git_command(args: list[str], cwd: Path) -> str | None:
    if shutil.which("git") is None:
        return None
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return result.stdout.strip()
    except Exception:
        return None


def _get_git_metadata(repo_path: Path) -> tuple[dict[str, str], list[str]]:
    info: dict[str, str] = {}
    sources: list[str] = []
    head = _run_git_command(["rev-parse", "HEAD"], repo_path)
    if not head:
        return info, sources
    sources.append("Git")
    info["commit_hash"] = head
    info["commit_short"] = head[:7]
    describe = _run_git_command(["describe", "--tags", "--always"], repo_path)
    if describe:
        info.setdefault("version", describe)
    branch = _run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], repo_path)
    if branch:
        info["branch"] = branch
    author = _run_git_command(["show", "-s", "--format=%cn", "HEAD"], repo_path)
    if author:
        info["commit_author"] = author
    commit_date = _run_git_command(["show", "-s", "--format=%cI", "HEAD"], repo_path)
    if commit_date:
        info["commit_date"] = commit_date
        try:
            info.setdefault(
                "build_time",
                datetime.fromisoformat(commit_date.replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M:%S"),
            )
        except Exception:
            pass
    return info, sources


def _read_version_file(base_dir: Path) -> tuple[dict[str, str], list[str]]:
    candidates = [
        "VERSION",
        "version.txt",
        "build_version.txt",
        "build_metadata.json",
        "build_info.json",
    ]
    info: dict[str, str] = {}
    sources: list[str] = []
    for name in candidates:
        path = base_dir / name
        if not path.exists():
            continue
        sources.append(name)
        try:
            if path.suffix.lower() == ".json":
                payload = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    for key in ("version", "build_time", "commit_hash", "commit_author", "commit_date", "branch"):
                        if key in payload and payload[key]:
                            info[key] = str(payload[key])
            else:
                text = path.read_text(encoding="utf-8").strip()
                for line in text.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip().lower()
                        v = v.strip()
                        if k in {"version", "build_time", "commit_hash", "commit_author", "commit_date", "branch"}:
                            info[k] = v
                    elif "version" not in info:
                        info["version"] = line
                if "build_time" not in info:
                    info["build_time"] = _format_timestamp(path.stat().st_mtime)
            break
        except Exception:
            continue
    return info, sources


def _metadata_cache_path(base_dir: Path) -> Path:
    return base_dir / ".build_metadata_cache.json"


def _load_metadata_cache(base_dir: Path) -> dict[str, str] | None:
    cache_path = _metadata_cache_path(base_dir)
    if not cache_path.exists():
        return None
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return {str(k): str(v) for k, v in payload.items()}
    except Exception:
        pass
    return None


def _store_metadata_cache(base_dir: Path, metadata: dict[str, str]) -> None:
    cache_path = _metadata_cache_path(base_dir)
    try:
        cache_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def get_build_metadata() -> dict[str, str]:
    base_dir = Path(Paths.BASE_DIR)
    metadata = dict(_DEFAULT_METADATA)
    sources: list[str] = []

    spec_info, spec_sources = _parse_build_spec(base_dir / "build.spec")
    if spec_info:
        metadata.update({k: v for k, v in spec_info.items() if v})
        sources.extend(spec_sources)

    git_info, git_sources = _get_git_metadata(base_dir)
    if git_info:
        metadata.update({k: v for k, v in git_info.items() if v})
        sources.extend(git_sources)

    version_info, version_sources = _read_version_file(base_dir)
    if version_info:
        metadata.update({k: v for k, v in version_info.items() if v})
        sources.extend(version_sources)

    if not sources:
        cache = _load_metadata_cache(base_dir)
        if cache:
            metadata.update({k: v for k, v in cache.items() if v})
            sources.append("缓存")

    if sources and "缓存" not in sources:
        _store_metadata_cache(base_dir, {k: v for k, v in metadata.items() if k != "data_source"})

    metadata["data_source"] = "、".join(dict.fromkeys(sources)) if sources else "未知"
    return metadata


class RouterConst:
    """路由器相关常量"""
    RUN_SETTING_ACTIVITY: Final[str] = 'am start -n com.android.tv.settings/.MainSettings'
    fields: Final[list[str]] = [
        'band', 'ssid', 'wireless_mode', 'channel', 'bandwidth', 'security_mode',
        'password', 'tx', 'rx', 'expected_rate', 'wifi6', 'wep_encrypt',
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
    INTERFACE_CONFIG = ['SDIO', 'PCIE', 'USB']
    dut_wifichip: Final[str] = 'w2_sdio'
    DEFAULT_WIRELESS_MODES: Final[dict[str, list[str]]] = {
        "2.4G": ["auto", "11n", "11b", "11g", "11ax"],
        "5G": ["auto", "11ac", "11ax"],
    }


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
