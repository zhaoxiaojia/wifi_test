from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
import hashlib
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from openpyxl import load_workbook
from PyQt5.QtWidgets import QFileDialog, QDialog
from qfluentwidgets import MessageBox

from src.tools.mysql_tool import MySqlClient
from src.tools.mysql_tool.operations import ensure_project, ensure_test_report
from src.tools.mysql_tool.operations import PerformanceTableManager
from src.tools.mysql_tool.schema import ensure_report_tables
from src.tools.mysql_tool.sql_writer import SqlWriter
from src.ui.view.titlebar.import_dialog import ImportDialog
from src.util.constants import IDENTIFIER_SANITIZE_PATTERN


def _store_excel_artifact(
    client: MySqlClient,
    *,
    test_report_id: int,
    excel_path: str,
) -> int:
    content = Path(excel_path).read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    file_name = Path(excel_path).name
    content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    size_bytes = len(content)

    insert_sql = (
        "INSERT INTO `artifact` "
        "(`test_report_id`, `file_name`, `content_type`, `sha256`, `size_bytes`, `content`) "
        "VALUES (%s, %s, %s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE `id`=LAST_INSERT_ID(`id`)"
    )
    artifact_id = client.insert(
        insert_sql,
        (
            int(test_report_id),
            file_name,
            content_type,
            digest,
            int(size_bytes),
            content,
        ),
    )
    return int(artifact_id)


def _insert_performance_rows(
    manager: PerformanceTableManager,
    *,
    execution_id: int,
    csv_name: str,
    data_type: str,
    rows: List[Mapping[str, Any]],
) -> int:
    if not rows:
        return 0

    manager.ensure_schema_initialized()
    insert_columns = [name for name, _ in manager._BASE_COLUMNS]
    insert_columns.extend(column.name for column in manager._STATIC_COLUMNS)

    writer = SqlWriter(manager.TABLE_NAME)
    insert_sql = writer.insert_statement(insert_columns)

    headers = list(rows[0].keys())
    throughput_aliases = manager._collect_throughput_headers(headers)

    values: List[List[Any]] = []
    for row in rows:
        row_values: List[Any] = [
            execution_id,
            csv_name,
            data_type,
        ]
        for column in manager._STATIC_COLUMNS:
            if column.original == "Throughput":
                samples: List[Any] = []
                if throughput_aliases:
                    for alias in throughput_aliases:
                        value = row.get(alias)
                        if value is not None:
                            samples.append(value)
                else:
                    value = row.get(column.original)
                    if value is not None:
                        samples.append(value)
                raw_value = manager._compute_throughput_average(samples)
            else:
                raw_value = row.get(column.original)
            if column.normalizer is not None:
                raw_value = column.normalizer(raw_value)
            row_values.append(manager._normalize_cell(raw_value, column.sql_type))
        values.append(row_values)

    return manager._client.executemany(insert_sql, values)


@dataclass(frozen=True)
class ScenarioSpec:
    band_label: str
    ssid: str
    wireless_mode: str
    channel: int
    bandwidth_label: str
    security_mode: str
    password: str
    tx: int
    rx: int

    @property
    def band_token(self) -> str:
        if self.band_label.startswith("2.4"):
            return "2.4"
        if self.band_label.startswith("5"):
            return "5"
        return self.band_label

    @property
    def bandwidth_mhz(self) -> int:
        text = self.bandwidth_label.strip().lower()
        digits = "".join(ch for ch in text if ch.isdigit())
        return int(digits or 0)


DEFAULT_SCENARIOS: Tuple[ScenarioSpec, ...] = (
    ScenarioSpec("2.4G", "ax3600_2g", "11ax", 1, "40 MHz", "Open System", "", 1, 1),
    ScenarioSpec("2.4G", "ax3600_2g", "11ax", 6, "40 MHz", "Open System", "", 1, 1),
    ScenarioSpec("2.4G", "ax3600_2g", "11ax", 11, "40 MHz", "Open System", "", 1, 1),
    ScenarioSpec("5G", "ax3600_5g", "11ax", 36, "80 MHz", "Open System", "", 1, 1),
    ScenarioSpec("5G", "ax3600_5g", "11ax", 64, "80 MHz", "Open System", "", 1, 1),
    ScenarioSpec("5G", "ax3600_5g", "11ax", 149, "80 MHz", "Open System", "", 1, 1),
    ScenarioSpec("5G", "ax3600_5g", "11ax", 161, "80 MHz", "Open System", "", 1, 1),
)


def build_scenario_group_key(spec: ScenarioSpec) -> str:
    def normalize(value: Any) -> str:
        text = "" if value is None else str(value).strip()
        if not text:
            return ""
        sanitized = IDENTIFIER_SANITIZE_PATTERN.sub("_", text).strip("_")
        return sanitized.upper()

    parts: list[str] = [
        f"BAND={normalize(spec.band_label)}",
        f"SSID={normalize(spec.ssid)}",
        f"MODE={normalize(spec.wireless_mode)}",
        f"CHANNEL={normalize(spec.channel)}",
        f"BANDWIDTH={normalize(spec.bandwidth_label)}",
        f"SECURITY={normalize(spec.security_mode)}",
        f"TX={normalize(spec.tx)}",
        f"RX={normalize(spec.rx)}",
    ]
    return "SCENARIO|" + "|".join(parts)


def build_peak_scenario_group_key(
    spec: ScenarioSpec,
    *,
    standard: str,
    bandwidth_mhz: int,
) -> str:
    def normalize(value: Any) -> str:
        text = "" if value is None else str(value).strip()
        if not text:
            return ""
        sanitized = IDENTIFIER_SANITIZE_PATTERN.sub("_", text).strip("_")
        return sanitized.upper()

    band_label = "2.4G" if spec.band_token == "2.4" else "5G" if spec.band_token == "5" else spec.band_label
    bw_label = f"{int(bandwidth_mhz)} MHz"
    mode_label = standard or spec.wireless_mode

    parts: list[str] = [
        f"BAND={normalize(band_label)}",
        f"SSID={normalize(spec.ssid)}",
        f"MODE={normalize(mode_label)}",
        f"CHANNEL={normalize(spec.channel)}",
        f"BANDWIDTH={normalize(bw_label)}",
        f"SECURITY={normalize(spec.security_mode)}",
        f"TX={normalize(spec.tx)}",
        f"RX={normalize(spec.rx)}",
    ]
    return "SCENARIO|" + "|".join(parts)


def _parse_angle(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = str(value)
    digits = []
    dot_seen = False
    for ch in text:
        if ch.isdigit():
            digits.append(ch)
            continue
        if ch == "." and not dot_seen:
            digits.append(ch)
            dot_seen = True
            continue
        if digits:
            break
    number = "".join(digits).strip(".")
    return float(number) if number else None


def _parse_standard(value: Any) -> str:
    text = "" if value is None else str(value).strip().lower()
    for token in ("11be", "11ax", "11ac", "11n", "11g", "11b", "11a"):
        if token in text:
            return token
    if "802.11ax" in text:
        return "11ax"
    if "802.11ac" in text:
        return "11ac"
    if "802.11n" in text:
        return "11n"
    return ""


def _parse_band_token(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    if "2.4" in text or "2.4G" in text:
        return "2.4"
    if "5" in text or "5G" in text:
        return "5"
    if "6" in text or "6G" in text:
        return "6"
    return ""


def _parse_bandwidth_mhz(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, float) and value.is_integer():
        return int(value)
    text = str(value).strip().upper()
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else None


def _performance_row(
    *,
    test_category: str,
    standard: str,
    band: str,
    bandwidth_mhz: int,
    channel: int,
    protocol: str,
    mode: Optional[str],
    direction: str,
    path_loss_db: float,
    rssi: Optional[float],
    angle_deg: Optional[float],
    throughput_mbps: Optional[float],
    throughput_peak_mbps: Optional[float],
    scenario_group_key: str,
) -> Dict[str, Any]:
    return {
        "Test_Category": test_category,
        "Standard": standard,
        "Freq_Band": band,
        "BW": bandwidth_mhz,
        "CH_Freq_MHz": channel,
        "Protocol": protocol,
        "Mode": mode,
        "Direction": direction,
        "DB": path_loss_db,
        "RSSI": rssi,
        "Angel": angle_deg,
        "Throughput": throughput_mbps,
        "Max_Rate": throughput_peak_mbps,
        "Profile_Mode": "",
        "Profile_Value": "",
        "Scenario_Group_Key": scenario_group_key,
    }


class PerformanceExcelImporter:
    def __init__(self, *, scenarios: Sequence[ScenarioSpec] = DEFAULT_SCENARIOS) -> None:
        self._scenarios = tuple(scenarios)
        self._scenario_by_channel: Dict[Tuple[str, int], ScenarioSpec] = {
            (spec.band_token, spec.channel): spec for spec in self._scenarios
        }

    def _load_workbook(self, path: str | Path):
        return load_workbook(Path(path), data_only=True)

    def build_peak_throughput_rows(self, workbook, *, sheet_name: str) -> Tuple[List[Dict[str, Any]], List[str]]:
        ws = workbook[sheet_name]
        required: Dict[Tuple[str, int], ScenarioSpec] = {}
        for spec in self._scenarios:
            required[(spec.band_token, int(spec.channel))] = spec

        context_wifi_mode: Any = None
        context_mode: Any = None
        context_protocol: Any = None
        context_bw: Any = None
        context_channel: Any = None
        context_rssi: Any = None

        seen_mode: set[Tuple[str, int, int, str, str]] = set()
        rows: List[Dict[str, Any]] = []

        for r in range(1, ws.max_row + 1):
            wifi_mode, mode, protocol, bw, txrx, channel, rssi, first, second, third, avg = [
                ws.cell(r, c).value for c in range(2, 13)
            ]

            if wifi_mode is not None:
                context_wifi_mode = wifi_mode
            if mode is not None:
                context_mode = mode
            if protocol is not None:
                context_protocol = protocol
            if bw is not None:
                context_bw = bw
            if channel is not None:
                context_channel = channel
            if rssi is not None:
                context_rssi = rssi

            if not isinstance(txrx, str):
                continue
            txrx_token = txrx.strip().upper()
            if txrx_token not in {"RX", "TX"}:
                continue

            band = _parse_band_token(context_wifi_mode)
            bw_mhz = _parse_bandwidth_mhz(context_bw)
            if not band or bw_mhz is None or context_channel is None:
                continue

            key = (band, int(context_channel))
            spec = required.get(key)
            if spec is None:
                continue

            direction = "downlink" if txrx_token == "RX" else "uplink"

            sample_values = [
                float(v) for v in (first, second, third) if isinstance(v, (int, float)) and not isinstance(v, bool)
            ]
            peak = max(sample_values) if sample_values else None

            if not isinstance(avg, (int, float)) or isinstance(avg, bool):
                continue

            standard = _parse_standard(context_wifi_mode) or spec.wireless_mode
            protocol_token = "" if context_protocol is None else str(context_protocol).strip()
            mode_token = self._normalize_peak_mode(context_mode)
            unique = (band, int(bw_mhz), int(context_channel), direction, mode_token)
            if unique in seen_mode:
                continue
            seen_mode.add(unique)
            scenario_group_key = build_peak_scenario_group_key(
                spec,
                standard=standard,
                bandwidth_mhz=int(bw_mhz),
            )

            rows.append(
                _performance_row(
                    test_category="PEAK_THROUGHPUT",
                    standard=standard,
                    band=band,
                    bandwidth_mhz=int(bw_mhz),
                    channel=int(context_channel),
                    protocol=protocol_token or "TCP",
                    mode=mode_token,
                    direction=direction,
                    path_loss_db=0.0,
                    rssi=float(context_rssi)
                    if isinstance(context_rssi, (int, float)) and not isinstance(context_rssi, bool)
                    else None,
                    angle_deg=None,
                    throughput_mbps=float(avg),
                    throughput_peak_mbps=peak,
                    scenario_group_key=scenario_group_key,
                )
            )

        return rows, []

    @staticmethod
    def _normalize_peak_mode(value: Any) -> str:
        text = "" if value is None else str(value).strip().upper()
        if not text:
            return ""
        if "BLE" in text and "CLASSIC" in text:
            return "Wi-Fi BLE CLASSIC"
        if "BLE" in text:
            return "Wi-Fi BLE"
        if "WIFI" in text:
            return "Wi-Fi Only"
        return ""

    def build_rvr_rows(self, workbook) -> Tuple[List[Dict[str, Any]], List[str]]:
        ws = workbook["RVR"]
        rows: List[Dict[str, Any]] = []
        allowed_channels_by_band: Dict[str, set[int]] = {}
        for spec in self._scenarios:
            allowed_channels_by_band.setdefault(spec.band_token, set()).add(int(spec.channel))

        def append_duplex_rows(
            *,
            standard: str,
            band: str,
            bandwidth_mhz: int,
            channel: int,
            path_loss_db: float,
            angle_deg: float,
            downlink_throughput_mbps: Optional[float],
            uplink_throughput_mbps: Optional[float],
            downlink_rssi: Optional[float],
            uplink_rssi: Optional[float],
            scenario_group_key: str,
        ) -> None:
            base = dict(
                test_category="RVR",
                standard=standard,
                band=band,
                bandwidth_mhz=bandwidth_mhz,
                channel=channel,
                protocol="TCP",
                mode=None,
                path_loss_db=path_loss_db,
                angle_deg=angle_deg,
                throughput_peak_mbps=None,
                scenario_group_key=scenario_group_key,
            )
            rows.append(
                _performance_row(
                    **base,
                    direction="downlink",
                    rssi=downlink_rssi,
                    throughput_mbps=downlink_throughput_mbps,
                )
            )
            rows.append(
                _performance_row(
                    **base,
                    direction="uplink",
                    rssi=uplink_rssi,
                    throughput_mbps=uplink_throughput_mbps,
                )
            )

        def find_title_row(start_row: int) -> Optional[str]:
            for offset in range(1, 8):
                r = start_row - offset
                if r <= 0:
                    break
                v = ws.cell(r, 1).value
                if not isinstance(v, str):
                    continue
                text = v.strip()
                if not text:
                    continue
                upper = text.upper()
                if "2.4G" in upper or "5G" in upper or "6G" in upper:
                    return text
            return None

        def parse_title(text: str) -> Tuple[str, str, int]:
            upper = (text or "").strip().upper()
            if "2.4G" in upper:
                band = "2.4"
            elif "5G" in upper:
                band = "5"
            elif "6G" in upper:
                band = "6"
            else:
                band = ""

            if "11AX" in upper or "HE" in upper:
                standard = "11ax"
            elif "11AC" in upper:
                standard = "11ac"
            elif "11N" in upper or "HT" in upper:
                standard = "11n"
            else:
                standard = ""

            bw = 0
            for token, value in (("HT20", 20), ("HT40", 40), ("HE80", 80), ("HE160", 160)):
                if token in upper:
                    bw = value
                    break
            if bw == 0:
                if "20M" in upper:
                    bw = 20
                elif "40M" in upper:
                    bw = 40
                elif "80M" in upper:
                    bw = 80
                elif "160M" in upper:
                    bw = 160
            return band, standard, bw

        def parse_channel_label(value: Any) -> Optional[int]:
            if not isinstance(value, str):
                return None
            text = value.strip().upper()
            if not text.startswith("CH"):
                return None
            digits = "".join(ch for ch in text if ch.isdigit())
            return int(digits) if digits else None

        def find_rssi_item_col(header_row: int) -> Optional[int]:
            for c in range(2, ws.max_column + 1):
                v = ws.cell(header_row, c).value
                if v != "Item":
                    continue
                for probe in range(c, min(ws.max_column, c + 15) + 1):
                    cell = ws.cell(header_row, probe).value
                    if isinstance(cell, str) and "RSSI" in cell.upper():
                        return c
            return None

        for header_row in range(1, ws.max_row + 1):
            if ws.cell(header_row, 1).value != "Item":
                continue
            if not isinstance(ws.cell(header_row, 2).value, str):
                continue
            if not isinstance(ws.cell(header_row, 3).value, str):
                continue

            rx_header_col = None
            tx_header_col = None
            for c in range(1, ws.max_column + 1):
                v = ws.cell(header_row, c).value
                if not isinstance(v, str):
                    continue
                upper = v.upper()
                if rx_header_col is None and "RX" in upper and "MBPS" in upper:
                    rx_header_col = c
                if tx_header_col is None and "TX" in upper and "MBPS" in upper:
                    tx_header_col = c
            if rx_header_col is None or tx_header_col is None:
                continue

            title = find_title_row(header_row)
            if not title:
                continue
            band, standard, bw_mhz = parse_title(title)
            if not band or bw_mhz <= 0:
                continue
            if band == "2.4" and bw_mhz == 20:
                continue

            allowed_channels = allowed_channels_by_band.get(band, set())
            if not allowed_channels:
                continue

            channel_row = header_row + 1
            rx_cols: Dict[int, int] = {}
            tx_cols: Dict[int, int] = {}

            for c in range(rx_header_col, tx_header_col):
                ch = parse_channel_label(ws.cell(channel_row, c).value)
                if ch is not None and ch in allowed_channels and ch not in rx_cols:
                    rx_cols[ch] = c
            for c in range(tx_header_col, ws.max_column + 1):
                ch = parse_channel_label(ws.cell(channel_row, c).value)
                if ch is not None and ch in allowed_channels and ch not in tx_cols:
                    tx_cols[ch] = c
                if ch is None and tx_cols:
                    break

            if not rx_cols or not tx_cols:
                continue

            rssi_item_col = find_rssi_item_col(header_row)
            rssi_rx_header_col = None
            rssi_tx_header_col = None
            rssi_rx_cols: Dict[int, int] = {}
            rssi_tx_cols: Dict[int, int] = {}
            if rssi_item_col is not None:
                for c in range(rssi_item_col, ws.max_column + 1):
                    v = ws.cell(header_row, c).value
                    if not isinstance(v, str):
                        continue
                    upper = v.upper().replace(" ", "_")
                    if rssi_rx_header_col is None and "RX_RSSI" in upper:
                        rssi_rx_header_col = c
                    if rssi_tx_header_col is None and "TX_RSSI" in upper:
                        rssi_tx_header_col = c
                if rssi_rx_header_col is not None and rssi_tx_header_col is not None:
                    for c in range(rssi_rx_header_col, rssi_tx_header_col):
                        ch = parse_channel_label(ws.cell(channel_row, c).value)
                        if ch is not None and ch in allowed_channels and ch not in rssi_rx_cols:
                            rssi_rx_cols[ch] = c
                    for c in range(rssi_tx_header_col, ws.max_column + 1):
                        ch = parse_channel_label(ws.cell(channel_row, c).value)
                        if ch is not None and ch in allowed_channels and ch not in rssi_tx_cols:
                            rssi_tx_cols[ch] = c
                        if ch is None and rssi_tx_cols:
                            break

            data_row = header_row + 2
            while data_row <= ws.max_row:
                att = ws.cell(data_row, 2).value
                if att is None:
                    break
                att_value = int(float(att))
                angle_value = 180.0
                for ch, rx_col in rx_cols.items():
                    tx_col = tx_cols.get(ch)
                    if tx_col is None:
                        continue
                    rx_value = ws.cell(data_row, rx_col).value
                    tx_value = ws.cell(data_row, tx_col).value
                    rx_throughput = (
                        float(rx_value) if isinstance(rx_value, (int, float)) and not isinstance(rx_value, bool) else None
                    )
                    tx_throughput = (
                        float(tx_value) if isinstance(tx_value, (int, float)) and not isinstance(tx_value, bool) else None
                    )
                    rx_rssi = None
                    tx_rssi = None
                    if rssi_rx_cols:
                        v = ws.cell(data_row, rssi_rx_cols.get(ch, 0)).value
                        if isinstance(v, (int, float)) and not isinstance(v, bool):
                            rx_rssi = float(v)
                    if rssi_tx_cols:
                        v = ws.cell(data_row, rssi_tx_cols.get(ch, 0)).value
                        if isinstance(v, (int, float)) and not isinstance(v, bool):
                            tx_rssi = float(v)

                    spec = self._scenario_by_channel.get((band, ch))
                    if spec is None:
                        continue
                    scenario_key = build_peak_scenario_group_key(
                        spec,
                        standard=standard,
                        bandwidth_mhz=bw_mhz,
                    )
                    append_duplex_rows(
                        standard=standard,
                        band=band,
                        bandwidth_mhz=bw_mhz,
                        channel=ch,
                        path_loss_db=float(att_value),
                        angle_deg=angle_value,
                        downlink_throughput_mbps=rx_throughput,
                        uplink_throughput_mbps=tx_throughput,
                        downlink_rssi=rx_rssi,
                        uplink_rssi=tx_rssi,
                        scenario_group_key=scenario_key,
                    )
                data_row += 1

        return rows, []

    def build_rvo_rows(self, workbook) -> Tuple[List[Dict[str, Any]], List[str]]:
        ws = workbook["RVO"]
        rows: List[Dict[str, Any]] = []

        required_by_band_bw: Dict[Tuple[str, int], List[int]] = {}
        for spec in self._scenarios:
            required_by_band_bw.setdefault((spec.band_token, spec.bandwidth_mhz), []).append(spec.channel)

        start_rows: List[Tuple[str, int, int, str]] = []
        for r in range(1, ws.max_row + 1):
            v = ws.cell(r, 1).value
            if not isinstance(v, str):
                continue
            text = v.strip().upper()
            if "2.4G" in text and "HT40" in text:
                start_rows.append(("2.4", 40, r, "11n"))
            if "5G" in text and "HE80" in text:
                start_rows.append(("5", 80, r, "11ax"))

        for band, bw_mhz, block_start, standard in start_rows:
            required_channels = required_by_band_bw.get((band, bw_mhz), [])
            block_end = ws.max_row
            for _other_band, _other_bw, other_start, _ in start_rows:
                if other_start > block_start:
                    block_end = min(block_end, other_start - 1)

            for item_row in range(block_start, block_end + 1):
                ch_header = ws.cell(item_row, 2).value
                metric_header = ws.cell(item_row, 4).value
                if ch_header != "CH" or not isinstance(metric_header, str):
                    continue
                metric = metric_header.strip().upper()
                if "RX" in metric:
                    direction = "downlink"
                elif "TX" in metric:
                    direction = "uplink"
                else:
                    continue

                angle_row = item_row + 1
                angles: List[Tuple[int, float]] = []
                for c in range(4, 12):
                    angle_value = _parse_angle(ws.cell(angle_row, c).value)
                    if angle_value is not None:
                        angles.append((c, float(angle_value)))
                if not angles:
                    continue

                r = angle_row + 1
                while r <= block_end:
                    ch_value = ws.cell(r, 2).value
                    att_value = ws.cell(r, 3).value
                    if ch_value == "CH" and isinstance(ws.cell(r, 4).value, str):
                        break
                    if not isinstance(ch_value, str) or not isinstance(att_value, str):
                        r += 1
                        continue
                    if att_value.strip().upper() != "0DB":
                        r += 1
                        continue

                    ch_text = ch_value.strip().upper()
                    if not ch_text.startswith("CH"):
                        r += 1
                        continue
                    ch_digits = "".join(ch for ch in ch_text if ch.isdigit())
                    if not ch_digits:
                        r += 1
                        continue
                    channel = int(ch_digits)
                    if channel not in required_channels:
                        r += 1
                        continue

                    spec = self._scenario_by_channel[(band, channel)]
                    scenario_key = build_peak_scenario_group_key(
                        spec,
                        standard=standard,
                        bandwidth_mhz=bw_mhz,
                    )
                    for col_idx, angle in angles:
                        val = ws.cell(r, col_idx).value
                        throughput = (
                            float(val) if isinstance(val, (int, float)) and not isinstance(val, bool) else None
                        )
                        if throughput is None:
                            continue
                        rows.append(
                            _performance_row(
                                test_category="RVO",
                                standard=standard,
                                band=band,
                                bandwidth_mhz=bw_mhz,
                                channel=channel,
                                protocol="TCP",
                                mode=None,
                                direction=direction,
                                path_loss_db=0.0,
                                rssi=None,
                                angle_deg=float(angle),
                                throughput_mbps=throughput,
                                throughput_peak_mbps=None,
                                scenario_group_key=scenario_key,
                            )
                        )
                    r += 1

        return rows, []

    def build_rows(
        self,
        path: str | Path,
        *,
        types: Iterable[str],
        throughput_sheet_name: Optional[str] = None,
    ) -> Tuple[Dict[str, List[Dict[str, Any]]], List[str]]:
        workbook = self._load_workbook(path)
        selected = [t.strip().upper() for t in types if str(t).strip()]

        throughput_sheet = throughput_sheet_name
        if throughput_sheet is None:
            excluded = {"Summary", "Test Setup", "RVR", "RVO", "MI_HW_cases-65", "BT-distance"}
            candidates = [name for name in workbook.sheetnames if name not in excluded]
            throughput_sheet = candidates[0] if candidates else None

        out: Dict[str, List[Dict[str, Any]]] = {}
        issues: List[str] = []

        alias_map = {
            "PEAK": "PEAK_THROUGHPUT",
            "THROUGHPUT": "PEAK_THROUGHPUT",
        }
        for t in selected:
            key = alias_map.get(t, t)
            if key == "PEAK_THROUGHPUT":
                if throughput_sheet is None:
                    issues.append("PEAK_THROUGHPUT: missing throughput sheet")
                    continue
                if throughput_sheet not in workbook.sheetnames:
                    issues.append(f"PEAK_THROUGHPUT: worksheet {throughput_sheet!r} not found")
                    continue
                try:
                    rows, row_issues = self.build_peak_throughput_rows(workbook, sheet_name=throughput_sheet)
                except Exception as exc:
                    issues.append(f"PEAK_THROUGHPUT: parse failed ({exc})")
                    continue
            elif key == "RVR":
                if "RVR" not in workbook.sheetnames:
                    issues.append("RVR: worksheet 'RVR' not found")
                    continue
                try:
                    rows, row_issues = self.build_rvr_rows(workbook)
                except Exception as exc:
                    issues.append(f"RVR: parse failed ({exc})")
                    continue
            elif key == "RVO":
                if "RVO" not in workbook.sheetnames:
                    issues.append("RVO: worksheet 'RVO' not found")
                    continue
                try:
                    rows, row_issues = self.build_rvo_rows(workbook)
                except Exception as exc:
                    issues.append(f"RVO: parse failed ({exc})")
                    continue
            else:
                issues.append(f"Unknown import type: {t}")
                continue
            out[key] = rows
            if not rows:
                issues.append(f"{key}: no rows parsed")
            issues.extend(row_issues)

        return out, issues


class ImportController:
    def __init__(self, main_window) -> None:
        self._main = main_window

    def run_import(self) -> None:
        dialog = ImportDialog(self._main)
        if dialog.exec_() != dialog.Accepted:
            return
        selected_types = dialog.selected_types()
        if not selected_types:
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self._main,
            "Select Excel file to import",
            str(Path.cwd()),
            "Excel Files (*.xlsx)",
        )
        if not file_path:
            return

        importer = PerformanceExcelImporter()
        try:
            extracted, issues = importer.build_rows(file_path, types=selected_types)
        except Exception as exc:
            MessageBox("Import failed", str(exc), self._main).exec()
            return

        non_empty = {k: v for k, v in extracted.items() if v}
        if issues:
            selected = ", ".join(selected_types)
            will_import = ", ".join(sorted(non_empty.keys())) if non_empty else "(none)"
            details = [f"Selected: {selected}", f"Will import: {will_import}", "", "Issues:"]
            details.extend(f"- {item}" for item in issues[:30])
            if len(issues) > 30:
                details.append(f"... ({len(issues) - 30} more)")

            if not non_empty:
                MessageBox("Import failed", "\n".join(details), self._main).exec()
                return

            box = MessageBox("Import validation", "\n".join(details), self._main)
            box.yesButton.setText("Import available")
            box.cancelButton.setText("Cancel")
            box.exec()
            if box.result() != QDialog.Accepted:
                return

        if not any(extracted.values()):
            MessageBox("Import failed", "No rows matched the import filters.", self._main).exec()
            return

        payload = self._collect_default_config()
        try:
            inserted = self._sync_golden_to_db(payload, file_path, extracted)
        except Exception as exc:
            MessageBox("Import failed", str(exc), self._main).exec()
            return

        summary_lines = [f"Inserted {inserted} performance row(s)."]
        if issues:
            summary_lines.append("")
            summary_lines.append("Some selected types were skipped/failed. See validation details above.")
        MessageBox("Import completed", "\n".join(summary_lines), self._main).exec()

    def _collect_default_config(self) -> dict[str, str]:
        view = self._main.caseConfigPage
        field_widgets: Mapping[str, Any] = view.field_widgets

        return {
            "brand": field_widgets["project.customer"].currentText(),
            "product_line": field_widgets["project.product_line"].currentText(),
            "project_name": field_widgets["project.project"].currentText(),
            "main_chip": field_widgets["project.main_chip"].text(),
            "wifi_module": field_widgets["project.wifi_module"].text(),
            "interface": field_widgets["project.interface"].text(),
            "hardware_version": field_widgets["hardware_info.hardware_version"].text(),
            "software_version": field_widgets["software_info.software_version"].text(),
            "driver_version": field_widgets["software_info.driver_version"].text(),
            "android_version": field_widgets["system.version"].currentText(),
            "kernel_version": field_widgets["system.kernel_version"].currentText(),
        }

    def _sync_golden_to_db(
        self,
        payload: Mapping[str, Any],
        excel_path: str,
        extracted: Mapping[str, List[Mapping[str, Any]]],
    ) -> int:
        project_payload = {
            "brand": payload.get("brand") or "",
            "product_line": payload.get("product_line") or "",
            "project_name": payload.get("project_name") or "",
            "hardware_version": payload.get("hardware_version") or "",
            "main_chip": payload.get("main_chip") or "",
            "wifi_module": payload.get("wifi_module") or "",
            "interface": payload.get("interface") or "",
            "ecosystem": payload.get("ecosystem") or "",
            "payload_json": None,
        }
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        with MySqlClient() as client:
            ensure_report_tables(client)
            project_id = ensure_project(client, project_payload)
            manager = PerformanceTableManager(client)
            inserted_total = 0

            for data_type, rows in extracted.items():
                if not rows:
                    continue

                existing = self._find_existing_golden_report(
                    client,
                    project_id=int(project_id),
                    report_type=str(data_type),
                )
                if existing and not self._confirm_overwrite_existing(existing, report_type=str(data_type)):
                    continue
                if existing:
                    client.execute(
                        "DELETE FROM `test_report` WHERE `id`=%s",
                        (int(existing["test_report_id"]),),
                    )

                report_name = f"GOLDEN_{data_type}_{stamp}"
                notes = "\n".join([excel_path, f"type={data_type}"])
                report_id = ensure_test_report(
                    client,
                    project_id=int(project_id),
                    report_name=report_name,
                    case_path=None,
                    is_golden=True,
                    report_type=str(data_type),
                    golden_group="GOLDEN",
                    notes=notes,
                )
                _store_excel_artifact(
                    client,
                    test_report_id=int(report_id),
                    excel_path=excel_path,
                )
                execution_id = self._insert_execution(
                    client,
                    test_report_id=int(report_id),
                    execution_type=data_type,
                    csv_name=f"{Path(excel_path).name}:{data_type}",
                    csv_path=excel_path,
                    run_source="import",
                    payload={
                        "source": "excel",
                        "excel_path": excel_path,
                        "data_type": data_type,
                        "ui_payload": dict(payload),
                    },
                )
                inserted_total += _insert_performance_rows(
                    manager,
                    execution_id=execution_id,
                    csv_name=Path(excel_path).name,
                    data_type=data_type,
                    rows=list(rows),
                )
            return inserted_total

    def _find_existing_golden_report(
        self,
        client: MySqlClient,
        *,
        project_id: int,
        report_type: str,
    ) -> Optional[Dict[str, Any]]:
        sql = (
            "SELECT "
            "tr.id AS test_report_id, tr.report_name, tr.created_at, tr.updated_at, "
            "a.file_name, a.created_at AS artifact_created_at "
            "FROM test_report AS tr "
            "LEFT JOIN artifact AS a ON a.test_report_id = tr.id "
            "WHERE tr.project_id = %s AND tr.is_golden = 1 "
            "AND tr.report_type = %s AND tr.golden_group = %s "
            "ORDER BY tr.updated_at DESC, tr.id DESC "
            "LIMIT 1"
        )
        rows = client.query_all(sql, (int(project_id), report_type, "GOLDEN"))
        if rows:
            return rows[0]

        legacy_sql = (
            "SELECT "
            "tr.id AS test_report_id, tr.report_name, tr.created_at, tr.updated_at, "
            "a.file_name, a.created_at AS artifact_created_at, "
            "GROUP_CONCAT(DISTINCT ex.execution_type ORDER BY ex.execution_type) AS execution_types "
            "FROM test_report AS tr "
            "JOIN execution AS ex ON ex.test_report_id = tr.id "
            "LEFT JOIN artifact AS a ON a.test_report_id = tr.id "
            "WHERE tr.project_id = %s AND tr.is_golden = 1 "
            "AND (tr.report_type IS NULL OR tr.report_type = '') "
            "AND ex.execution_type = %s "
            "GROUP BY tr.id "
            "ORDER BY tr.updated_at DESC, tr.id DESC "
            "LIMIT 1"
        )
        rows = client.query_all(legacy_sql, (int(project_id), report_type))
        if rows:
            row = dict(rows[0])
            row["legacy"] = True
            return row
        return None

    def _confirm_overwrite_existing(self, existing: Mapping[str, Any], *, report_type: str) -> bool:
        file_name = existing.get("file_name") or "(unknown)"
        uploaded_at = existing.get("artifact_created_at") or existing.get("updated_at") or existing.get("created_at")
        report_name = existing.get("report_name") or "(unknown)"
        legacy = bool(existing.get("legacy"))
        legacy_types = existing.get("execution_types") or ""

        details_lines = [
            f"Project already has golden data for type: {report_type}",
            f"Existing report: {report_name}",
            f"Existing excel: {file_name}",
            f"Uploaded at: {uploaded_at}",
        ]
        if legacy:
            details_lines.append("")
            details_lines.append("Legacy golden report detected.")
            if legacy_types:
                details_lines.append(f"This legacy report contains types: {legacy_types}")
            details_lines.append("Overwriting will delete the entire legacy report.")

        box = MessageBox("Overwrite golden data?", "\n".join(details_lines), self._main)
        box.yesButton.setText("Overwrite")
        box.cancelButton.setText("Cancel")
        box.exec()
        return box.result() == QDialog.Accepted

    def _insert_execution(
        self,
        client: MySqlClient,
        *,
        test_report_id: int,
        execution_type: str,
        csv_name: str,
        csv_path: str,
        run_source: str,
        payload: Mapping[str, Any],
        duration_seconds: Optional[float] = None,
    ) -> int:
        insert_sql = (
            "INSERT INTO `execution` "
            "(`test_report_id`, `execution_type`, `serial_number`, `connect_type`, `adb_device`, `telnet_ip`, "
            "`software_version`, `driver_version`, `android_version`, `kernel_version`, "
            "`router_name`, `router_address`, `rf_model`, `corner_model`, `lab_name`, "
            "`csv_name`, `csv_path`, `run_source`, `duration_seconds`, `payload_json`) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        )
        payload_json = json.dumps(dict(payload), ensure_ascii=True, separators=(",", ":"))
        return client.insert(
            insert_sql,
            (
                test_report_id,
                execution_type,
                None,
                None,
                None,
                None,
                payload.get("ui_payload", {}).get("software_version"),
                payload.get("ui_payload", {}).get("driver_version"),
                payload.get("ui_payload", {}).get("android_version"),
                payload.get("ui_payload", {}).get("kernel_version"),
                None,
                None,
                None,
                None,
                None,
                csv_name,
                csv_path,
                (run_source or "import")[:32],
                int(duration_seconds) if duration_seconds is not None else None,
                payload_json,
            ),
        )
