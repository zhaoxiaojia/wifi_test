from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Tuple

import yaml

from src.tools.config_sections import (
    DUT_CONFIG_FILENAME,
    OTHER_CONFIG_FILENAME,
    merge_config_sections,
    save_config_sections,
    split_config_data,
)
from src.tools.mysql_tool.MySqlControl import sync_configuration
from src.util.constants import get_config_base


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as exc:
        logging.error("Failed to load config section %s: %s", path, exc)
        return {}
    return data or {}


def _write_yaml(path: Path, data: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(data or {}, f, allow_unicode=True, sort_keys=False, width=4096)
    except Exception as exc:
        logging.error("Failed to write config section %s: %s", path, exc)


def _load_sections() -> Tuple[dict, dict]:
    config_dir = get_config_base()
    dut_path = config_dir / DUT_CONFIG_FILENAME
    other_path = config_dir / OTHER_CONFIG_FILENAME
    legacy_path = config_dir / "config.yaml"

    dut_section = _read_yaml(dut_path)
    other_section = _read_yaml(other_path)

    if not dut_section and not other_section and legacy_path.exists():
        legacy_data = _read_yaml(legacy_path)
        dut_section, other_section = split_config_data(legacy_data)
        try:
            save_config_sections(dut_section, other_section, base_dir=config_dir)
        except Exception:
            # 回退到旧行为，至少保持内存中的拆分结果
            _write_yaml(dut_path, dut_section)
            _write_yaml(other_path, other_section)

    return dut_section, other_section


@lru_cache()
def _cached_load_config():
    dut_section, other_section = _load_sections()
    merged = merge_config_sections(dut_section, other_section)

    legacy_path = get_config_base() / "config.yaml"
    if merged:
        _write_yaml(legacy_path, merged)
    elif legacy_path.exists():
        # Keep legacy file in sync even when empty
        _write_yaml(legacy_path, {})

    return merged


def load_config(refresh: bool = False):
    """Load merged configuration composed from DUT and other sections."""
    if refresh:
        load_config.cache_clear()
        dut_path = get_config_base() / DUT_CONFIG_FILENAME
        other_path = get_config_base() / OTHER_CONFIG_FILENAME
        logging.debug("Cache cleared, reloading %s and %s", dut_path, other_path)
    else:
        logging.debug("Loading config sections with cache: %s, %s",
                      get_config_base() / DUT_CONFIG_FILENAME,
                      get_config_base() / OTHER_CONFIG_FILENAME)

    config = _cached_load_config() or {}

    if refresh:
        try:
            logging.debug("DUT section keys: %s", list(config.keys()))
        except Exception as exc:
            logging.warning("Failed to introspect config keys: %s", exc)
        try:
            legacy_path = get_config_base() / "config.yaml"
            with legacy_path.open(encoding="utf-8") as f:
                logging.debug("Legacy config snapshot:\n%s", f.read())
        except Exception as exc:
            logging.warning("Failed to read legacy config file: %s", exc)

    return config


load_config.cache_clear = _cached_load_config.cache_clear


def save_config(config: dict | None) -> None:
    """保存配置，并保持新旧配置文件的同步。"""

    config = config or {}
    dut_section, other_section = split_config_data(config)
    base_dir = get_config_base()
    save_config_sections(dut_section, other_section, base_dir=base_dir)

    merged = merge_config_sections(dut_section, other_section)
    legacy_path = base_dir / "config.yaml"
    _write_yaml(legacy_path, merged)
    load_config.cache_clear()
    try:
        sync_configuration(merged)
    except Exception:
        logging.exception("Failed to sync configuration to database")
