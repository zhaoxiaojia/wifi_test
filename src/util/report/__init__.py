"""Centralized report/Excel helpers.

This package is the canonical home for all reporting utilities, including:
- Excel plan read/write helpers
- Result import/export utilities
- Project report (xlsx) generation
- RVR chart dataframe preparation
"""

from .facade import generate_project_report
from .rvr_chart_facade import RvrChartLogic

__all__ = ["generate_project_report", "RvrChartLogic"]
