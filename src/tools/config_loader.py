from __future__ import annotations

"""Configuration loader proxy module.

This module re-exports the :func:`load_config` and :func:`save_config`
functions from :mod:`src.util.constants`.  Importing from this module
provides a stable interface for configuration loading and saving within the
project.  See the referenced functions for detailed usage.
"""

from src.util.constants import load_config, save_config

__all__ = ["load_config", "save_config"]
