"""Controller for the BT FW log analysis tool.

This controller owns I/O and behaviour for :class:`BtFwLogToolView`,
leaving the view focused on widget layout only.

For now the implementation is a lightweight stub; actual serial and
log parsing logic can be integrated later.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt5.QtWidgets import QFileDialog, QWidget

from src.ui.view.tools_bt_fw_log import BtFwLogToolView


class BtFwLogToolController:
    """Behaviour for the BT FW log analysis tool."""

    def __init__(self, view: BtFwLogToolView, parent: Optional[QWidget] = None) -> None:
        self.view = view
        self.parent = parent or view

        self.view.browseFileRequested.connect(self._on_browse_file)
        self.view.analyzeRequested.connect(self._on_analyze_requested)

    def _on_browse_file(self) -> None:
        """Open a file dialog and update the view with the selected path."""
        path, _ = QFileDialog.getOpenFileName(
            self.parent, "Select BT FW log file", str(Path.home()), "Log files (*.log *.txt);;All files (*.*)"
        )
        if not path:
            return
        self.view.set_file_path(path)

    def _on_analyze_requested(self) -> None:
        """Placeholder handler for the Analyze button."""
        self.view.append_result_text("Analysis is not implemented yet.")


__all__ = ["BtFwLogToolController"]
