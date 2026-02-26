"""Result logging utilities for receiver sensitivity and throughput tests.

This module defines the :class:`PerformanceResult` class which collects,
normalizes and persists performance test results from Wi-Fi receiver
sensitivity (RVR) and related throughput executions. It constructs
appropriate CSV headers based on the number of repeat runs, writes
results to disk, and provides helpers for normalizing profile and
scenario metadata. All public methods and parameters are documented
using a ``Parameters`` section.
"""

import logging
import os
import time
from pathlib import Path
from typing import Any, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages

plt.rcParams["font.family"] = ["SimHei"]


class PerformanceResult:
    """Collect and persist Wi-Fi performance results for each RVR execution.

    Instances of this class manage the construction of CSV headers, the
    accumulation of throughput results across repeated runs, and the
    normalization of metadata such as profile modes, profile values and
    scenario group keys. Results are saved to a CSV file in the configured
    log directory and can be extended to additional output formats if needed.

    Parameters:
        logdir (str): Path to the directory where log files will be written.
        step (Sequence[Any]): A sequence of x-axis positions or other step
            values corresponding to the measurement series.
        repeat_times (int, optional): Number of times the measurement should be
            repeated. Determines how many throughput columns to allocate.
            Defaults to ``0``.
    """

    _BASE_HEADERS: Tuple[str, ...] = (
        "SerianNumber",
        "Test_Category",
        "Standard",
        "Freq_Band",
        "BW",
        "Data_Rate",
        "CH_Freq_MHz",
        "Protocol",
        "Direction",
        "Total_Path_Loss",
        "DB",
        "RSSI",
        "Angel",
        "MCS_Rate",
        "Throughput",
        "Expect_Rate",
        "Latency",
        "Packet_Loss",
        "Profile_Mode",
        "Profile_Value",
        "Scenario_Group_Key",
    )

    def __init__(self, logdir: str, step: List[Any], repeat_times: int = 0) -> None:
        """Initialize a new PerformanceResult instance and prepare result storage.

        Parameters:
            logdir (str): Directory in which to create result files.
            step (List[Any]): A list of x-axis values (e.g., attenuation settings)
                used for plotting or indexing results.
            repeat_times (int, optional): Number of repeated measurements for
                each test case. Determines how many throughput columns will
                be created. Defaults to ``0``.

        Returns:
            None
        """
        self.logdir = logdir
        self.current_number = 0
        self.x_path = step
        self.x_length = len(self.x_path)
        self._profile_mode: str = ""
        self._profile_value: str = ""
        self._scenario_group_key: str = ""
        try:
            repeat = int(repeat_times)
        except Exception:
            repeat = 0
        self._repeat_times = max(0, repeat)
        self._throughput_header: List[str] = self._build_throughput_header()
        self._headers: List[str] = self._build_header_row()
        self.init_rvr_result()

    def ensure_log_file_prefix(self, test_type: str) -> None:
        """Ensure that the current log file name starts with a given prefix.

        If a log file has been created, this method will rename it so that
        its filename begins with the upper-cased ``test_type``.  It will
        gracefully handle missing files and OS errors.

        Parameters:
            test_type (str): A short prefix to apply to the log file name.

        Returns:
            None
        """
        prefix = (test_type or "").strip().upper()
        if not prefix:
            return
        log_file = getattr(self, "log_file", None)
        if not log_file:
            return
        current_path = Path(log_file)
        current_name_upper = current_path.name.upper()
        if current_name_upper.startswith(prefix):
            return
        if current_path.name.startswith("Performance"):
            new_name = prefix + current_path.name[len("Performance") :]
        else:
            new_name = f"{prefix}_{current_path.name}"
        new_path = current_path.with_name(new_name)
        try:
            os.replace(current_path, new_path)
        except FileNotFoundError:
            return
        except OSError as exc:
            logging.warning(
                "Failed to rename performance log %s -> %s: %s",
                current_path,
                new_path,
                exc,
            )
            return
        self.log_file = str(new_path)

    def _build_throughput_header(self) -> List[str]:
        """Construct the list of throughput column headers.

        Returns:
            List[str]: A list containing ``Throughput`` when there are no
            repeated runs, or ``Throughput n`` for each run where n
            increments from 1 to the total number of runs.
        """
        total_runs = self._repeat_times + 1
        if total_runs <= 1:
            return ["Throughput"]
        return [f"Throughput {index}" for index in range(1, total_runs + 1)]

    def _build_header_row(self) -> List[str]:
        """Build the complete list of CSV header names for result files.

        This method expands the single ``Throughput`` placeholder in
        :attr:`_BASE_HEADERS` into multiple throughput columns when repeated
        runs are configured.

        Returns:
            List[str]: The list of header names to write to the CSV.
        """
        headers: List[str] = []
        for name in self._BASE_HEADERS:
            if name == "Throughput":
                headers.extend(self._throughput_header)
            else:
                headers.append(name)
        return headers

    def init_rvr_result(self) -> None:
        """Initialize on-disk files for RVR result collection.

        This method creates a new CSV file for performance data and writes
        the header row.  It also sets the path for the Excel summary file
        used by other tools.

        Returns:
            None
        """
        self.rvr_excelfile = os.path.join(self.logdir, "RvrCheckExcel.xlsx")
        if not hasattr(self, "log_file"):
            self.log_file = os.path.join(
                self.logdir,
                "Performance"
                + time.asctime().replace(" ", "_").replace(":", "_")
                + ".csv",
            )
            with open(self.log_file, "a", encoding="utf-8-sig") as f:
                f.write(",".join(self._headers))
                f.write("\n")

    def save_result(self, result: str) -> None:
        """Append a result line to the CSV log file.

        Parameters:
            result (str): A comma-separated string containing result data
                corresponding to the base headers (excluding profile and
                scenario metadata). Typically includes the throughput values.

        Returns:
            None
        """
        logging.info("Writing to csv")
        mode, value = self._get_active_profile_columns()
        scenario_key = self._get_scenario_group_key()
        line = f"{result},{mode},{value},{scenario_key}"
        with open(self.log_file, "a", encoding="utf-8-sig") as f:
            f.write(line)
            f.write("\n")
        logging.info("Write done")

    # --- profile helpers -------------------------------------------------

    def set_active_profile(self, mode: Optional[str], value: Any) -> None:
        """Set the current profile mode and value for subsequent results.

        Parameters:
            mode (Optional[str]): A symbolic name describing the active
                profile, e.g., ``"target"`` or ``"static"``. Can be ``None``.
            value (Any): The corresponding profile value. This can be a
                number, string, or iterable of values. Values will be
                normalized to a string representation.

        Returns:
            None
        """
        normalized_mode = self._normalize_profile_mode(mode)
        normalized_value = self._normalize_profile_value(value)
        if normalized_mode == "" and normalized_value != "":
            normalized_mode = "CUSTOM"
        self._profile_mode = normalized_mode
        self._profile_value = normalized_value

    def clear_active_profile(self) -> None:
        """Clear the current profile mode and value."""
        self._profile_mode = ""
        self._profile_value = ""

    def set_scenario_group_key(self, key: Optional[str]) -> None:
        """Set the scenario group key associated with subsequent results."""
        self._scenario_group_key = self._normalize_scenario_group_key(key)

    def clear_scenario_group_key(self) -> None:
        """Clear the scenario group key for subsequent results."""
        self._scenario_group_key = ""

    # internal helpers ----------------------------------------------------

    def _get_active_profile_columns(self) -> Tuple[str, str]:
        """Return the current profile mode and value as a pair."""
        return self._profile_mode, self._profile_value

    def _get_scenario_group_key(self) -> str:
        """Return the current scenario group key."""
        return self._scenario_group_key

    @staticmethod
    def _normalize_profile_mode(mode: Optional[str]) -> str:
        """Normalize a profile mode string to an uppercase canonical form."""
        if mode is None:
            return ""
        text = str(mode).strip().lower()
        if not text:
            return ""
        if text in {"target", "target_rssi", "rvo_target"}:
            return "TARGET_RSSI"
        if text in {"static", "static_db", "rvo_static"}:
            return "STATIC_DB"
        if text in {"default", "normal"}:
            return "DEFAULT"
        return text.upper()

    @staticmethod
    def _normalize_profile_value(value: Any) -> str:
        """Normalize a profile value to a concise string representation."""
        if value is None:
            return ""
        if isinstance(value, (list, tuple, set)):
            items = [PerformanceResult._normalize_profile_value(item) for item in value]
            items = [item for item in items if item]
            return items[0] if items else ""
        text = str(value).strip()
        if not text:
            return ""
        try:
            number = float(text)
        except ValueError:
            return text
        if number.is_integer():
            return str(int(number))
        return f"{number:.2f}".rstrip("0").rstrip(".")

    @staticmethod
    def _normalize_scenario_group_key(key: Optional[str]) -> str:
        """Normalize and sanitize a scenario group key."""
        if key is None:
            return ""
        text = str(key).strip()
        if not text:
            return ""
        sanitized = text.replace("\r", " ").replace("\n", " ")
        sanitized = sanitized.replace(",", "_")
        return sanitized.strip()
