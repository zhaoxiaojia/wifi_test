from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Dict, Tuple

import yaml

from src.util.constants import get_config_base

DUT_CONFIG_FILENAME = "config_dut.yaml"
OTHER_CONFIG_FILENAME = "config_other.yaml"

# 需要归类为 DUT 配置的顶层键
_DUT_SECTION_KEYS: frozenset[str] = frozenset(
    {
        "connect_type",
        "fpga",
        "serial_port",
        "software_info",
        "hardware_info",
        "android_system",
    }
)

# 允许的顶层键别名（例如历史遗留命名）
_KEY_ALIASES: Dict[str, str] = {
    "dut": "connect_type",
}


def _canonical_key(key: str) -> str:
    """将键映射为规范化名称，用于判断归属的配置段。"""

    return _KEY_ALIASES.get(key, key)


def split_config_data(config: dict | None) -> Tuple[dict, dict]:
    """按照 DUT/其它配置段拆分配置字典。"""

    if not isinstance(config, dict):
        return {}, {}

    dut_section: dict = {}
    other_section: dict = {}

    for key, value in config.items():
        target = dut_section if _canonical_key(key) in _DUT_SECTION_KEYS else other_section
        target[key] = copy.deepcopy(value)

    return dut_section, other_section


def merge_config_sections(dut_section: dict | None, other_section: dict | None) -> dict:
    """合并 DUT 与其它配置段，DUT 段键值优先生效。"""

    merged: dict = {}
    for section in (other_section, dut_section):
        if not isinstance(section, dict):
            continue
        for key, value in section.items():
            merged[key] = copy.deepcopy(value)
    return merged


def save_config_sections(
    dut_section: dict | None,
    other_section: dict | None,
    base_dir: Path | None = None,
) -> Tuple[Path, Path]:
    """将拆分后的配置写入对应文件，并返回写入的路径。"""

    base_path = Path(base_dir) if base_dir is not None else get_config_base()
    dut_path = base_path / DUT_CONFIG_FILENAME
    other_path = base_path / OTHER_CONFIG_FILENAME

    for path, payload in ((dut_path, dut_section), (other_path, other_section)):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as f:
                yaml.safe_dump(payload or {}, f, allow_unicode=True, sort_keys=False, width=4096)
        except Exception as exc:  # pragma: no cover - I/O 依赖环境
            logging.error("Failed to write config section %s: %s", path, exc)
            raise

    return dut_path, other_path
