from __future__ import annotations

"""Configuration section proxy module.

This module re-exports constants and helper functions related to splitting,
merging and saving configuration sections from :mod:`src.util.constants`.
Using this module provides a stable and concise API surface for other parts
of the codebase.
"""

from src.util.constants import (
    BASIC_CONFIG_FILENAME,
    BASIC_SECTION_KEYS,
    COMPATIBILITY_CONFIG_FILENAME,
    CONFIG_KEY_ALIASES,
    DUT_CONFIG_FILENAME,
    EXECUTION_CONFIG_FILENAME,
    STABILITY_CONFIG_FILENAME,
    get_config_base,
    merge_config_sections,
    save_config_sections,
    split_config_data,
)

__all__ = [
    "CONFIG_KEY_ALIASES",
    "BASIC_CONFIG_FILENAME",
    "BASIC_SECTION_KEYS",
    "DUT_CONFIG_FILENAME",
    "EXECUTION_CONFIG_FILENAME",
    "COMPATIBILITY_CONFIG_FILENAME",
    "STABILITY_CONFIG_FILENAME",
    "get_config_base",
    "split_config_data",
    "merge_config_sections",
    "save_config_sections",
]
