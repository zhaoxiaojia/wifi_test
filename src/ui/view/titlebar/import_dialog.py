from __future__ import annotations

from typing import Final

from PyQt5.QtWidgets import QWidget
from qfluentwidgets import BodyLabel, CheckBox, MessageBoxBase, SubtitleLabel


class ImportDialog(MessageBoxBase):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Import")
        self.yesButton.setText("Import")
        self.cancelButton.setText("Cancel")

        title = SubtitleLabel("Import", self)
        subtitle = BodyLabel("Select import options", self)
        self.viewLayout.addWidget(title)
        self.viewLayout.addWidget(subtitle)

        self._golden_cb: Final[CheckBox] = CheckBox("Import as golden data", self)
        self._golden_cb.setChecked(False)
        self.viewLayout.addWidget(self._golden_cb)

    def import_as_golden(self) -> bool:
        return bool(self._golden_cb.isChecked())
