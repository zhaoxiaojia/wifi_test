"""Controller for the About page behaviour.

This module contains the non-UI logic that previously lived in
``src.ui.about_page.AboutPage``. It is intentionally UI-agnostic in
the sense that it operates on the pure view object (``AboutView``)
and wires the behaviour (open paths, external links, populate
metadata) to the view's widgets.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QMessageBox

from src.util.constants import Paths, get_build_metadata
from src.util.test_history import get_total_test_duration_hh_mm
from src.ui.view.theme.style import (
    acknowledgements_from_readme,
    latest_version_from_changelog,
    normalize_data_source_label,
)


class AboutController:
    """Controller that wires behaviour onto an ``AboutView`` instance.

    Parameters
    ----------
    view : AboutView
        The pure UI view instance created by the caller.
    """

    def __init__(self, view: Any) -> None:
        self.view = view

        # Wire directory shortcut buttons.
        self.view.open_config_btn.clicked.connect(lambda: self.open_path(Paths.CONFIG_DIR))
        self.view.open_res_btn.clicked.connect(lambda: self.open_path(Paths.RES_DIR))

        # Wire frequently used config file buttons.
        for btn in getattr(self.view, "config_file_buttons", []):
            file_name = btn.property("configFileName") or btn.text()
            btn.clicked.connect(lambda _=False, name=file_name: self.open_path(os.path.join(Paths.CONFIG_DIR, name)))

        # Wire support / documentation buttons.
        self.view.email_btn.clicked.connect(self.show_support_email)
        self.view.jira_btn.clicked.connect(self.open_ticket_portal)
        self.view.doc_btn.clicked.connect(self.open_internal_doc)

        # Populate metadata into the table and data source label.
        self.populate_metadata()

    def open_path(self, path: str) -> None:
        """Open a local path in the OS file manager."""
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def show_support_email(self) -> None:
        QMessageBox.information(
            self.view,
            "Maintainer Contact",
            "For assistance, contact the testing platform maintainer: chao.li@amlogic.com",
        )

    def open_ticket_portal(self) -> None:
        QDesktopServices.openUrl(QUrl("https://jira.amlogic.com/browse/FQ-383"))

    def open_internal_doc(self) -> None:
        QDesktopServices.openUrl(QUrl("https://confluence.amlogic.com/pages/viewpage.action?pageId=448826402"))

    def populate_metadata(self) -> None:
        """Read build metadata and fill the view's table and data source label."""
        metadata = get_build_metadata()
        latest_version = latest_version_from_changelog(metadata)
        acknowledgements = acknowledgements_from_readme()
        total_duration = get_total_test_duration_hh_mm()

        display_rows = [
            ("Application Name", metadata.get("package_name", "Unknown")),
            ("Version", latest_version or "Unknown"),
            ("Build Time", metadata.get("build_time", "Unknown")),
            ("Total Test Duration", total_duration or "00:00"),
            ("Author", "chao.li"),
            ("Acknowledgements", acknowledgements if acknowledgements else "Unknown"),
        ]

        table = getattr(self.view, "info_table")
        table.setRowCount(len(display_rows))
        for row, (label, value) in enumerate(display_rows):
            from PyQt5.QtCore import Qt
            from PyQt5.QtWidgets import QTableWidgetItem

            key_item = QTableWidgetItem(label)
            if not isinstance(value, str):
                value = str(value) if value is not None else ""
            value_item = QTableWidgetItem((value or "").strip() or "Unknown")
            key_item.setFlags(Qt.ItemIsEnabled)
            value_item.setFlags(Qt.ItemIsEnabled)
            table.setItem(row, 0, key_item)
            table.setItem(row, 1, value_item)
        table.resizeColumnsToContents()

        source = metadata.get("data_source", "Unknown") or "Unknown"
        source_label = getattr(self.view, "source_label")
        source_label.setText(f"Data Source: {normalize_data_source_label(source)}")
