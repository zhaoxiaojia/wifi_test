from __future__ import annotations

import base64
import csv
import logging
import math
from collections import Counter
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from openpyxl import Workbook
from openpyxl.chart import Reference, ScatterChart, Series
from openpyxl.chart.axis import ChartLines
from openpyxl.chart.layout import Layout, ManualLayout
from openpyxl.chart.legend import Legend
from openpyxl.chart.marker import Marker
from openpyxl.chart.shapes import GraphicalProperties
from openpyxl.drawing.line import LineProperties
from openpyxl.drawing.image import Image
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from src.test.performance import get_rvo_static_db_list, get_rvo_target_rssi_list
from src.tools.performance.rvr_chart_generator import PerformanceRvrChartGenerator
LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Style constants derived from Demo.xlsx
# ---------------------------------------------------------------------------

COLUMN_WIDTHS: Dict[str, float] = {
    "A": 13.75,
    "B": 12.625,
    "C": 11.5,
    "D": 15.0,
    "E": 14.875,
    "F": 15.125,
    "G": 18.375,
    "H": 16.125,
    "I": 14.375,
    "J": 15.0,
    "K": 12.25,
    "L": 13.5,
    "M": 12.5,
    "N": 14.0,
    "O": 12.25,
}

ROW_HEIGHT_TITLE = 42.95

CHART_COLUMN_GAP = 1
CHART_TITLE_ROW = 4
CHART_MIN_TOP_ROW = 5
CHART_VERTICAL_HEIGHT_ROWS = 18

COLOR_BRAND_BLUE = "2D529F"
COLOR_SUBHEADER = "B4C6E7"
COLOR_RATE_PRIMARY = "FFF2CC"
COLOR_RATE_SECONDARY = "D9E1F2"
COLOR_RSSI_RX = "CFE2F3"
COLOR_RSSI_TX = "E2F0D9"
COLOR_GRIDLINE = "BFBFBF"
SERIES_COLORS = [
    "2D529F",  # brand blue
    "FF8C00",  # orange
    "2CA02C",  # green
    "9467BD",  # purple
    "D62728",  # red
    "17BECF",  # teal
    "8C564B",  # brown
]

FONT_TITLE = Font(name="Arial", color="FFFFFF", bold=True, size=20)
FONT_SECTION = Font(name="Arial", color="1F4E78", bold=True, size=16)
FONT_HEADER = Font(name="Arial", color="FFFFFF", bold=True, size=11)
FONT_SUBHEADER = Font(name="Arial", color="1F4E78", bold=True, size=11)
FONT_BODY = Font(name="Arial", color="333333", size=11)
FONT_STANDARD = Font(name="Arial", color="333333", size=11)

ALIGN_CENTER_WRAP = Alignment(horizontal="center", vertical="center", wrap_text=True)
ALIGN_CENTER = Alignment(horizontal="center", vertical="center")
ALIGN_LEFT_WRAP = Alignment(horizontal="left", vertical="center", wrap_text=True)

BORDER_THIN = Border(
    left=Side(style="thin", color="8A8A8A"),
    right=Side(style="thin", color="8A8A8A"),
    top=Side(style="thin", color="8A8A8A"),
    bottom=Side(style="thin", color="8A8A8A"),
)

LOGO_PNG_BASE64 = (
    "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"
)


# ---------------------------------------------------------------------------
# Scenario model
# ---------------------------------------------------------------------------


DEFAULT_ATTENUATIONS = list(range(0, 78, 3))


@dataclass
class ProjectScenario:
    key: str = "SCENARIO|DEFAULT"
    freq: str = "5G"
    standard: str = "Auto"
    bandwidth: str = "20/40/80 MHz"
    channel_label: str = "CH36"
    angle_label: str = "0deg"
    attenuation_steps: List[float] = field(default_factory=lambda: DEFAULT_ATTENUATIONS.copy())
    step_summary: str = ""
    rx_values: Dict[float, float] = field(default_factory=dict)
    tx_values: Dict[float, float] = field(default_factory=dict)
    rssi_rx: Dict[float, float] = field(default_factory=dict)
    rssi_tx: Dict[float, float] = field(default_factory=dict)

    @property
    def title(self) -> str:
        return f"{self.freq.upper()} {self.standard.upper()} {self.bandwidth.upper()}"

    @property
    def subtitle(self) -> str:
        parts = [self.freq, self.standard.upper(), self.bandwidth]
        return " ".join(part for part in parts if part)

    @property
    def channel(self) -> str:
        return self.channel_label


@dataclass
class ScenarioGroup:
    key: str
    freq: str
    standard: str
    bandwidth: str
    angle_label: str
    attenuation_steps: List[float] = field(default_factory=list)
    step_summary: str = ""
    channels: List[ProjectScenario] = field(default_factory=list)
    raw_keys: set[str] = field(default_factory=set)
    test_type: str = "RVR"

    @property
    def title(self) -> str:
        return f"{self.freq.upper()} {self.standard.upper()} {self.bandwidth.upper()}"

    @property
    def summary_label(self) -> str:
        parts = [self.freq, self.standard.upper(), self.bandwidth]
        return " ".join(part for part in parts if part)


@dataclass
class GroupLayout:
    rx_cols: List[int]
    tx_cols: List[int]
    aml_standard_col: int
    aml_result_col: int
    rssi_start_col: int
    right_rx_cols: List[int]
    right_tx_cols: List[int]



def _normalize_scenario_key(value: Optional[str]) -> str:
    text = str(value or "").strip()
    if not text:
        return "SCENARIO|DEFAULT"
    return text


def _group_base_key(raw_key: Optional[str]) -> str:
    normalized = _normalize_scenario_key(raw_key)
    if not normalized:
        return "SCENARIO|DEFAULT"
    parts = normalized.split("|")
    filtered = [part for part in parts if not part.upper().startswith("CHANNEL=")]
    if not filtered:
        return normalized
    return "|".join(filtered)


def _normalize_test_type(value: Optional[str]) -> str:
    """Normalize the provided test type string.

    Empty inputs intentionally return an empty string so the caller can decide
    whether to fall back to a default (usually "RVR").
    """

    text = str(value or "").strip()
    if not text:
        return ""
    return text.upper()


def _detect_row_test_type(row: dict[str, object]) -> str:
    candidates = (
        row.get("__test_type_display__"),
        row.get("Test_Type"),
        row.get("Test Type"),
        row.get("TestType"),
        row.get("Test"),
    )
    for candidate in candidates:
        text = str(candidate or "").strip()
        if not text:
            continue
        normalized = _normalize_test_type(text)
        if normalized:
            return normalized
    has_profile = any(
        str(row.get(name) or "").strip()
        for name in ("Profile_Mode", "Profile Mode", "RVO_Profile_Mode")
    )
    if has_profile:
        return "RVO"
    return "RVR"


def _build_group_layout(channel_count: int) -> GroupLayout:
    base_col = 3  # Column C
    rx_cols: list[int] = []
    tx_cols: list[int] = []

    for index in range(channel_count):
        rx_col = base_col + index * 2
        tx_col = rx_col + 1
        rx_cols.append(rx_col)
        tx_cols.append(tx_col)

    aml_standard_col = base_col + channel_count * 2
    aml_result_col = aml_standard_col + 1

    rssi_start_col = aml_result_col + 1

    right_rx_cols: list[int] = []
    right_tx_cols: list[int] = []
    for index in range(channel_count):
        rx_col = rssi_start_col + index * 2
        tx_col = rx_col + 1
        right_rx_cols.append(rx_col)
        right_tx_cols.append(tx_col)

    return GroupLayout(
        rx_cols=rx_cols,
        tx_cols=tx_cols,
        aml_standard_col=aml_standard_col,
        aml_result_col=aml_result_col,
        rssi_start_col=rssi_start_col,
        right_rx_cols=right_rx_cols,
        right_tx_cols=right_tx_cols,
    )


def _most_common(counter: Counter[str], default: str) -> str:
    for candidate, _count in counter.most_common():
        text = str(candidate or "").strip()
        if text:
            return text
    return default


def _format_numeric_label(value: Optional[float]) -> str:
    if value is None:
        return ""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return ""
    if math.isclose(numeric, round(numeric), abs_tol=1e-6):
        return str(int(round(numeric)))
    return f"{numeric:.2f}".rstrip('0').rstrip('.')


def _summarize_attenuation_steps(values: Sequence[float]) -> str:
    if not values:
        return ""
    unique_values = sorted({float(v) for v in values})
    if not unique_values:
        return ""
    start = unique_values[0]
    end = unique_values[-1]
    if len(unique_values) == 1:
        return f"{_format_numeric_label(start)} dB"
    deltas = [
        round(unique_values[idx + 1] - unique_values[idx], 4)
        for idx in range(len(unique_values) - 1)
    ]
    positive_deltas = [delta for delta in deltas if delta > 0]
    step_value = 0.0
    if positive_deltas:
        delta_counter = Counter(positive_deltas)
        step_value = float(delta_counter.most_common(1)[0][0])
    start_label = _format_numeric_label(start)
    end_label = _format_numeric_label(end)
    if step_value > 0:
        step_label = _format_numeric_label(step_value)
        return f"{start_label} - {end_label} (step {step_label} dB)"
    return f"{start_label} - {end_label}"


def _resolve_rvo_att_steps() -> List[Tuple[Optional[float], str, str]]:
    """Return RVO attenuation display entries as (value, item_label, att_label)."""

    def _safe_values(loader) -> list[Optional[int]]:
        try:
            return [value for value in loader() if value is not None]
        except Exception:
            LOGGER.exception("Failed to load RVO configuration values from %s", loader)
            return []

    static_values = _safe_values(get_rvo_static_db_list)
    target_values = _safe_values(get_rvo_target_rssi_list)

    if static_values and target_values:
        LOGGER.warning(
            "Both static_db and target_rssi configured; prefer target_rssi for ATT rows."
        )
        static_values = []

    entries: List[Tuple[Optional[float], str, str]] = []
    if target_values:
        for value in target_values:
            numeric = float(value) if value is not None else None
            label = f"Target RSSI {value} dBm" if value is not None else "Target RSSI"
            att_text = f"{value} dBm" if value is not None else ""
            entries.append((numeric, label, att_text))
    elif static_values:
        for value in static_values:
            numeric = float(value) if value is not None else None
            label = f"Static {value} dB" if value is not None else "Static"
            att_text = f"{value} dB" if value is not None else ""
            entries.append((numeric, label, att_text))

    return entries



def _sanitize_number(value: Optional[str]) -> Optional[float]:
    if value in (None, "", "NULL"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_angle(value: Optional[str]) -> str:
    text = str(value or '').strip()
    if not text:
        return '0deg'
    normalized = text.replace('\u00B0', 'deg').replace('?', '').strip()
    if not normalized:
        return '0deg'
    if normalized.lower().endswith('deg'):
        return normalized
    return f"{normalized}deg"

def _format_bandwidth(value: Optional[str]) -> str:
    text = str(value or "").strip()
    if not text:
        return "20/40/80 MHz"
    normalized = text.replace("_", " ").replace("MHz", "").strip()
    if normalized.lower().endswith("mhz"):
        return normalized
    return f"{normalized} MHz"


def _format_channel(value: Optional[str]) -> str:
    text = str(value or "").strip()
    if not text:
        return "CH36"
    upper = text.upper()
    if upper.startswith("CH"):
        return text.title()
    if upper.replace(".", "").isdigit():
        return f"CH{upper}"
    return f"CH {text.title()}"



# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def _configure_sheet(ws: Worksheet) -> None:
    for column, width in COLUMN_WIDTHS.items():
        ws.column_dimensions[column].width = width


def _merge(ws: Worksheet, range_string: str) -> None:
    ws.merge_cells(range_string)


def _set_cell(
    ws: Worksheet,
    row: int,
    column: int,
    value,
    font: Optional[Font] = None,
    alignment: Optional[Alignment] = None,
    fill: Optional[str] = None,
    border: bool = False,
) -> None:
    cell = ws.cell(row=row, column=column, value=value)
    if font:
        cell.font = font
    if alignment:
        cell.alignment = alignment
    if fill:
        cell.fill = PatternFill("solid", fgColor=fill)
    if border:
        cell.border = BORDER_THIN


# ---------------------------------------------------------------------------
# Standard text helpers
# ---------------------------------------------------------------------------


def _aml_standard_text(att: float) -> Optional[str]:
    if att <= 15:
        return "RX Tput>=503.5\nTX Tput>=475"
    if att <= 21:
        return "RX Tput>=320\nTX Tput>=300"
    if 30 <= att <= 45:
        return "RX Tput>100\nTX Tput>95"
    if att >= 48:
        return "N/A"
def _aml_threshold(att: float) -> Optional[Tuple[int, int]]:
    if att <= 12:
        return 400, 300
    if att <= 21:
        return 320, 200
    if att <= 45:
        return 100, 80
    return None


def _group_runs(values: Sequence[float], formatter) -> List[Tuple[int, int, Optional[str]]]:
    if not values:
        return []
    groups: List[Tuple[int, int, Optional[str]]] = []
    start = 0
    current = formatter(values[0])
    for idx in range(1, len(values)):
        text = formatter(values[idx])
        if text != current:
            groups.append((start, idx - 1, current))
            start = idx
            current = text
    groups.append((start, len(values) - 1, current))
    return groups


def _apply_grouped_texts(ws: Worksheet, column: int, start_row: int, values: Sequence[float], formatter) -> None:
    for start_idx, end_idx, text in _group_runs(values, formatter):
        if not text:
            continue
        top = start_row + start_idx
        bottom = start_row + end_idx
        if top != bottom:
            _merge(ws, f"{get_column_letter(column)}{top}:{get_column_letter(column)}{bottom}")
        _set_cell(ws, top, column, text, font=FONT_STANDARD, alignment=ALIGN_LEFT_WRAP, border=True)
        for r in range(top + 1, bottom + 1):
            cell = ws.cell(row=r, column=column)
            cell.border = BORDER_THIN
            cell.alignment = ALIGN_LEFT_WRAP


def _set_result_cell(ws: Worksheet, row: int, column: int, threshold: Optional[Tuple[int, int]], rx_column: int, tx_column: int) -> None:
    if threshold is None:
        value = "Pass"
    else:
        rx, tx = threshold
        rx_letter = get_column_letter(rx_column)
        tx_letter = get_column_letter(tx_column)
        value = f'=IF(AND({rx_letter}{row}>{rx},{tx_letter}{row}>{tx}),"Pass","Fail")'
    _set_cell(ws, row, column, value, font=FONT_BODY, alignment=ALIGN_CENTER, border=True)


def _apply_result_formatting(ws: Worksheet, start_row: int, end_row: int, result_column: int) -> None:
    if start_row > end_row:
        return
    column_letter = get_column_letter(result_column)
    fail_rule = FormulaRule(
        formula=[f"={column_letter}{start_row}=\"Fail\""],
        font=Font(name="Arial", color="FF0000", bold=True),
    )
    pass_rule = FormulaRule(
        formula=[f"={column_letter}{start_row}=\"Pass\""],
        font=Font(name="Arial", color="008000", bold=True),
    )
    ws.conditional_formatting.add(f"{column_letter}{start_row}:{column_letter}{end_row}", fail_rule)
    ws.conditional_formatting.add(f"{column_letter}{start_row}:{column_letter}{end_row}", pass_rule)


# ---------------------------------------------------------------------------
# Layout writer
# ---------------------------------------------------------------------------


def _write_report_title(ws: Worksheet, start_row: int = 1) -> int:
    top_row = start_row
    _merge(ws, f"A{top_row}:W{top_row}")
    ws.row_dimensions[top_row].height = ROW_HEIGHT_TITLE
    _set_cell(
        ws,
        top_row,
        1,
        "Project Wi-Fi Test Report",
        font=FONT_TITLE,
        alignment=ALIGN_CENTER,
        fill=COLOR_BRAND_BLUE,
        border=True,
    )

    logo_bytes = base64.b64decode(LOGO_PNG_BASE64)
    image = Image(BytesIO(logo_bytes))
    image.width = 240
    image.height = 70
    image.anchor = f"A{top_row}"
    ws.add_image(image)
    LOGGER.info("Report title written at row %d", top_row)
    return top_row


def _write_group_header(ws: Worksheet, group: ScenarioGroup, start_row: int) -> int:
    _merge(ws, f"A{start_row}:W{start_row}")
    _set_cell(
        ws,
        start_row,
        1,
        group.summary_label,
        font=FONT_SECTION,
        alignment=ALIGN_CENTER,
        border=True,
    )
    LOGGER.info("Group header written | row=%d label=%s", start_row, group.summary_label)
    return start_row


def _write_headers(
    ws: Worksheet,
    group: ScenarioGroup,
    channels: Sequence[ProjectScenario],
    layout: GroupLayout,
    *,
    header_row: int,
) -> int:
    headers: list[tuple[int, int, str]] = [
        (header_row, 1, "Item"),
        (header_row, 2, "ATT\n(Unit:dB)"),
    ]
    for rx_col in layout.rx_cols:
        headers.append((header_row, rx_col, "RX(Unit:Mbps)"))
    for tx_col in layout.tx_cols:
        headers.append((header_row, tx_col, "TX(Unit:Mbps)"))

    headers.extend(
        [
            (header_row, layout.aml_standard_col, "AML_Standard"),
            (header_row, layout.aml_result_col, "AML_Result"),
        ]
    )

    for row, col, text in headers:
        _set_cell(
            ws,
            row,
            col,
            text,
            font=FONT_HEADER,
            alignment=ALIGN_CENTER_WRAP,
            fill=COLOR_BRAND_BLUE,
            border=True,
        )

    sub_row = header_row + 1
    step_text = group.step_summary or ""
    _set_cell(ws, sub_row, 1, step_text, font=FONT_SUBHEADER, alignment=ALIGN_CENTER, fill=COLOR_SUBHEADER, border=True)

    if layout.right_rx_cols:
        rssi_start = layout.rssi_start_col
        rssi_end = layout.right_tx_cols[-1]
        start_letter = get_column_letter(rssi_start)
        end_letter = get_column_letter(rssi_end)
        _merge(ws, f"{start_letter}{header_row}:{end_letter}{header_row}")
    else:
        start_letter = end_letter = get_column_letter(layout.aml_result_col + 1)

    _set_cell(
        ws,
        header_row,
        layout.rssi_start_col,
        "RSSI",
        font=FONT_HEADER,
        alignment=ALIGN_CENTER_WRAP,
        fill=COLOR_BRAND_BLUE,
        border=True,
    )

    _set_cell(
        ws,
        sub_row,
        layout.rssi_start_col,
        step_text,
        font=FONT_SUBHEADER,
        alignment=ALIGN_CENTER,
        fill=COLOR_SUBHEADER,
        border=True,
    )

    rssi_start = layout.rssi_start_col if layout.right_rx_cols else layout.aml_result_col + 1
    if layout.right_rx_cols:
        rssi_end = layout.right_tx_cols[-1]
        start_letter = get_column_letter(rssi_start)
        end_letter = get_column_letter(rssi_end)
        _merge(ws, f"{start_letter}{header_row}:{end_letter}{header_row}")
        _set_cell(
            ws,
            header_row,
            rssi_start,
            "RSSI",
            font=FONT_HEADER,
            alignment=ALIGN_CENTER_WRAP,
            fill=COLOR_BRAND_BLUE,
            border=True,
        )
    for idx, scenario in enumerate(channels):
        channel_text = scenario.channel
        _set_cell(
            ws,
            sub_row,
            layout.rx_cols[idx],
            channel_text,
            font=FONT_SUBHEADER,
            alignment=ALIGN_CENTER,
            fill=COLOR_SUBHEADER,
            border=True,
        )
        _set_cell(
            ws,
            sub_row,
            layout.tx_cols[idx],
            channel_text,
            font=FONT_SUBHEADER,
            alignment=ALIGN_CENTER,
            fill=COLOR_SUBHEADER,
            border=True,
        )

    _set_cell(ws, sub_row, layout.aml_standard_col, None, font=FONT_SUBHEADER, alignment=ALIGN_CENTER, fill=COLOR_SUBHEADER, border=True)
    _set_cell(ws, sub_row, layout.aml_result_col, None, font=FONT_SUBHEADER, alignment=ALIGN_CENTER, fill=COLOR_SUBHEADER, border=True)

    for idx, scenario in enumerate(channels):
        channel_text = scenario.channel
        rx_header_col = layout.right_rx_cols[idx]
        tx_header_col = layout.right_tx_cols[idx]
        _set_cell(
            ws,
            sub_row,
            rx_header_col,
            channel_text,
            font=FONT_SUBHEADER,
            alignment=ALIGN_CENTER,
            fill=COLOR_SUBHEADER,
            border=True,
        )
        _set_cell(
            ws,
            sub_row,
            tx_header_col,
            channel_text,
            font=FONT_SUBHEADER,
            alignment=ALIGN_CENTER,
            fill=COLOR_SUBHEADER,
            border=True,
        )
    LOGGER.info(
        "Header row configured | start_row=%d channel_count=%d step_summary=%s",
        header_row,
        len(channels),
        step_text or "N/A",
    )
    return sub_row


def _write_data(
    ws: Worksheet,
    group: ScenarioGroup,
    channels: Sequence[ProjectScenario],
    layout: GroupLayout,
    start_row: int = 7,
    *,
    override_steps: Optional[Sequence[Optional[float]]] = None,
    att_labels: Optional[Sequence[str]] = None,
    item_labels: Optional[Sequence[str]] = None,
) -> int:
    base_steps = list(group.attenuation_steps or DEFAULT_ATTENUATIONS)
    if override_steps is not None:
        override = [step for step in override_steps if step is not None]
        steps = list(override) if override else base_steps
    else:
        steps = base_steps

    if not steps:
        steps = DEFAULT_ATTENUATIONS.copy()

    end_row = start_row + len(steps) - 1

    if steps and not item_labels:
        _merge(ws, f"A{start_row}:A{end_row}")
        _set_cell(
            ws,
            start_row,
            1,
            group.summary_label,
            font=FONT_BODY,
            alignment=ALIGN_CENTER_WRAP,
            border=True,
        )

    for index, attenuation in enumerate(steps):
        row = start_row + index
        highlight = COLOR_RATE_PRIMARY if index < 6 else COLOR_RATE_SECONDARY

        if item_labels:
            label = item_labels[index] if index < len(item_labels) else ""
            _set_cell(ws, row, 1, label, font=FONT_BODY, alignment=ALIGN_CENTER_WRAP, border=True)

        att_value = att_labels[index] if att_labels and index < len(att_labels) else attenuation
        _set_cell(ws, row, 2, att_value, font=FONT_BODY, alignment=ALIGN_CENTER, border=True)

        for channel_idx, scenario in enumerate(channels):
            rx_col = layout.rx_cols[channel_idx]
            tx_col = layout.tx_cols[channel_idx]
            rx_value = scenario.rx_values.get(attenuation)
            tx_value = scenario.tx_values.get(attenuation)
            _set_cell(
                ws,
                row,
                rx_col,
                rx_value,
                font=FONT_BODY,
                alignment=ALIGN_CENTER,
                fill=highlight,
                border=True,
            )
            _set_cell(
                ws,
                row,
                tx_col,
                tx_value,
                font=FONT_BODY,
                alignment=ALIGN_CENTER,
                fill=highlight,
                border=True,
            )

        _set_cell(ws, row, layout.aml_standard_col, None, font=FONT_STANDARD, alignment=ALIGN_LEFT_WRAP, border=True)
        ref_rx_col = layout.rx_cols[0] if layout.rx_cols else 3
        ref_tx_col = layout.tx_cols[0] if layout.tx_cols else 4
        _set_result_cell(ws, row, layout.aml_result_col, _aml_threshold(attenuation), ref_rx_col, ref_tx_col)

        for channel_idx, scenario in enumerate(channels):
            rx_col = layout.right_rx_cols[channel_idx]
            tx_col = layout.right_tx_cols[channel_idx]
            _set_cell(
                ws,
                row,
                rx_col,
                scenario.rssi_rx.get(attenuation),
                font=FONT_BODY,
                alignment=ALIGN_CENTER,
                fill=COLOR_RSSI_RX,
                border=True,
            )
            _set_cell(
                ws,
                row,
                tx_col,
                scenario.rssi_tx.get(attenuation),
                font=FONT_BODY,
                alignment=ALIGN_CENTER,
                fill=COLOR_RSSI_TX,
                border=True,
            )

    if override_steps is None:
        _apply_grouped_texts(ws, layout.aml_standard_col, start_row, steps, _aml_standard_text)
    _apply_result_formatting(ws, start_row, end_row, layout.aml_result_col)
    LOGGER.info(
        'Data rows populated | group=%s start_row=%d end_row=%d points=%d channels=%d',
        group.key,
        start_row,
        end_row,
        len(attenuations),
        len(channels),
    )
    return end_row

def _nice_number(value: float, *, round_up: bool = True) -> float:
    if value <= 0:
        return 0.0
    exponent = math.floor(math.log10(value))
    fraction = value / (10 ** exponent)
    candidates = (1, 2, 2.5, 5, 10)
    if round_up:
        for candidate in candidates:
            if fraction <= candidate:
                fraction = candidate
                break
        else:
            fraction = candidates[-1]
    else:
        for candidate in reversed(candidates):
            if fraction >= candidate:
                fraction = candidate
                break
        else:
            fraction = candidates[0]
    return fraction * (10 ** exponent)


def _resolve_throughput_axis(values: Sequence[Optional[float]]) -> Tuple[float, float]:
    numeric_values: list[float] = []
    for value in values:
        if value is None:
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(numeric):
            continue
        numeric_values.append(numeric)
    if not numeric_values:
        return 10.0, 2.0
    max_value = max(numeric_values)
    if max_value <= 0:
        return 10.0, 2.0
    padded = max_value * 1.1
    upper = _nice_number(padded, round_up=True)
    if upper <= 0:
        upper = 10.0
    major = _nice_number(upper / 5.0, round_up=True)
    if major <= 0:
        major = upper
    LOGGER.info(
        "Resolved throughput axis | max=%.2f padded=%.2f upper=%.2f major=%.2f",
        max_value,
        padded,
        upper,
        major,
    )
    return upper, major


def _style_chart(
    chart: ScatterChart,
    *,
    data_points: Sequence[Optional[float]],
    show_markers: bool,
    step_values: Sequence[float],
) -> None:
    chart.width = 12.0
    chart.height = 7.5
    chart.varyColors = False
    LOGGER.info("Configured scatter chart | vary_colors=%s", chart.varyColors)

    if chart.legend is None:
        chart.legend = Legend()
    chart.legend.position = 'b'
    chart.legend.overlay = False
    LOGGER.info(
        'Chart legend configured | position=%s overlay=%s series=%d',
        chart.legend.position,
        chart.legend.overlay,
        len(chart.series),
    )
    chart.x_axis.majorGridlines = None
    chart.y_axis.majorGridlines = ChartLines()
    chart.y_axis.majorGridlines.spPr = GraphicalProperties(
        ln=LineProperties(solidFill=COLOR_GRIDLINE, w=12000)
    )
    chart.x_axis.delete = False
    chart.y_axis.delete = False
    chart.x_axis.title = None
    chart.y_axis.title = None
    chart.x_axis.majorTickMark = "cross"
    chart.y_axis.majorTickMark = "out"
    chart.x_axis.tickLblPos = "low"
    chart.y_axis.tickLblPos = "nextTo"
    chart.x_axis.crosses = "min"
    chart.y_axis.crosses = "min"
    chart.x_axis.number_format = "0"
    chart.y_axis.number_format = "0"
    chart.x_axis.tickLblSkip = 1
    chart.x_axis.tickMarkSkip = 1
    if step_values:
        x_min = float(step_values[0])
        x_max = float(step_values[-1])
        if len(step_values) > 1:
            raw_step = float(step_values[1] - step_values[0])
            major_step = raw_step if raw_step > 0 else 1.0
        else:
            major_step = 1.0
    else:
        x_min = 0.0
        x_max = float(max(len(data_points) - 1, 0))
        major_step = 1.0 if x_max == 0 else x_max / max(len(data_points) - 1, 1)
        if major_step <= 0:
            major_step = 1.0

    chart.x_axis.scaling.min = x_min
    chart.x_axis.scaling.max = x_max
    chart.x_axis.majorUnit = max(major_step, 1.0)

    upper, major = _resolve_throughput_axis(data_points)
    chart.y_axis.scaling.min = 0
    chart.y_axis.scaling.max = upper
    chart.y_axis.majorUnit = major
    chart.y_axis.minorTickMark = "none"
    chart.x_axis.minorTickMark = "none"

    chart.plot_area.layout = Layout(
        manualLayout=ManualLayout(x=0.06, y=0.12, w=0.8, h=0.7)
    )
    LOGGER.info(
        "Chart layout + axis | width=%.1f height=%.1f y_max=%.2f major=%.2f x_min=%.2f x_max=%.2f x_step=%.2f layout=(x=%.2f y=%.2f w=%.2f h=%.2f)",
        chart.width,
        chart.height,
        upper,
        major,
        x_min,
        x_max,
        chart.x_axis.majorUnit,
        chart.plot_area.layout.manualLayout.x,
        chart.plot_area.layout.manualLayout.y,
        chart.plot_area.layout.manualLayout.w,
        chart.plot_area.layout.manualLayout.h,
    )

    for idx, series in enumerate(chart.series):
        color = SERIES_COLORS[idx % len(SERIES_COLORS)]
        if hasattr(series, "graphicalProperties") and hasattr(series.graphicalProperties, "line"):
            series.graphicalProperties.line.width = 20000  # 2pt
            series.graphicalProperties.line.solidFill = color
        series.smooth = False
        if show_markers:
            marker = Marker(symbol="circle")
            marker.graphicalProperties = GraphicalProperties(solidFill=color)
            marker.size = 6
        else:
            marker = Marker(symbol="none")
        series.marker = marker
        LOGGER.info(
            "Styled chart series | title=%s line_width=%s marker_symbol=%s marker_size=%s smooth=%s",
            getattr(series, "title", None),
            getattr(series.graphicalProperties.line, "width", None) if hasattr(series, "graphicalProperties") else None,
            marker.symbol,
            getattr(marker, "size", None),
            series.smooth,
        )


def _build_throughput_chart(
    *,
    title: str,
    series_definitions: Sequence[tuple[str, Reference, Reference]],
    data_points: Sequence[Optional[float]],
    show_markers: bool,
    step_values: Sequence[float],
) -> ScatterChart:
    chart = ScatterChart()
    chart.scatterStyle = 'line'
    chart.varyColors = False
    chart.title = title
    for series_title, categories, values in series_definitions:
        series = Series(values, xvalues=categories, title=series_title)
        series.smooth = False
        chart.series.append(series)
    _style_chart(
        chart,
        data_points=data_points,
        show_markers=show_markers,
        step_values=step_values,
    )
    LOGGER.info(
        'Built throughput chart | title=%s series_count=%d point_count=%d markers=%s',
        title,
        len(series_definitions),
        len(data_points),
        show_markers,
    )
    return chart

def _add_group_charts(
    ws: Worksheet,
    group: ScenarioGroup,
    layout: GroupLayout,
    sections: Sequence[dict[str, object]],
    *,
    anchor_row: int,
) -> int:
    if not sections:
        return anchor_row

    attenuations = sorted(group.attenuation_steps) or DEFAULT_ATTENUATIONS
    rx_series_defs: list[tuple[str, Reference, Reference]] = []
    tx_series_defs: list[tuple[str, Reference, Reference]] = []
    rx_points: list[float] = []
    tx_points: list[float] = []
    for idx, section in enumerate(sections):
        scenario = section['scenario']  # type: ignore[index]
        data_start = section['data_start']  # type: ignore[index]
        data_end = section['data_end']  # type: ignore[index]
        categories = Reference(ws, min_col=2, min_row=data_start, max_row=data_end)
        rx_col = layout.rx_cols[idx] if idx < len(layout.rx_cols) else 4
        tx_col = layout.tx_cols[idx] if idx < len(layout.tx_cols) else 5
        rx_values = Reference(ws, min_col=rx_col, min_row=data_start, max_row=data_end)
        tx_values = Reference(ws, min_col=tx_col, min_row=data_start, max_row=data_end)
        rx_series_defs.append((scenario.channel, categories, rx_values))
        tx_series_defs.append((scenario.channel, categories, tx_values))
        rx_points.extend(float(val) for val in scenario.rx_values.values() if val is not None)
        tx_points.extend(float(val) for val in scenario.tx_values.values() if val is not None)

    rx_chart = _build_throughput_chart(
        title=f"{group.title} RVR Throughput_RX",
        series_definitions=rx_series_defs,
        data_points=rx_points,
        show_markers=False,
        step_values=attenuations,
    )
    tx_chart = _build_throughput_chart(
        title=f"{group.title} RVR Throughput_TX",
        series_definitions=tx_series_defs,
        data_points=tx_points,
        show_markers=False,
        step_values=attenuations,
    )

    data_last_row = max(section['data_end'] for section in sections)  # type: ignore[index]
    first_anchor_row = max(data_last_row + 2, CHART_MIN_TOP_ROW)
    base_col_index = layout.rx_cols[0] if layout.rx_cols else 3
    rx_col_anchor = get_column_letter(base_col_index)

    gap_columns = 3
    tx_col_index = (layout.tx_cols[-1] if layout.tx_cols else base_col_index) + gap_columns
    if layout.right_rx_cols:
        tx_col_index = min(tx_col_index, layout.right_rx_cols[0] - 1)
        if tx_col_index <= base_col_index:
            tx_col_index = layout.right_rx_cols[0]
    tx_col_index = max(tx_col_index, base_col_index + 1)
    tx_col_anchor = get_column_letter(tx_col_index)

    rx_chart.anchor = f"{rx_col_anchor}{first_anchor_row}"
    ws.add_chart(rx_chart)

    tx_chart.anchor = f"{tx_col_anchor}{first_anchor_row}"
    ws.add_chart(tx_chart)

    chart_bottom = first_anchor_row + CHART_VERTICAL_HEIGHT_ROWS
    bottom_row = max(data_last_row, chart_bottom)

    LOGGER.info(
        'Group charts placed | group=%s anchor=%s rx_series=%d tx_series=%d bottom_row=%d',
        group.key,
        f"{rx_col_anchor}{first_anchor_row}",
        len(rx_series_defs),
        len(tx_series_defs),
        bottom_row,
    )
    return bottom_row


def _prepare_rvo_chart_context(result_file: Path | str) -> dict[str, Any]:
    chart_dir = Path(result_file).resolve().parent / "rvo_charts"
    chart_dir.mkdir(parents=True, exist_ok=True)
    generator = PerformanceRvrChartGenerator()
    try:
        dataframe = generator._load_rvr_dataframe(Path(result_file))  # type: ignore[attr-defined]
    except Exception:
        LOGGER.exception('Failed to load RVO dataframe for charts: %s', result_file)
        dataframe = None
    return {"generator": generator, "dataframe": dataframe, "directory": chart_dir}


def _add_rvo_polar_chart(
    ws: Worksheet,
    group: ScenarioGroup,
    layout: GroupLayout,
    sections: Sequence[dict[str, object]],
    *,
    anchor_row: int,
    context: dict[str, Any],
) -> int:
    data_last_row = max((section['data_end'] for section in sections), default=anchor_row)
    generator: Optional[PerformanceRvrChartGenerator] = context.get("generator")
    dataframe = context.get("dataframe")
    chart_dir: Optional[Path] = context.get("directory")

    if generator is None or chart_dir is None:
        LOGGER.warning('Invalid RVO chart context; skip chart for %s', group.key)
        return data_last_row

    if dataframe is None or getattr(dataframe, "empty", True):
        LOGGER.warning('RVO dataframe empty; polar chart unavailable for %s', group.key)
        placeholder_col = layout.right_tx_cols[-1] + 2 if layout.right_tx_cols else layout.tx_cols[-1] + 2
        _set_cell(
            ws,
            anchor_row,
            placeholder_col,
            "Polar chart unavailable",
            font=FONT_BODY,
            alignment=ALIGN_CENTER,
            border=True,
        )
        return max(data_last_row, anchor_row)

    try:
        df = dataframe
        if "Scenario_Group_Key" in df.columns:
            df = df[df["Scenario_Group_Key"].isin(group.raw_keys)]
        if "__test_type_display__" in df.columns:
            df = df[df["__test_type_display__"].astype(str).str.upper() == "RVO"]
        if df.empty:
            raise ValueError("No RVO rows matched group keys")

        direction_column = "__direction_display__" if "__direction_display__" in df.columns else "Direction"
        if direction_column in df.columns:
            directions = [
                str(direction).strip()
                for direction in df[direction_column].unique()
                if str(direction).strip()
            ]
        else:
            directions = ["RX"]
        preferred = [d for d in directions if d.upper() in {"RX", "DL"}] + [d for d in directions if d.upper() not in {"RX", "DL"}]
        image_path: Optional[Path] = None
        used_direction = None
        for direction in preferred or ["RX"]:
            subset = df[df[direction_column] == direction] if direction_column in df.columns else df
            if subset.empty:
                continue
            title = generator._format_chart_title(
                group.standard,
                group.bandwidth,
                group.freq,
                group.test_type,
                direction,
            )
            image_path = generator._save_rvo_chart(subset, title, chart_dir)
            if image_path is not None:
                used_direction = direction
                break

        if image_path is None:
            raise ValueError("Failed to generate polar chart")

        anchor_base = layout.right_tx_cols[-1] if layout.right_tx_cols else layout.tx_cols[-1]
        anchor_col_index = anchor_base + CHART_COLUMN_GAP + 1
        anchor_letter = get_column_letter(anchor_col_index)
        image = Image(str(image_path))
        image.anchor = f"{anchor_letter}{anchor_row}"
        ws.add_image(image)
        LOGGER.info('Inserted RVO polar chart | group=%s direction=%s path=%s', group.key, used_direction, image_path)
    except Exception:
        LOGGER.exception('Failed to insert RVO polar chart for group %s', group.key)
        fallback_col = layout.right_tx_cols[-1] + 2 if layout.right_tx_cols else layout.tx_cols[-1] + 2
        _set_cell(
            ws,
            anchor_row,
            fallback_col,
            "Polar chart unavailable",
            font=FONT_BODY,
            alignment=ALIGN_CENTER,
            border=True,
        )

    chart_bottom = anchor_row + CHART_VERTICAL_HEIGHT_ROWS
    bottom_row = max(data_last_row, chart_bottom)
    return bottom_row

# ---------------------------------------------------------------------------
# Data extraction
# ---------------------------------------------------------------------------


def _load_scenario_groups(result_file: Path | str, *, test_type: str | None = None) -> List[ScenarioGroup]:
    path = Path(result_file)
    if not path.exists():
        LOGGER.warning('Result CSV not found for project report: %s', path)
        return []

    normalized_filter = _normalize_test_type(test_type) if test_type else None
    buckets: dict[str, dict[str, object]] = {}
    total_rows = 0
    filtered_rows = 0
    matched_rows = 0
    type_counts: Counter[str] = Counter()
    try:
        with path.open('r', encoding='utf-8-sig', newline='') as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if not row:
                    continue
                total_rows += 1
                row_type = _detect_row_test_type(row)
                type_counts[row_type] += 1
                if normalized_filter and row_type != normalized_filter:
                    filtered_rows += 1
                    continue
                matched_rows += 1
                raw_key = row.get('Scenario_Group_Key')
                base_key = _group_base_key(raw_key)
                bucket = buckets.setdefault(
                    base_key,
                    {
                        'raw_keys': set(),
                        'freq': Counter(),
                        'standard': Counter(),
                        'bandwidth': Counter(),
                        'angle': Counter(),
                        'attenuations': set(),
                        'channels': {},
                        'channel_order': [],
                        'test_type': Counter(),
                    },
                )

                bucket['raw_keys'].add(_normalize_scenario_key(raw_key))
                bucket['test_type'][row_type] += 1

                freq = str(row.get('Freq_Band') or '').strip()
                if freq:
                    bucket['freq'][freq] += 1
                standard = str(row.get('Standard') or '').strip()
                if standard:
                    bucket['standard'][standard] += 1
                bandwidth_raw = row.get('BW') or row.get('Bandwidth')
                bandwidth = _format_bandwidth(bandwidth_raw)
                if bandwidth:
                    bucket['bandwidth'][bandwidth] += 1
                angle = _format_angle(row.get('Angel') or row.get('Angle'))
                if angle:
                    bucket['angle'][angle] += 1

                channel_label = _format_channel(row.get('CH_Freq_MHz') or row.get('Channel'))
                channels = bucket['channels']
                channel_bucket = channels.setdefault(
                    channel_label,
                    {
                        'scenario_key': _normalize_scenario_key(raw_key),
                        'rx': {},
                        'tx': {},
                        'rssi_rx': {},
                        'rssi_tx': {},
                        'attenuations': set(),
                    },
                )
                if channel_label not in bucket['channel_order']:
                    bucket['channel_order'].append(channel_label)

                attenuation = _sanitize_number(row.get('DB') or row.get('Total_Path_Loss'))
                if attenuation is None:
                    continue
                bucket['attenuations'].add(attenuation)
                channel_bucket['attenuations'].add(attenuation)

                direction = str(row.get('Direction') or '').upper()
                throughput = _sanitize_number(row.get('Throughput'))
                if throughput is not None:
                    if direction in {'DL', 'RX'}:
                        channel_bucket['rx'][attenuation] = throughput
                    elif direction in {'UL', 'TX'}:
                        channel_bucket['tx'][attenuation] = throughput

                rssi = _sanitize_number(row.get('RSSI'))
                if rssi is not None:
                    if direction in {'DL', 'RX'}:
                        channel_bucket['rssi_rx'][attenuation] = rssi
                    elif direction in {'UL', 'TX'}:
                        channel_bucket['rssi_tx'][attenuation] = rssi
    except Exception:
        LOGGER.exception('Failed to parse project CSV: %s', path)
        return []

    groups: List[ScenarioGroup] = []
    for base_key, bucket in buckets.items():
        attenuation_steps = sorted(bucket['attenuations'])
        group_attenuations = attenuation_steps if attenuation_steps else DEFAULT_ATTENUATIONS.copy()
        group = ScenarioGroup(
            key=base_key,
            freq=_most_common(bucket['freq'], default='5G'),
            standard=_most_common(bucket['standard'], default='Auto'),
            bandwidth=_most_common(bucket['bandwidth'], default='20/40/80 MHz'),
            angle_label=_most_common(bucket['angle'], default='0deg'),
            attenuation_steps=group_attenuations,
        )
        group.step_summary = _summarize_attenuation_steps(group_attenuations)
        group.raw_keys = set(bucket['raw_keys'])
        group.test_type = _most_common(
            bucket['test_type'],
            default=_normalize_test_type(normalized_filter or 'RVR'),
        )

        channel_scenarios: List[ProjectScenario] = []
        for channel_label in bucket['channel_order']:
            channel_bucket = bucket['channels'].get(channel_label) or {}
            channel_atts = sorted(channel_bucket.get('attenuations', set()))
            scenario = ProjectScenario(
                key=channel_bucket.get('scenario_key') or base_key,
                freq=group.freq,
                standard=group.standard,
                bandwidth=group.bandwidth,
                channel_label=channel_label,
                angle_label=group.angle_label,
                attenuation_steps=channel_atts if channel_atts else group_attenuations.copy(),
                step_summary=group.step_summary,
                rx_values=dict(sorted(channel_bucket.get('rx', {}).items())),
                tx_values=dict(sorted(channel_bucket.get('tx', {}).items())),
                rssi_rx=dict(sorted(channel_bucket.get('rssi_rx', {}).items())),
                rssi_tx=dict(sorted(channel_bucket.get('rssi_tx', {}).items())),
            )
            LOGGER.info(
                'Channel aggregated | base_key=%s channel=%s attenuations=%d rx_points=%d tx_points=%d',
                base_key,
                channel_label,
                len(scenario.attenuation_steps),
                len(scenario.rx_values),
                len(scenario.tx_values),
            )
            channel_scenarios.append(scenario)

        if not channel_scenarios:
            continue
        group.channels = channel_scenarios
        LOGGER.info(
            'Scenario group aggregated | base_key=%s freq=%s standard=%s channels=%d step_summary=%s',
            base_key,
            group.freq,
            group.standard,
            len(group.channels),
            group.step_summary or 'N/A',
        )
        groups.append(group)

    groups.sort(
        key=lambda grp: (
            grp.freq.upper(),
            grp.standard.upper(),
            grp.bandwidth.upper(),
            grp.key,
        ),
    )
    distribution = ', '.join(
        f"{name}={count}" for name, count in sorted(type_counts.items())
    ) or 'none'
    LOGGER.info(
        'Scenario test type summary | total_rows=%d matched=%d filtered=%d filter=%s distribution=%s',
        total_rows,
        matched_rows,
        filtered_rows,
        normalized_filter or 'ALL',
        distribution,
    )
    LOGGER.info(
        'Loaded project scenario groups | count=%d total_rows=%d source=%s filter=%s',
        len(groups),
        total_rows,
        path,
        normalized_filter or 'ALL',
    )
    return groups

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_project_report(
    result_file: Path | str,
    output_path: Path | str,
    forced_test_type: str | None = None,
) -> Path:
    normalized_type = _normalize_test_type(forced_test_type) if forced_test_type else None
    groups = _load_scenario_groups(result_file, test_type=normalized_type)
    actual_type = normalized_type or (groups[0].test_type if groups else "RVR")
    LOGGER.info(
        "Preparing project %s report | groups=%d source=%s",
        actual_type,
        len(groups),
        result_file,
    )

    workbook = Workbook()
    sheet = workbook.active
    sheet_name = actual_type.lower()
    sheet.title = sheet_name[:31]
    _configure_sheet(sheet)

    chart_context: Optional[dict[str, Any]] = None
    if actual_type == "RVO":
        chart_context = _prepare_rvo_chart_context(result_file)

    if not groups:
        title_row = _write_report_title(sheet, start_row=1)
        placeholder_row = title_row + 2
        _merge(sheet, f"A{placeholder_row}:W{placeholder_row}")
        _set_cell(
            sheet,
            placeholder_row,
            1,
            "No Wi-Fi data available for project report",
            font=FONT_SECTION,
            alignment=ALIGN_CENTER,
            border=True,
        )
        LOGGER.warning("No scenarios found; generated placeholder sheet named %s.", sheet.title)
    else:
        title_row = _write_report_title(sheet, start_row=1)
        current_row = title_row + 2
        rvo_att_entries = _resolve_rvo_att_steps() if actual_type == "RVO" else []
        for group_index, group in enumerate(groups):
            if group_index > 0:
                current_row += 1
            group_layout = _build_group_layout(len(group.channels))
            group_header_row = _write_group_header(sheet, group, start_row=current_row)
            header_row = group_header_row + 1

            sub_header_row = _write_headers(
                sheet,
                group,
                group.channels,
                group_layout,
                header_row=header_row,
            )
            data_start = sub_header_row + 1
            override_steps = [entry[0] for entry in rvo_att_entries if entry[0] is not None]
            att_labels = [entry[2] for entry in rvo_att_entries]
            item_labels = [entry[1] for entry in rvo_att_entries]
            att_labels_to_use = att_labels if override_steps else None
            item_labels_to_use = item_labels if override_steps else None
            used_channels = group.channels
            if actual_type == "RVO" and override_steps:
                data_end = _write_data(
                    sheet,
                    group,
                    used_channels,
                    group_layout,
                    start_row=data_start,
                    override_steps=override_steps,
                    att_labels=att_labels_to_use,
                    item_labels=item_labels_to_use,
                )
            else:
                data_end = _write_data(
                    sheet,
                    group,
                    used_channels,
                    group_layout,
                    start_row=data_start,
                    att_labels=att_labels_to_use if actual_type == "RVO" else None,
                    item_labels=item_labels_to_use if actual_type == "RVO" else None,
                )
            current_row = data_end + 1

            sections = [
                {"scenario": scenario, "header_row": header_row, "data_start": data_start, "data_end": data_end}
                for scenario in used_channels
            ]

            if sections:
                anchor_row = header_row
                if actual_type == "RVO" and chart_context is not None:
                    last_row = _add_rvo_polar_chart(
                        sheet,
                        group,
                        group_layout,
                        sections,
                        anchor_row=anchor_row,
                        context=chart_context,
                    )
                else:
                    last_row = _add_group_charts(sheet, group, group_layout, sections, anchor_row=anchor_row)
                current_row = max(current_row, last_row + 2)
            else:
                LOGGER.warning("Group %s has no channel sections to chart.", group.key)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output)
    LOGGER.info("Project report saved to %s (sheet=%s)", output, sheet.title)
    return output.resolve()


__all__ = ["generate_project_report", "ProjectScenario"]

