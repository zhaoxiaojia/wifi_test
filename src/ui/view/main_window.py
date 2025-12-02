"""Main application window view for the Wi-Fi Test Tool.

This module hosts the :class:`MainWindow` class and UI-specific helpers
that were previously defined in ``main.py``.  The goal is to keep
widget creation, navigation wiring and animations inside the view
layer so that ``main.py`` can focus on application bootstrap only.
"""

from __future__ import annotations

from pathlib import Path
import traceback
import logging
from contextlib import suppress
from typing import Annotated

from PyQt5.QtWidgets import (
    QAbstractButton,
    QGraphicsOpacityEffect,
    QMessageBox,
)
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtCore import (
    QCoreApplication,
    QPropertyAnimation,
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
)
import sip
from qfluentwidgets import FluentIcon, FluentWindow, NavigationItemPosition

from src.ui import SIDEBAR_PAGE_LABELS, SIDEBAR_PAGE_KEYS
from src.ui.view.case import RvrWifiConfigPage
from src.ui.view.config.page import CaseConfigPage
from src.ui.view.run import RunPage
from src.ui.view.report import ReportView
from src.ui.view.about import AboutView
from src.ui.view.account import CompanyLoginPage
from src.ui.controller.about_ctl import AboutController
from src.ui.controller.report_ctl import ReportController
from src.ui.controller.account_ctl import (
    get_configured_ldap_server,
    ldap_authenticate,
    load_auth_state,
    save_auth_state,
    clear_auth_state,
)
from src.ui.controller import set_run_locked
from src.ui.model.tools_registry import load_tools_registry
from src.ui.view.tools_global import GlobalToolsBar, GlobalToolsPanel
from src.ui.controller.tools_ctl import GlobalToolsController


def log_exception(exc_type, exc_value, exc_tb) -> None:
    """Write an unhandled exception to the application log.

    This helper mirrors the original implementation from ``main.py`` and
    is intended to be registered via ``sys.excepthook`` so that uncaught
    exceptions in Qt slots are recorded in the log.
    """

    formatted = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    logging.error("Unhandled exception:\n%s", formatted)


class MainWindow(FluentWindow):
    """Main application window for the Wi‑Fi Test Tool.

    This class is moved from ``main.py`` into the view layer without
    behavioural changes.  It owns creation of all top-level pages,
    navigation buttons, window animations and page transitions.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("FAE-QA  Wi-Fi Test Tool")
        screen = QGuiApplication.primaryScreen().availableGeometry()
        width = int(screen.width() * 0.7)
        height = int(screen.height() * 0.7)
        self.resize(width, height)
        self.setMinimumSize(width, height)
        # Global tools (toolbar + side panel)
        tool_specs = load_tools_registry()
        self.global_tools_bar = GlobalToolsBar(tool_specs, parent=self.stackedWidget)
        self.global_tools_panel = GlobalToolsPanel(parent=self.stackedWidget)
        self.global_tools_panel.hide()
        self.global_tools_controller = GlobalToolsController(
            self, self.global_tools_bar, self.global_tools_panel, tool_specs
        )
        self.center_window()
        self.show()

        self._active_account: dict | None = None

        final_rect = self.geometry()
        start_rect = final_rect.adjusted(
            int(final_rect.width() * 0.1),
            int(final_rect.height() * 0.1),
            -int(final_rect.width() * 0.1),
            -int(final_rect.height() * 0.1),
        )
        self.setGeometry(start_rect)
        self.setWindowOpacity(0)

        self._geo_animation = QPropertyAnimation(self, b"geometry")
        self._geo_animation.setDuration(400)
        self._geo_animation.setStartValue(start_rect)
        self._geo_animation.setEndValue(final_rect)
        self._geo_animation.setEasingCurve(QEasingCurve.OutBack)

        self._opacity_animation = QPropertyAnimation(self, b"windowOpacity")
        self._opacity_animation.setDuration(400)
        self._opacity_animation.setStartValue(0)
        self._opacity_animation.setEndValue(1)
        self._opacity_animation.setEasingCurve(QEasingCurve.OutBack)

        self._show_group = QParallelAnimationGroup(self)
        self._show_group.addAnimation(self._geo_animation)
        self._show_group.addAnimation(self._opacity_animation)

        def _restore():
            self.setGeometry(final_rect)
            self.setWindowOpacity(1)

        self._show_group.finished.connect(_restore)
        self._show_group.start()

        # Pages
        self.login_page = CompanyLoginPage(self)
        self.login_page.loginResult.connect(self._on_login_result)
        self.login_page.logoutRequested.connect(self._on_logout_requested)

        self.caseConfigPage = CaseConfigPage(self.on_run)
        self.rvr_wifi_config_page = RvrWifiConfigPage()

        # Keep RvR Wi‑Fi Case page in sync with the selected CSV from
        # the Config page.
        self.caseConfigPage.csvFileChanged.connect(
            self.rvr_wifi_config_page.on_csv_file_changed
        )
        initial_csv = self.caseConfigPage.selected_csv_path
        if initial_csv:
            self.rvr_wifi_config_page.on_csv_file_changed(initial_csv)
        self.run_page = RunPage("", parent=self)
        # Ensure run page starts empty
        self.run_page.reset()
        # Report page (disabled until report_dir created)
        self.report_view = ReportView(self)
        self.report_ctl = ReportController(self.report_view)

        # Navigation buttons
        # Logical sidebar keys (top -> bottom): account, config, case, run, report, about
        self.sidebar_page_keys = SIDEBAR_PAGE_KEYS
        self.sidebar_labels = SIDEBAR_PAGE_LABELS

        # Account / login entry
        self.login_nav_button = self._create_sidebar_button(
            "account",
            self.login_page,
            FluentIcon.PEOPLE,
        )
        self.login_nav_button.setVisible(True)
        self.login_nav_button.setEnabled(True)

        # Case configuration / main config page
        self.case_nav_button = self._create_sidebar_button(
            "config",
            self.caseConfigPage,
            FluentIcon.SETTING,
        )
        self.case_nav_button.setVisible(True)

        # RVR Wi‑Fi / scenario configuration
        self.rvr_nav_button = self._create_sidebar_button(
            "case",
            self.rvr_wifi_config_page,
            FluentIcon.WIFI,
        )

        # Run / execution page
        self.run_nav_button = self._create_sidebar_button(
            "run",
            self.run_page,
            FluentIcon.PLAY,
            position=NavigationItemPosition.BOTTOM,
        )
        self.run_nav_button.setVisible(True)

        # Report browser
        self.report_nav_button = self._create_sidebar_button(
            "report",
            self.report_view,
            FluentIcon.DOCUMENT,
            position=NavigationItemPosition.BOTTOM,
        )
        self.report_nav_button.setVisible(True)

        self.last_report_dir = None

        self.about_page = AboutView(self)
        # Attach behaviour from the controller (migrated from the old AboutPage)
        self.about_ctl = AboutController(self.about_page)
        self.about_nav_button = self._create_sidebar_button(
            "about",
            self.about_page,
            FluentIcon.INFO,
            position=NavigationItemPosition.BOTTOM,
        )
        self.about_nav_button.setVisible(True)

        # Canonical mapping from logical sidebar keys to pages/buttons
        self.sidebar_pages = {
            "account": self.login_page,
            "config": self.caseConfigPage,
            "case": self.rvr_wifi_config_page,
            "run": self.run_page,
            "report": self.report_view,
            "about": self.about_page,
        }
        self.sidebar_nav_buttons = {
            "account": self.login_nav_button,
            "config": self.case_nav_button,
            "case": self.rvr_nav_button,
            "run": self.run_nav_button,
            "report": self.report_nav_button,
            "about": self.about_nav_button,
        }

        self._nav_logged_out_states = {
            self.sidebar_nav_buttons["config"]: False,
            self.sidebar_nav_buttons["case"]: False,
            self.sidebar_nav_buttons["run"]: False,
            self.sidebar_nav_buttons["report"]: False,
            self.sidebar_nav_buttons["about"]: False,
        }
        # In the logged-in state, all feature pages are enabled.
        self._nav_logged_in_states = {
            self.sidebar_nav_buttons["config"]: True,
            self.sidebar_nav_buttons["case"]: True,
            self.sidebar_nav_buttons["run"]: True,
            self.sidebar_nav_buttons["report"]: True,
            self.sidebar_nav_buttons["about"]: True,
        }
        self._initialize_login_state()

        # Backward compatibility fields
        self._run_nav_button = self.run_nav_button
        self._rvr_nav_button = self.rvr_nav_button
        self._rvr_route_key = None
        self._nav_button_clicked_log_slot = None
        self._runner_finished_slot = None
        self._rvr_visible = False

        # Enable Mica effect on Windows 11
        self.setMicaEffectEnabled(True)
        # Position global tools after initial layout
        self._update_global_tools_geometry()

    # ------------------------------------------------------------------
    # Navigation button helpers
    # ------------------------------------------------------------------

    def _create_sidebar_button(
        self,
        key: str,
        page,
        icon,
        *,
        position: NavigationItemPosition | None = None,
    ):
        """Create a navigation button based on a logical sidebar key."""
        text, subtext = SIDEBAR_PAGE_LABELS.get(key, (key.title(), None))
        kwargs = {}
        if position is not None:
            kwargs["position"] = position
        if subtext:
            button = self._add_interface(page, icon, text, subtext, **kwargs)
        else:
            button = self._add_interface(page, icon, text, **kwargs)
        return button

    def _apply_nav_enabled(self, states: dict) -> None:
        """Enable or disable multiple navigation buttons in one call."""
        for btn, enabled in states.items():
            if btn and not sip.isdeleted(btn):
                btn.setEnabled(bool(enabled))

    # ------------------------------------------------------------------
    # Login / logout
    # ------------------------------------------------------------------

    def _initialize_login_state(self) -> None:
        """Restore navigation and initial page based on persisted auth state."""
        auth_state = load_auth_state()
        if (
            isinstance(auth_state, dict)
            and auth_state.get("authenticated")
            and auth_state.get("username")
        ):
            # Treat as already authenticated: enable all features and go to Config page.
            username = str(auth_state.get("username", "") or "").strip()
            self._active_account = {"username": username, "source": "cached"}
            self._apply_nav_enabled(self._nav_logged_in_states)
            # Keep Account page UI in sync with the cached login state.
            self.login_page.apply_cached_login(username)
            self.setCurrentIndex(self.caseConfigPage)
        else:
            # No previous login or explicitly cleared: force Account page and lock features.
            self._active_account = None
            self._apply_nav_enabled(self._nav_logged_out_states)
            self.setCurrentIndex(self.login_page)
        # Ensure About page metadata (including test duration) is in sync with
        # the latest on-disk state when the application starts.
        self.refresh_about_metadata()

    def _on_login_result(self, success: bool, message: str, payload: dict) -> None:
        """Handle completion of a login attempt."""
        logging.info(
            "MainWindow: sign-in finished success=%s message=%s payload=%s",
            success,
            message,
            payload,
        )
        if success:
            self._active_account = dict(payload)
            username = str(self._active_account.get("username", "") or "").strip()
            save_auth_state(username=username, authenticated=True)
            self._apply_nav_enabled(self._nav_logged_in_states)
            self.setCurrentIndex(self.caseConfigPage)
        else:
            self._active_account = None
            clear_auth_state()
            self._apply_nav_enabled(self._nav_logged_out_states)
            self.setCurrentIndex(self.login_page)

    def _on_logout_requested(self) -> None:
        """Respond to a user-initiated sign-out."""
        logging.info("MainWindow: user requested sign-out (active_account=%s)", self._active_account)
        self._apply_nav_enabled(self._nav_logged_out_states)
        self.setCurrentIndex(self.login_page)
        self._active_account = None
        clear_auth_state()
        self.login_page.set_status_message("Signed out. Please sign in again.", state="info")

    def refresh_about_metadata(self) -> None:
        """Refresh the About page metadata, including total test duration."""
        self.about_ctl.populate_metadata()

    # ------------------------------------------------------------------
    # RVR Wi-Fi page animation
    # ------------------------------------------------------------------

    def show_rvr_wifi_config(self):
        """Ensure the RVR config page exists, then slide it into view."""
        page = self._ensure_rvr_page()
        if not page:
            return
        try:
            width = self.stackedWidget.width()
            page.move(width, 0)
            self.setCurrentIndex(page)

            def _reset_pos():
                page.move(0, 0)

            anim = self._build_slide_animation(page)
            if anim:
                anim.setStartValue(QPoint(width, 0))
                anim.setEndValue(QPoint(0, 0))
                anim.finished.connect(_reset_pos)
                anim.start()
                self._rvr_slide_anim = anim
        except Exception as exc:
            logging.warning("show_rvr_wifi_config animation failed: %s", exc)

    def hide_rvr_wifi_config(self):
        """Slide the RVR Wi‑Fi configuration page out of view."""
        if not self._rvr_visible:
            return
        logging.debug(
            "hide_rvr_wifi_config start: page=%s current=%s",
            self.rvr_wifi_config_page,
            self.stackedWidget.currentWidget(),
        )

        width = self.stackedWidget.width()
        page = self.rvr_wifi_config_page

        # Switch to a safe page, keep current page visible to play slide animation
        self.setCurrentIndex(self.rvr_wifi_config_page)
        QCoreApplication.processEvents()

        if page:

            def _after():
                page.move(0, 0)
                page.hide()
                if self._rvr_nav_button and not sip.isdeleted(self._rvr_nav_button):
                    self._rvr_nav_button.setVisible(False)
                    logging.debug("hide_rvr_wifi_config: setVisible(False) for nav item")
                self._rvr_visible = False
                logging.debug("hide_rvr_wifi_config end: page=%s", self.rvr_wifi_config_page)

            anim = self._build_slide_animation(page)
            if anim:
                anim.setStartValue(QPoint(0, 0))
                anim.setEndValue(QPoint(width, 0))
                anim.finished.connect(_after)
                anim.start()
                self._rvr_slide_anim = anim
        else:
            if self._rvr_nav_button and not sip.isdeleted(self._rvr_nav_button):
                self._rvr_nav_button.setVisible(False)
                logging.debug("hide_rvr_wifi_config: setVisible(False) for nav item")
            self._rvr_visible = False
            logging.debug("hide_rvr_wifi_config end: page=%s", self.rvr_wifi_config_page)

    def _build_slide_animation(self, widget, duration_ms: int = 250) -> QPropertyAnimation | None:
        """Return a QPropertyAnimation configured for slide transitions."""
        if widget is None or sip.isdeleted(widget):
            return None
        anim = QPropertyAnimation(widget, b"pos", self)
        anim.setDuration(duration_ms)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        return anim

    def _ensure_rvr_page(self):
        """Return a live RVR page, registering it with the nav stack if required."""
        page = self.rvr_wifi_config_page
        if sip.isdeleted(page):
            self.rvr_wifi_config_page = RvrWifiConfigPage()
            page = self.rvr_wifi_config_page
        if page and not sip.isdeleted(page) and hasattr(page, "reload_csv"):
            page.reload_csv()
        if self._rvr_nav_button and not sip.isdeleted(self._rvr_nav_button):
            if self.stackedWidget.indexOf(page) == -1:
                self.stackedWidget.addWidget(page)
            self._rvr_nav_button.setVisible(True)
            self._rvr_visible = True
            logging.debug("show_rvr_wifi_config: reuse nav item; setVisible(True)")
            return page
        nav_items = [btn.text() for btn in self.navigationInterface.findChildren(QAbstractButton)]
        logging.debug(
            "show_rvr_wifi_config start: page id=%s nav items=%s",
            id(page),
            nav_items,
        )
        route_key = self._rvr_route_key or page.objectName()
        self._cleanup_route(route_key)
        self._rvr_nav_button = self._create_sidebar_button("case", page, FluentIcon.WIFI)
        if not self._rvr_nav_button:
            logging.warning(
                "addSubInterface returned None (duplicate routeKey or internal reject)",
            )
            self._rvr_visible = False
            QMessageBox.critical(
                self,
                "Error",
                "Failed to add RVR Wi-Fi Config page. Please check logs.",
            )
            return None
        self._rvr_route_key = (
            self._rvr_nav_button.property("routeKey") or page.objectName()
        )
        logging.debug("show_rvr_wifi_config: routeKey=%s", self._rvr_route_key)
        self._rvr_nav_button.setVisible(True)
        if self.stackedWidget.indexOf(page) == -1:
            self.stackedWidget.addWidget(page)
        self._rvr_visible = True
        return page

    def _cleanup_route(self, route_key: str | None) -> None:
        """Remove stale FluentWindow route mappings if they still exist."""
        if not route_key:
            return
        for mapping in (self._interfaces, self._routes):
            if mapping.pop(route_key, None) is not None:
                logging.debug("show_rvr_wifi_config: removed stale route %s", route_key)

    def _detach_sub_interface(self, page):
        """Disconnect a page from the Fluent navigation system."""
        nav = self.navigationInterface
        if not page or sip.isdeleted(page):
            return False

        # Prefer official APIs (try in order, finally removeWidget(page))
        for func in (
            nav.removeSubInterface,
            nav.removeInterface,
            nav.removeItem,
            nav.removeWidget,
        ):
            try:
                func(page)
                return True
            except Exception:
                pass

        # Fallback: remove any child with the same routeKey (not always QAbstractButton)
        try:
            from PyQt5.QtWidgets import QWidget

            rk = page.objectName() or "rvrWifiConfigPage"
            for w in nav.findChildren(QWidget):
                try:
                    if w.property("routeKey") == rk:
                        try:
                            w.setParent(None)
                        except Exception:
                            pass
                        try:
                            w.deleteLater()
                        except Exception:
                            pass
                        return True
                except Exception:
                    continue
        except Exception:
            pass
        return False

    def _add_interface(self, *args, **kwargs):
        """Wrapper around :meth:`addSubInterface` that logs diagnostic information."""
        widget = args[0] if args else kwargs.get("interface") or kwargs.get("widget")
        if widget is None or sip.isdeleted(widget):
            raise RuntimeError("_add_interface called with a None/invalid widget")
        logging.debug("_add_interface: adding %s", widget)
        btn = self.addSubInterface(*args, **kwargs)
        nav = self.navigationInterface
        nav_count = len(nav.findChildren(QAbstractButton))
        stack_count = self.stackedWidget.count()
        logging.debug(
            "_add_interface: nav count=%s stack count=%s", nav_count, stack_count
        )
        if btn is None:
            logging.warning(
                "addSubInterface returned None (maybe duplicate routeKey or rejected by framework)"
            )
        return btn

    def _remove_interface(self, page, route_key=None, nav_button=None):
        """Remove a page and its navigation entry from the UI."""
        nav = self.navigationInterface

        rk = route_key or (nav_button.property("routeKey") if nav_button else None) or page.objectName()
        removed = False
        try:
            # 1) Prefer FluentWindow.removeSubInterface
            removed = bool(self.removeSubInterface(page))
            # 2) Fallback: navigationInterface.removeItem
            if not removed and rk:
                removed = bool(nav.removeItem(rk))
        except Exception as e:
            logging.error("_remove_interface: failed to remove nav item %s: %s", rk, e)
            raise

        if not removed:
            logging.error("_remove_interface: removal failed for %s", rk)
            raise RuntimeError(f"failed to remove navigation item {rk}")

        # 3) After nav item removed, detach nav_button
        if nav_button and not sip.isdeleted(nav_button):
            with suppress(Exception):
                nav_button.clicked.disconnect()
            with suppress(Exception):
                nav_button.setParent(None)

        # 4) Remove page from stacked widget
        if page and not sip.isdeleted(page):
            with suppress(Exception):
                self.stackedWidget.removeWidget(page)

        QCoreApplication.processEvents()

        # 5) Clear pointers
        self._rvr_nav_button = None
        self._rvr_route_key = None
        self.rvr_wifi_config_page = None

        # 6) Clean routeKey mappings inside FluentWindow (if exist)
        self._cleanup_route(rk)

    # ------------------------------------------------------------------
    # Run-page helpers
    # ------------------------------------------------------------------

    def clear_run_page(self):
        """Reset the RunPage and disconnect any associated event hooks."""
        if not sip.isdeleted(self.run_page):
            if self._runner_finished_slot:
                with suppress(Exception):
                    self.run_page.runner.finished.disconnect(self._runner_finished_slot)
            self._runner_finished_slot = None
            if self._run_nav_button and self._nav_button_clicked_log_slot:
                with suppress(Exception):
                    self._run_nav_button.clicked.disconnect(self._nav_button_clicked_log_slot)
                    logging.info(
                        "Disconnected nav button clicked for RunPage id=%s",
                        id(self.run_page),
                    )
            with suppress(Exception):
                self.run_page.reset()
        QCoreApplication.processEvents()
        logging.info("RunPage cleared")
        if hasattr(self.rvr_wifi_config_page, "run_btn"):
            self.rvr_wifi_config_page.run_btn.setEnabled(True)

    def _set_nav_buttons_enabled(self, enabled: bool):
        """Enable all navigation buttons and optionally adjust their appearance."""
        buttons = self.navigationInterface.findChildren(QAbstractButton)
        for btn in buttons:
            # Keep run button visible
            if btn is self._run_nav_button:
                btn.setVisible(True)
            btn.setEnabled(True)
            btn.setStyleSheet("font-family: Verdana;")

    # ------------------------------------------------------------------
    # Geometry / transitions
    # ------------------------------------------------------------------

    def center_window(self):
        """Center this window on the primary monitor."""
        screen_geometry = QGuiApplication.primaryScreen().availableGeometry()
        window_geometry = self.frameGeometry()
        center_point = screen_geometry.center()
        window_geometry.moveCenter(center_point)
        self.move(window_geometry.topLeft())
        self._update_global_tools_geometry()

    def resizeEvent(self, event):  # type: ignore[override]
        """Reposition global tool widgets when the window is resized."""
        super().resizeEvent(event)
        self._update_global_tools_geometry()

    def _update_global_tools_geometry(self) -> None:
        """Place the global tools bar and panel relative to the content area."""
        content = self.stackedWidget
        width = content.width()
        height = content.height()
        margin = 8

        bar = self.global_tools_bar
        bar_height = bar.sizeHint().height()
        content.setContentsMargins(0, bar_height + margin, 0, 0)
        bar.setGeometry(0, 0, width, bar_height)

        panel = self.global_tools_panel
        if not panel.isVisible():
            return
        panel_width = max(int(width * 0.3), 320)
        panel_x = max(0, width - panel_width)
        panel_y = bar_height + margin
        panel_height = max(0, height - panel_y)
        panel.setGeometry(panel_x, panel_y, max(0, width - panel_x), panel_height)

    def setCurrentIndex(self, page_widget, ssid: str | None = None, passwd: str | None = None):
        """Switch the active page with a cross-fade animation."""
        try:
            if page_widget is self.rvr_wifi_config_page and (ssid or passwd):
                self.rvr_wifi_config_page.set_router_credentials(ssid or "", passwd or "")
            self._route_to_page(page_widget)
        except Exception as e:
            logging.error("Failed to set current widget: %s", e)

    def _route_to_page(self, page_widget) -> None:
        """Apply a fade transition to the requested stacked widget."""
        if page_widget is None:
            return
        current = self.stackedWidget.currentWidget()
        if current is page_widget:
            return
        if current:
            effect = QGraphicsOpacityEffect(current)
            current.setGraphicsEffect(effect)
            fade_out = QPropertyAnimation(effect, b"opacity", current)
            fade_out.setDuration(200)
            fade_out.setStartValue(1.0)
            fade_out.setEndValue(0.0)
            fade_out.setEasingCurve(QEasingCurve.OutCubic)
            fade_out.start()
            self._fade_out = fade_out

            def _clear_old_effect():
                current.setGraphicsEffect(None)

            fade_out.finished.connect(_clear_old_effect)
        self.stackedWidget.setCurrentWidget(page_widget)
        effect_in = QGraphicsOpacityEffect(page_widget)
        page_widget.setGraphicsEffect(effect_in)
        fade_in = QPropertyAnimation(effect_in, b"opacity", page_widget)
        fade_in.setDuration(200)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.OutCubic)
        fade_in.start()
        self._fade_in = fade_in

        def _clear_new_effect():
            page_widget.setGraphicsEffect(None)

        fade_in.finished.connect(_clear_new_effect)
        logging.debug("Switched widget to %s", page_widget)

    # ------------------------------------------------------------------
    # Run orchestration
    # ------------------------------------------------------------------

    def on_run(self, case_path, display_case_path, config):
        """Kick off execution of a test case and display the run page."""
        # Lock Config + Case pages while the run is active.
        set_run_locked(self, True)
        try:
            self._trigger_run(case_path, display_case_path, config)
        except Exception as e:
            logging.error("on_run failed: %s", e, exc_info=True)
            QMessageBox.critical(self, "Error", f"Unable to run: {e}")
            set_run_locked(self, False)
            if self._run_nav_button and not sip.isdeleted(self._run_nav_button):
                self._run_nav_button.setEnabled(False)
                self._run_nav_button.setVisible(False)

    def _trigger_run(self, case_path, display_case_path, config) -> None:
        """Populate the RunPage state and start executing the selected case."""
        with suppress(Exception):
            self.run_page.reset()
        self.run_page.case_path = case_path
        self.run_page.display_case_path = self.run_page._calc_display_path(
            case_path, display_case_path
        )
        self.run_page.case_path_label.setText(self.run_page.display_case_path)
        self.run_page.config = config

        self.run_nav_button.setVisible(True)
        self.run_nav_button.setEnabled(True)
        if self.stackedWidget.indexOf(self.run_page) == -1:
            self.stackedWidget.addWidget(self.run_page)
        self.switchTo(self.run_page)
        self.run_page.run_case()
        runner = self.run_page.runner

        def _on_runner_finished():
            set_run_locked(self, False)
            self.refresh_about_metadata()

        self._runner_finished_slot = _on_runner_finished
        runner.finished.connect(self._runner_finished_slot)

        logging.info("Switched to RunPage: %s", self.run_page)

    # NOTE: switchTo is provided by FluentWindow; callers use setCurrentIndex.

    # ------------------------------------------------------------------
    # Case config + report helpers
    # ------------------------------------------------------------------

    def show_case_config(self):
        """Switch to the case configuration page."""
        self.setCurrentIndex(self.rvr_wifi_config_page)
        logging.info("Switched to CaseConfigPage")

    def stop_run_and_show_case_config(self):
        """Abort a running test and return to the case configuration page."""
        self.setCurrentIndex(self.rvr_wifi_config_page)
        QCoreApplication.processEvents()
        set_run_locked(self, False)
        self.refresh_about_metadata()
        if self._run_nav_button and not sip.isdeleted(self._run_nav_button):
            self._run_nav_button.setEnabled(False)
        logging.info("Switched to CaseConfigPage")

    def enable_report_page(self, report_dir: str) -> None:
        """Activate the report viewing page after test execution."""
        try:
            self.last_report_dir = str(Path(report_dir).resolve())
            case_path = self.run_page.case_path
            self.report_ctl.set_case_context(case_path or None)
            self.report_ctl.set_report_dir(self.last_report_dir)
            if not sip.isdeleted(self.report_nav_button):
                self.report_nav_button.setEnabled(True)
                self.report_nav_button.setVisible(True)
        except Exception:
            pass


__all__ = ["MainWindow", "log_exception"]
