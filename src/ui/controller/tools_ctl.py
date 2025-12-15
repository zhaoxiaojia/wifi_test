"""Controller glue for the global tools bar and side panel.

This module wires together the toolbar, the side-panel stack, and the
individual tool controllers so that tools can be toggled globally from
the main window.
"""

from __future__ import annotations

from typing import Dict, Sequence

from PyQt5.QtCore import QObject

from src.ui.model.tools_registry import ToolSpec
from src.ui.view.tools_global import GlobalToolsBar, GlobalToolsPanel
from src.ui.view.toolbar.tools_bt_fw_log import BtFwLogToolView
from src.ui.view.toolbar.tools_ai_chat import AiChatToolView
from src.ui.controller.tools_bt_fw_log_ctl import BtFwLogToolController
from src.ui.controller.tools_ai_chat_ctl import AiChatToolController


class GlobalToolsController(QObject):
    """High-level controller for global tools."""

    def __init__(
        self,
        main_window,
        tools_bar: GlobalToolsBar,
        tools_panel: GlobalToolsPanel,
        specs: Sequence[ToolSpec],
    ) -> None:
        super().__init__(main_window)
        self.main_window = main_window
        self.tools_bar = tools_bar
        self.tools_panel = tools_panel
        self._specs: Dict[str, ToolSpec] = {s.tool_id: s for s in specs}
        self._current_tool_id: str | None = None
        self._panel_visible = False

        self._tool_views: Dict[str, object] = {}
        self._tool_controllers: Dict[str, object] = {}

        self._create_tool_instances()

        self.tools_bar.toolTriggered.connect(self._on_tool_triggered)

    # ------------------------------------------------------------------
    # Tool creation
    # ------------------------------------------------------------------

    def _create_tool_instances(self) -> None:
        """Instantiate tool views and controllers based on registry ids."""
        for tool_id in self._specs:
            if tool_id == "bt_fw_log":
                view = BtFwLogToolView(parent=self.main_window)
                controller = BtFwLogToolController(view, parent=self.main_window)
            elif tool_id == "ai_chat":
                view = AiChatToolView(parent=self.main_window)
                controller = AiChatToolController(view, parent=self.main_window)
            else:
                continue

            self.tools_panel.register_tool_widget(tool_id, view)
            self._tool_views[tool_id] = view
            self._tool_controllers[tool_id] = controller

    # ------------------------------------------------------------------
    # Visibility / toggling
    # ------------------------------------------------------------------

    def _on_tool_triggered(self, tool_id: str) -> None:
        """Handle a toolbar button being clicked."""
        if self._panel_visible and self._current_tool_id == tool_id:
            self._hide_panel()
            return
        self.tools_panel.set_current_tool(tool_id)
        self._show_panel()
        self._current_tool_id = tool_id
        self.tools_bar.set_active_tool(tool_id)

    def _show_panel(self) -> None:
        if self._panel_visible:
            return
        self.tools_panel.show()
        self.tools_panel.raise_()
        self._panel_visible = True
        self.main_window._update_global_tools_geometry()

    def _hide_panel(self) -> None:
        if not self._panel_visible:
            return
        self.tools_panel.hide()
        self._panel_visible = False
        self._current_tool_id = None
        self.tools_bar.set_active_tool(None)
        # Refresh geometry so that the central content regains
        # the space previously reserved for the tools panel.
        try:
            self.main_window._update_global_tools_geometry()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def hide_tools(self) -> None:
        """Hide the tools side panel."""
        self._hide_panel()

    def show_tools_for(self, tool_id: str) -> None:
        """Programmatically show a specific tool."""
        self._on_tool_triggered(tool_id)


__all__ = ["GlobalToolsController"]
