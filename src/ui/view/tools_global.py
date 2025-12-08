"""Global tools bar and side-panel views.

These widgets host the application-wide tools (BT FW log analysis,
AI chat, etc.).  They are intentionally UI-only and do not perform any
I/O; behaviour is provided by controllers in ``src.ui.controller``.
"""

from __future__ import annotations

from typing import Dict, Iterable, Sequence

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget
from qfluentwidgets import CardWidget, FluentIcon, ToolButton

from src.ui.model.tools_registry import ToolSpec
from src.ui.view.theme import apply_theme, apply_tool_text_style


_ICON_MAP = {
    "BLUETOOTH": FluentIcon.BLUETOOTH,
    "DEVELOPER_TOOLS": FluentIcon.DEVELOPER_TOOLS,
    "CODE": FluentIcon.CODE,
    "ROBOT": FluentIcon.ROBOT,
}


def _resolve_icon(name: str | None):
    """Return an icon value (FluentIcon or path string) for the given registry icon name."""
    if not name:
        return FluentIcon.MORE
    text = name.strip()
    if "." in text or "/" in text or "\\" in text:
        return text
    candidate = text.upper()
    return _ICON_MAP.get(candidate, FluentIcon.MORE)


class GlobalToolsBar(QWidget):
    """Horizontal toolbar that exposes global tool shortcuts."""

    toolTriggered = pyqtSignal(str)

    def __init__(self, tools: Sequence[ToolSpec], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 3, 2, 1)
        layout.setSpacing(2)

        self._buttons: Dict[str, ToolButton] = {}

        layout.addStretch(1)

        for spec in tools:
            icon = _resolve_icon(spec.icon)
            button = ToolButton(self)
            button.setIcon(icon)
            button.setObjectName(f"globalToolButton_{spec.tool_id}")
            button.setToolTip(spec.title)
            button.setFixedSize(26, 26)
            apply_tool_text_style(button)
            button.clicked.connect(
                lambda _checked=False, tool_id=spec.tool_id: self.toolTriggered.emit(tool_id)
            )
            self._buttons[spec.tool_id] = button
            layout.addWidget(button)

    def set_tools_enabled(self, enabled: bool, tool_ids: Iterable[str] | None = None) -> None:
        """Enable or disable the entire toolbar or a subset of tools."""
        ids = list(tool_ids) if tool_ids is not None else list(self._buttons.keys())
        for tid in ids:
            button = self._buttons[tid]
            button.setEnabled(enabled)

    def set_active_tool(self, tool_id: str | None) -> None:
        """Currently a no-op; toolbar icons do not change on selection."""
        _ = tool_id


class GlobalToolsPanel(CardWidget):
    """Side panel that hosts the active tool widgets."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("globalToolsPanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        self._stack = QStackedWidget(self)
        layout.addWidget(self._stack, 1)

        self._tool_indices: Dict[str, int] = {}

        apply_theme(self, recursive=True)

    def register_tool_widget(self, tool_id: str, widget: QWidget) -> None:
        """Register a tool widget with the panel."""
        if tool_id in self._tool_indices:
            index = self._tool_indices[tool_id]
            existing = self._stack.widget(index)
            if existing is widget:
                return
        index = self._stack.addWidget(widget)
        self._tool_indices[tool_id] = index

    def set_current_tool(self, tool_id: str) -> None:
        """Switch the visible page to the given tool, if registered."""
        index = self._tool_indices.get(tool_id)
        if index is None:
            return
        if self._stack.currentIndex() != index:
            self._stack.setCurrentIndex(index)

    def current_tool_id(self) -> str | None:
        """Return the tool_id of the current widget, if any."""
        current_index = self._stack.currentIndex()
        for tool_id, index in self._tool_indices.items():
            if index == current_index:
                return tool_id
        return None
