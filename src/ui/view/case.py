"""Case (RvR Wi-Fi) configuration view and page.

This module now defines three widgets:

* :class:`FormListPage` - generic, read-only CSV/list table with an optional
  checkbox column that can be reused by other features (such as the
  switch-Wi-Fi stability editor).
* :class:`RouterConfigForm` - left-hand form used to edit a single Wi-Fi
  row (band, channel, security, SSID, password, tx/rx flags).
* :class:`RvrWifiConfigPage` - the actual Case page shown in the
  application, implemented as a composition of ``RouterConfigForm`` and
  ``FormListPage`` plus router/CSV persistence logic.
"""

from __future__ import annotations

import logging
from contextlib import ExitStack, suppress
import csv
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from PyQt5.QtCore import Qt, QSignalBlocker, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QVBoxLayout,
    QWidget,
    QTableWidgetItem,
    QLabel,
    QVBoxLayout,
    QSizePolicy,
)
from qfluentwidgets import CardWidget, ComboBox, LineEdit, PushButton, TableWidget, InfoBar, InfoBarPosition, PrimaryPushButton

from src.util.constants import AUTH_OPTIONS, OPEN_AUTH, Paths, RouterConst
from src.tools.router_tool.router_factory import get_router
from src.ui.view.theme import apply_theme, apply_font_and_selection
from src.ui.view import FormListPage, RouterConfigForm, FormListBinder
from src.ui.view.config.config_function import FunctionConfigForm
from src.ui.view.run import apply_run_action_button_style


class RvrWifiConfigPage(CardWidget):
    """RVR Wi-Fi test parameter configuration page (form + list + behaviour)."""

    dataChanged = pyqtSignal()

    def __init__(self) -> None:
        _t0 = time.perf_counter()
        super().__init__()
        _t = time.perf_counter()
        apply_theme(self)
        self.setObjectName("rvrWifiConfigPage")

        # Compute CSV path and load router/rows.
        _t = time.perf_counter()
        self.csv_path = self._compute_csv_path()
        _t = time.perf_counter()
        self.router, self.router_name = self._load_router()
        _t = time.perf_counter()
        self.headers, self.rows = self._load_csv()

        # Outer layout holds both the RvR Wi-Fi editor and optional case-specific widgets.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._content = QWidget(self)
        layout = QHBoxLayout(self._content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        outer.addWidget(self._content, 1)

        # # For Function test (func mode)
        # # create func qwidget
        # self.func_content = QWidget(self)
        # self.func_content.setSizePolicy(
        #     QSizePolicy.Expanding,
        #     QSizePolicy.Expanding
        # )
        # func_layout = QHBoxLayout(self.func_content)
        # func_layout.setContentsMargins(0, 0, 0, 0)
        # func_layout.setSpacing(8)
        #
        # # ➕ 左侧：功能测试配置表单（来自独立模块）
        # self.func_form = FunctionConfigForm(parent=self.func_content)
        # func_layout.addWidget(self.func_form, 1)
        #
        # # ➕ 右侧：功能测试项列表（占位，未来可替换为 FormListPage）
        # self.func_list = QWidget()
        # list_layout = QVBoxLayout(self.func_list)
        # #list_layout.addWidget(QLabel("Function Name:）"))
        # func_layout.addWidget(self.func_list, 5)
        #
        # self.func_content.setVisible(False)
        # outer.addWidget(self.func_content, 1)

        self.func_form = FunctionConfigForm(parent=self)
        self.func_form.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        outer.addWidget(self.func_form, 1)
        self.func_form.setVisible(False)

        self.form = RouterConfigForm(self.router, parent=self._content)
        layout.addWidget(self.form, 2)

        self.list = FormListPage(self.headers, self.rows, parent=self._content, checkable=True)
        layout.addWidget(self.list, 5)

        # Wiring between form, list and persistence.
        self._binder = FormListBinder(
            form=self.form,
            list_widget=self.list,
            rows=self.rows,
            on_row_updated=self._on_row_updated,
            on_rows_changed=self._on_rows_changed,
        )
        self.list.checkToggled.connect(self._on_list_check_toggled)
        self.dataChanged.connect(self._save_csv)

        # Initialise selection/form from first row when available.
        if self.rows:
            self.list.set_current_row(0)
            self.form.load_row(self.rows[0])

        # Hidden by default until the Config page decides which mode
        # should be active for the selected testcase.
        self._content.setVisible(False)

        self.run_btn = PushButton("Run", self)
        apply_run_action_button_style(self.run_btn)
        self.run_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.run_btn.clicked.connect(self._on_run_clicked)
        outer.addWidget(self.run_btn, 0)

    def set_case_content_visible(self, visible: bool) -> None:
        """Show or hide the RvR Wi-Fi UI for the current case."""
        self._content.setVisible(bool(visible))

    def set_case_mode(self, mode: str) -> None:
        """
        Select which Case-page content is visible.

        Modes
        -----
        - ``\"performance\"`` - show RvR Wi-Fi CSV editor.
        - anything else - hide, leaving the Case page empty.
        """
        mode = str(mode or "").lower()
        show_rvr = mode == "performance"
        show_func = mode in ("functionality", "func", "project", "stb", "function")
        logging.debug("case mode=%s show_rvr=%s show_func=%s", mode, show_rvr, show_func)
        self._content.setVisible(show_rvr)
        #self.func_content.setVisible(show_func)
        self.func_form.setVisible(show_func)

        return

    def _on_run_clicked(self) -> None:
        main_window = self.window()
        if hasattr(main_window, "caseConfigPage"):
            main_window.caseConfigPage.config_ctl.on_run()

    # --- router / CSV helpers -------------------------------------------------

    def _compute_csv_path(self, router_name: str | None = None) -> Path:
        """Return the CSV path used by performance tests."""
        from src.util.constants import load_config
        from src.util.constants import get_config_base

        cfg = load_config(refresh=True) or {}
        config_base = Path(get_config_base())
        raw_csv = cfg.get("csv_path") or ""
        if raw_csv:
            csv_path = Path(raw_csv)
            if not csv_path.is_absolute():
                csv_path = (config_base / csv_path).resolve()
            return csv_path

        csv_dir = config_base / "performance_test_csv"
        csv_dir.mkdir(parents=True, exist_ok=True)
        name = router_name or cfg.get("router", {}).get("name") or "rvr_wifi_setup"
        return (csv_dir / f"{name}.csv").resolve()

    def _load_router(self, name: str | None = None, address: str | None = None):
        from src.util.constants import load_config

        try:
            cfg = load_config(refresh=True) or {}
            router_name = name or cfg.get("router", {}).get("name", "asusax86u")
            if address is None and cfg.get("router", {}).get("name") == router_name:
                address = cfg.get("router", {}).get("address")
            router = get_router(router_name, address)
        except Exception as e:
            logging.error("load router error: %s", e)
            router_name = name or "asusax86u"
            router = get_router(router_name, address)
        return (router, router_name)

    def _load_csv(self) -> tuple[list[str], list[dict[str, str]]]:
        default_headers = [
            "band",
            "ssid",
            "wireless_mode",
            "channel",
            "bandwidth",
            "security_mode",
            "password",
            "tx",
            "rx",
        ]
        headers: list[str] = default_headers
        rows: list[dict[str, str]] = []
        try:
            with open(self.csv_path, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if reader.fieldnames:
                    headers = [h.strip() for h in reader.fieldnames]
                for row in reader:
                    data = {h: (row.get(h) or "").strip() for h in headers}
                    rows.append(data)
        except FileNotFoundError:
            logging.warning("CSV not found: %s. Creating a new one with default headers.", self.csv_path)
            try:
                self.csv_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=default_headers)
                    writer.writeheader()
            except Exception as e:
                logging.error("Create CSV failed: %s", e)
        except Exception as e:
            InfoBar.error(title="Error", content=str(e), parent=self, position=InfoBarPosition.TOP)
            logging.exception("CSV load error: %s", e)
        logging.debug("Loaded headers %s with %d rows", headers, len(rows))
        return headers, rows

    def reload_csv(self) -> None:
        logging.info("Reloading CSV from %s", self.csv_path)
        self.headers, self.rows = self._load_csv()
        # Keep FormListBinder and FormListPage in sync with the new rows
        # list so that subsequent edits update the correct CSV data.
        if hasattr(self.list, "set_rows"):
            self.list.set_data(self.headers, self.rows)
        # Rebind binder's internal row reference to the freshly loaded list.
        try:
            self._binder._rows = self.rows  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - defensive
            logging.debug("Failed to rebind binder rows after CSV reload", exc_info=True)
        self.dataChanged.emit()

    def _save_csv(self) -> None:
        """Persist current rows back to the CSV file."""
        if not self.csv_path:
            return
        try:
            fieldnames = list(self.headers)
            with open(self.csv_path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                for row in self.rows:
                    writer.writerow({h: row.get(h, "") for h in fieldnames})
            debug_rows = [
                {h: row.get(h, "") for h in fieldnames}
                for row in self.rows
                if row.get("_checked")
            ]
        except Exception:
            logging.exception("Failed to save Wi-Fi CSV to %s", self.csv_path)

    def reload_router(self) -> None:
        try:
            (self.router, self.router_name) = self._load_router()
            self.csv_path = self._compute_csv_path(self.router_name)
        except Exception as e:
            logging.error("reload router failed: %s", e)
            return
        self.form.set_router(self.router)
        # When router changes, reload CSV for the new router so that the
        # form/list/binder all operate on the same row list.
        self.headers, self.rows = self._load_csv()
        self.list.set_data(self.headers, self.rows)
        try:
            self._binder._rows = self.rows  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - defensive
            logging.debug("Failed to rebind binder rows after router reload", exc_info=True)
        if not self.rows:
            self.form.reset_form()
        else:
            self.form.load_row(self.rows[0])

    def on_csv_file_changed(self, path: str) -> None:
        if not path:
            return
        logging.debug("CSV file changed: %s", path)
        self.csv_path = Path(path).resolve()
        logging.debug("Resolved CSV path: %s", self.csv_path)
        self.reload_csv()
        if self.rows:
            self.list.set_current_row(0)
            self.form.load_row(self.rows[0])

    # --- form/list sync -------------------------------------------------------

    def _on_list_check_toggled(self, row_index: int, checked: bool) -> None:
        if not (0 <= row_index < len(self.rows)):
            return
        row = self.rows[row_index]
        # List checkbox只表示“该行是否启用”，不再强制把 tx/rx
        # 都改为 1，保留表单中用户单独勾选的方向设置。
        row["_checked"] = bool(checked)
        self.dataChanged.emit()

    def _on_row_updated(self, index: int, row: dict[str, str]) -> None:
        # Keep checkbox in sync with tx/rx fields via the _checked flag.
        _ = index
        checked = row.get("tx") == "1" or row.get("rx") == "1"
        row["_checked"] = checked

    def _on_rows_changed(self, rows: list[dict[str, str]]) -> None:  # noqa: ARG002
        self.dataChanged.emit()

    # --- router / CSV helpers -------------------------------------------------
    # --- 新增：供外部（如 CaseConfigPage）调用，以动态加载指定目录的用例 ---
    def load_function_cases_from_dirs(self, target_dirs: list[str]) -> None:
        """
        Load function test cases from the specified directories.

        Args:
            target_dirs (list[str]): List of directory names relative to test/project/.
        """
        if self.func_form and hasattr(self.func_form, 'load_cases_from_dirs'):
            self.func_form.load_cases_from_dirs(target_dirs)
        else:
            logging.warning("func_form or load_cases_from_dirs not available.")

    def reset_function_cases(self) -> None:
        """Reset function test cases to show all."""
        if self.func_form and hasattr(self.func_form, 'on_reset_clicked'):
            self.func_form.on_reset_clicked()
        else:
            logging.warning("func_form or on_reset_clicked not available.")
