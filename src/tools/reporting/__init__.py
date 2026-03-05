"""Backward-compatible reporting exports.

This package exists for historical imports such as:
`from src.tools.reporting import generate_project_report`.
"""

from src.util.report.facade import generate_project_report

__all__ = ["generate_project_report"]

