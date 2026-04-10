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
import ctypes

from PyQt5.QtWidgets import QApplication
from qfluentwidgets import setTheme, Theme

from src.util.constants import Paths, cleanup_temp_dir
from src.ui.view.main_window import MainWindow, log_exception


# Ensure project root is importable and working directory matches the executable
sys.path.insert(0, str(Path(__file__).parent))
os.chdir(Paths.BASE_DIR)

# Route uncaught exceptions through the shared handler in the view layer.
sys.excepthook = log_exception
#multiprocessing.freeze_support()


def _hide_console_window() -> None:
    """Hide the Windows console window when the app is launched via python.exe."""

    if os.name != "nt":
        return
    try:
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        hwnd = kernel32.GetConsoleWindow()
        if hwnd:
            user32.ShowWindow(hwnd, 0)
    except Exception:
        pass


def main() -> int:
    multiprocessing.freeze_support()
    _hide_console_window()
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    try:
        app = QApplication(sys.argv)
        setTheme(Theme.DARK)
        window = MainWindow()
        window.show()
        return app.exec()
    finally:
        cleanup_temp_dir()


if __name__ == "__main__":
    sys.exit(main())

