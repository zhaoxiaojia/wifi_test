"""Model helpers for the global tools bar.

This module loads the declarative YAML registry that describes which
tools are available in the application and how they should be wired
into the UI layer.

The registry is intentionally small and focused so the view/controller
layers can remain free of hard-coded tool lists.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

import yaml

from src.util.constants import get_model_config_base


@dataclass(frozen=True)
class ToolSpec:
    """Declarative description of a single global tool."""

    tool_id: str
    title: str
    icon: str | None = None


def _registry_path() -> Path:
    base = get_model_config_base().resolve()
    return base / "tools_registry.yaml"


def load_tools_registry() -> List[ToolSpec]:
    """Return the list of ToolSpec items defined in tools_registry.yaml."""
    path = _registry_path()
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text) or {}
    tools_raw = data.get("tools") or []
    specs: list[ToolSpec] = []
    for item in tools_raw:
        tool_id = str(item.get("id") or "").strip()
        title = str(item.get("title") or "").strip()
        if not tool_id or not title:
            continue
        icon = item.get("icon")
        icon_str = str(icon).strip() if icon else None
        specs.append(ToolSpec(tool_id=tool_id, title=title, icon=icon_str or None))
    return specs


__all__ = ["ToolSpec", "load_tools_registry"]
