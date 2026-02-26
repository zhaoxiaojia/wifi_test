"""Data model for the project Excel report.

This module exists so future structural changes (scenario grouping, etc.) are localized.
"""

from __future__ import annotations

# Import everything from the builder for now.
# Next step after you confirm the split: move dataclasses here and update the
# builder to import from this module.
from src.util.report.builder import *  # noqa: F401,F403
