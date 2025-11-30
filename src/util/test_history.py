from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from src.util.constants import Paths


TEST_HISTORY_FILENAME = "test_history.csv"
TEST_HISTORY_HEADERS = ("account", "start_time", "test_case", "duration")


@dataclass(slots=True)
class TestHistoryRecord:
    account: str
    start_time: datetime
    test_case: str
    duration_seconds: float

    def to_row(self) -> list[str]:
        duration_str = format_duration_hh_mm(self.duration_seconds)
        start_str = self.start_time.strftime("%Y-%m-%d %H:%M:%S")
        return [self.account, start_str, self.test_case, duration_str]


def get_history_path() -> Path:
    """Return the absolute path to the test_history.csv file under CONFIG_DIR."""
    return Path(Paths.CONFIG_DIR) / TEST_HISTORY_FILENAME


def ensure_history_file_exists() -> Path:
    """
    Ensure that the history CSV file exists with a header row.

    The file is placed under the shared config directory so that it
    stays alongside other tool configuration, but it is only modified
    programmatically by this tool.
    """
    path = get_history_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        logging.warning("Failed to create directory for test history: %s", exc)
        return path

    if path.exists():
        # Best-effort header validation to guard against accidental edits.
        try:
            with path.open("r", newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                first = next(reader, None)
        except Exception as exc:
            logging.warning("Failed to read existing test history file %s: %s", path, exc)
            first = None
        if first is not None and tuple(first) != TEST_HISTORY_HEADERS:
            # If the header has been modified, rotate the file and create a
            # fresh history file to avoid parsing inconsistent formats.
            try:
                from datetime import datetime as _dt

                timestamp = _dt.now().strftime("%Y%m%d_%H%M%S")
                backup = path.with_name(f"{path.stem}_backup_{timestamp}{path.suffix}")
                path.rename(backup)
                logging.warning(
                    "Existing test history file %s had an unexpected header and was "
                    "rotated to %s; a new history file will be created.",
                    path,
                    backup,
                )
            except Exception as exc:
                logging.warning("Failed to rotate invalid test history file %s: %s", path, exc)
    if not path.exists():
        try:
            with path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(TEST_HISTORY_HEADERS)
        except Exception as exc:
            logging.warning("Failed to initialise test history file %s: %s", path, exc)
    return path


def append_test_history_record(
    account_name: str | None,
    start_time: datetime,
    test_case: str,
    duration_seconds: float,
) -> None:
    """
    Append a single test run record to ``config/test_history.csv``.

    Parameters
    ----------
    account_name:
        Logical account / operator running the test (may be empty).
    start_time:
        Timestamp when pytest execution was started.
    test_case:
        Human-readable identifier, typically the display case path.
    duration_seconds:
        Run duration in seconds; recorded as HH:mm in the CSV.
    """
    record = TestHistoryRecord(
        account=(account_name or "").strip(),
        start_time=start_time,
        test_case=(test_case or "").strip(),
        duration_seconds=max(0.0, float(duration_seconds)),
    )

    path = ensure_history_file_exists()
    try:
        with path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(record.to_row())
    except Exception as exc:
        logging.warning("Failed to append test history record to %s: %s", path, exc)


def _parse_duration_to_minutes(value: str) -> int:
    """Return duration in whole minutes parsed from an HH:mm string."""
    try:
        parts = value.strip().split(":")
        if len(parts) != 2:
            return 0
        hours = int(parts[0])
        minutes = int(parts[1])
        if hours < 0 or minutes < 0:
            return 0
        return hours * 60 + minutes
    except Exception:
        return 0


def get_total_test_duration_seconds() -> int:
    """
    Return the total accumulated test duration in seconds.

    The value is derived by summing the HH:mm duration column from the
    history CSV. If the file does not exist or cannot be parsed,
    ``0`` is returned.
    """
    path = get_history_path()
    if not path.exists():
        # Create an empty file with header so that the user can
        # inspect it from the config directory if needed.
        ensure_history_file_exists()
        return 0

    total_minutes = 0
    try:
        with path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            # Skip header if present.
            first = next(reader, None)
            if first and tuple(first) != TEST_HISTORY_HEADERS:
                # If the first row is not the expected header, treat it
                # as a data row as best effort.
                row = first
                if len(row) >= 4:
                    total_minutes += _parse_duration_to_minutes(row[3])
            for row in reader:
                if not row or len(row) < 4:
                    continue
                total_minutes += _parse_duration_to_minutes(row[3])
    except Exception as exc:
        logging.warning("Failed to read test history file %s: %s", path, exc)
        return 0

    return max(0, int(total_minutes) * 60)


def format_duration_hh_mm(total_seconds: float | int) -> str:
    """Format a duration in seconds as an ``HH:mm`` string."""
    try:
        seconds = int(total_seconds)
    except Exception:
        seconds = 0
    if seconds <= 0:
        return "00:00"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours:02d}:{minutes:02d}"


def get_total_test_duration_hh_mm() -> str:
    """
    Convenience helper: return the total test duration as ``HH:mm``.

    This is intended for display in the About page.
    """
    seconds = get_total_test_duration_seconds()
    return format_duration_hh_mm(seconds)
