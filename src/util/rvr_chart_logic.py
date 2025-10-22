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

        profile_mode_series = source_series("Profile_Mode", "Profile Mode", "RVO_Profile_Mode").apply(
            self._normalize_profile_mode_value
        )
        profile_value_series = source_series("Profile_Value", "Profile Value", "RVO_Profile_Value").apply(
            self._normalize_profile_value
        )
        prepared["__profile_mode__"] = profile_mode_series
        prepared["__profile_value__"] = profile_value_series
        prepared["__profile_key__"] = [
            self._build_profile_key(mode, value) for mode, value in zip(profile_mode_series, profile_value_series)
        ]
        prepared["__profile_label__"] = [
            self._format_profile_label(mode, value)
            for mode, value in zip(profile_mode_series, profile_value_series)
        ]

        angle_series = source_series(
            "Angel",
            "Angle",
            "corner",
            "Corner",
            "corner_angle",
            "Corner_Angle",
            "CornerAngle",
        )
        prepared["__angle_value__"] = angle_series.apply(self._parse_angle_value)
        prepared["__angle_display__"] = angle_series.apply(self._format_angle_display)
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
                if normalized and normalized not in {"", "null", "none", "nan"}:
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
            *,
            require_numeric: bool = False,
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
                    normalized_value = self._normalize_value(raw_value)
                    if column_matches or all(key in normalized_value for key in keyword_set):
                        formatted = formatter(raw_value)
                    if not formatted:
                        continue
                    stripped = str(formatted).strip()
                    if not stripped:
                        continue
                    if require_numeric and not re.search(r"\d", stripped):
                        continue
                    lowered = stripped.lower()
                    if lowered in {"", "nan", "null", "none"}:
                        continue
                    if stripped not in seen:
                        seen.add(stripped)
                        results.append(stripped)
            return results

        static_values = _extract_annotation_values(
            ("static", "db"),
            self._format_db_display,
            require_numeric=True,
        )
        target_values = _extract_annotation_values(
            ("target", "rssi"),
            self._format_metric_display,
            require_numeric=True,
        )

        annotations: list[str] = []
        if static_values:
            annotations.append(f"Static dB: {', '.join(static_values)}")
        if target_values:
            formatted_rssi = []
            for value in target_values:
                lower = value.lower()
                formatted_rssi.append(value if lower.endswith("dbm") else f"{value} dBm")
            annotations.append(f"Target RSSI: {', '.join(formatted_rssi)}")

        if annotations:
            print(f"[RVO] annotations collected -> {annotations}")
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

    def _collect_angle_positions(self, group: pd.DataFrame) -> list[tuple[float, str]]:
        if (
            group is None
            or group.empty
            or "__angle_value__" not in group
            or "__angle_display__" not in group
        ):
            return []

        angles: dict[float, tuple[float, str]] = {}
        values = group["__angle_value__"].tolist()
        displays = group["__angle_display__"].tolist()
        for numeric, display in zip(values, displays):
            if numeric is None:
                continue
            try:
                numeric_value = float(numeric)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(numeric_value):
                continue
            normalized = self._normalize_angle_numeric(numeric_value)
            if normalized is None:
                continue
            key = round(normalized, 4)
            label = display if isinstance(display, str) and display else self._format_angle_label_from_numeric(normalized)
            if key not in angles:
                angles[key] = (normalized, label)
        ordered_keys = sorted(angles.keys())
        return [angles[key] for key in ordered_keys]

    def _collect_rvo_channel_series(
        self, group: pd.DataFrame, angle_values: list[float]
    ) -> list[tuple[str, list[Optional[float]]]]:
        if (
            group is None
            or group.empty
            or "__angle_value__" not in group
            or "__throughput_value__" not in group
        ):
            return []

        series_data: list[tuple[str, list[Optional[float]]]] = []
        group_by_columns = ["__channel_display__"]
        if "__profile_key__" in group.columns:
            group_by_columns.append("__profile_key__")
        grouped = group.groupby(group_by_columns, dropna=False)
        for key, channel_df in grouped:
            if isinstance(key, tuple):
                channel = key[0]
            else:
                channel = key
            values: list[Optional[float]] = []
            for angle in angle_values:
                subset = self._filter_dataframe_by_angle(channel_df, angle)
                raw_values = [v for v in subset["__throughput_value__"].tolist() if v is not None]
                finite_values = [
                    float(v)
                    for v in raw_values
                    if isinstance(v, (int, float))
                    and pd.notna(v)
                    and math.isfinite(float(v))
                ]
                if finite_values:
                    values.append(sum(finite_values) / len(finite_values))
                else:
                    values.append(None)
            if any(v is not None for v in values):
                label = self._format_rvo_series_label(channel, channel_df)
                print(
                    f"[RVO] series collected -> channel={channel!r}, key={key!r}, label={label!r}, values={values}"
                )
                series_data.append((label, values))
        if not series_data:
            print("[RVO] no channel series were generated for polar plot")
        else:
            print(f"[RVO] total channel series -> {len(series_data)}")
        return series_data

    def _filter_dataframe_by_angle(self, df: pd.DataFrame, angle: float) -> pd.DataFrame:
        if "__angle_value__" not in df:
            return df.iloc[0:0]
        tolerance = 0.51
        normalized_target = self._normalize_angle_numeric(angle)
        if normalized_target is None:
            return df.iloc[0:0]

        def _matches(value) -> bool:
            if value is None:
                return False
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                return False
            if not math.isfinite(numeric_value):
                return False
            normalized_value = self._normalize_angle_numeric(numeric_value)
            if normalized_value is None:
                return False
            diff = abs((normalized_value - normalized_target + 180.0) % 360.0 - 180.0)
            return diff <= tolerance

        mask = df["__angle_value__"].apply(_matches)
        return df[mask]

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

    def _normalize_profile_mode_value(self, value) -> str:
        if value is None:
            return ""
        text = str(value).strip().lower()
        if not text or text in {"nan", "none", "null"}:
            return ""
        if text in {"target", "target_rssi", "rvo_target"}:
            return "TARGET_RSSI"
        if text in {"static", "static_db", "rvo_static"}:
            return "STATIC_DB"
        if text in {"default", "normal"}:
            return "DEFAULT"
        return text.upper()

    def _normalize_profile_value(self, value) -> str:
        if value is None:
            return ""
        if isinstance(value, (list, tuple, set)):
            items = [self._normalize_profile_value(item) for item in value]
            items = [item for item in items if item]
            return items[0] if items else ""
        text = str(value).strip()
        if not text:
            return ""
        try:
            number = float(text)
        except ValueError:
            return text
        if math.isfinite(number) and float(int(number)) == number:
            return str(int(number))
        if not math.isfinite(number):
            return ""
        return f"{number:.2f}".rstrip("0").rstrip(".")

    def _build_profile_key(self, mode: str, value: str) -> str:
        normalized_mode = (mode or "").strip().upper() or "DEFAULT"
        normalized_value = (value or "").strip()
        return f"{normalized_mode}::{normalized_value}"

    def _format_profile_label(self, mode: str, value: str) -> str:
        normalized_mode = (mode or "").strip().upper()
        normalized_value = (value or "").strip()
        if not normalized_mode and not normalized_value:
            return ""

        display_value = ""
        if normalized_value:
            trimmed = normalized_value.strip()
            numeric_tokens = re.findall(r"-?\d+(?:\.\d+)?", trimmed)
            if len(numeric_tokens) == 1 and re.fullmatch(r"[-+]?\d+(?:\.\d+)?", trimmed):
                token = numeric_tokens[0]
                try:
                    numeric_value = float(token)
                except ValueError:
                    display_value = trimmed
                else:
                    if math.isfinite(numeric_value) and float(int(numeric_value)) == numeric_value:
                        display_value = str(int(numeric_value))
                    else:
                        display_value = str(numeric_value).rstrip("0").rstrip(".")
            else:
                display_value = trimmed

        if normalized_mode == "TARGET_RSSI":
            prefix = "Target RSSI"
            return f"{prefix} {display_value}".strip()
        if normalized_mode == "STATIC_DB":
            prefix = "Static db"
            return f"{prefix} {display_value}".strip()
        if normalized_mode in {"DEFAULT", "CUSTOM"}:
            return display_value
        if display_value:
            return f"{normalized_mode.replace('_', ' ')} {display_value}".strip()
        return normalized_mode.replace('_', ' ')

    def _extract_profile_label(self, df: pd.DataFrame) -> str:
        if df is None or df.empty:
            return ""
        if "__profile_label__" in df.columns:
            for value in df["__profile_label__"]:
                if isinstance(value, str) and value.strip():
                    return value.strip()
        mode = ""
        if "__profile_mode__" in df.columns:
            for candidate in df["__profile_mode__"]:
                if isinstance(candidate, str) and candidate.strip():
                    mode = candidate.strip()
                    break
        value = ""
        if "__profile_value__" in df.columns:
            for candidate in df["__profile_value__"]:
                if isinstance(candidate, str) and candidate.strip():
                    value = candidate.strip()
                    break
        return self._format_profile_label(mode, value)

    def _extract_db_label(self, df: pd.DataFrame) -> str:
        if df is None or df.empty or "__db_display__" not in df:
            return ""
        for value in df["__db_display__"]:
            if not value:
                continue
            text = str(value).strip()
            if not text:
                continue
            lowered = text.lower()
            if lowered.endswith("db"):
                return text
            return f"{text}dB"
        return ""

    def _format_rvo_series_label(self, channel: str, df: pd.DataFrame) -> str:
        base_label = self._format_channel_series_label(channel)
        profile_label = self._extract_profile_label(df)
        if profile_label:
            final_label = f"{profile_label} {base_label}".strip()
            print(
                f"[RVO] resolved profile label -> channel={channel!r}, profile={profile_label!r}, final={final_label!r}"
            )
            return final_label
        db_label = self._extract_db_label(df)
        if db_label:
            final_label = f"{base_label} {db_label}".strip()
            print(
                f"[RVO] resolved db label -> channel={channel!r}, db={db_label!r}, final={final_label!r}"
            )
            return final_label
        print(f"[RVO] using base label -> channel={channel!r}, final={base_label!r}")
        return base_label

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

    def _parse_angle_value(self, value) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            numeric = float(value)
            if math.isfinite(numeric):
                return numeric
            return None
        s = str(value).strip()
        if not s:
            return None
        lowered = s.lower()
        if lowered in {"nan", "null", "none", "n/a", "na", "-"}:
            return None
        match = re.search(r"-?\d+(?:\.\d+)?", s)
        if not match:
            return None
        try:
            numeric = float(match.group())
        except ValueError:
            return None
        if not math.isfinite(numeric):
            return None
        return numeric

    def _normalize_angle_numeric(self, value: float) -> Optional[float]:
        if value is None or not math.isfinite(float(value)):
            return None
        normalized = float(value) % 360.0
        if normalized < 0:
            normalized += 360.0
        return normalized

    def _format_angle_label_from_numeric(self, value: float) -> str:
        if value is None or not math.isfinite(float(value)):
            return ""
        rounded = round(value)
        if abs(value - rounded) < 1e-6:
            return f"{int(rounded)}°"
        formatted = f"{value:.1f}°"
        if formatted.endswith(".0°"):
            formatted = formatted[:-3] + "°"
        return formatted

    def _format_angle_display(self, value) -> str:
        numeric = self._parse_angle_value(value)
        if numeric is None:
            return str(value).strip() if value is not None else ""
        return self._format_angle_label_from_numeric(self._normalize_angle_numeric(numeric) or numeric)

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
