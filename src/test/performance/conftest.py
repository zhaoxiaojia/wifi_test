import logging
from pathlib import Path
from typing import Callable, Dict, Optional

import pytest

from src.tools.mysql_tool.MySqlControl import MySqlClient, sync_file_to_db

from src.tools.performance.rvr_chart_generator import generate_rvr_charts


@pytest.fixture(scope="session")
def performance_sync_manager() -> Callable[[str, str], None]:
    """注册需要在会话结束时同步到数据库的 CSV。"""

    pending: Dict[str, Dict[str, str]] = {}
    mysql_available: Optional[bool] = None

    def _can_use_mysql() -> bool:
        nonlocal mysql_available
        if mysql_available is not None:
            return mysql_available
        try:
            with MySqlClient():
                pass
        except Exception as exc:  # pragma: no cover - 环境依赖
            logging.info("跳过性能数据同步：无法连接到 MySQL（%s）", exc)
            mysql_available = False
            return False
        mysql_available = True
        return True

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
        test_result = getattr(pytest, "testResult", None)
        if normalized_type in {"RVR", "RVO"} and test_result is not None and hasattr(test_result, "ensure_log_file_prefix"):
            try:
                test_result.ensure_log_file_prefix(normalized_type)
                log_file = getattr(test_result, "log_file", log_file)
            except Exception:
                logging.exception("Failed to align log file prefix for %s", normalized_type)
        pending[normalized_type] = {
            "log_file": log_file,
            "data_type": normalized_type,
            "run_source": (run_source or "FRAMEWORK").strip() or "FRAMEWORK",
            "message": message or f"Stored rows for {normalized_type}",
        }
        if normalized_type in {"RVR", "RVO"}:
            logging.info("Trigger auto chart generation for %s: %s", normalized_type, log_file)
            charts_subdir = "rvo_charts" if normalized_type == "RVO" else "rvr_charts"
            try:
                generated = generate_rvr_charts(log_file, charts_subdir=charts_subdir)
            except Exception:
                logging.exception("Failed to generate %s charts for %s", normalized_type, log_file)
            else:
                if generated:
                    charts_dir = Path(generated[0]).parent
                    logging.info(
                        "Generated %d %s chart images under %s",
                        len(generated),
                        normalized_type,
                        charts_dir,
                    )
                else:
                    logging.warning(
                        "No chart images were generated for %s (%s)",
                        normalized_type,
                        log_file,
                    )

    yield register

    if not pending:
        return

    if not _can_use_mysql():
        return

    for info in pending.values():
        log_file = info.get("log_file")
        data_type = info.get("data_type")
        run_source = info.get("run_source", "FRAMEWORK")
        message = info.get("message")
        if not log_file or not data_type:
            continue
        try:
            rows = sync_file_to_db(log_file, data_type, run_source=run_source)
        except Exception as exc:
            logging.info(
                "跳过 %s 数据同步：MySQL 操作失败（%s）",
                data_type,
                exc,
            )
            mysql_available = False
            break
        if rows:
            logging.info("%s: %s", message, rows)
        else:
            logging.warning(
                "No rows stored for %s when syncing %s", data_type, log_file
            )
