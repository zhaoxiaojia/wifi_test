"""View module for the Report sidebar page.

This module contains the *pure UI* layout for the report browser:

- Left: file list for log / result artifacts.
- Right: stacked viewer that can show either a text tail (``QTextEdit``)
  or a set of RVR/RVO charts in a ``QTabWidget``.

All business logic (file system scanning, tailing, chart rendering) lives in
``src.ui.controller.report_ctl`` which operates on this view and wires
signals/slots.
"""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QListWidget,
    QTextEdit,
    QStackedWidget,
    QTabWidget,
    QWidget,
)
from qfluentwidgets import CardWidget, StrongBodyLabel

from src.ui.view.theme import (
    ACCENT_COLOR,
    BACKGROUND_COLOR,
    FONT_FAMILY,
    STYLE_BASE,
    TEXT_COLOR,
    apply_theme,
)


class ReportView(CardWidget):
    """Pure UI view for the Report page (no file or chart logic)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("reportView")
        apply_theme(self)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        # Header title
        self.title_label = StrongBodyLabel("Reports", self)
        apply_theme(self.title_label)
        self.title_label.setStyleSheet(
            f"border-left: 4px solid {ACCENT_COLOR}; "
            f"padding-left: 8px; font-family:{FONT_FAMILY};"
        )
        root.addWidget(self.title_label)

        # Clickable directory label (logic hooks in controller)
        self.dir_label = QLabel("Report dir: -", self)
        apply_theme(self.dir_label)
        self.dir_label.setCursor(Qt.PointingHandCursor)
        root.addWidget(self.dir_label)

        body = QHBoxLayout()
        body.setSpacing(12)
        root.addLayout(body)

        # Left: file list
        self.file_list = QListWidget(self)
        apply_theme(self.file_list)
        self.file_list.setSelectionMode(self.file_list.SingleSelection)
        body.addWidget(self.file_list, 1)

        # Right: stacked viewer (text tail + chart tabs)
        self.viewer_stack = QStackedWidget(self)
        body.addWidget(self.viewer_stack, 3)

        self.viewer = QTextEdit(self.viewer_stack)
        self.viewer.setReadOnly(True)
        apply_theme(self.viewer)
        self.viewer.document().setMaximumBlockCount(5000)
        self.viewer.setMinimumHeight(400)
        self.viewer_stack.addWidget(self.viewer)

        self.chart_tabs = QTabWidget(self.viewer_stack)
        apply_theme(self.chart_tabs)
        self.chart_tabs.setDocumentMode(True)
        self.chart_tabs.setElideMode(Qt.ElideRight)

        pane_style = f"""
        QTabWidget::pane {{
            background: {BACKGROUND_COLOR};
            border: 1px solid #3a3a3a;
        }}
        """
        tab_bar_style = f"""
        QTabBar::tab {{
            {STYLE_BASE}
            color: {TEXT_COLOR};
            background: #3a3a3a;
            padding: 6px 14px;
            margin: 2px 8px 0 0;
            border-radius: 4px;
        }}
        QTabBar::tab:selected {{
            background: #565656;
            color: {TEXT_COLOR};
        }}
        QTabBar::tab:hover {{
            background: #464646;
        }}
        """
        self.chart_tabs.setStyleSheet(self.chart_tabs.styleSheet() + pane_style)
        tab_bar = self.chart_tabs.tabBar()
        if tab_bar is not None:
            tab_bar.setStyleSheet(tab_bar.styleSheet() + tab_bar_style)
        self.viewer_stack.addWidget(self.chart_tabs)
        self.viewer_stack.setCurrentWidget(self.viewer)

        # Logical control map for the report page.
        # Keys follow: page_frame_group_purpose_type
        self.report_controls: dict[str, object] = {
            "report_main_title_label": self.title_label,
            "report_main_dir_label": self.dir_label,
            "report_main_file_list_list": self.file_list,
            "report_main_viewer_stack": self.viewer_stack,
            "report_main_text_viewer": self.viewer,
            "report_main_chart_tabs": self.chart_tabs,
        }

    # ------------------------------------------------------------------
    # Chart tab helpers (UI only, no file I/O)
    # ------------------------------------------------------------------

    def rebuild_chart_tabs(self, charts: list[tuple[str, QWidget]], *, keep_index: int | None = None) -> None:
        """
        Replace all chart tabs with ``charts`` while preserving the active tab index when possible.

        Parameters
        ----------
        charts : list[tuple[str, QWidget]]
            List of ``(title, widget)`` pairs. Widgets are added into a container
            with zero margins so they fill the tab area.
        keep_index : int | None
            Optional index to restore after rebuilding; when None, the current
            index is used as the preferred target.
        """
        if keep_index is None:
            keep_index = self.chart_tabs.currentIndex()
        self.chart_tabs.blockSignals(True)
        try:
            self.chart_tabs.clear()
            for title, chart_widget in charts:
                if chart_widget is None:
                    continue
                container = QWidget(self.chart_tabs)
                container.setSizePolicy(container.sizePolicy().Expanding, container.sizePolicy().Expanding)
                layout = QVBoxLayout(container)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(0)
                layout.addWidget(chart_widget)
                self.chart_tabs.addTab(container, title)
        finally:
            self.chart_tabs.blockSignals(False)
        if 0 <= keep_index < self.chart_tabs.count():
            self.chart_tabs.setCurrentIndex(keep_index)
        elif self.chart_tabs.count() > 0:
            self.chart_tabs.setCurrentIndex(0)
