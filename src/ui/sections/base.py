"""Base abstractions for modular configuration sections."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol

from PyQt5.QtWidgets import QWidget


class CaseSectionContext(Protocol):
    """Interface describing contextual data passed to sections."""

    case_type: str
    tags: set[str]


@dataclass(slots=True)
class SectionContext:
    """Lightweight immutable context passed to section instances."""

    case_type: str = "default"
    tags: set[str] = field(default_factory=set)


class ConfigSection:
    """Abstract base class implemented by all configuration sections."""

    section_id: str = ""
    config_keys: Iterable[str] = ()
    panel: str = "execution"

    def __init__(self, page: "CaseConfigPage") -> None:
        self.page = page
        self.widgets: dict[str, QWidget] = {}
        self.groups: dict[str, QWidget] = {}
        self._context = SectionContext()

    # -- lifecycle ------------------------------------------------------
    def build(self, config: dict[str, Any]) -> None:
        """Create widgets for the section and attach them to the page."""

    def load(self, config: dict[str, Any]) -> None:
        """Load values from ``config`` into the section widgets."""

    def dump(self, config: dict[str, Any]) -> None:
        """Persist values from widgets back into ``config``."""

    def set_case_context(self, context: CaseSectionContext) -> None:
        """Update the section with the active case metadata."""

        self._context = SectionContext(context.case_type, set(context.tags))

    # -- helpers --------------------------------------------------------
    def register_group(self, key: str, group: QWidget, *, is_dut: bool) -> None:
        """Register ``group`` with the hosting page and track it locally."""

        self.groups[key] = group
        self.page._register_group(key, group, is_dut)
        # Also expose the group via the page's logical control registry when available.
        register = getattr(self.page, "_register_config_control_from_section", None)
        if callable(register):
            try:
                register(self.section_id or key, getattr(self, "panel", "main"), key, group)
            except Exception:
                pass

    def register_field(self, key: str, widget: QWidget) -> None:
        """Expose ``widget`` through the page field registry."""

        self.widgets[key] = widget
        self.page.field_widgets[key] = widget
        # Optionally register a logical control identifier on the hosting page.
        register = getattr(self.page, "_register_config_control_from_section", None)
        if callable(register):
            try:
                register(self.section_id or key, getattr(self, "panel", "main"), key, widget)
            except Exception:
                # Mapping failures should never break UI construction.
                pass


__all__ = [
    "CaseSectionContext",
    "SectionContext",
    "ConfigSection",
]
