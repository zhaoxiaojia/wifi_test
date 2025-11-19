"""View module for the Config sidebar page (DUT/Execution/Stability)."""

from __future__ import annotations

from typing import Any, Sequence

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
    QLabel,
)
from qfluentwidgets import CardWidget, PushButton, ScrollArea, FluentIcon

from src.ui.view.common import (
    AnimatedTreeView,
    ConfigGroupPanel,
    PAGE_CONTENT_MARGIN,
)
from src.ui.view.theme import (
    CASE_TREE_FONT_SIZE_PX,
    apply_font_and_selection,
    apply_theme,
    apply_settings_tab_label_style,
)
from src.ui.view.builder import build_groups_from_schema, load_ui_schema
from src.ui.view.config.actions import init_fpga_dropdowns, handle_config_event


class _ConfigTabLabel(QLabel):
    """Clickable label used for DUT/Execution/Stability tabs."""

    clicked = pyqtSignal()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ConfigView(CardWidget):
    """Pure UI view for the Config page (no business logic)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        apply_theme(self)

        # Left/right splitter
        self.splitter = QSplitter(Qt.Horizontal, self)
        self.splitter.setChildrenCollapsible(False)

        # Left: case tree
        self.case_tree = AnimatedTreeView(self)
        apply_theme(self.case_tree)
        apply_font_and_selection(self.case_tree, size_px=CASE_TREE_FONT_SIZE_PX)
        self.splitter.addWidget(self.case_tree)

        # Right: scroll area with step view + stacked pages
        scroll_area = ScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setContentsMargins(0, 0, 0, 0)
        self.scroll_area = scroll_area

        container = QWidget()
        right = QVBoxLayout(container)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(10)

        # Track which logical pages are currently available
        self._current_page_keys: list[str] = []

        # Simple tab row for DUT / Execution / Stability
        self._page_label_map: dict[str, str] = {
            "dut": "DUT",
            "execution": "Execution",
            "stability": "Stability",
        }
        self._page_buttons: dict[str, _ConfigTabLabel] = {}
        tabs_row = QHBoxLayout()
        tabs_row.setContentsMargins(PAGE_CONTENT_MARGIN, PAGE_CONTENT_MARGIN, PAGE_CONTENT_MARGIN, 0)
        tabs_row.setSpacing(8)
        for key in ("dut", "execution", "stability"):
            lbl = _ConfigTabLabel(self._page_label_map[key], self)
            apply_settings_tab_label_style(lbl, active=(key == "dut"))

            def _make_handler(page_key: str) -> Any:
                def _handler() -> None:
                    page = self.parent()
                    # Climb parents until we reach the owning page (CaseConfigPage).
                    while page is not None and not hasattr(page, "get_editable_fields"):
                        page = page.parent()
                    if page is not None:
                        handle_config_event(page, "settings_tab_clicked", key=page_key)

                return _handler

            lbl.clicked.connect(_make_handler(key))
            self._page_buttons[key] = lbl
            tabs_row.addWidget(lbl)
        tabs_row.addStretch(1)
        right.addLayout(tabs_row)

        self.stack = QStackedWidget(self)
        right.addWidget(self.stack, 1)

        self._page_panels: dict[str, ConfigGroupPanel] = {
            "dut": ConfigGroupPanel(self),
            "execution": ConfigGroupPanel(self),
            "stability": ConfigGroupPanel(self),
        }
        self._page_widgets: dict[str, QWidget] = {}
        self._run_buttons: list[PushButton] = []

        for key in ("dut", "execution", "stability"):
            panel = self._page_panels[key]
            page = QWidget()
            page.setObjectName(f"config_{key}_page")
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(
                PAGE_CONTENT_MARGIN,
                PAGE_CONTENT_MARGIN,
                PAGE_CONTENT_MARGIN,
                PAGE_CONTENT_MARGIN,
            )
            page_layout.setSpacing(PAGE_CONTENT_MARGIN)
            # 让设置区域占满垂直空间，Run 按钮贴底部。
            page_layout.addWidget(panel, 1)
            run_btn = self._create_run_button(page)
            # Run 按钮只占自身高度，宽度拉满。
            page_layout.addWidget(run_btn, 0)
            self._page_widgets[key] = page

        # Initialise stack and step view with the default page selection.
        # This keeps all layout concerns inside the view layer.
        self.set_available_pages(["dut"])

        scroll_area.setWidget(container)
        self.splitter.addWidget(scroll_area)
        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 3)

        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.addWidget(self.splitter)

    def _create_run_button(self, parent: QWidget) -> PushButton:
        """Create a Run button for the page (UI only)."""
        button = PushButton("Run", parent)
        button.setIcon(FluentIcon.PLAY)
        if hasattr(button, "setUseRippleEffect"):
            button.setUseRippleEffect(True)
        if hasattr(button, "setUseStateEffect"):
            button.setUseStateEffect(True)
        # Let the button stretch horizontally so it visually anchors the page.
        button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._run_buttons.append(button)
        return button

    # Public API used by controllers
    # ------------------------------------------------------------------

    def set_available_pages(self, page_keys: Sequence[str]) -> None:
        """Show the given logical pages in the stacked widget."""
        normalized: list[str] = []
        for key in page_keys:
            if key not in self._page_widgets:
                continue
            if key not in normalized:
                normalized.append(key)
        if "dut" not in normalized:
            normalized.insert(0, "dut")
        if normalized == getattr(self, "_current_page_keys", []):
            return

        current_widget = self.stack.currentWidget() if self.stack.count() else None
        current_key: str | None = None
        if current_widget is not None:
            for key, widget in self._page_widgets.items():
                if widget is current_widget:
                    current_key = key
                    break

        # Rebuild stack order to match normalized keys.
        while self.stack.count():
            widget = self.stack.widget(0)
            self.stack.removeWidget(widget)
        for key in normalized:
            self.stack.addWidget(self._page_widgets[key])

        self._current_page_keys = normalized

        # Update tab visibility based on available pages.
        for key, lbl in self._page_buttons.items():
            lbl.setVisible(key in normalized)

        # Preserve current page when possible.
        target_index = 0
        if current_key in normalized:
            target_index = normalized.index(current_key)
        self.stack.setCurrentIndex(target_index)
        self._update_tab_checked(target_index)

    # ------------------------------------------------------------------
    # Tab helpers
    # ------------------------------------------------------------------

    def _update_tab_checked(self, index: int) -> None:
        """Update which tab button appears active."""
        if not (0 <= index < len(self._current_page_keys)):
            return
        active_key = self._current_page_keys[index]
        for key, lbl in self._page_buttons.items():
            apply_settings_tab_label_style(lbl, active=(key == active_key))

    def set_current_page(self, key: str) -> None:
        """Public helper to switch to a logical page key."""
        if key not in self._current_page_keys:
            return
        index = self._current_page_keys.index(key)
        self.stack.setCurrentIndex(index)
        self._update_tab_checked(index)

__all__ = ["ConfigView"]
