from __future__ import annotations

from PyQt5.QtCore import QObject
from qfluentwidgets import MessageBox


class ImportController(QObject):
    """Legacy controller stub.

    The previous implementation imported Excel artifacts into a MySQL-backed
    reporting database. Database features have been removed from this project,
    so the File -> Import action now shows a message instead of performing any
    import.
    """

    def __init__(self, main_window) -> None:
        super().__init__(main_window)
        self._main_window = main_window

    def run_import(self) -> None:
        MessageBox(
            "Import",
            "Database import has been removed from this project.",
            self._main_window,
        ).exec()

