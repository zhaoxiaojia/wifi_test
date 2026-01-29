from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QWidget

from src.ui.view.theme import BACKGROUND_COLOR, TEXT_COLOR
from src.ui.view.tools_global import GlobalToolsBar, GlobalToolsPanel

class GlobalToolsChrome:
    def __init__(self, content: QWidget, tool_specs) -> None:
        self._content = content
        self._margin = 5

        self.bar_frame = QFrame(content)
        self.bar_frame.setObjectName("globalToolsBarFrame")
        self.bar_frame.setAttribute(Qt.WA_StyledBackground, True)
        self.bar_frame.setStyleSheet(
            f"""
            QFrame#globalToolsBarFrame {{
                border: 1px solid #3a3a3a;
                border-radius: 0px;
                background-color: {BACKGROUND_COLOR};
            }}
            """
        )

        self.bar = GlobalToolsBar(tool_specs, parent=self.bar_frame)
        layout = QHBoxLayout(self.bar_frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.bar)

        self.panel = GlobalToolsPanel(parent=content)
        self.panel.hide()

        # DEBUG_TOOLBAR_CONTAINER: remove later
        print("[DEBUG_TOOLBAR_CONTAINER] GlobalToolsChrome initialized")

    def update_geometry(self) -> None:
        width = self._content.width()
        height = self._content.height()

        bar_height = self.bar_frame.sizeHint().height() if self.bar_frame.isVisible() else 0
        min_bar_width = self.bar_frame.sizeHint().width()

        top_strip_height = bar_height + self._margin if bar_height else 0
        panel_width = 0
        if self.panel.isVisible():
            panel_width = max(int(width * 0.3), 320)

        self._content.setContentsMargins(0, top_strip_height, panel_width, 0)

        if bar_height:
            bar_available_width = max(0, width - panel_width - (self._margin * 2))
            bar_width = max(min_bar_width, bar_available_width)
            bar_x = self._margin
            bar_y = max(0, (top_strip_height - bar_height) // 2)
            self.bar_frame.setGeometry(bar_x, bar_y, bar_width, bar_height)
            self.bar_frame.raise_()

        if self.panel.isVisible():
            panel_x = max(0, width - panel_width)
            self.panel.setGeometry(panel_x, 0, panel_width, height)
