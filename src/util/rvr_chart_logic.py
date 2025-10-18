"""Shared RVR chart data processing helpers.

This module extracts the data preparation logic that was previously
embedded in the report page UI so it can be reused by both the GUI and
non-interactive workflows (e.g. automated chart generation after tests
finish).
"""

from __future__ import annotations

import logging
import math
import re
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

from src.util.constants import (
    BANDWIDTH_ORDER_MAP,
    DIRECTION_ORDER_MAP,
    FREQ_BAND_ORDER_MAP,
    STANDARD_ORDER_MAP,
    TEST_TYPE_ORDER_MAP,
)


class RvrChartLogic:
    """Mixin that provides common helpers for RVR chart preparation."""

    def _load_rvr_dataframe(self, path: Path) -> pd.DataFrame:
        try:
            if path.suffix.lower() == ".csv":
                try:
                    df = pd.read_csv(path)
                except UnicodeDecodeError:
                    df = pd.read_csv(path, encoding="gbk")
            else:
                sheets = pd.read_excel(path, sheet_name=None)
                frames = [sheet for sheet in sheets.values() if sheet is not None and not sheet.empty]
                df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        except Exception as exc:
            logging.exception("Failed to read RVR results: %s", exc)
            return pd.DataFrame()
        if df is None or df.empty:
            return pd.DataFrame()
        prepared = self._prepare_rvr_dataframe(df)
        final_type = self._resolve_dataframe_test_type(prepared, path)
        if final_type:
            normalized_type = (final_type or "").strip().upper()
            prepared["__test_type_display__"] = normalized_type or "RVR"
        elif "__test_type_display__" not in prepared.columns:
            prepared["__test_type_display__"] = "RVR"
        return prepared

    def _prepare_rvr_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()
        prepared = df.copy()
        prepared.columns = [str(c).strip() for c in prepared.columns]
        for column in prepared.columns:
            prepared[column] = prepared[column].apply(lambda v: v.strip() if isinstance(v, str) else v)
        if "Direction" in prepared.columns:
            prepared["Direction"] = prepared["Direction"].astype(str).str.upper()
        for col in ("Freq_Band", "Standard", "BW", "CH_Freq_MHz", "DB"):
            if col in prepared.columns:
                prepared[col] = prepared[col].astype(str)
        row_count = len(prepared)

        def source_series(*names: str) -> pd.Series:
            for name in names:
                if name in prepared.columns:
                    return prepared[name]
            return pd.Series([""] * row_count, index=prepared.index, dtype=object)

        standard_series = source_series("Standard")
        prepared["__standard_display__"] = standard_series.apply(self._format_standard_display).replace("", "Unknown")

        bandwidth_series = source_series("BW", "Bandwidth")
        prepared["__bandwidth_display__"] = bandwidth_series.apply(self._format_bandwidth_display).replace("", "Unknown")

        freq_series = source_series("Freq_Band", "Frequency Band", "Band")
        freq_display = freq_series.apply(self._format_freq_band_display)
        if freq_display.eq("").all() and "CH_Freq_MHz" in prepared.columns:
            channel_freq = source_series("CH_Freq_MHz").apply(self._format_freq_band_display)
            freq_display = freq_display.where(freq_display != "", channel_freq)
        prepared["__freq_band_display__"] = freq_display.replace("", "Unknown")

        prepared["__direction_display__"] = source_series("Direction").apply(self._format_direction_display)

        prepared["__channel_display__"] = source_series("CH_Freq_MHz", "Channel").apply(
            self._format_channel_display
        )

        prepared["__db_display__"] = source_series("DB", "Total_Path_Loss", "RxP", "Attenuation", "Path_Loss").apply(
            self._format_db_display
        )

        prepared["__rssi_display__"] = source_series("RSSI", "Data_RSSI", "Data RSSI").apply(
            self._format_metric_display
        )

        step_candidates = ("DB", "Total_Path_Loss", "RxP", "Step", "Attenuation")

        def resolve_step(row: pd.Series) -> Optional[str]:
            for name in step_candidates:
                if name in row:
                    value = row.get(name)
                    display = self._format_db_display(value)
                    if display:
                        return display
                    normalized = self._normalize_step(value)
                    if normalized:
                        return normalized
            return None

        prepared["__step__"] = prepared.apply(resolve_step, axis=1)
        fallback_steps = pd.Series([str(i + 1) for i in range(row_count)], index=prepared.index)
        prepared["__step__"] = prepared["__step__"].fillna(fallback_steps)
        empty_mask = prepared["__step__"] == ""
        if empty_mask.any():
            prepared.loc[empty_mask, "__step__"] = fallback_steps[empty_mask]

        throughput_columns = self._resolve_throughput_columns(prepared.columns)
        if throughput_columns:
            prepared["__throughput_value__"] = prepared.apply(
                lambda row: self._aggregate_throughput_row(row, throughput_columns),
                axis=1,
            )
        else:
            prepared["__throughput_value__"] = source_series("Throughput").apply(self._safe_float)

        prepared["__throughput_value__"] = prepared["__throughput_value__"].apply(
            lambda value: float(value) if isinstance(value, (int, float)) else value
        )

        return prepared.reset_index(drop=True)

    def _resolve_throughput_columns(self, columns: Iterable[str]) -> list[str]:
        columns = list(columns)
        if "Throughput" not in columns:
            return []
        start = columns.index("Throughput")
        if "Expect_Rate" in columns:
            end = columns.index("Expect_Rate")
            if end <= start:
                end = start + 1
        else:
            end = len(columns)
        return list(columns[start:end])

    def _aggregate_throughput_row(self, row: pd.Series, columns: list[str]) -> Optional[float]:
        values: list[float] = []
        for col in columns:
            values.extend(self._parse_numeric_list(row.get(col)))
        if not values:
            return None
        return sum(values) / len(values)

    def _parse_numeric_list(self, value) -> list[float]:
        if value is None:
            return []
        if isinstance(value, (int, float)):
            return [float(value)]
        s = str(value).strip()
        if not s:
            return []
        parts = re.split(r"[\s,;/]+", s)
        numbers: list[float] = []
        for part in parts:
            if not part:
                continue
            try:
                numbers.append(float(part))
            except ValueError:
                continue
        return numbers

    def _detect_test_type_from_row(self, row: pd.Series) -> str:
        for column in ("Test_Category", "Sub_Category", "Data_Rate", "Protocol"):
            value = row.get(column)
            normalized = self._normalize_value(value)
            if not normalized:
                continue
            if "peak" in normalized and "throughput" in normalized:
                return "PEAK_THROUGHPUT"
            if "rvo" in normalized:
                return "RVO"
            if "rvr" in normalized:
                return "RVR"

        angle_value = self._extract_first_non_empty(
            row,
            (
                "Angel",
                "Angle",
                "corner",
                "Corner",
                "corner_angle",
                "Corner_Angle",
            ),
        )
        if angle_value is not None:
            normalized_angle = self._normalize_value(angle_value)
            if normalized_angle and normalized_angle not in {"", "null", "none"}:
                return "RVO"

        for value in row.tolist():
            normalized = self._normalize_value(value)
            if not normalized:
                continue
            if "peak" in normalized and "throughput" in normalized:
                return "PEAK_THROUGHPUT"
            if "rvo" in normalized:
                return "RVO"
            if "rvr" in normalized:
                return "RVR"
        return "RVR"

    def _resolve_dataframe_test_type(self, df: pd.DataFrame, path: Optional[Path]) -> Optional[str]:
        if df is None or df.empty:
            return None
        selection_override = self._infer_test_type_from_selection()
        if selection_override:
            normalized_selection = selection_override.strip().upper()
            if normalized_selection:
                return normalized_selection

        override = self._infer_test_type_from_path(path) if path is not None else None
        if override:
            normalized_override = override.strip().upper()
            if normalized_override:
                return normalized_override

        detected = self._determine_dataframe_test_type(df)
        if detected:
            return detected
        return "RVR"

    def _determine_dataframe_test_type(self, df: pd.DataFrame) -> Optional[str]:
        if df is None or df.empty:
            return None

        if self._dataframe_contains_corner_angles(df):
            return "RVO"

        sample = df.head(200)
        detected: set[str] = set()
        for _, row in sample.iterrows():
            candidate = self._detect_test_type_from_row(row)
            if candidate:
                detected.add(candidate.upper())
        if "RVO" in detected:
            return "RVO"
        if "PEAK_THROUGHPUT" in detected:
            return "PEAK_THROUGHPUT"
        if "RVR" in detected:
            return "RVR"

        column_tokens = " ".join(str(name).lower() for name in df.columns)
        if "rvo" in column_tokens:
            return "RVO"
        if "peak" in column_tokens and "throughput" in column_tokens:
            return "PEAK_THROUGHPUT"
        return None

    def _infer_test_type_from_selection(self) -> Optional[str]:
        explicit = getattr(self, "_selected_test_type", None)
        if isinstance(explicit, str):
            normalized = explicit.strip().upper()
            if normalized:
                return normalized

        case_path = getattr(self, "_active_case_path", None)
        if case_path:
            inferred = self._infer_test_type_from_case_path(case_path)
            if inferred:
                return inferred
        return None

    def _infer_test_type_from_case_path(self, case_path: str | Path) -> Optional[str]:
        if case_path is None:
            return None
        try:
            name = Path(case_path).name.lower()
        except Exception:
            try:
                name = str(case_path).lower()
            except Exception:
                return None
        if not name:
            return None
        if "peak" in name and "throughput" in name:
            return "PEAK_THROUGHPUT"
        if "rvo" in name:
            return "RVO"
        if any(token in name for token in ("rvr", "performance")):
            return "RVR"
        return None

    def _dataframe_contains_corner_angles(self, df: pd.DataFrame) -> bool:
        if df is None or df.empty:
            return False

        angle_columns = []
        for column in df.columns:
            name = str(column).strip().lower()
            if name in {"angel", "angle", "corner", "corner_angle", "cornerangle"}:
                angle_columns.append(column)
        if not angle_columns:
            return False

        for column in angle_columns:
            try:
                series = df[column] if isinstance(df[column], pd.Series) else pd.Series(df[column])
            except Exception:
                continue
            for value in series.tolist():
                normalized = self._normalize_value(value)
                if normalized and normalized not in {"", "null", "none"}:
                    return True
        return False

    def _format_standard_display(self, value) -> str:
        if value is None:
            return ""
        s = str(value).strip()
        if not s or s.lower() in {"nan", "null"}:
            return ""
        compact = s.replace(" ", "").replace("_", "")
        lower = compact.lower()
        if lower.startswith("11"):
            return lower
        return compact

    def _format_bandwidth_display(self, value) -> str:
        if value is None:
            return ""
        s = str(value).strip()
        if not s or s.lower() in {"nan", "null"}:
            return ""
        match = re.search(r"-?\d+(?:\.\d+)?", s)
        if match:
            num = match.group()
            if num.endswith(".0"):
                num = num[:-2]
            return f"{num}MHz"
        return s.replace(" ", "")

    def _format_freq_band_display(self, value) -> str:
        if value is None:
            return ""
        s = str(value).strip()
        if not s:
            return ""
        lowered = s.lower()
        if lowered in {"nan", "null", "none", "n/a", "na", "-"}:
            return ""
        compact = lowered.replace(" ", "")
        if "2g4" in compact or "2.4g" in compact:
            return "2.4G"
        if "5g" in compact and "2.4g" not in compact:
            return "5G"
        if "6g" in compact or "6e" in compact:
            return "6G"
        match = re.search(r"-?\d+(?:\.\d+)?", compact)
        if match:
            try:
                num = float(match.group())
            except ValueError:
                num = None
            if num is not None:
                if "mhz" in compact and num >= 100:
                    ghz = num / 1000.0
                elif num >= 1000:
                    ghz = num / 1000.0
                else:
                    ghz = num
                if ghz < 3.5:
                    return "2.4G"
                if ghz < 6.0:
                    return "5G"
                if ghz < 8.0:
                    return "6G"
                if num <= 14:
                    return "2.4G"
                if 30 <= num < 200:
                    return "5G"
                if num >= 200:
                    return "6G"
        cleaned = s.upper().replace("GHZ", "G").replace(" ", "")
        return cleaned

    def _format_direction_display(self, value) -> str:
        if value is None:
            return ""
        s = str(value).strip().upper()
        if not s or s in {"NAN", "NULL"}:
            return ""
        if s in {"UL", "UP", "TX"}:
            return "TX"
        if s in {"DL", "DOWN", "RX"}:
            return "RX"
        return s

    def _format_channel_display(self, value) -> str:
        if value is None:
            return ""
        s = str(value).strip()
        if not s or s.lower() in {"nan", "null"}:
            return ""
        if s.endswith(".0"):
            s = s[:-2]
        return s

    def _format_db_display(self, value) -> str:
        if value is None:
            return ""
        s = str(value).strip()
        if not s or s.lower() in {"nan", "null"}:
            return ""
        match = re.search(r"-?\d+(?:\.\d+)?", s)
        if match:
            num = match.group()
            if num.endswith(".0"):
                num = num[:-2]
            return num
        return s

    def _format_metric_display(self, value) -> str:
        if value is None:
            return ""
        s = str(value).strip()
        if not s or s.lower() in {"nan", "null", "n/a", "false"}:
            return ""
        match = re.search(r"-?\d+(?:\.\d+)?", s)
        if match:
            num = match.group()
            if num.endswith(".0"):
                num = num[:-2]
            return num
        return s

    def _collect_user_annotations(self, df: pd.DataFrame) -> list[str]:
        if df is None or df.empty:
            return []

        def _extract_annotation_values(
            keywords: tuple[str, ...],
            formatter,
        ) -> list[str]:
            results: list[str] = []
            seen: set[str] = set()
            keyword_set = tuple(key.lower() for key in keywords)
            for column in df.columns:
                column_name = str(column)
                column_lower = column_name.lower()
                column_matches = all(key in column_lower for key in keyword_set)
                series = df[column] if isinstance(df[column], pd.Series) else pd.Series(df[column])
                for raw_value in series.tolist():
                    if raw_value is None or (isinstance(raw_value, float) and pd.isna(raw_value)):
                        continue
                    formatted = ""
                    if column_matches:
                        formatted = formatter(raw_value)
                    else:
                        normalized_value = self._normalize_value(raw_value)
                        if all(key in normalized_value for key in keyword_set):
                            formatted = formatter(raw_value)
                    if not formatted and isinstance(raw_value, str):
                        normalized_raw = raw_value.strip()
                        if normalized_raw:
                            formatted = formatter(normalized_raw)
                    if formatted:
                        lowered = formatted.lower()
                        if lowered in {"", "nan", "null", "none"}:
                            continue
                        if formatted not in seen:
                            seen.add(formatted)
                            results.append(formatted)
            return results

        static_values = _extract_annotation_values(("static", "db"), self._format_db_display)
        target_values = _extract_annotation_values(("target", "rssi"), self._format_metric_display)

        annotations: list[str] = []
        if static_values:
            annotations.append(f"Static dB: {', '.join(static_values)}")
        if target_values:
            formatted_rssi = []
            for value in target_values:
                lower = value.lower()
                formatted_rssi.append(value if lower.endswith("dbm") else f"{value} dBm")
            annotations.append(f"Target RSSI: {', '.join(formatted_rssi)}")
        return annotations

    def _infer_test_type_from_path(self, path: Path) -> Optional[str]:
        if path is None:
            return None
        try:
            raw = str(path).lower()
        except Exception:
            return None
        if not raw:
            return None
        if "rvo" in raw:
            return "RVO"
        peak_keywords = {"peak_throughput", "peak-throughput", "peakthroughput"}
        if any(keyword in raw for keyword in peak_keywords) or ("peak" in raw and "throughput" in raw):
            return "PEAK_THROUGHPUT"
        if "rvr" in raw:
            return "RVR"
        return None

    def _aggregate_channel_throughput(self, group: pd.DataFrame) -> list[tuple[str, float]]:
        channel_values: list[tuple[str, float]] = []
        for channel, channel_df in group.groupby("__channel_display__", dropna=False):
            throughput_values = [
                float(v)
                for v in channel_df["__throughput_value__"].tolist()
                if isinstance(v, (int, float))
                and pd.notna(v)
                and math.isfinite(float(v))
            ]
            if not throughput_values:
                continue
            avg_value = sum(throughput_values) / len(throughput_values)
            label = self._format_pie_channel_label(channel, channel_df)
            channel_values.append((label, avg_value))
        return channel_values

    def _parse_db_numeric(self, value) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        s = str(value).strip()
        if not s:
            return None
        match = re.search(r"-?\d+(?:\.\d+)?", s)
        if not match:
            return None
        try:
            return float(match.group())
        except ValueError:
            return None

    def _group_sort_key(self, key: tuple[str, str, str, str, str]):
        standard, bandwidth, freq_band, test_type, direction = key
        standard_idx = STANDARD_ORDER_MAP.get((standard or "").lower(), len(STANDARD_ORDER_MAP))
        bandwidth_idx = BANDWIDTH_ORDER_MAP.get((bandwidth or "").lower(), len(BANDWIDTH_ORDER_MAP))
        freq_idx = FREQ_BAND_ORDER_MAP.get((freq_band or "").lower(), len(FREQ_BAND_ORDER_MAP))
        test_idx = TEST_TYPE_ORDER_MAP.get((test_type or "").upper(), len(TEST_TYPE_ORDER_MAP))
        direction_idx = DIRECTION_ORDER_MAP.get((direction or "").upper(), len(DIRECTION_ORDER_MAP))
        return (
            standard_idx,
            bandwidth_idx,
            freq_idx,
            test_idx,
            direction_idx,
            standard,
            bandwidth,
            freq_band,
            test_type,
            direction,
        )

    def _format_chart_title(
        self,
        standard: str,
        bandwidth: str,
        freq_band: str,
        test_type: str,
        direction: str,
    ) -> str:
        parts: list[str] = []
        std = (standard or "").strip()
        bw = (bandwidth or "").strip()
        freq = (freq_band or "").strip()
        tt = (test_type or "").strip().upper()
        direction = (direction or "").strip().upper()
        parts.append(std or "Unknown")
        if bw:
            parts.append(bw)
        if freq:
            parts.append(freq)
        label = self._format_test_type_label(tt)
        parts.append(label)
        if direction:
            parts.append(direction)
        return " ".join(parts).strip()

    def _format_test_type_label(self, test_type: str) -> str:
        mapping = {
            "RVR": "RVR Throughput",
            "RVO": "RVO Throughput",
            "PEAK_THROUGHPUT": "Peak Throughput",
        }
        normalized = (test_type or "").strip().upper()
        if normalized in mapping:
            return mapping[normalized]
        if not normalized:
            return "RVR Throughput"
        return f"{normalized} Throughput"

    def _collect_step_labels(self, group: pd.DataFrame) -> list[str]:
        steps: list[str] = []
        for step in group["__step__"]:
            if step and step not in steps:
                steps.append(step)
        if not steps:
            count = int(group["__throughput_value__"].notna().sum())
            if count <= 0:
                count = len(group.index)
            if count <= 0:
                return []
            steps = [str(i + 1) for i in range(count)]
        steps.sort(
            key=lambda item: (0, self._parse_db_numeric(item))
            if self._parse_db_numeric(item) is not None
            else (1, item)
        )
        return steps

    def _format_step_label(self, step: str) -> str:
        if not step:
            return ""
        formatted = self._format_db_display(step)
        return formatted or step

    @staticmethod
    def _compute_major_step_indices(count: int, max_labels: int = 18) -> list[int]:
        if count <= 0:
            return []
        if count <= max_labels:
            return list(range(count))
        stride = max(1, math.ceil(count / max_labels))
        indices = list(range(0, count, stride))
        last_index = count - 1
        if indices[-1] != last_index:
            indices.append(last_index)
        if indices[0] != 0:
            indices.insert(0, 0)
        # remove possible duplicates and keep order
        seen: set[int] = set()
        deduped: list[int] = []
        for idx in indices:
            if idx not in seen:
                seen.add(idx)
                deduped.append(idx)
        return deduped

    def _configure_step_axis(self, ax, steps: list[str], max_labels: int = 18) -> None:
        if not steps:
            ax.set_xticks([])
            ax.set_xlim(0, 1)
            return
        count = len(steps)
        positions = list(range(count))
        ax.set_xticks(positions, minor=True)
        max_index = max(1, count - 1)
        padding = min(0.4, max_index * 0.05 if max_index else 0.4)
        ax.set_xlim(-padding, max_index + padding)
        major_indices = self._compute_major_step_indices(count, max_labels=max_labels)
        major_positions = [positions[i] for i in major_indices]
        major_labels = [self._format_step_label(steps[i]) for i in major_indices]
        ax.set_xticks(major_positions)
        ax.set_xticklabels(major_labels, rotation=0)
        for label in ax.get_xticklabels():
            label.set_horizontalalignment("center")
            label.set_verticalalignment("top")

    def _format_channel_series_label(self, channel: str) -> str:
        channel = (channel or "").strip()
        return f"CH{channel}" if channel else "Unknown"

    def _make_pie_autopct(self, values: tuple[float, ...]):
        total = sum(values)

        def _formatter(pct):
            absolute = pct * total / 100.0
            return f"{pct:.1f}%\n{absolute:.1f} Mbps"

        return _formatter

    def _format_pie_channel_label(self, channel: str, df: pd.DataFrame) -> str:
        channel_name = (channel or "").strip()
        if not channel_name:
            channel_name = "Unknown"
        db_values = [value for value in df["__db_display__"].tolist() if value]
        if db_values:
            return f"CH{channel_name} {db_values[0]}dB"
        return f"CH{channel_name}"

    def _series_with_nan(self, values: list[Optional[float]]) -> list[float]:
        series: list[float] = []
        for value in values:
            series.append(math.nan if value is None else float(value))
        return series

    def _normalize_value(self, value) -> str:
        return str(value).strip().lower() if value is not None else ""

    def _normalize_step(self, value) -> Optional[str]:
        if value is None:
            return None
        s = str(value).strip()
        if not s or s.lower() in {"nan", "null"}:
            return None
        return s

    def _extract_first_non_empty(self, row: pd.Series, columns: tuple[str, ...]):
        for column in columns:
            if column not in row:
                continue
            value = row.get(column)
            if value is None:
                continue
            s = str(value).strip()
            if not s or s.lower() in {"nan", "null", "none", "n/a", "na", "-"}:
                continue
            return value
        return None

    def _safe_float(self, value) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        s = str(value).strip()
        if not s:
            return None
        lowered = s.lower()
        if lowered in {"nan", "null", "n/a", "false"}:
            return None
        normalized = s.replace("，", ",")
        match = re.search(r"-?\d+(?:\.\d+)?", normalized)
        if match:
            try:
                return float(match.group())
            except ValueError:
                return None
        try:
            return float(normalized)
        except Exception:
            return None

    def _safe_chart_name(self, title: str) -> str:
        safe = re.sub(r"[^0-9A-Za-z_-]+", "_", title).strip("_")
        return safe or "rvr_chart"
