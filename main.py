# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""Main entry point for the FAE‑QA Wi‑Fi Test Tool.

This module now only bootstraps the Qt application:

- sets up the Python path and working directory
- installs the global exception hook
- applies the Windows subprocess console-hiding patch
- creates the :class:`~src.ui.view.main_window.MainWindow` instance

All window layout and page/navigation logic lives in ``src/ui/view``.
"""

from __future__ import annotations

import sys
from pathlib import Path
import logging
import os
import multiprocessing

from PyQt5.QtWidgets import QApplication
from qfluentwidgets import setTheme, Theme

from src.util.constants import Paths, cleanup_temp_dir
from src.ui.view.main_window import MainWindow, log_exception


# Ensure project root is importable and working directory matches the executable
sys.path.insert(0, str(Path(__file__).parent))
os.chdir(Paths.BASE_DIR)

# Route uncaught exceptions through the shared handler in the view layer.
sys.excepthook = log_exception


multiprocessing.freeze_support()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    try:
        app = QApplication(sys.argv)
        setTheme(Theme.DARK)
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    finally:
        cleanup_temp_dir()

