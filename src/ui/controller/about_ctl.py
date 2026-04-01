"""Controller for the About page.

This branch intentionally keeps the About page UI but removes the
metadata/resources business logic (no filesystem reads, links, or
test-history aggregation). The page is rendered blank by default.
"""
from __future__ import annotations

from typing import Any


class AboutController:
    """Controller that wires behaviour onto an ``AboutView`` instance.

    Parameters
    ----------
    view : AboutView
        The pure UI view instance created by the caller.
    """

    def __init__(self, view: Any) -> None:
        self.view = view
        self.populate_metadata()

    def populate_metadata(self) -> None:
        """Leave the About page intentionally blank."""
        table = getattr(self.view, "info_table", None)
        if table is not None:
            try:
                table.setRowCount(0)
                table.hide()
            except Exception:
                pass

        source_label = getattr(self.view, "source_label", None)
        if source_label is not None:
            try:
                source_label.setText("")
                source_label.hide()
            except Exception:
                pass

        resources_card = getattr(self.view, "resources_card", None)
        if resources_card is not None:
            try:
                resources_card.hide()
            except Exception:
                pass
