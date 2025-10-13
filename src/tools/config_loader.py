from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import yaml

from src.tools.config_sections import (
    DUT_CONFIG_FILENAME,
    OTHER_CONFIG_FILENAME,
    merge_config_sections,
    save_config_sections,
    split_config_data,
)
from src.tools.mysql_tool import sync_configuration
from src.util.constants import get_config_base


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as handler:
            return yaml.safe_load(handler) or {}
    except Exception as exc:
        logging.error("Failed to load config section %s: %s", path, exc)
        return {}


def _section_paths(base_dir: Path) -> tuple[Path, Path]:
    return (
        base_dir / DUT_CONFIG_FILENAME,
        base_dir / OTHER_CONFIG_FILENAME,
    )


def _load_sections() -> tuple[dict, dict]:
    config_dir = get_config_base()
    dut_path, other_path = _section_paths(config_dir)
    return _read_yaml(dut_path), _read_yaml(other_path)


@lru_cache()
def _cached_load_config():
    dut_section, other_section = _load_sections()
    return merge_config_sections(dut_section, other_section)


def load_config(refresh: bool = False):
    """Load merged configuration composed from DUT and other sections."""
    if refresh:
        load_config.cache_clear()
        dut_path, other_path = _section_paths(get_config_base())
        logging.debug("Cache cleared, reloading %s and %s", dut_path, other_path)

    return _cached_load_config() or {}


load_config.cache_clear = _cached_load_config.cache_clear


def save_config(config: dict | None) -> None:
    """保存配置并触发数据库同步。"""

    config = config or {}
    dut_section, other_section = split_config_data(config)
    base_dir = get_config_base()
    save_config_sections(dut_section, other_section, base_dir=base_dir)
    load_config.cache_clear()
    try:
        sync_configuration(merge_config_sections(dut_section, other_section))
    except Exception:
        logging.exception("Failed to sync configuration to database")
