"""Utilities shared by stability stress test suites."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

__all__ = ["is_stability_case_path"]


def _iter_segments(candidate: Path) -> Iterable[str]:
    """Yield lowercase path segments for ``candidate``."""

    for segment in candidate.as_posix().split("/"):
        segment = segment.strip()
        if segment:
            yield segment.lower()


def is_stability_case_path(path: Any) -> bool:
    """Return True when ``path`` points into the stability test suite.

    Args:
        path: Path-like value describing the test module location.

    Returns:
        bool: True if the path contains a ``test/stability`` segment.
    """

    normalized = str(path or "").replace("\\", "/").strip()
    if not normalized:
        return False

    lowered = normalized.lower()
    if "test/stability/" in lowered:
        return True

    try:
        candidate = Path(path)
    except (TypeError, ValueError):
        return False

    try:
        resolved = candidate.resolve()
    except OSError:
        resolved = candidate

    for probe in (candidate, resolved):
        segments = tuple(_iter_segments(probe))
        for idx in range(len(segments) - 1):
            if segments[idx] == "test" and segments[idx + 1] == "stability":
                return True

    return False
