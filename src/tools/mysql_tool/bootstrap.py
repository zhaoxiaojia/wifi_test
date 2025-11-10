from __future__ import annotations

import logging
from typing import Optional, Tuple

from .operations import sync_configuration


def bootstrap_mysql_environment(*, refresh_config: bool = False) -> Tuple[dict, Optional[object]]:
    """
    Bootstrap MySQL environment.

    Loads configuration settings from a YAML or configuration file.
    Logs informational messages and errors for debugging purposes.

    Parameters
    ----------
    None
        This function does not accept any parameters.

    Returns
    -------
    Tuple[dict, Optional[object]]
        A value of type ``Tuple[dict, Optional[object]]``.
    """

    try:
        from src.tools import config_loader
    except Exception:
        logging.exception("Failed to import config_loader during MySQL bootstrap")
        return {}, None

    config = config_loader.load_config(refresh=refresh_config) or {}
    result = sync_configuration(config)
    return config, result
