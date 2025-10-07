from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

import pymysql
import yaml

BASE_DIR = Path(__file__).resolve().parents[3]
_TOOL_CONFIG_PATH = BASE_DIR / "config" / "tool_config.yaml"


def get_tool_config_path() -> Path:
    """Return the absolute path to tool_config.yaml."""

    return _TOOL_CONFIG_PATH


def load_mysql_config() -> Dict[str, Any]:
    """Return MySQL connection parameters loaded from tool_config.yaml."""

    config_path = get_tool_config_path()
    try:
        with config_path.open(encoding="utf-8") as fh:
            config = yaml.safe_load(fh) or {}
    except FileNotFoundError:
        logging.error("tool_config.yaml not found at %s", config_path)
        return {}
    except Exception as exc:
        logging.error("Failed to read tool_config.yaml: %s", exc)
        return {}

    mysql_cfg = config.get("mysql") or {}
    params = {
        "host": mysql_cfg.get("host"),
        "port": int(mysql_cfg.get("port", 3306)) if mysql_cfg.get("port") else 3306,
        "user": str(mysql_cfg.get("user")) if mysql_cfg.get("user") is not None else None,
        "password": str(mysql_cfg.get("passwd")) if mysql_cfg.get("passwd") is not None else None,
        "database": mysql_cfg.get("database"),
        "charset": mysql_cfg.get("charset", "utf8mb4"),
    }

    missing_keys = [key for key in ("host", "user", "password", "database") if not params.get(key)]
    if missing_keys:
        logging.error("Missing MySQL keys in tool_config.yaml: %s", ", ".join(missing_keys))
        return {}

    logging.debug("Loaded MySQL config from tool_config.yaml: %s", params)
    return params


def ensure_database_exists(config: Dict[str, Any]) -> None:
    """Create database if it does not exist."""

    db_name = config.get("database")
    if not db_name:
        raise RuntimeError("Database name is missing in mysql config.")

    connection = pymysql.connect(
        host=config.get("host"),
        port=int(config.get("port", 3306)),
        user=config.get("user"),
        password=config.get("password"),
        charset=config.get("charset", "utf8mb4"),
        autocommit=True,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    finally:
        connection.close()
