from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMenuBar, QSizePolicy, QWidget
from qfluentwidgets.window.fluent_window import FluentTitleBar

from src.ui.view.theme import BACKGROUND_COLOR, TEXT_COLOR


class MenuTitleBar(FluentTitleBar):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.hBoxLayout.removeWidget(self.titleLabel)
        self.titleLabel.hide()

        self.menu_bar = QMenuBar(self)
        self.menu_bar.setObjectName("mainMenuBar")
        self.menu_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.menu_bar.setStyleSheet(
            f"""
            QMenuBar {{
                background-color: transparent;
                color: {TEXT_COLOR};
            }}
            QMenuBar::item {{
                padding: 4px 10px;
                background: transparent;
                color: {TEXT_COLOR};
            }}
            QMenuBar::item:selected {{
                background-color: #3a3a3a;
            }}
            QMenu {{
                background-color: {BACKGROUND_COLOR};
                color: {TEXT_COLOR};
                border: 1px solid #555555;
            }}
            QMenu::item:selected {{
                background-color: #3a3a3a;
            }}
            """
        )
        self.hBoxLayout.insertWidget(1, self.menu_bar, 1, Qt.AlignVCenter)

