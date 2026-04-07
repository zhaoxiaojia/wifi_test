from __future__ import annotations

from typing import Callable, Final, Iterable, Optional, Sequence

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QScrollArea, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, CheckBox, MessageBox, MessageBoxBase, SubtitleLabel


class ImportSheetsDialog(MessageBoxBase):
    def __init__(
        self,
        parent: QWidget,
        *,
        summary_lines: Sequence[str],
        sheet_names: Sequence[str],
        on_import: Optional[Callable[[list[str]], None]] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Import sheets")
        self.yesButton.setText("Import")
        self.cancelButton.setText("Cancel")

        self._on_import: Optional[Callable[[list[str]], None]] = on_import
        self._checkboxes: list[CheckBox] = []
        self._loading: bool = False

        title = SubtitleLabel("Select worksheets", self)
        self.viewLayout.addWidget(title)

        for line in summary_lines:
            text = str(line).strip()
            if not text:
                continue
            self.viewLayout.addWidget(BodyLabel(text, self))

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget(scroll)
        layout: Final[QVBoxLayout] = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        for name in sheet_names:
            label = str(name).strip()
            if not label:
                continue
            cb = CheckBox(label, container)
            cb.setChecked(True)
            self._checkboxes.append(cb)
            layout.addWidget(cb)

        layout.addStretch(1)
        scroll.setWidget(container)
        self.viewLayout.addWidget(scroll)

        self.yesButton.clicked.connect(self._handle_import_clicked)

    def set_loading(self, loading: bool) -> None:
        self._loading = bool(loading)
        self.yesButton.setEnabled(not self._loading)
        self.cancelButton.setEnabled(not self._loading)
        for cb in self._checkboxes:
            cb.setEnabled(not self._loading)
        self.yesButton.setText("Importing..." if self._loading else "Import")

    def selected_sheets(self) -> list[str]:
        return [cb.text() for cb in self._checkboxes if cb.isChecked()]

    def _handle_import_clicked(self) -> None:
        if self._loading:
            return

        selected = self.selected_sheets()
        if not selected:
            MessageBox("Import blocked", "Select at least one worksheet to import.", self).exec()
            return

        self.set_loading(True)
        if self._on_import is None:
            self.accept()
            return

        try:
            self._on_import(list(selected))
        except Exception as exc:
            self.set_loading(False)
            MessageBox("Import failed", str(exc), self).exec()

