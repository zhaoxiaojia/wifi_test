from __future__ import annotations

from pathlib import Path
import sys

import pytest

pd = pytest.importorskip("pandas")
openpyxl = pytest.importorskip("openpyxl")
Workbook = openpyxl.Workbook

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from src.tools.reporting.xiaomi_report import (  # noqa: E402  # pylint: disable=wrong-import-position
    _TemplateLayout,
    _populate_rvr,
    _populate_rvo,
)


def _build_minimal_workbook() -> Workbook:
    wb = Workbook()
    default = wb.active
    wb.remove(default)

    rvr = wb.create_sheet("Coffey RVR")
    rvr["A1"] = "Item"
    rvr["B1"] = "Attenuation"
    rvr["C1"] = "RX Mbps"
    rvr["D1"] = "TX Mbps"
    rvr["E1"] = "RX RSSI"
    rvr["F1"] = "TX RSSI"
    rvr["C2"] = "CH 36"
    rvr["D2"] = "CH 36"
    rvr["E2"] = "CH 36"
    rvr["F2"] = "CH 36"
    rvr["A3"] = "11AX HE80"
    rvr["B4"] = "0"
    rvr["B5"] = "10"

    rvo = wb.create_sheet("Coffey RVO")
    rvo["A1"] = "Item"
    rvo["D1"] = "RX Throughput (Mbps)"
    rvo["D2"] = "0"
    rvo["A3"] = "11AX HE80"
    rvo["B3"] = "CH 36"
    rvo["C3"] = "0"

    return wb


def _build_rvr_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Scenario_Group_Key": "SCENARIO|BAND=5G|MODE=11AX|BANDWIDTH=80MHZ|INTERFACE=USB",
                "__freq_key__": "5g",
                "__freq_band_display__": "5G",
                "__standard_key__": "11ax",
                "__standard_display__": "11AX",
                "__bandwidth_key__": "80mhz",
                "__bandwidth_display__": "80MHz",
                "__direction_key__": "RX",
                "__channel_key__": "36",
                "__db_key__": "0",
                "__throughput_value__": 120.5,
            },
            {
                "Scenario_Group_Key": "SCENARIO|BAND=5G|MODE=11AX|BANDWIDTH=80MHZ|INTERFACE=PCIE",
                "__freq_key__": "5g",
                "__freq_band_display__": "5G",
                "__standard_key__": "11ax",
                "__standard_display__": "11AX",
                "__bandwidth_key__": "80mhz",
                "__bandwidth_display__": "80MHz",
                "__direction_key__": "RX",
                "__channel_key__": "36",
                "__db_key__": "0",
                "__throughput_value__": 98.2,
            },
        ]
    )


def _build_rvr_fallback_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Scenario_Group_Key": "SCENARIO|BAND=5G|MODE=11AX|BANDWIDTH=160MHZ|INTERFACE=USB",
                "__freq_key__": "5g",
                "__freq_band_display__": "5G",
                "__standard_key__": "11ax",
                "__standard_display__": "11AX",
                "__bandwidth_key__": "160mhz",
                "__bandwidth_display__": "160MHz",
                "__direction_key__": "RX",
                "__channel_key__": "36",
                "__db_key__": "0",
                "__throughput_value__": 140.0,
            }
        ]
    )


def _build_rvo_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Scenario_Group_Key": "SCENARIO|BAND=5G|MODE=11AX|BANDWIDTH=80MHZ|INTERFACE=USB",
                "__freq_key__": "5g",
                "__freq_band_display__": "5G",
                "__standard_key__": "11ax",
                "__standard_display__": "11AX",
                "__bandwidth_key__": "80mhz",
                "__bandwidth_display__": "80MHz",
                "__direction_key__": "RX",
                "__channel_key__": "36",
                "__db_key__": "0",
                "__angle_key__": "0",
                "__angle_display__": "0",
                "__throughput_value__": 50.0,
            },
            {
                "Scenario_Group_Key": "SCENARIO|BAND=5G|MODE=11AX|BANDWIDTH=80MHZ|INTERFACE=PCIE",
                "__freq_key__": "5g",
                "__freq_band_display__": "5G",
                "__standard_key__": "11ax",
                "__standard_display__": "11AX",
                "__bandwidth_key__": "80mhz",
                "__bandwidth_display__": "80MHz",
                "__direction_key__": "RX",
                "__channel_key__": "36",
                "__db_key__": "0",
                "__angle_key__": "0",
                "__angle_display__": "0",
                "__throughput_value__": 80.0,
            },
        ]
    )


def _build_rvo_fallback_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Scenario_Group_Key": "SCENARIO|BAND=5G|MODE=11AX|BANDWIDTH=160MHZ|INTERFACE=USB",
                "__freq_key__": "5g",
                "__freq_band_display__": "5G",
                "__standard_key__": "11ax",
                "__standard_display__": "11AX",
                "__bandwidth_key__": "160mhz",
                "__bandwidth_display__": "160MHz",
                "__direction_key__": "RX",
                "__channel_key__": "36",
                "__db_key__": "0",
                "__angle_key__": "0",
                "__angle_display__": "0",
                "__throughput_value__": 70.0,
            }
        ]
    )


def test_populate_rvr_dynamic_creates_additional_blocks_and_titles():
    wb = _build_minimal_workbook()
    layout = _TemplateLayout(wb)
    df = _build_rvr_dataframe()

    _populate_rvr(layout, df)

    blocks = {block.scenario: block for block in layout.rvr_blocks.values()}
    assert "5G 11AX 80MHz USB" in blocks
    assert "5G 11AX 80MHz PCIE" in blocks

    usb_block = blocks["5G 11AX 80MHz USB"]
    pcie_block = blocks["5G 11AX 80MHz PCIE"]

    usb_row = usb_block.rows_by_db["0"]
    pcie_row = pcie_block.rows_by_db["0"]
    usb_column = usb_block.rx_columns["36"]
    pcie_column = pcie_block.rx_columns["36"]

    sheet = layout.rvr_sheet
    assert sheet.cell(row=usb_row, column=usb_column).value == 120.5
    assert sheet.cell(row=pcie_row, column=pcie_column).value == 98.2


def test_populate_rvr_dynamic_clones_template_for_unmapped_bandwidth():
    wb = _build_minimal_workbook()
    layout = _TemplateLayout(wb)
    df = _build_rvr_fallback_dataframe()

    _populate_rvr(layout, df)

    blocks = {block.scenario: block for block in layout.rvr_blocks.values()}
    assert "11AX HE80" in blocks
    assert "5G 11AX 160MHz USB" in blocks

    template_block = blocks["11AX HE80"]
    cloned_block = blocks["5G 11AX 160MHz USB"]

    assert template_block is not cloned_block
    assert cloned_block.identifier == "SCENARIO|BAND=5G|MODE=11AX|BANDWIDTH=160MHZ|INTERFACE=USB"

    usb_row = cloned_block.rows_by_db["0"]
    usb_column = cloned_block.rx_columns["36"]

    sheet = layout.rvr_sheet
    assert sheet.cell(row=usb_row, column=usb_column).value == 140.0
    assert template_block.scenario == "11AX HE80"


def test_populate_rvo_dynamic_creates_additional_blocks_and_titles():
    wb = _build_minimal_workbook()
    layout = _TemplateLayout(wb)
    df = _build_rvo_dataframe()

    _populate_rvo(layout, df)

    blocks = {block.scenario: block for block in layout.rvo_blocks.values()}
    assert "5G 11AX 80MHz USB" in blocks
    assert "5G 11AX 80MHz PCIE" in blocks

    usb_block = blocks["5G 11AX 80MHz USB"]
    pcie_block = blocks["5G 11AX 80MHz PCIE"]

    usb_dir = usb_block.directions["RX"]
    pcie_dir = pcie_block.directions["RX"]

    usb_row = usb_dir.rows_by_channel["36"]["0"]
    pcie_row = pcie_dir.rows_by_channel["36"]["0"]
    usb_column = layout.ensure_rvo_angle(usb_block, usb_dir, "0")
    pcie_column = layout.ensure_rvo_angle(pcie_block, pcie_dir, "0")

    sheet = layout.rvo_sheet
    assert sheet.cell(row=usb_row, column=usb_column).value == 50.0
    assert sheet.cell(row=pcie_row, column=pcie_column).value == 80.0


def test_populate_rvo_dynamic_clones_template_for_unmapped_bandwidth():
    wb = _build_minimal_workbook()
    layout = _TemplateLayout(wb)
    df = _build_rvo_fallback_dataframe()

    _populate_rvo(layout, df)

    blocks = {block.scenario: block for block in layout.rvo_blocks.values()}
    assert "11AX HE80" in blocks
    assert "5G 11AX 160MHz USB" in blocks

    template_block = blocks["11AX HE80"]
    cloned_block = blocks["5G 11AX 160MHz USB"]

    assert template_block is not cloned_block
    assert cloned_block.identifier == "SCENARIO|BAND=5G|MODE=11AX|BANDWIDTH=160MHZ|INTERFACE=USB"

    rx_block = cloned_block.directions["RX"]
    usb_row = rx_block.rows_by_channel["36"]["0"]
    usb_column = layout.ensure_rvo_angle(cloned_block, rx_block, "0")

    sheet = layout.rvo_sheet
    assert sheet.cell(row=usb_row, column=usb_column).value == 70.0
    assert template_block.scenario == "11AX HE80"
