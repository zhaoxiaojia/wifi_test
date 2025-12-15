from __future__ import annotations

from typing import Dict, Sequence
from src.util.constants import IDENTIFIER_SANITIZE_PATTERN


class IdentifierBuilder:
    """
    Identifier builder.

    Parameters
    ----------
    None
        This class does not take constructor arguments beyond ``self``.

    Returns
    -------
    None
        This class does not return a value.
    """

    def __init__(self) -> None:
        """
        Init.

        Parameters
        ----------
        None
            This method does not accept any additional parameters beyond ``self``.

        Returns
        -------
        None
            This method does not return a value.
        """
        self._counts: Dict[str, int] = {}

    def build(self, parts: Sequence[str], *, fallback: str = "field") -> str:
        """
        Build.

        Parameters
        ----------
        parts : Any
            Sequence of strings used to build an identifier.

        Returns
        -------
        str
            A value of type ``str``.
        """
        sanitized_parts = []
        for part in parts:
            sanitized = IDENTIFIER_SANITIZE_PATTERN.sub("_", str(part).strip())
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
    """
    Sanitize identifier.

    Parameters
    ----------
    value : Any
        Value to sanitize, normalize, or convert.

    Returns
    -------
    str
        A value of type ``str``.
    """

    sanitized = IDENTIFIER_SANITIZE_PATTERN.sub("_", value.strip())
    sanitized = sanitized.strip("_").lower()
    if not sanitized:
        sanitized = fallback
    if sanitized[0].isdigit():
        prefix = fallback[0] if fallback else "t"
        sanitized = f"{prefix}_{sanitized}"
    return sanitized
