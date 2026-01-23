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

    from src.util.constants import load_config

    config = load_config(refresh=refresh_config) or {}
    result = sync_configuration(config)
    return config, result
