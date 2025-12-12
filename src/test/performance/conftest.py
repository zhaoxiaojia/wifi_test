import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Optional

import pytest

from src.tools.mysql_tool.MySqlControl import MySqlClient, sync_file_to_db

from src.tools.performance.rvr_chart_generator import generate_rvr_charts


def _generate_charts(data_type: str, log_file: str) -> None:
    charts_subdir = "rvo_charts" if data_type == "RVO" else "rvr_charts"
    logging.info("Trigger auto chart generation for %s: %s", data_type, log_file)
    try:
        generated = generate_rvr_charts(log_file, charts_subdir=charts_subdir)
    except Exception:
        logging.exception("Failed to generate %s charts for %s", data_type, log_file)
        return
    if not generated:
        logging.warning("No chart images were generated for %s (%s)", data_type, log_file)
        return
    charts_dir = Path(generated[0]).parent
    logging.info("Generated %d %s chart images under %s", len(generated), data_type, charts_dir)


@dataclass
class _PendingSync:
    log_file: str
    data_type: str
    run_source: str
    message: str


@dataclass
class _PerformanceSyncSession:
    pending: Dict[str, _PendingSync] = field(default_factory=dict)
    _mysql_available: Optional[bool] = None

    def register(
        self,
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
        log_file = self._align_prefix_if_needed(normalized_type, log_file)
        self.pending[normalized_type] = _PendingSync(
            log_file=log_file,
            data_type=normalized_type,
            run_source=(run_source or "FRAMEWORK").strip() or "FRAMEWORK",
            message=message or f"Stored rows for {normalized_type}",
        )
        if normalized_type in {"RVR", "RVO", "PEAK"}:
            _generate_charts(normalized_type, log_file)

    def flush(self) -> None:
        if not self.pending or not self._can_use_mysql():
            return
        for info in self.pending.values():
            self._sync_entry(info)

    def _align_prefix_if_needed(self, normalized_type: str, log_file: str) -> str:
        test_result = getattr(pytest, "testResult", None)
        if normalized_type not in {"RVR", "RVO"} or test_result is None:
            return log_file
        if not hasattr(test_result, "ensure_log_file_prefix"):
            return log_file
        try:
            test_result.ensure_log_file_prefix(normalized_type)
            return getattr(test_result, "log_file", log_file)
        except Exception:
            logging.exception("Failed to align log file prefix for %s", normalized_type)
            return log_file

    def _can_use_mysql_client(self) -> bool:
        if self._mysql_available is not None:
            return self._mysql_available
        try:
            with MySqlClient():
                pass
        except Exception as exc:  # pragma: no cover - environment-dependent
            logging.info("跳过性能数据同步：无法连接到 MySQL（%s）", exc)
            self._mysql_available = False
            return False
        self._mysql_available = True
        return True

    def _can_use_mysql(self) -> bool:
        return self._mysql_available is True or self._can_use_mysql_client()

    def _sync_entry(self, info: _PendingSync) -> None:
        if not info.log_file or not info.data_type:
            return
        try:
            rows = sync_file_to_db(
                info.log_file,
                info.data_type,
                run_source=info.run_source,
                duration_seconds=(
                    getattr(pytest, "_session_duration_seconds", None)
                    or max(0.0, time.time() - float(getattr(pytest, "_session_start_ts", time.time())))
                ),
            )
        except Exception as exc:
            logging.info("跳过 %s 数据同步：MySQL 操作失败（%s）", info.data_type, exc)
            self._mysql_available = False
            return
        if rows:
            logging.info("%s: %s", info.message, rows)
        else:
            logging.warning("No rows stored for %s when syncing %s", info.data_type, info.log_file)


@pytest.fixture(scope="session")
def performance_sync_manager() -> Callable[[str, str], None]:
    """注册需要在会话结束时同步到数据库的 CSV。"""

    session = _PerformanceSyncSession()
    yield session.register
    session.flush()
