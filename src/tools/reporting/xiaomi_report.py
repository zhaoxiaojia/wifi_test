from __future__ import annotations

import logging
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Mapping

import pandas as pd
from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from src.util.rvr_chart_logic import RvrChartLogic

"""Utilities to export Xiaomi Wi-Fi performance reports."""
_LOGGER = logging.getLogger(__name__)

_RVR_SCENARIO_MAPPING: Mapping[tuple[str, str, str], str] = {
    ("11n", "2.4g", "20mhz"): "11N HT20",
    ("11n", "2.4g", "40mhz"): "11N HT40",
    ("11ax", "2.4g", "20mhz"): "11AX HE20",
    ("11ax", "2.4g", "40mhz"): "11AX HE40",
    ("11ax", "5g", "80mhz"): "11AX HE80",
    ("11ac", "5g", "80mhz"): "11AC VHT80",
}

_RVO_SCENARIO_MAPPING: Mapping[tuple[str, str, str], str] = {
    ("11n", "2.4g", "20mhz"): "11N HT20",
    ("11n", "2.4g", "40mhz"): "11N HT40",
    ("11ax", "2.4g", "20mhz"): "11AX HE20",
    ("11ax", "2.4g", "40mhz"): "11AX HE40",
    ("11ax", "5g", "80mhz"): "11AX HE80",
}


def _normalize_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_key(value) -> str:
    return _normalize_text(value).lower()


def _normalize_header_label(value) -> str:
    text = _normalize_text(value)
    if not text:
        return ""
    sanitized = re.sub(r"\s+", "", text).upper()
    if sanitized.startswith("RX"):
        return "RX"
    if sanitized.startswith("TX"):
        return "TX"
    return ""


_CHANNEL_PATTERN = re.compile(r"(?:CH)?\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE)
_NUMERIC_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")


def _sanitize_channel(value) -> str:
    text = _normalize_text(value)
    if not text:
        return ""
    match = _CHANNEL_PATTERN.search(text)
    if not match:
        return ""
    number = match.group(1)
    return number.strip()


def _normalize_db(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        if math.isnan(value):
            return ""
        if float(value).is_integer():
            return str(int(value))
        return f"{float(value):.2f}".rstrip("0").rstrip(".")
    text = _normalize_text(value)
    if not text:
        return ""
    match = _NUMERIC_PATTERN.search(text)
    if not match:
        return ""
    number = match.group(0)
    if number.endswith(".0"):
        number = number[:-2]
    return number


def _normalize_angle(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        if math.isnan(value):
            return ""
        return str(int(value)) if float(value).is_integer() else f"{float(value):.2f}".rstrip("0").rstrip(".")
    text = _normalize_text(value)
    if not text:
        return ""
    match = _NUMERIC_PATTERN.search(text)
    if not match:
        return ""
    number = match.group(0)
    if number.endswith(".0"):
        number = number[:-2]
    return number


def _is_finite_number(value) -> bool:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(numeric)


def _write_cell_if_higher(ws: Worksheet, row: int, column: int, value: float) -> None:
    if not _is_finite_number(value):
        return
    numeric = float(value)
    cell = ws.cell(row=row, column=column)
    existing = cell.value
    if existing is None:
        cell.value = round(numeric, 2)
        return
    if _is_finite_number(existing):
        if numeric > float(existing):
            cell.value = round(numeric, 2)


def _select_closest_label(value: str, candidates: Iterable[str]) -> tuple[str | None, bool]:
    """Return the closest candidate label for *value* and whether an adjustment was required."""
    candidate_list = [c for c in candidates if c is not None and str(c).strip() != ""]
    if not value:
        return (None, False)
    if value in candidate_list:
        return (value, False)
    try:
        target = float(value)
    except (TypeError, ValueError):
        return (None, False)
    best_label: str | None = None
    best_diff: float | None = None
    for candidate in candidate_list:
        try:
            candidate_value = float(candidate)
        except (TypeError, ValueError):
            continue
        diff = abs(candidate_value - target)
        if best_diff is None or diff < best_diff or (math.isclose(diff, best_diff) and candidate_value < float(best_label or candidate_value)):
            best_diff = diff
            best_label = str(int(candidate_value)) if float(candidate_value).is_integer() else str(candidate_value)
    return (best_label, best_label is not None and best_label != value)


@dataclass
class _RvrBlock:
    sheet: Worksheet
    scenario: str
    rows_by_db: Dict[str, int] = field(default_factory=dict)
    rx_columns: Dict[str, int] = field(default_factory=dict)
    tx_columns: Dict[str, int] = field(default_factory=dict)
    rx_rssi_columns: Dict[str, int] = field(default_factory=dict)
    tx_rssi_columns: Dict[str, int] = field(default_factory=dict)
    template_row: int = 0


@dataclass
class _RvoDirectionBlock:
    rows_by_channel: Dict[str, Dict[str, int]] = field(default_factory=dict)
    angle_columns: Dict[str, int] = field(default_factory=dict)
    header_row: int = 0
    angle_row: int = 0
    data_start_row: int = 0
    data_end_row: int = 0
    summary_start_col: int = 0


@dataclass
class _RvoBlock:
    sheet: Worksheet
    scenario: str
    directions: Dict[str, _RvoDirectionBlock] = field(default_factory=dict)


class _TemplateLayout:
    """Parse Xiaomi template structure for RVR/RVO sections."""

    def __init__(self, workbook):
        self.workbook = workbook
        self.rvr_sheet = workbook["Coffey RVR"]
        self.rvo_sheet = workbook["Coffey RVO"]
        self.rvr_blocks = self._parse_rvr_blocks()
        self.rvo_blocks = self._parse_rvo_blocks()

    def _parse_rvr_blocks(self) -> Dict[str, _RvrBlock]:
        sheet = self.rvr_sheet
        item_rows = [
            cell.row for cell in sheet["A"] if _normalize_text(cell.value) == "Item"
        ]
        max_row = sheet.max_row
        blocks: Dict[str, _RvrBlock] = {}
        for index, item_row in enumerate(item_rows):
            scenario_value = sheet.cell(row=item_row + 2, column=1).value
            scenario = _normalize_text(scenario_value)
            if not scenario:
                continue
            next_row = item_rows[index + 1] if index + 1 < len(item_rows) else max_row + 1
            rows_by_db = self._collect_rvr_rows(sheet, item_row + 2, next_row - 1)
            rx_columns, tx_columns, rx_rssi_columns, tx_rssi_columns = self._extract_rvr_channel_columns(
                sheet, item_row, item_row + 1
            )
            template_row = min(rows_by_db.values()) if rows_by_db else item_row + 2
            blocks[scenario.upper()] = _RvrBlock(
                sheet=sheet,
                scenario=scenario,
                rows_by_db=rows_by_db,
                rx_columns=rx_columns,
                tx_columns=tx_columns,
                rx_rssi_columns=rx_rssi_columns,
                tx_rssi_columns=tx_rssi_columns,
                template_row=template_row,
            )
        return blocks

    @staticmethod
    def _collect_rvr_rows(sheet: Worksheet, start_row: int, end_row: int) -> Dict[str, int]:
        mapping: Dict[str, int] = {}
        for row in range(start_row, end_row + 1):
            db_value = sheet.cell(row=row, column=2).value
            normalized = _normalize_db(db_value)
            if normalized:
                mapping[normalized] = row
        return mapping

    @staticmethod
    def _extract_rvr_channel_columns(
        sheet: Worksheet, header_row: int, channel_row: int
    ) -> tuple[Dict[str, int], Dict[str, int], Dict[str, int], Dict[str, int]]:
        rx_columns: Dict[str, int] = {}
        tx_columns: Dict[str, int] = {}
        rx_rssi_columns: Dict[str, int] = {}
        tx_rssi_columns: Dict[str, int] = {}
        max_col = sheet.max_column
        last_section: str | None = None
        for column in range(1, max_col + 1):
            header_val = sheet.cell(row=header_row, column=column).value
            header_text = _normalize_text(header_val).upper()
            if header_text and "ITEM" in header_text and column > 1:
                last_section = None
                continue

            section: str | None = None
            if "RSSI" in header_text:
                if "RX" in header_text:
                    section = "RX_RSSI"
                elif "TX" in header_text:
                    section = "TX_RSSI"
            elif "RX" in header_text and "MBPS" in header_text:
                section = "RX_TPUT"
            elif "TX" in header_text and "MBPS" in header_text:
                section = "TX_TPUT"

            if section is None:
                # inherit previous section unless header explicitly resets
                section = last_section
            else:
                last_section = section

            if section not in {"RX_TPUT", "TX_TPUT", "RX_RSSI", "TX_RSSI"}:
                continue

            channel_value = sheet.cell(row=channel_row, column=column).value
            channel_id = _sanitize_channel(channel_value)
            if not channel_id:
                continue
            if section == "RX_TPUT":
                rx_columns[channel_id] = column
            elif section == "TX_TPUT":
                tx_columns[channel_id] = column
            elif section == "RX_RSSI":
                rx_rssi_columns[channel_id] = column
            elif section == "TX_RSSI":
                tx_rssi_columns[channel_id] = column
        return rx_columns, tx_columns, rx_rssi_columns, tx_rssi_columns

    def _parse_rvo_blocks(self) -> Dict[str, _RvoBlock]:
        sheet = self.rvo_sheet
        item_rows = [
            cell.row for cell in sheet["A"] if _normalize_text(cell.value) == "Item"
        ]
        max_row = sheet.max_row
        blocks: Dict[str, _RvoBlock] = {}
        for index, item_row in enumerate(item_rows):
            scenario_value = sheet.cell(row=item_row + 2, column=1).value
            scenario = _normalize_text(scenario_value)
            if not scenario:
                continue
            next_row = item_rows[index + 1] if index + 1 < len(item_rows) else max_row + 1
            directions = self._extract_rvo_directions(sheet, item_row, next_row)
            blocks[scenario.upper()] = _RvoBlock(sheet=sheet, scenario=scenario, directions=directions)
        return blocks

    def _extract_rvo_directions(self, sheet: Worksheet, start_row: int, stop_row: int) -> Dict[str, _RvoDirectionBlock]:
        directions: Dict[str, _RvoDirectionBlock] = {}
        row = start_row
        while row < stop_row:
            header_label = _normalize_header_label(sheet.cell(row=row, column=4).value)
            if header_label not in {"RX", "TX"}:
                row += 1
                continue
            header_row = row
            angle_row = row + 1
            angle_columns = self._extract_angle_columns(sheet, angle_row)
            rows_by_channel: Dict[str, Dict[str, int]] = {}
            current_channel = ""
            data_row = angle_row + 1
            data_start_row = data_row
            last_data_row = angle_row
            while data_row < stop_row:
                next_header = _normalize_header_label(sheet.cell(row=data_row, column=4).value)
                if next_header in {"RX", "TX"}:
                    break
                att_value = sheet.cell(row=data_row, column=3).value
                if not _normalize_text(att_value):
                    data_row += 1
                    continue
                channel_cell = sheet.cell(row=data_row, column=2).value
                channel_id = _sanitize_channel(channel_cell) or current_channel
                if not channel_id:
                    data_row += 1
                    continue
                current_channel = channel_id
                db_key = _normalize_db(att_value)
                if not db_key:
                    data_row += 1
                    continue
                rows_by_channel.setdefault(channel_id, {})[db_key] = data_row
                last_data_row = data_row
                data_row += 1
            summary_start_col = (max(angle_columns.values()) + 1) if angle_columns else 0
            directions[header_label] = _RvoDirectionBlock(
                rows_by_channel=rows_by_channel,
                angle_columns=angle_columns,
                header_row=header_row,
                angle_row=angle_row,
                data_start_row=data_start_row,
                data_end_row=last_data_row if last_data_row >= data_start_row else data_start_row - 1,
                summary_start_col=summary_start_col,
            )
            row = data_row
        return directions

    @staticmethod
    def _extract_angle_columns(sheet: Worksheet, angle_row: int) -> Dict[str, int]:
        mapping: Dict[str, int] = {}
        max_col = sheet.max_column
        for column in range(1, max_col + 1):
            angle_value = sheet.cell(row=angle_row, column=column).value
            normalized = _normalize_angle(angle_value)
            if normalized:
                mapping[normalized] = column
        return mapping

    @staticmethod
    def _relocate_formula(value, source_row: int, target_row: int):
        if not isinstance(value, str) or not value.startswith("="):
            return value

        def repl(match: re.Match[str]) -> str:
            col = match.group(1)
            row_str = match.group(2)
            try:
                row_val = int(row_str)
            except ValueError:
                return match.group(0)
            if row_val == source_row:
                return f"{col}{target_row}"
            return match.group(0)

        return re.sub(r"(\$?[A-Z]{1,3})\$?(\d+)", repl, value)

    @staticmethod
    def _copy_row(sheet: Worksheet, source_row: int, target_row: int) -> None:
        max_col = sheet.max_column
        for column in range(1, max_col + 1):
            source = sheet.cell(row=source_row, column=column)
            target = sheet.cell(row=target_row, column=column)
            if source.has_style:
                target._style = source._style
            target.value = _TemplateLayout._relocate_formula(source.value, source_row, target_row)
            target.number_format = source.number_format
            target.protection = source.protection
            target.alignment = source.alignment
            target.font = source.font
            target.fill = source.fill
            target.border = source.border

    @staticmethod
    def _copy_column_styles(
        sheet: Worksheet,
        source_col: int,
        target_col: int,
        start_row: int,
        end_row: int,
    ) -> None:
        for row in range(start_row, end_row + 1):
            source = sheet.cell(row=row, column=source_col)
            target = sheet.cell(row=row, column=target_col)
            if source.has_style:
                target._style = source._style
            target.value = source.value
            target.number_format = source.number_format
            target.protection = source.protection
            target.alignment = source.alignment
            target.font = source.font
            target.fill = source.fill
            target.border = source.border

    def _adjust_rvr_mappings(self, start_row: int, delta: int) -> None:
        for block in self.rvr_blocks.values():
            for key, row in list(block.rows_by_db.items()):
                if row >= start_row:
                    block.rows_by_db[key] = row + delta
            if block.template_row >= start_row:
                block.template_row += delta

    def _set_rvr_label(self, block: _RvrBlock, row_index: int, db_key: str) -> None:
        sheet = block.sheet
        primary = sheet.cell(row=row_index, column=2)
        secondary = sheet.cell(row=row_index, column=24)
        try:
            numeric = float(db_key)
        except (TypeError, ValueError):
            primary.value = db_key
            secondary.value = db_key
            return
        if math.isfinite(numeric) and numeric.is_integer():
            value = int(numeric)
        else:
            value = numeric
        primary.value = value
        secondary.value = value

    @staticmethod
    def _format_db_label(db_key: str) -> str:
        try:
            numeric = float(db_key)
        except (TypeError, ValueError):
            return str(db_key)
        if math.isfinite(numeric) and numeric.is_integer():
            return f"{int(numeric)}"
        return f"{numeric:.2f}".rstrip("0").rstrip(".")

    @staticmethod
    def _format_angle_label(angle_key: str) -> str:
        try:
            numeric = float(angle_key)
        except (TypeError, ValueError):
            return str(angle_key)
        if math.isfinite(numeric) and numeric.is_integer():
            return f"{int(numeric)}"
        return f"{numeric:.2f}".rstrip("0").rstrip(".")

    def _clear_rvr_measurements(self, block: _RvrBlock, row_index: int) -> None:
        columns = (
            set(block.rx_columns.values())
            | set(block.tx_columns.values())
            | set(block.rx_rssi_columns.values())
            | set(block.tx_rssi_columns.values())
        )
        for column in columns:
            block.sheet.cell(row=row_index, column=column).value = None

    def _insert_rvr_row(self, block: _RvrBlock, db_key: str) -> int:
        try:
            target_value = float(db_key)
        except (TypeError, ValueError):
            target_value = math.inf
        sorted_rows = sorted(
            ((float(k), row) for k, row in block.rows_by_db.items() if k not in ("", None)),
            key=lambda item: item[0],
        )
        insert_position = None
        for value, row in sorted_rows:
            if target_value < value:
                insert_position = row
                break
        if insert_position is None:
            insert_position = max(block.rows_by_db.values(), default=block.template_row) + 1
        block.sheet.insert_rows(insert_position)
        self._adjust_rvr_mappings(insert_position, 1)
        self._copy_row(block.sheet, block.template_row, insert_position)
        self._clear_rvr_measurements(block, insert_position)
        self._set_rvr_label(block, insert_position, db_key)
        block.rows_by_db[db_key] = insert_position
        _LOGGER.info(
            "Inserted RVR row for scenario %s at attenuation %s dB (row %s)",
            block.scenario,
            db_key,
            insert_position,
        )
        return insert_position

    def ensure_rvr_row(self, block: _RvrBlock, db_key: str) -> int:
        if db_key in block.rows_by_db:
            row_index = block.rows_by_db[db_key]
            self._set_rvr_label(block, row_index, db_key)
            return row_index
        resolved_key, _ = _select_closest_label(db_key, block.rows_by_db.keys())
        if resolved_key:
            row_index = block.rows_by_db.pop(resolved_key)
            block.rows_by_db[db_key] = row_index
            self._set_rvr_label(block, row_index, db_key)
            self._clear_rvr_measurements(block, row_index)
            return row_index
        return self._insert_rvr_row(block, db_key)

    def _adjust_rvo_column_mappings(self, insert_col: int, delta: int) -> None:
        for block in self.rvo_blocks.values():
            for dir_block in block.directions.values():
                for key, col in list(dir_block.angle_columns.items()):
                    if col >= insert_col:
                        dir_block.angle_columns[key] = col + delta
                if dir_block.summary_start_col and dir_block.summary_start_col >= insert_col:
                    dir_block.summary_start_col += delta

    def _set_rvo_angle_label(self, block: _RvoBlock, dir_block: _RvoDirectionBlock, column: int, angle_key: str) -> None:
        label = self._format_angle_label(angle_key)
        block.sheet.cell(row=dir_block.angle_row, column=column).value = f"{label}锟斤拷"

    def _clear_rvo_column(self, block: _RvoBlock, dir_block: _RvoDirectionBlock, column: int) -> None:
        for row_index in range(dir_block.data_start_row, dir_block.data_end_row + 1):
            block.sheet.cell(row=row_index, column=column).value = None

    def _insert_rvo_angle(self, block: _RvoBlock, dir_block: _RvoDirectionBlock, angle_key: str) -> int:
        try:
            target_value = float(angle_key)
        except (TypeError, ValueError):
            target_value = math.inf
        sorted_cols = sorted(
            ((float(k), col) for k, col in dir_block.angle_columns.items() if k not in ("", None)),
            key=lambda item: item[0],
        )
        insert_col = dir_block.summary_start_col if dir_block.summary_start_col else (sorted_cols[0][1] if sorted_cols else 4)
        for value, col in sorted_cols:
            if target_value < value:
                insert_col = col
                break
        block.sheet.insert_cols(insert_col)
        self._adjust_rvo_column_mappings(insert_col, 1)
        existing_columns = [col for col in dir_block.angle_columns.values()]
        reference_col = min(existing_columns) if existing_columns else insert_col + 1
        reference_col = max(reference_col, 1)
        self._copy_column_styles(
            block.sheet,
            reference_col,
            insert_col,
            dir_block.header_row,
            dir_block.data_end_row if dir_block.data_end_row >= dir_block.data_start_row else dir_block.header_row,
        )
        if dir_block.summary_start_col == 0:
            dir_block.summary_start_col = insert_col + 1
        dir_block.angle_columns[angle_key] = insert_col
        self._set_rvo_angle_label(block, dir_block, insert_col, angle_key)
        self._clear_rvo_column(block, dir_block, insert_col)
        _LOGGER.info(
            "Inserted RVO angle column for scenario %s (%s) at %s° (column %s)",
            block.scenario,
            dir_block,
            angle_key,
            insert_col,
        )
        return insert_col

    def ensure_rvo_angle(self, block: _RvoBlock, dir_block: _RvoDirectionBlock, angle_key: str) -> int:
        angle_key = angle_key or ""
        if angle_key in dir_block.angle_columns:
            column = dir_block.angle_columns[angle_key]
            self._set_rvo_angle_label(block, dir_block, column, angle_key)
            return column
        resolved_key, _ = _select_closest_label(angle_key, dir_block.angle_columns.keys())
        if resolved_key:
            column = dir_block.angle_columns.pop(resolved_key)
            dir_block.angle_columns[angle_key] = column
            self._set_rvo_angle_label(block, dir_block, column, angle_key)
            self._clear_rvo_column(block, dir_block, column)
            return column
        return self._insert_rvo_angle(block, dir_block, angle_key)

    def _adjust_rvo_row_mappings(self, insert_row: int, delta: int) -> None:
        for block in self.rvo_blocks.values():
            for dir_block in block.directions.values():
                for channel, mappings in dir_block.rows_by_channel.items():
                    for key, row in list(mappings.items()):
                        if row >= insert_row:
                            mappings[key] = row + delta
                if dir_block.header_row >= insert_row:
                    dir_block.header_row += delta
                    dir_block.angle_row += delta
                    dir_block.data_start_row += delta
                    dir_block.data_end_row += delta
                elif dir_block.data_end_row >= insert_row:
                    dir_block.data_end_row += delta

    def _set_rvo_row_label(
        self,
        block: _RvoBlock,
        dir_block: _RvoDirectionBlock,
        channel_id: str,
        row_index: int,
        db_key: str,
    ) -> None:
        sheet = block.sheet
        sheet.cell(row=row_index, column=2).value = f"CH{channel_id}"
        sheet.cell(row=row_index, column=3).value = f"{self._format_db_label(db_key)}dB"

    def _clear_rvo_row(self, block: _RvoBlock, dir_block: _RvoDirectionBlock, row_index: int) -> None:
        for column in dir_block.angle_columns.values():
            block.sheet.cell(row=row_index, column=column).value = None

    def _insert_rvo_row(
        self,
        block: _RvoBlock,
        dir_block: _RvoDirectionBlock,
        channel_id: str,
        db_key: str,
    ) -> int:
        channel_rows = dir_block.rows_by_channel.setdefault(channel_id, {})
        try:
            target_value = float(db_key)
        except (TypeError, ValueError):
            target_value = math.inf
        sorted_rows = sorted(
            ((float(k), row, k) for k, row in channel_rows.items() if k not in ("", None)),
            key=lambda item: item[0],
        )
        insert_position: int
        for value, row_index, _ in sorted_rows:
            if target_value < value:
                insert_position = row_index
                break
        else:
            existing_rows = [row for _, row, _ in sorted_rows]
            max_current_row = max(existing_rows) if existing_rows else dir_block.data_start_row - 1
            subsequent_rows = [
                row
                for other_channel, mappings in dir_block.rows_by_channel.items()
                if other_channel != channel_id
                for row in mappings.values()
                if row > max_current_row
            ]
            insert_position = min(subsequent_rows) if subsequent_rows else dir_block.data_end_row + 1
        block.sheet.insert_rows(insert_position)
        self._adjust_rvo_row_mappings(insert_position, 1)
        reference_row = sorted_rows[0][1] if sorted_rows else dir_block.data_start_row
        self._copy_row(block.sheet, reference_row, insert_position)
        self._clear_rvo_row(block, dir_block, insert_position)
        self._set_rvo_row_label(block, dir_block, channel_id, insert_position, db_key)
        channel_rows[db_key] = insert_position
        _LOGGER.info(
            "Inserted RVO attenuation row for scenario %s channel %s at %s dB (row %s)",
            block.scenario,
            channel_id,
            db_key,
            insert_position,
        )
        return insert_position

    def ensure_rvo_row(
        self,
        block: _RvoBlock,
        dir_block: _RvoDirectionBlock,
        channel_id: str,
        db_key: str,
    ) -> int:
        channel_rows = dir_block.rows_by_channel.setdefault(channel_id, {})
        if db_key in channel_rows:
            row_index = channel_rows[db_key]
            self._set_rvo_row_label(block, dir_block, channel_id, row_index, db_key)
            return row_index
        resolved_key, _ = _select_closest_label(db_key, channel_rows.keys())
        if resolved_key:
            row_index = channel_rows.pop(resolved_key)
            channel_rows[db_key] = row_index
            self._set_rvo_row_label(block, dir_block, channel_id, row_index, db_key)
            self._clear_rvo_row(block, dir_block, row_index)
            return row_index
        return self._insert_rvo_row(block, dir_block, channel_id, db_key)


class _DataLoader(RvrChartLogic):
    """Load and prepare CSV data."""

    def __init__(self, forced_type: str | None = None) -> None:
        super().__init__()
        self._forced_type = forced_type.upper() if forced_type else None
        if self._forced_type:
            self._selected_test_type = self._forced_type

    def load(self, path: Path) -> pd.DataFrame:
        df = self._load_rvr_dataframe(path)
        if df is None or df.empty:
            return pd.DataFrame()
        if self._forced_type:
            df["__test_type_display__"] = self._forced_type
        df["__standard_key__"] = df["__standard_display__"].astype(str).str.lower()
        df["__bandwidth_key__"] = df["__bandwidth_display__"].astype(str).str.lower()
        df["__freq_key__"] = df["__freq_band_display__"].astype(str).str.lower()
        df["__direction_key__"] = df["__direction_display__"].astype(str).str.upper()
        df["__channel_key__"] = df["__channel_display__"].apply(_sanitize_channel)
        df["__db_key__"] = df["__step__"].apply(_normalize_db)
        df["__angle_key__"] = df["__angle_display__"].apply(_normalize_angle)
        return df


def _populate_rvr(layout: _TemplateLayout, df: pd.DataFrame) -> None:
    if df.empty:
        _LOGGER.info("Populate RVR skipped: dataframe empty")
        return
    sheet = layout.rvr_sheet
    scenario_stats: dict[str, Counter] = defaultdict(Counter)
    for name, block in layout.rvr_blocks.items():
        _LOGGER.debug(
            "RVR block mapping [%s]: rows=%s rx=%s tx=%s rx_rssi=%s tx_rssi=%s",
            name,
            len(block.rows_by_db),
            block.rx_columns,
            block.tx_columns,
            block.rx_rssi_columns,
            block.tx_rssi_columns,
        )
    for _, row_data in df.iterrows():
        scenario_key = (
            row_data.get("__standard_key__", ""),
            row_data.get("__freq_key__", ""),
            row_data.get("__bandwidth_key__", ""),
        )
        scenario_name = _RVR_SCENARIO_MAPPING.get(scenario_key)
        if not scenario_name:
            scenario_stats["_UNKNOWN"]["unknown_scenario"] += 1
            continue
        block = layout.rvr_blocks.get(scenario_name.upper())
        if block is None:
            scenario_stats[scenario_name]["missing_block"] += 1
            continue
        direction = row_data.get("__direction_key__", "")
        stats = scenario_stats[scenario_name]
        stats["total"] += 1
        if direction not in {"RX", "TX"}:
            stats["bad_direction"] += 1
            continue
        channel_id = row_data.get("__channel_key__", "")
        db_key = row_data.get("__db_key__", "")
        if not channel_id or not db_key:
            stats["missing_channel_or_db"] += 1
            continue
        columns_map = block.rx_columns if direction == "RX" else block.tx_columns
        column_index = columns_map.get(channel_id)
        if not column_index:
            stats["missing_channel_column"] += 1
            continue
        row_index = layout.ensure_rvr_row(block, db_key)
        throughput = row_data.get("__throughput_value__", None)
        if throughput is None:
            stats["missing_throughput"] += 1
            continue
        stats["written"] += 1
        _write_cell_if_higher(sheet, row_index, column_index, throughput)

        rssi_value = row_data.get("RSSI")
        if rssi_value is None or (isinstance(rssi_value, float) and pd.isna(rssi_value)):
            rssi_value = row_data.get("__rssi_display__")
        if rssi_value not in (None, ""):
            try:
                rssi_numeric = float(rssi_value)
            except (TypeError, ValueError):
                rssi_numeric = None
            if rssi_numeric is not None:
                rssi_map = block.rx_rssi_columns if direction == "RX" else block.tx_rssi_columns
                rssi_col = rssi_map.get(channel_id)
                if rssi_col:
                    sheet.cell(row=row_index, column=rssi_col).value = rssi_numeric
                    stats["written_rssi"] += 1
                else:
                    stats["missing_rssi_column"] += 1
    for scenario_name, counts in scenario_stats.items():
        _LOGGER.info("RVR populate summary [%s]: %s", scenario_name, dict(counts))


def _populate_rvo(layout: _TemplateLayout, df: pd.DataFrame) -> None:
    if df.empty:
        _LOGGER.info("Populate RVO skipped: dataframe empty")
        return
    sheet = layout.rvo_sheet
    scenario_stats: dict[str, Counter] = defaultdict(Counter)
    for _, row_data in df.iterrows():
        scenario_key = (
            row_data.get("__standard_key__", ""),
            row_data.get("__freq_key__", ""),
            row_data.get("__bandwidth_key__", ""),
        )
        scenario_name = _RVO_SCENARIO_MAPPING.get(scenario_key)
        if not scenario_name:
            scenario_stats["_UNKNOWN"]["unknown_scenario"] += 1
            continue
        block = layout.rvo_blocks.get(scenario_name.upper())
        if block is None:
            scenario_stats[scenario_name]["missing_block"] += 1
            continue
        direction = row_data.get("__direction_key__", "")
        dir_block = block.directions.get(direction)
        if dir_block is None:
            scenario_stats[scenario_name]["bad_direction"] += 1
            continue
        channel_id = row_data.get("__channel_key__", "")
        db_key = row_data.get("__db_key__", "")
        angle_key = row_data.get("__angle_key__", "")
        if not channel_id or not db_key or not angle_key:
            scenario_stats[scenario_name]["missing_channel_or_db_or_angle"] += 1
            continue
        column_index = layout.ensure_rvo_angle(block, dir_block, angle_key)
        row_index = layout.ensure_rvo_row(block, dir_block, channel_id, db_key)
        throughput = row_data.get("__throughput_value__", None)
        if throughput is None:
            scenario_stats[scenario_name]["missing_throughput"] += 1
            continue
        scenario_stats[scenario_name]["written"] += 1
        _write_cell_if_higher(sheet, row_index, column_index, throughput)
    for scenario_name, counts in scenario_stats.items():
        _LOGGER.info("RVO populate summary [%s]: %s", scenario_name, dict(counts))


def generate_xiaomi_report(
    result_file: Path | str,
    template_path: Path | str,
    output_path: Path | str,
    forced_test_type: str | None = None,
) -> Path:
    """Populate Xiaomi Wi-Fi report template with available performance data.

    Parameters
    ----------
    result_file:
        Path to the aggregated CSV file produced by the performance runner.
    template_path:
        Baseline Excel template path.
    output_path:
        Destination path for the generated workbook.
    forced_test_type:
        Optional explicit test type selected by the user (`"RVR"` or `"RVO"`). When
        provided, the data loader skips heuristic detection and treats all rows as
        belonging to the specified type.

    Returns
    -------
    Path
        The absolute path to the saved report.
    """

    template = Path(template_path)
    output = Path(output_path)
    result_path = Path(result_file)

    if forced_test_type:
        _LOGGER.info("Forced test type received: %s", forced_test_type)

    if not template.exists():
        raise FileNotFoundError(f"Template file not found: {template}")

    workbook = load_workbook(template, data_only=False)
    layout = _TemplateLayout(workbook)

    if result_path.exists():
        loader = _DataLoader(forced_type=forced_test_type)
        df = loader.load(result_path)
        if not df.empty:
            type_series = df.get("__test_type_display__")
            if type_series is not None:
                type_counts = (
                    type_series.fillna("UNKNOWN")
                    .astype(str)
                    .str.upper()
                    .value_counts()
                    .to_dict()
                )
            else:
                type_counts = {}
            _LOGGER.info(
                "Loaded %s rows from %s (test types=%s)",
                len(df),
                result_path,
                ", ".join(f"{k}:{v}" for k, v in type_counts.items()) or "NONE",
            )
            if type_counts:
                df["_type_key"] = df["__test_type_display__"].astype(str).str.upper()
                rvr_df = df[df["_type_key"] == "RVR"]
                rvo_df = df[df["_type_key"] == "RVO"]
                _LOGGER.info("RVR rows detected: %s | RVO rows detected: %s", len(rvr_df), len(rvo_df))
                if not rvr_df.empty:
                    _populate_rvr(layout, rvr_df)
                if not rvo_df.empty:
                    _populate_rvo(layout, rvo_df)
            else:
                _LOGGER.info("Test type column missing; default to RVR population.")
                _populate_rvr(layout, df)
        else:
            _LOGGER.warning("Result CSV %s contains no rows after parsing.", result_path)
            _populate_rvr(layout, df)
    else:
        _LOGGER.warning("Result CSV not found for Xiaomi report: %s", result_path)

    output.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output)
    return output.resolve()


__all__ = ["generate_xiaomi_report"]
