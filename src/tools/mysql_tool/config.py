from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

import pymysql
from pymysql.err import OperationalError

from src.util.constants import load_config
from src.util.constants import Paths, TOOL_CONFIG_FILENAME, TOOL_SECTION_KEY


def get_tool_config_path() -> Path:
    """
    Get tool config path.

    Parameters
    ----------
    None
        This function does not accept any parameters.

    Returns
    -------
    Path
        A value of type ``Path``.
    """

    return Path(Paths.CONFIG_DIR) / TOOL_CONFIG_FILENAME


def load_mysql_config() -> Dict[str, Any]:
    """
    Load MySQL config.

    Loads configuration settings from a YAML or configuration file.
    Logs informational messages and errors for debugging purposes.

    Parameters
    ----------
    None
        This function does not accept any parameters.

    Returns
    -------
    Dict[str, Any]
        A value of type ``Dict[str, Any]``.
    """

    config_path = get_tool_config_path()
    try:
        config = load_config(refresh=True)
    except Exception as exc:
        logging.error("Failed to load configuration for MySQL: %s", exc)
        return {}
    tool_cfg = config.get(TOOL_SECTION_KEY) or {}
    mysql_cfg = tool_cfg.get("mysql") or {}
    if not mysql_cfg:
        logging.error("Missing mysql section in %s", config_path)
        return {}
    try:
        params = {
            "host": mysql_cfg.get("host"),
            "port": int(mysql_cfg.get("port", 3306)) if mysql_cfg.get("port") else 3306,
            "user": str(mysql_cfg.get("user")) if mysql_cfg.get("user") is not None else None,
            "password": str(mysql_cfg.get("passwd")) if mysql_cfg.get("passwd") is not None else None,
            "database": mysql_cfg.get("database"),
            "charset": mysql_cfg.get("charset", "utf8mb4"),
        }
    except Exception as exc:
        logging.error("Invalid mysql section in %s: %s", config_path, exc)
        return {}

    missing_keys = [key for key in ("host", "user", "password", "database") if not params.get(key)]
    if missing_keys:
        logging.error("Missing MySQL keys in %s: %s", config_path, ", ".join(missing_keys))
        return {}

    logging.debug("Loaded MySQL config from %s: %s", config_path, params)
    return params


def load_mysql_admin_config() -> Dict[str, Any]:
    config_path = get_tool_config_path()
    config = load_config(refresh=True)
    tool_cfg = config.get(TOOL_SECTION_KEY) or {}
    admin_cfg = tool_cfg.get("mysql_admin") or {}
    if not admin_cfg:
        return {}
    params = {
        "host": admin_cfg.get("host"),
        "port": int(admin_cfg.get("port", 3306)) if admin_cfg.get("port") else 3306,
        "user": str(admin_cfg.get("user")) if admin_cfg.get("user") is not None else None,
        "password": str(admin_cfg.get("passwd")) if admin_cfg.get("passwd") is not None else None,
        "charset": admin_cfg.get("charset", "utf8mb4"),
    }
    missing_keys = [key for key in ("host", "user", "password") if not params.get(key)]
    if missing_keys:
        logging.error("Missing MySQL admin keys in %s: %s", config_path, ", ".join(missing_keys))
        return {}
    return params


def ensure_database_exists(config: Dict[str, Any]) -> None:
    """
    Ensure database exists.

    Runs an SQL statement using a database cursor.

    Parameters
    ----------
    config : Any
        Dictionary containing MySQL configuration parameters.

    Returns
    -------
    None
        This function does not return a value.
    """

    db_name = config.get("database")
    if not db_name:
        raise RuntimeError("Database name is missing in mysql config.")

    host = config.get("host")
    port = int(config.get("port", 3306))
    charset = config.get("charset", "utf8mb4")
    user = config.get("user")
    password = config.get("password")

    connection = None
    try:
        connection = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            charset=charset,
            autocommit=True,
        )
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        return
    except OperationalError:
        admin = load_mysql_admin_config()
        if not admin:
            raise
    finally:
        if connection:
            connection.close()

    admin_conn = pymysql.connect(
        host=admin.get("host"),
        port=int(admin.get("port", 3306)),
        user=admin.get("user"),
        password=admin.get("password"),
        charset=admin.get("charset", "utf8mb4"),
        autocommit=True,
    )
    try:
        with admin_conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            cursor.execute(
                f"CREATE USER IF NOT EXISTS '{user}'@'%' IDENTIFIED BY '{password}'"
            )
            cursor.execute(
                f"GRANT ALL PRIVILEGES ON `{db_name}`.* TO '{user}'@'%'"
            )
            cursor.execute("FLUSH PRIVILEGES")
    finally:
        admin_conn.close()
