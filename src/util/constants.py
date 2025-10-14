﻿import os
import sys
import json
import shutil
from functools import lru_cache
import yaml
import re
import logging
import copy
import signal
import tempfile
import subprocess
import atexit
from datetime import datetime
from pathlib import Path
from typing import Any, Final, Mapping
from contextlib import suppress

# Default RF attenuation spec (start,stop:step format).
# Shared by UI and performance modules to avoid scattered literals.
DEFAULT_RF_STEP_SPEC: Final[str] = "0,75:3"


def get_config_base() -> Path:
    """Return the configuration directory path。

    Prefer a ``config`` directory alongside the executable; if missing,
        fallback to ``Path(__file__).resolve().parents[2] / "config"``.
    """
    exe_dir = Path(sys.argv[0]).resolve().parent
    candidate = exe_dir / "config"
    if candidate.exists():
        return candidate
    return Path(__file__).resolve().parents[2] / "config"


_SRC_TEMP_DIR: Path | None = None


def get_src_base() -> Path:
    """Return the extracted src directory。

    Frozen bundles unpack ``src`` into a temporary directory,
    while development mode returns the repository source directory.
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
    """Remove the temporary src directory"""
    global _SRC_TEMP_DIR
    if _SRC_TEMP_DIR and _SRC_TEMP_DIR.exists():
        shutil.rmtree(_SRC_TEMP_DIR.parent, ignore_errors=True)
        _SRC_TEMP_DIR = None


class Paths:
    """Project path constants"""
    if getattr(sys, "frozen", False):
        # sys.executable points into a temporary _MEI directory; use sys.argv[0] for the real executable path
        BASE_DIR: Final[str] = os.path.dirname(os.path.abspath(sys.argv[0]))
    else:
        BASE_DIR: Final[str] = str(Path(__file__).resolve().parents[2])
    CONFIG_DIR: Final[str] = os.path.join(BASE_DIR, "config")
    RES_DIR: Final[str] = os.path.join(BASE_DIR, "res")
    SRC_DIR: Final[str] = str(get_src_base())


_DEFAULT_METADATA = {
    "package_name": "Unknown",
    "version": "Unknown",
    "build_time": "Unknown",
    "branch": "Unknown",
    "commit_hash": "Unknown",
    "commit_short": "Unknown",
    "commit_author": "Unknown",
    "commit_date": "Unknown",
}
# Configuration file split/save constants
DUT_CONFIG_FILENAME: Final[str] = "config_dut.yaml"
OTHER_CONFIG_FILENAME: Final[str] = "config_other.yaml"
DUT_SECTION_KEYS: Final[frozenset[str]] = frozenset({
    "connect_type",
    "fpga",
    "serial_port",
    "software_info",
    "hardware_info",
    "android_system",
})
CONFIG_KEY_ALIASES: Final[dict[str, str]] = {
    "dut": "connect_type",
}
TOOL_CONFIG_FILENAME: Final[str] = "tool_config.yaml"

# UI theme defaults
FONT_SIZE: Final[int] = 14
FONT_FAMILY: Final[str] = "Verdana"
TEXT_COLOR: Final[str] = "#fafafa"
BACKGROUND_COLOR: Final[str] = "#2b2b2b"
STYLE_BASE: Final[str] = f"font-size:{FONT_SIZE}px; font-family:{FONT_FAMILY};"
HTML_STYLE: Final[str] = f"{STYLE_BASE} color:{TEXT_COLOR};"

# Run page layout defaults
CONTROL_HEIGHT: Final[int] = 32
ACCENT_COLOR: Final[str] = "#0067c0"
ICON_SIZE: Final[int] = 18
ICON_TEXT_SPACING: Final[int] = 8
LEFT_PAD: Final[int] = ICON_SIZE + ICON_TEXT_SPACING

# Report page sort orders
CHART_DPI: Final[int] = 150
STANDARD_ORDER: Final[tuple[str, ...]] = ("11ax", "11ac", "11n")
BANDWIDTH_ORDER: Final[tuple[str, ...]] = ("20MHz", "40MHz", "80MHz", "160MHz")
FREQ_BAND_ORDER: Final[tuple[str, ...]] = ("2.4G", "5G", "6G")
TEST_TYPE_ORDER: Final[tuple[str, ...]] = ("RVR", "RVO")
DIRECTION_ORDER: Final[tuple[str, ...]] = ("TX", "RX")
STANDARD_ORDER_MAP: Final[dict[str, int]] = {value.lower(): index for index, value in enumerate(STANDARD_ORDER)}
BANDWIDTH_ORDER_MAP: Final[dict[str, int]] = {value.lower(): index for index, value in enumerate(BANDWIDTH_ORDER)}
FREQ_BAND_ORDER_MAP: Final[dict[str, int]] = {value.lower(): index for index, value in enumerate(FREQ_BAND_ORDER)}
TEST_TYPE_ORDER_MAP: Final[dict[str, int]] = {value.upper(): index for index, value in enumerate(TEST_TYPE_ORDER)}
DIRECTION_ORDER_MAP: Final[dict[str, int]] = {value.upper(): index for index, value in enumerate(DIRECTION_ORDER)}

# Wi-Fi authentication options
AUTH_OPTIONS: Final[tuple[str, ...]] = (
    "Open System",
    "WPA2-Personal",
    "WPA3-Personal",
    "WPA2-Enterprise",
)
OPEN_AUTH: Final[frozenset[str]] = frozenset({"Open System"})

# Android version defaults
DEFAULT_ANDROID_VERSION_CHOICES: Final[tuple[str, ...]] = (
    "Android 15",
    "Android 14",
    "Android 13",
    "Android 12",
    "Android 11",
    "Android 10",
)
ANDROID_KERNEL_MAP: Final[dict[str, str]] = {
    "Android 15": "Kernel 6.1",
    "Android 14": "Kernel 6.1",
    "Android 13": "Kernel 5.15",
    "Android 12": "Kernel 5.10",
    "Android 11": "Kernel 5.4",
    "Android 10": "Kernel 4.14",
}
DEFAULT_KERNEL_VERSION_CHOICES: Final[tuple[str, ...]] = tuple(sorted(set(ANDROID_KERNEL_MAP.values())))

# Telnet connection defaults
DEFAULT_CONNECT_MINWAIT: Final[float] = 0.1
DEFAULT_CONNECT_MAXWAIT: Final[float] = 0.5

# Shared helpers
PYQT_ACTUAL_PARAMS_ATTR: Final[str] = "_pyqt_actual_fixture_params"
RF_STEP_SPLIT_PATTERN = re.compile(r"[;\uFF1B|\r\n]+")
IDENTIFIER_SANITIZE_PATTERN = re.compile(r"[^0-9A-Za-z]+")


def _normalize_config_keys(data: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a shallow copy of *data* with legacy aliases normalised."""
    if not data:
        return {}
    normalised: dict[str, Any] = {}
    for key, value in data.items():
        target_key = CONFIG_KEY_ALIASES.get(key, key)
        normalised[target_key] = copy.deepcopy(value)
    return normalised


def split_config_data(config: Mapping[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split the full configuration into DUT-specific and general sections."""
    normalised = _normalize_config_keys(config)
    dut_section: dict[str, Any] = {}
    other_section: dict[str, Any] = {}
    for key, value in normalised.items():
        if key in DUT_SECTION_KEYS:
            dut_section[key] = copy.deepcopy(value)
        else:
            other_section[key] = copy.deepcopy(value)
    return dut_section, other_section


def merge_config_sections(
    dut_section: Mapping[str, Any] | None,
    other_section: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return a merged configuration mapping from DUT and general sections."""
    merged: dict[str, Any] = {}
    merged.update(_normalize_config_keys(other_section))
    merged.update(_normalize_config_keys(dut_section))
    return merged


def _read_yaml_dict(path: Path) -> dict[str, Any]:
    """Return mapping parsed from *path*, raising on malformed YAML."""
    if not path.exists():
        logging.debug("Config file %s does not exist; using empty mapping", path)
        return {}
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as exc:  # pragma: no cover - file permission issues are environment-dependent
        raise RuntimeError(f"Failed to read config file {path}: {exc}") from exc
    try:
        data = yaml.safe_load(content) or {}
    except yaml.YAMLError as exc:
        raise RuntimeError(f"Failed to parse YAML file {path}: {exc}") from exc
    if not isinstance(data, Mapping):
        raise RuntimeError(f"Config file {path} must contain a mapping, got {type(data).__name__}")
    return dict(data)


def _write_yaml_dict(path: Path, payload: Mapping[str, Any]) -> None:
    """Persist *payload* into *path* as YAML."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(
                payload or {},
                handle,
                allow_unicode=True,
                sort_keys=False,
                default_flow_style=False,
            )
    except Exception as exc:  # pragma: no cover - disk errors are environment-dependent
        raise RuntimeError(f"Failed to write config file {path}: {exc}") from exc


@lru_cache(maxsize=None)
def _load_config_cached(base_dir: str) -> dict[str, Any]:
    """Load configuration sections from disk and merge them."""
    config_dir = Path(base_dir)
    dut_path = config_dir / DUT_CONFIG_FILENAME
    other_path = config_dir / OTHER_CONFIG_FILENAME
    dut_section = _read_yaml_dict(dut_path)
    other_section = _read_yaml_dict(other_path)
    return merge_config_sections(dut_section, other_section)


def load_config(
    refresh: bool = False,
    *,
    base_dir: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Return a deep-copied configuration dictionary.

    Set ``refresh=True`` to discard the cached content and re-read from disk.
    """
    config_base = Path(base_dir) if base_dir is not None else get_config_base()
    cache_key = str(config_base.resolve())
    if refresh:
        _load_config_cached.cache_clear()
    data = _load_config_cached(cache_key)
    return copy.deepcopy(data)


def _coerce_truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def is_database_debug_enabled(
    *, config: Mapping[str, Any] | None = None, refresh: bool = False
) -> bool:
    """Return whether database debug mode is enabled in the configuration."""

    try:
        data = config if config is not None else load_config(refresh=refresh)
    except Exception:
        logging.debug("Failed to load config for debug flag", exc_info=True)
        return False
    if not isinstance(data, Mapping):
        return False
    debug_section = data.get("debug")
    if isinstance(debug_section, Mapping):
        candidate = debug_section.get("database_mode")
    else:
        candidate = debug_section
    return _coerce_truthy(candidate)


def save_config_sections(
    dut_section: Mapping[str, Any] | None,
    other_section: Mapping[str, Any] | None,
    *,
    base_dir: str | os.PathLike[str] | None = None,
) -> None:
    """Persist DUT and general configuration sections to their respective files."""
    config_base = Path(base_dir) if base_dir is not None else get_config_base()
    dut_path = config_base / DUT_CONFIG_FILENAME
    other_path = config_base / OTHER_CONFIG_FILENAME
    _write_yaml_dict(dut_path, _normalize_config_keys(dut_section))
    _write_yaml_dict(other_path, _normalize_config_keys(other_section))


def save_config(
    config: Mapping[str, Any] | None,
    *,
    base_dir: str | os.PathLike[str] | None = None,
) -> None:
    """Persist the combined configuration dictionary."""
    dut_section, other_section = split_config_data(config)
    save_config_sections(dut_section, other_section, base_dir=base_dir)
    _load_config_cached.cache_clear()


def get_telnet_connect_window(
    refresh: bool = False,
) -> tuple[float, float]:
    """Return the configured telnet handshake wait window."""
    try:
        config = load_config(refresh=refresh)
    except Exception:
        logging.debug("Falling back to default telnet wait window", exc_info=True)
        return DEFAULT_CONNECT_MINWAIT, DEFAULT_CONNECT_MAXWAIT
    telnet_cfg = (
        (config.get("connect_type") or {}).get("telnet") or {}
    )
    minwait = telnet_cfg.get("connect_minwait", DEFAULT_CONNECT_MINWAIT)
    maxwait = telnet_cfg.get("connect_maxwait", DEFAULT_CONNECT_MAXWAIT)
    try:
        minwait_val = float(minwait)
        maxwait_val = float(maxwait)
    except (TypeError, ValueError):
        logging.warning(
            "Invalid telnet connect window %r/%r; using defaults",
            minwait,
            maxwait,
        )
        return DEFAULT_CONNECT_MINWAIT, DEFAULT_CONNECT_MAXWAIT
    minwait_val = max(0.0, minwait_val)
    if maxwait_val < minwait_val:
        logging.warning(
            "telnet connect_maxwait %.3f smaller than connect_minwait %.3f; clamping",
            maxwait_val,
            minwait_val,
        )
        maxwait_val = minwait_val
    return minwait_val, maxwait_val




def _format_timestamp(ts: float | int | None) -> str:
    if not ts:
        return "Unknown"
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "Unknown"


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
            sources.append("Cache")

    if sources and "Cache" not in sources:
        _store_metadata_cache(base_dir, {k: v for k, v in metadata.items() if k != "data_source"})

    metadata["data_source"] = "、".join(dict.fromkeys(sources)) if sources else "Unknown"
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


# TODO: 后续补充更多产品线和项目映射
WIFI_PRODUCT_PROJECT_MAP: Final[dict[str, dict[str, dict[str, str]]]] = {
    "OTT": {
        "OB1": {
            "main_chip": "905X5M",
            "wifi_module": "W2",
            "interface": "USB",
        },
        "OB2": {
            "main_chip": "905X5M",
            "wifi_module": "W2",
            "interface": "USB",
        },
    },
    "SH": {
        "OB6": {
            "main_chip": "905X5M",
            "wifi_module": "W2",
            "interface": "USB",
        },
        "OB7": {
            "main_chip": "S805X3",
            "wifi_module": "W1U",
            "interface": "SDIO",
        },
    },
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

