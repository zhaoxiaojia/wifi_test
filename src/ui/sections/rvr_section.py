"""Section for RvR generator and CSV configuration."""

from __future__ import annotations

from typing import Any

from PyQt5.QtWidgets import QLabel, QGroupBox, QVBoxLayout, QWidget, QSizePolicy

from qfluentwidgets import ComboBox, LineEdit

from ..sections import register_case_sections, register_section
from ..sections.base import ConfigSection


@register_section("rvr", case_types=("default",))
class RvrSection(ConfigSection):
    """Render RvR tool configuration with iperf/ixChariot controls."""

    panel = "execution"

    def build(self, config: dict[str, Any]) -> None:  # type: ignore[override]
        value = config.get("rvr") if isinstance(config, dict) else {}
        if not isinstance(value, dict):
            value = {}
        group = QGroupBox("RvR Config", self.page)
        vbox = QVBoxLayout(group)
        self.page.rvr_tool_combo = ComboBox(self.page)
        self.page.rvr_tool_combo.addItems(["iperf", "ixchariot"])
        self.page.rvr_tool_combo.setCurrentText(value.get("tool", "iperf"))
        self.page.rvr_tool_combo.currentTextChanged.connect(self.page.on_rvr_tool_changed)
        vbox.addWidget(QLabel("Data Generator:", group))
        vbox.addWidget(self.page.rvr_tool_combo)

        self.page.rvr_iperf_group = QWidget()
        iperf_box = QVBoxLayout(self.page.rvr_iperf_group)
        self.page.iperf_path_edit = LineEdit(self.page)
        self.page.iperf_path_edit.setPlaceholderText("iperf path (DUT)")
        self.page.iperf_path_edit.setText(value.get("iperf", {}).get("path", ""))
        iperf_box.addWidget(QLabel("Path:", group))
        iperf_box.addWidget(self.page.iperf_path_edit)

        self.page.iperf_server_edit = LineEdit(self.page)
        self.page.iperf_server_edit.setPlaceholderText("iperf -s command")
        self.page.iperf_server_edit.setText(value.get("iperf", {}).get("server_cmd", ""))
        iperf_box.addWidget(QLabel("Server cmd:", group))
        iperf_box.addWidget(self.page.iperf_server_edit)

        self.page.iperf_client_edit = LineEdit(self.page)
        self.page.iperf_client_edit.setPlaceholderText("iperf -c command")
        self.page.iperf_client_edit.setText(value.get("iperf", {}).get("client_cmd", ""))
        iperf_box.addWidget(QLabel("Client cmd:", group))
        iperf_box.addWidget(self.page.iperf_client_edit)
        vbox.addWidget(self.page.rvr_iperf_group)

        self.page.rvr_ix_group = QWidget()
        ix_box = QVBoxLayout(self.page.rvr_ix_group)
        vbox.addWidget(QLabel("Select config csv file", group))
        self.page.csv_combo = ComboBox(self.page)
        self.page.csv_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.page.csv_combo.setEnabled(False)
        self.page.csv_combo.currentIndexChanged.connect(self.page.on_csv_changed)
        self.page.csv_combo.activated.connect(self.page.on_csv_activated)
        vbox.addWidget(self.page.csv_combo)
        self.page.ix_path_edit = LineEdit(self.page)
        self.page.ix_path_edit.setPlaceholderText("IxChariot path")
        self.page.ix_path_edit.setText(value.get("ixchariot", {}).get("path", ""))
        ix_box.addWidget(self.page.ix_path_edit)
        vbox.addWidget(self.page.rvr_ix_group)

        self.page.repeat_combo = LineEdit()
        self.page.repeat_combo.setText(str(value.get("repeat", 0)))
        vbox.addWidget(QLabel("Repeat:", group))
        vbox.addWidget(self.page.repeat_combo)

        self.page.rvr_threshold_edit = LineEdit()
        self.page.rvr_threshold_edit.setPlaceholderText("throughput threshold")
        self.page.rvr_threshold_edit.setText(str(value.get("throughput_threshold", 0)))
        vbox.addWidget(QLabel("Zero Point Threshold:", group))
        vbox.addWidget(self.page.rvr_threshold_edit)

        self.register_group("rvr", group, is_dut=False)
        self.register_field("rvr.tool", self.page.rvr_tool_combo)
        self.register_field("rvr.iperf.path", self.page.iperf_path_edit)
        self.register_field("rvr.iperf.server_cmd", self.page.iperf_server_edit)
        self.register_field("rvr.iperf.client_cmd", self.page.iperf_client_edit)
        self.register_field("rvr.ixchariot.path", self.page.ix_path_edit)
        self.register_field("rvr.repeat", self.page.repeat_combo)
        self.register_field("rvr.throughput_threshold", self.page.rvr_threshold_edit)
        self.page.on_rvr_tool_changed(self.page.rvr_tool_combo.currentText())


__all__ = ["RvrSection"]

register_case_sections("default", ["rvr"])
