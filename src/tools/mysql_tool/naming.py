from __future__ import annotations

import re
from typing import Dict, Sequence

_IDENTIFIER_RE = re.compile(r"[^0-9a-zA-Z]+")


class IdentifierBuilder:
    """Generate SQL-compliant identifiers with disambiguation."""

    def __init__(self) -> None:
        self._counts: Dict[str, int] = {}

    def build(self, parts: Sequence[str], *, fallback: str = "field") -> str:
        sanitized_parts = []
        for part in parts:
            sanitized = _IDENTIFIER_RE.sub("_", str(part).strip())
            sanitized = sanitized.strip("_").lower()
            if not sanitized:
                sanitized = fallback
            if sanitized[0].isdigit():
                sanitized = f"f_{sanitized}"
            sanitized_parts.append(sanitized)

        base = "_".join(sanitized_parts) if sanitized_parts else fallback
        if not base:
            base = fallback

        count = self._counts.get(base, 0)
        self._counts[base] = count + 1
        if count:
            return f"{base}_{count}"
        return base


def sanitize_identifier(value: str, *, fallback: str) -> str:
    """Sanitize a single identifier, preserving SQL validity."""

    sanitized = _IDENTIFIER_RE.sub("_", value.strip())
    sanitized = sanitized.strip("_").lower()
    if not sanitized:
        sanitized = fallback
    if sanitized[0].isdigit():
        prefix = fallback[0] if fallback else "t"
        sanitized = f"{prefix}_{sanitized}"
    return sanitized
