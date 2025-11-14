"""Section registry utilities for modular case configuration UI."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable, Iterable, Type

from .base import ConfigSection, SectionContext

SectionFactory = Callable[["CaseConfigPage"], ConfigSection]

_SECTION_REGISTRY: dict[str, SectionFactory] = {}
_CASE_SECTION_MAP: dict[str, list[str]] = defaultdict(list)
_SECTION_TAG_RULES: dict[str, dict[str, set[str]]] = {}


def register_section(section_id: str, case_types: Iterable[str] | None = None) -> Callable[[Type[ConfigSection]], Type[ConfigSection]]:
    """Decorator used by section modules to register themselves."""

    def decorator(cls: Type[ConfigSection]) -> Type[ConfigSection]:
        _SECTION_REGISTRY[section_id] = cls  # type: ignore[assignment]
        cls.section_id = section_id
        if case_types is not None:
            for case_type in case_types:
                mapping = _CASE_SECTION_MAP.setdefault(case_type, [])
                if section_id not in mapping:
                    mapping.append(section_id)
        return cls

    return decorator


def register_case_sections(case_type: str, section_ids: Iterable[str]) -> None:
    """Associate ``section_ids`` with ``case_type`` in the registry."""

    mapping = _CASE_SECTION_MAP.setdefault(case_type, [])
    for section_id in section_ids:
        if section_id not in mapping:
            mapping.append(section_id)


def register_section_tags(section_id: str, *, show: Iterable[str] | None = None, hide: Iterable[str] | None = None) -> None:
    """Record tag-based visibility rules for a section."""

    rules = _SECTION_TAG_RULES.setdefault(section_id, {"show": set(), "hide": set()})
    if show is not None:
        rules.setdefault("show", set()).update(show)
    if hide is not None:
        rules.setdefault("hide", set()).update(hide)


def build_sections(page: "CaseConfigPage", case_type: str, tags: Iterable[str]) -> list[ConfigSection]:
    """Instantiate sections for ``case_type`` honouring tag rules."""

    resolved_ids: list[str] = []
    mapping = _CASE_SECTION_MAP.get(case_type) or _CASE_SECTION_MAP.get("default", [])
    for section_id in mapping:
        factory = _SECTION_REGISTRY.get(section_id)
        if factory is None:
            continue
        resolved_ids.append(section_id)
    sections: list[ConfigSection] = []
    tag_set = set(tags)
    for section_id in resolved_ids:
        rules = _SECTION_TAG_RULES.get(section_id)
        if rules:
            show_tags = rules.get("show", set())
            hide_tags = rules.get("hide", set())
            if show_tags and not (show_tags & tag_set):
                continue
            if hide_tags and hide_tags & tag_set:
                continue
        factory = _SECTION_REGISTRY.get(section_id)
        if factory is None:
            continue
        section = factory(page)
        section.set_case_context(SectionContext(case_type, tag_set))
        sections.append(section)
    return sections


def list_registered_sections() -> list[str]:
    """Return identifiers for all registered sections."""

    return sorted(_SECTION_REGISTRY.keys())


__all__ = [
    "ConfigSection",
    "SectionContext",
    "register_section",
    "register_case_sections",
    "register_section_tags",
    "build_sections",
    "list_registered_sections",
]

# Import section modules to register implementations.
from . import wifi_section  # noqa: F401
from . import rf_step_section  # noqa: F401
from . import debug_section  # noqa: F401
from . import rvr_section  # noqa: F401
from . import turntable_section  # noqa: F401
from . import router_section  # noqa: F401
