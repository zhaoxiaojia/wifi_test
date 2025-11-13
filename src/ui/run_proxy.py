from __future__ import annotations

import copy
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt5.QtCore import QSortFilterProxyModel

from src.util.constants import TOOL_SECTION_KEY

if TYPE_CHECKING:  # pragma: no cover - circular import guard
    from .case_config_page import CaseConfigPage


def on_run(page: "CaseConfigPage") -> None:
    """Proxy implementation for CaseConfigPage.on_run."""
    if not page._validate_first_page():
        page.stack.setCurrentIndex(0)
        return
    page.config = page._load_config()
    if hasattr(page, "_config_tool_snapshot"):
        page._config_tool_snapshot = copy.deepcopy(
            page.config.get(TOOL_SECTION_KEY, {})
        )
    page._capture_preselected_csv()
    page._sync_widgets_to_config()
    if not page._validate_test_str_requirements():
        return
    logging.info(
        "[on_run] start case=%s csv=%s config=%s",
        page.field_widgets['text_case'].text().strip(),
        page.selected_csv_path,
        page.config,
    )
    base = Path(page._get_application_base())
    case_path = page.config.get("text_case", "")
    abs_case_path = (
        (base / case_path).resolve().as_posix() if case_path else ""
    )
    logging.debug(
        "[on_run] before performance check abs_case_path=%s csv=%s",
        abs_case_path,
        page.selected_csv_path,
    )
    logging.debug(
        "[on_run] after performance check abs_case_path=%s csv=%s",
        abs_case_path,
        page.selected_csv_path,
    )
    proxy_idx = page.case_tree.currentIndex()
    model = page.case_tree.model()
    src_idx = (
        model.mapToSource(proxy_idx)
        if isinstance(model, QSortFilterProxyModel)
        else proxy_idx
    )
    selected_path = page.fs_model.filePath(src_idx)
    if os.path.isfile(selected_path) and selected_path.endswith(".py"):
        abs_path = Path(selected_path).resolve()
        display_path = os.path.relpath(abs_path, base)
        case_path = Path(display_path).as_posix()

        abs_case_path = abs_path.as_posix()
        page.config["text_case"] = case_path
    logging.debug("[on_run] before _save_config")
    page._save_config()
    logging.debug("[on_run] after _save_config")
    try:
        if page._is_performance_case(abs_case_path) and not getattr(
            page, "selected_csv_path", None
        ):
            try:
                bar = page._show_info_bar(
                    "warning",
                    "Hint",
                    "This is a performance test. Please select a CSV file before running.",
                    duration=3000,
                )
                if bar is None:
                    raise RuntimeError("InfoBar unavailable")
            except Exception:
                from PyQt5.QtWidgets import QMessageBox

                QMessageBox.warning(
                    page,
                    "Hint",
                    "This is a performance test.\nPlease select a CSV file before running.",
                )
            return
    except Exception:
        pass

    if os.path.isfile(abs_case_path) and abs_case_path.endswith(".py"):
        try:
            page.on_run_callback(abs_case_path, case_path, page.config)
        except Exception as exc:  # pragma: no cover - callback logging only
            logging.exception("Run callback failed: %s", exc)
        else:
            page._reset_wizard_after_run()
    else:
        page._show_info_bar(
            "warning",
            "Hint",
            "Pls select a test case before test",
            duration=1800,
        )
