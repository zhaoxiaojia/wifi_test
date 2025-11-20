"""Backward-compatibility shim for the Config page controller.

The real implementation now lives in :mod:`src.ui.view.config.page`
as :class:`CaseConfigPage`.  This module simply re-exports that class
so existing imports continue to work.
"""

from __future__ import annotations

from src.ui.view.config.page import CaseConfigPage

__all__ = ["CaseConfigPage"]

