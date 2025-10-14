import logging
from typing import Callable, Dict, Optional

import pytest

from src.tools.mysql_tool.MySqlControl import sync_file_to_db


@pytest.fixture(scope="session")
def performance_sync_manager() -> Callable[[str, str], None]:
    """注册需要在会话结束时同步到数据库的 CSV。"""

    pending: Dict[str, Dict[str, str]] = {}

    def register(
        data_type: str,
        log_file: str,
        *,
        run_source: str = "FRAMEWORK",
        message: Optional[str] = None,
    ) -> None:
        if not log_file:
            logging.warning("Skip registering database sync for %s: missing log file path", data_type)
            return
        normalized_type = (data_type or "").strip().upper() or "UNKNOWN"
        pending[normalized_type] = {
            "log_file": log_file,
            "data_type": normalized_type,
            "run_source": (run_source or "FRAMEWORK").strip() or "FRAMEWORK",
            "message": message or f"Stored rows for {normalized_type}",
        }

    yield register

    for info in pending.values():
        log_file = info.get("log_file")
        data_type = info.get("data_type")
        run_source = info.get("run_source", "FRAMEWORK")
        message = info.get("message")
        if not log_file or not data_type:
            continue
        rows = sync_file_to_db(log_file, data_type, run_source=run_source)
        if rows:
            logging.info("%s: %s", message, rows)
        else:
            logging.warning(
                "No rows stored for %s when syncing %s", data_type, log_file
            )
