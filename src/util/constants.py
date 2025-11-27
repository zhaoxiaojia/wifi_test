import os
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
from dataclasses import dataclass
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


def get_model_config_base() -> Path:
    """Return the base directory for YAML model configuration."""
    return Path(__file__).resolve().parents[2] / "src" / "ui" / "model" / "config"


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
EXECUTION_CONFIG_FILENAME: Final[str] = "config_performance.yaml"
DUT_SECTION_KEYS: Final[frozenset[str]] = frozenset({
    "connect_type",
    # Project / Wi‑Fi chipset configuration (formerly "fpga").
    "project",
    "serial_port",
    "software_info",
    "hardware_info",
    # Support both legacy and new naming for the system section.
    "android_system",
    "system",
})
CONFIG_KEY_ALIASES: Final[dict[str, str]] = {
    "dut": "connect_type",
    # Backwards‑compatibility: legacy top-level "fpga" section is now
    # normalised as "project" in the merged config.
    "fpga": "project",
}
TOOL_SECTION_KEY: Final[str] = "tool"
TOOL_CONFIG_FILENAME: Final[str] = "config_tool.yaml"
STABILITY_CONFIG_FILENAME: Final[str] = "config_stability.yaml"
COMPATIBILITY_CONFIG_FILENAME: Final[str] = "config_compatibility.yaml"
STABILITY_SECTION_KEYS: Final[frozenset[str]] = frozenset({
    "stability",
    "duration_control",
    "check_point",
    "cases",
})
COMPATIBILITY_SECTION_KEYS: Final[frozenset[str]] = frozenset({
    "compatibility",
})
PERFORMANCE_SECTION_KEYS: Final[frozenset[str]] = frozenset({
    "Turntable",
    "rf_solution",
    "rvr",
    "router",
    "text_case",
    "debug",
    "duration_control",
    "check_point",
    "cases",
    "csv_path",
})

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
TEST_TYPE_ORDER: Final[tuple[str, ...]] = ("RVR", "PEAK_THROUGHPUT", "RVO")
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

# ``test_switch_wifi`` / ``test_switch_wifi_str`` case field names reused by UI and configuration helpers.
# Canonical key uses the merged stability script name; legacy aliases keep older
# configs and test paths working transparently.
SWITCH_WIFI_CASE_KEY: Final[str] = "test_switch_wifi_str"
SWITCH_WIFI_CASE_ALIASES: Final[tuple[str, ...]] = (
    "test_switch_wifi",
    "test_swtich_wifi",
)
SWITCH_WIFI_CASE_KEYS: Final[frozenset[str]] = frozenset(
    (SWITCH_WIFI_CASE_KEY, *SWITCH_WIFI_CASE_ALIASES)
)
SWITCH_WIFI_USE_ROUTER_FIELD: Final[str] = "use_router"
SWITCH_WIFI_ROUTER_CSV_FIELD: Final[str] = "router_csv"
SWITCH_WIFI_MANUAL_ENTRIES_FIELD: Final[str] = "manual_entries"
SWITCH_WIFI_ENTRY_SSID_FIELD: Final[str] = "ssid"
SWITCH_WIFI_ENTRY_SECURITY_FIELD: Final[str] = "security_mode"
SWITCH_WIFI_ENTRY_PASSWORD_FIELD: Final[str] = "password"

# Turntable configuration keys shared between the UI and YAML files.
TURN_TABLE_SECTION_KEY: Final[str] = "Turntable"
TURN_TABLE_LEGACY_SECTION_KEY: Final[str] = "corner_angle"
TURN_TABLE_FIELD_MODEL: Final[str] = "Turntable"
TURN_TABLE_FIELD_IP_ADDRESS: Final[str] = "IP address"
TURN_TABLE_FIELD_STEP: Final[str] = "Step"
TURN_TABLE_FIELD_STATIC_DB: Final[str] = "Static dB"
TURN_TABLE_FIELD_TARGET_RSSI: Final[str] = "Target RSSI"
TURN_TABLE_MODEL_RS232: Final[str] = "RS232Board5"
TURN_TABLE_MODEL_OTHER: Final[str] = "other"
TURN_TABLE_MODEL_CHOICES: Final[tuple[str, ...]] = (
    TURN_TABLE_MODEL_RS232,
    TURN_TABLE_MODEL_OTHER,
)

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


def _stringify_turntable_value(value: Any) -> str:
    """Return a normalized string representation for turntable inputs."""

    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple, set)):
        items: list[str] = []
        for item in value:
            text = str(item).strip()
            if text:
                items.append(text)
        return ",".join(items)
    return str(value).strip()


def _normalize_turntable_section(data: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a mapping that aligns the turntable section with the UI field names."""

    if isinstance(data, Mapping):
        source = dict(data)
    else:
        source = {}

    if any(
        key in source
        for key in (
            TURN_TABLE_FIELD_MODEL,
            TURN_TABLE_FIELD_IP_ADDRESS,
            TURN_TABLE_FIELD_STEP,
            TURN_TABLE_FIELD_STATIC_DB,
            TURN_TABLE_FIELD_TARGET_RSSI,
        )
    ):
        model_value = source.get(TURN_TABLE_FIELD_MODEL, TURN_TABLE_MODEL_RS232)
        ip_value = source.get(TURN_TABLE_FIELD_IP_ADDRESS, "")
        step_value = source.get(TURN_TABLE_FIELD_STEP, "")
        static_value = source.get(TURN_TABLE_FIELD_STATIC_DB, "")
        target_value = source.get(TURN_TABLE_FIELD_TARGET_RSSI, "")
    else:
        model_value = source.get("turntable_type") or source.get("model") or TURN_TABLE_MODEL_RS232
        ip_value = source.get("ip_address") or source.get("ip") or ""
        step_value = source.get("step", "")
        static_value = source.get("static_db", "")
        target_value = source.get("target_rssi", "")

    model_text = str(model_value).strip() if model_value is not None else ""
    if model_text not in TURN_TABLE_MODEL_CHOICES:
        model_text = TURN_TABLE_MODEL_RS232

    normalized = {
        TURN_TABLE_FIELD_MODEL: model_text,
        TURN_TABLE_FIELD_IP_ADDRESS: _stringify_turntable_value(ip_value),
        TURN_TABLE_FIELD_STEP: _stringify_turntable_value(step_value),
        TURN_TABLE_FIELD_STATIC_DB: _stringify_turntable_value(static_value),
        TURN_TABLE_FIELD_TARGET_RSSI: _stringify_turntable_value(target_value),
    }
    return normalized


def _normalize_config_keys(data: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a shallow copy of *data* with legacy aliases normalised."""
    if not data:
        return {}
    normalised: dict[str, Any] = {}
    for key, value in data.items():
        if key in {TURN_TABLE_SECTION_KEY, TURN_TABLE_LEGACY_SECTION_KEY}:
            normalised[TURN_TABLE_SECTION_KEY] = _normalize_turntable_section(value)
            continue
        target_key = CONFIG_KEY_ALIASES.get(key, key)
        normalised[target_key] = copy.deepcopy(value)
    return normalised


def split_config_data(
    config: Mapping[str, Any] | None,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    """Split the full configuration into DUT, execution, stability, compatibility, and tool sections."""
    normalised = _normalize_config_keys(config)

    # Section payloads written back to individual YAML files.
    dut_section: dict[str, Any] = {}
    execution_section: dict[str, Any] = {}
    stability_section: dict[str, Any] = {}
    compatibility_section: dict[str, Any] = {}
    tool_section: dict[str, Any] = {}

    for key, value in normalised.items():
        # Tool section is stored as-is in its own YAML.
        if key == TOOL_SECTION_KEY:
            if isinstance(value, Mapping):
                tool_section = copy.deepcopy(value)
            continue

        # Stability Settings (stability/duration_control/check_point/cases).
        if key in STABILITY_SECTION_KEYS:
            # Primary stability section lives under the ``stability`` key.
            if key == "stability" and isinstance(value, Mapping):
                # If stability_section already has content, merge it so that
                # any per-key updates (duration_control/cases/etc.) from the
                # flat config are preserved. Keys already present in
                # stability_section take precedence.
                base = copy.deepcopy(value)
                if isinstance(stability_section, Mapping):
                    base.update(stability_section)
                stability_section = base
            elif key == "cases":
                # Legacy top-level ``cases`` keys are no longer persisted.
                # Canonical stability case data lives under ``stability.cases``.
                continue
            else:
                # duration_control / check_point written into stability section.
                if not isinstance(stability_section, dict):
                    stability_section = {}
                stability_section[key] = copy.deepcopy(value)
            continue

        # Compatibility Settings live under a top-level ``compatibility`` key
        # in their own YAML file.
        if key in COMPATIBILITY_SECTION_KEYS:
            if isinstance(value, Mapping):
                compatibility_section = {"compatibility": copy.deepcopy(value)}
            else:
                compatibility_section = {}
            continue

        # DUT Settings use a fixed set of top-level keys (connect_type/project/etc.).
        if key in DUT_SECTION_KEYS:
            dut_section[key] = copy.deepcopy(value)
            continue

        # All remaining keys belong to the Performance/Execution config.
        execution_section[key] = copy.deepcopy(value)

    return dut_section, execution_section, stability_section, compatibility_section, tool_section


def merge_config_sections(
    dut_section: Mapping[str, Any] | None,
    execution_section: Mapping[str, Any] | None,
    stability_section: Mapping[str, Any] | None = None,
    compatibility_section: Mapping[str, Any] | None = None,
    tool_section: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a merged configuration mapping from DUT, execution, stability, compatibility, and tool sections."""
    merged: dict[str, Any] = {}
    merged.update(_normalize_config_keys(execution_section))
    merged.update(_normalize_config_keys(dut_section))
    # Compatibility settings live in their own config file but use the same
    # top-level key as execution/dut sections, so we merge them after the
    # other sections so they take precedence.
    if isinstance(compatibility_section, Mapping):
        merged.update(_normalize_config_keys(compatibility_section))
    if isinstance(stability_section, Mapping):
        merged["stability"] = copy.deepcopy(stability_section)
    else:
        merged.setdefault("stability", {})
    if isinstance(tool_section, Mapping):
        merged[TOOL_SECTION_KEY] = copy.deepcopy(tool_section)
    else:
        merged.setdefault(TOOL_SECTION_KEY, {})
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
    execution_path = config_dir / EXECUTION_CONFIG_FILENAME
    stability_path = config_dir / STABILITY_CONFIG_FILENAME
    tool_path = config_dir / TOOL_CONFIG_FILENAME
    compatibility_path = config_dir / COMPATIBILITY_CONFIG_FILENAME
    dut_section = _read_yaml_dict(dut_path)
    execution_section = _read_yaml_dict(execution_path)
    stability_section = _read_yaml_dict(stability_path)
    tool_section = _read_yaml_dict(tool_path)
    compatibility_section = _read_yaml_dict(compatibility_path)
    logging.debug("compatibility section loaded: %s", compatibility_section)
    return merge_config_sections(
        dut_section,
        execution_section,
        stability_section,
        compatibility_section,
        tool_section,
    )


def load_config(
    refresh: bool = False,
    *,
    base_dir: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Return a deep-copied configuration dictionary including stability data.

    Set ``refresh=True`` to discard the cached content and re-read from disk.
    """
    config_base = Path(base_dir) if base_dir is not None else get_model_config_base()
    cache_key = str(config_base.resolve())
    if refresh:
        _load_config_cached.cache_clear()
    data = _load_config_cached(cache_key)
    return copy.deepcopy(data)


def _coerce_truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


@dataclass(frozen=True)
class DebugFlags:
    """Aggregated debug switches parsed from configuration."""

    database_mode: bool = False
    skip_router: bool = False
    skip_corner_rf: bool = False


def get_debug_flags(
    *, config: Mapping[str, Any] | None = None, refresh: bool = False
) -> DebugFlags:
    """Return the consolidated debug switches from the configuration."""

    try:
        data = config if config is not None else load_config(refresh=refresh)
    except Exception:
        logging.debug("Failed to load config for debug flag", exc_info=True)
        return DebugFlags()
    if not isinstance(data, Mapping):
        return DebugFlags()

    debug_section = data.get("debug")
    if isinstance(debug_section, Mapping):
        debug_cfg = dict(debug_section)
    else:
        debug_cfg = {"database_mode": debug_section}

    database_mode = _coerce_truthy(debug_cfg.get("database_mode"))
    skip_router = database_mode or _coerce_truthy(debug_cfg.get("skip_router"))
    skip_corner_rf = database_mode or _coerce_truthy(debug_cfg.get("skip_corner_rf"))
    return DebugFlags(
        database_mode=database_mode,
        skip_router=skip_router,
        skip_corner_rf=skip_corner_rf,
    )


def is_database_debug_enabled(
    *, config: Mapping[str, Any] | None = None, refresh: bool = False
) -> bool:
    """Return whether database debug mode is enabled in the configuration."""

    return get_debug_flags(config=config, refresh=refresh).database_mode


def save_config_sections(
    dut_section: Mapping[str, Any] | None,
    execution_section: Mapping[str, Any] | None,
    stability_section: Mapping[str, Any] | None,
    compatibility_section: Mapping[str, Any] | None,
    tool_section: Mapping[str, Any] | None,
    *,
    base_dir: str | os.PathLike[str] | None = None,
) -> None:
    """Persist DUT, execution, stability, compatibility, and tool configuration sections."""
    config_base = Path(base_dir) if base_dir is not None else get_model_config_base()
    dut_path = config_base / DUT_CONFIG_FILENAME
    execution_path = config_base / EXECUTION_CONFIG_FILENAME
    stability_path = config_base / STABILITY_CONFIG_FILENAME
    compatibility_path = config_base / COMPATIBILITY_CONFIG_FILENAME
    tool_path = config_base / TOOL_CONFIG_FILENAME
    _write_yaml_dict(dut_path, _normalize_config_keys(dut_section))
    _write_yaml_dict(execution_path, _normalize_config_keys(execution_section))
    stability_payload = stability_section if isinstance(stability_section, Mapping) else {}
    _write_yaml_dict(stability_path, stability_payload)
    compatibility_payload = (
        compatibility_section if isinstance(compatibility_section, Mapping) else {}
    )
    logging.debug("compatibility payload persisted: %s", compatibility_payload)
    _write_yaml_dict(compatibility_path, compatibility_payload)
    tool_payload = tool_section if isinstance(tool_section, Mapping) else {}
    _write_yaml_dict(tool_path, tool_payload)


def save_config(
    config: Mapping[str, Any] | None,
    *,
    base_dir: str | os.PathLike[str] | None = None,
) -> None:
    """Persist the combined configuration dictionary."""
    (
        dut_section,
        execution_section,
        stability_section,
        compatibility_section,
        tool_section,
    ) = split_config_data(config)
    save_config_sections(
        dut_section,
        execution_section,
        stability_section,
        compatibility_section,
        tool_section,
        base_dir=base_dir,
    )
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
    connect_cfg = (config.get("connect_type") or {})
    telnet_cfg = connect_cfg.get("Linux") or connect_cfg.get("telnet") or {}
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
        "5G": ["auto", "11n", "11ac", "11ax"],
    }


# TODO: 后续补充更多产品线和项目映射
WIFI_PRODUCT_PROJECT_MAP: Final[dict[str, dict[str, dict[str, dict[str, str]]]]] = {
    "XIAOMI": {
        "TV": {
            "Blueplanet": {
                "main_chip": "T963D4",
                "wifi_module": "W2",
                "interface": "USB",
            },
        },
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
