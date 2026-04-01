import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Optional

import pytest

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

    def register(
        self,
        data_type: str,
        log_file: str,
        *,
        run_source: str = "FRAMEWORK",
        message: Optional[str] = None,
    ) -> None:
        if not log_file:
            logging.warning("Skip registering performance artifact for %s: missing log file path", data_type)
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
        return

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

@pytest.fixture(scope="session")
def performance_sync_manager() -> Callable[[str, str], None]:
    """Register performance CSV artifacts produced during the session."""

    session = _PerformanceSyncSession()
    yield session.register
    session.flush()
