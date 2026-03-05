from __future__ import annotations

from typing import List

from PyQt5.QtWidgets import QWidget
from qfluentwidgets import BodyLabel, CheckBox, MessageBoxBase, SubtitleLabel


class ImportDialog(MessageBoxBase):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Import")
        self.yesButton.setText("Import")
        self.cancelButton.setText("Cancel")

        title = SubtitleLabel("Import", self)
        subtitle = BodyLabel("Select data types to import", self)
        self.viewLayout.addWidget(title)
        self.viewLayout.addWidget(subtitle)

        self._peak_cb = CheckBox("Peak Throughput", self)
        self._rvr_cb = CheckBox("RVR", self)
        self._rvo_cb = CheckBox("RVO", self)
        self.viewLayout.addWidget(self._peak_cb)
        self.viewLayout.addWidget(self._rvr_cb)
        self.viewLayout.addWidget(self._rvo_cb)

        for cb in (self._peak_cb, self._rvr_cb, self._rvo_cb):
            cb.stateChanged.connect(self._sync_ok_enabled)
        self._sync_ok_enabled()

    def selected_types(self) -> List[str]:
        out: List[str] = []
        if self._peak_cb.isChecked():
            out.append("PEAK_THROUGHPUT")
        if self._rvr_cb.isChecked():
            out.append("RVR")
        if self._rvo_cb.isChecked():
            out.append("RVO")
        return out

    def _sync_ok_enabled(self) -> None:
        self.yesButton.setEnabled(bool(self.selected_types()))
