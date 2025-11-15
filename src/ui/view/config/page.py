"""View module for the Config sidebar page (DUT/Execution/Stability)."""

from __future__ import annotations

from typing import Any, Sequence

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QLabel,
)
from qfluentwidgets import CardWidget, PushButton, ScrollArea

from src.ui.view.common import (
    AnimatedTreeView,
    ConfigGroupPanel,
    PAGE_CONTENT_MARGIN,
    STEP_LABEL_SPACING,
    USE_QFLUENT_STEP_VIEW,
    _apply_step_font,
)
from src.ui.view.theme import (
    CASE_TREE_FONT_SIZE_PX,
    apply_font_and_selection,
    apply_theme,
)
from src.ui.view.builder import build_groups_from_schema, load_ui_schema
from src.ui.view.config.actions import init_fpga_dropdowns


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
        self._right_layout = right

        # Track which logical pages are currently available
        self._current_page_keys: list[str] = []

        self._page_label_map: dict[str, str] = {
            "dut": "DUT Settings",
            "execution": "Execution Settings",
            "stability": "Stability Settings",
        }
        self.step_view_widget = self._create_step_view([self._page_label_map["dut"]])
        self.step_view_widget.setVisible(False)
        right.addWidget(self.step_view_widget)

        self.stack = QStackedWidget(self)
        right.addWidget(self.stack, 1)

        self._page_panels: dict[str, ConfigGroupPanel] = {
            "dut": ConfigGroupPanel(self),
            "execution": ConfigGroupPanel(self),
            "stability": ConfigGroupPanel(self),
        }
        self._page_widgets: dict[str, QWidget] = {}
        self._wizard_pages: list[QWidget] = []
        self._run_buttons: list[PushButton] = []

        for key in ("dut", "execution", "stability"):
            panel = self._page_panels[key]
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(
                PAGE_CONTENT_MARGIN,
                PAGE_CONTENT_MARGIN,
                PAGE_CONTENT_MARGIN,
                PAGE_CONTENT_MARGIN,
            )
            page_layout.setSpacing(PAGE_CONTENT_MARGIN)
            page_layout.addWidget(panel)
            page_layout.addStretch(1)
            run_btn = self._create_run_button(page)
            page_layout.addWidget(run_btn)
            self._page_widgets[key] = page
            self._wizard_pages.append(page)

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

    # ------------------------------------------------------------------
    # Step view helpers
    # ------------------------------------------------------------------

    def _create_step_view(self, labels: list[str]) -> QWidget:
        """Create a simple step indicator widget for the wizard pages."""
        if USE_QFLUENT_STEP_VIEW:
            try:
                from qfluentwidgets import StepView  # type: ignore

                view = StepView(self)
                for i, text in enumerate(labels):
                    view.addStep(text, i == 0)
                _apply_step_font(view)
                view.setFixedHeight(STEP_LABEL_SPACING * 3)
                return view
            except Exception:
                pass
        # Fallback: simple label-based step view
        container = QWidget(self)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(PAGE_CONTENT_MARGIN, PAGE_CONTENT_MARGIN, PAGE_CONTENT_MARGIN, 0)
        layout.setSpacing(STEP_LABEL_SPACING)
        for text in labels:
            label = QLabel(text, container)
            _apply_step_font(label)
            layout.addWidget(label)
        layout.addStretch(1)
        return container

    def _create_run_button(self, parent: QWidget) -> PushButton:
        """Create a Run button for a wizard page (UI only)."""
        button = PushButton("Run", parent)
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
        self.refresh_step_view(normalized)

        # Preserve current page when possible.
        target_index = 0
        if current_key in normalized:
            target_index = normalized.index(current_key)
        self.stack.setCurrentIndex(target_index)

    def refresh_step_view(self, page_keys: Sequence[str]) -> None:
        """Refresh the step indicator labels based on active page keys."""
        labels = [self._page_label_map.get(key, key.title()) for key in page_keys]
        if not labels:
            labels = [self._page_label_map["dut"]]
        new_view = self._create_step_view(list(labels))
        old_view = getattr(self, "step_view_widget", None)
        layout = getattr(self, "_right_layout", None)
        if layout is not None:
            if old_view is not None:
                index = layout.indexOf(old_view)
                if index < 0:
                    index = 0
                layout.insertWidget(index, new_view)
                layout.removeWidget(old_view)
                old_view.setParent(None)
            else:
                layout.insertWidget(0, new_view)
        self.step_view_widget = new_view
        # Step view is only useful when more than one page is available.
        self.step_view_widget.setVisible(len(page_keys) > 1)


__all__ = ["ConfigView"]
