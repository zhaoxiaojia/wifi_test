# !/usr/bin/env python
# -*-coding:utf-8 -*-

from __future__ import annotations

import sys
from pathlib import Path
import traceback
import logging
import os
from contextlib import suppress

sys.path.insert(0, str(Path(__file__).parent))
from PyQt5.QtWidgets import (
    QApplication,
    QAbstractButton,
    QGraphicsOpacityEffect,
    QMessageBox,
)
import sip
from qfluentwidgets import FluentIcon, FluentWindow, NavigationItemPosition
from src.ui.windows_case_config import CaseConfigPage
from src.ui.rvr_wifi_config import RvrWifiConfigPage
from src.ui.run import RunPage
from src.ui.report_page import ReportPage
from src.ui.about_page import AboutPage
from src.ui.company_login import (
    CompanyLoginPage,
    get_configured_ldap_server,
    ldap_authenticate,
)
from qfluentwidgets import setTheme, Theme
from PyQt5.QtGui import QGuiApplication, QFont
from PyQt5.QtCore import (
    QCoreApplication,
    QPropertyAnimation,
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
)
from src.util.constants import Paths, cleanup_temp_dir

# Ensure working directory equals executable directory
os.chdir(Paths.BASE_DIR)


def log_exception(exc_type, exc_value, exc_tb):
    logging.error("".join(traceback.format_exception(exc_type, exc_value, exc_tb)))

class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FAE-QA  Wi-Fi Test Tool")
        screen = QGuiApplication.primaryScreen().availableGeometry()
        width = int(screen.width() * 0.7)
        height = int(screen.height() * 0.7)
        self.resize(width, height)
        self.setMinimumSize(width, height)
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

        self.case_config_page = CaseConfigPage(self.on_run)
        self.rvr_wifi_config_page = RvrWifiConfigPage(self.case_config_page)
        self.run_page = RunPage("", parent=self)
        # Ensure run page starts empty
        self.run_page.reset()
        # Report page (disabled until report_dir created)
        self.report_page = ReportPage(self)

        # Navigation buttons
        self.login_nav_button = self.addSubInterface(
            self.login_page,
            FluentIcon.PEOPLE,
            "Login",
        )
        self.login_nav_button.setVisible(True)
        self.login_nav_button.setEnabled(True)

        self.case_nav_button = self.addSubInterface(
            self.case_config_page, FluentIcon.SETTING, "Config Setup", "Case Config"
        )
        self.case_nav_button.setVisible(True)

        self.rvr_nav_button = self.addSubInterface(
            self.rvr_wifi_config_page,
            FluentIcon.WIFI,
            "RVR Scenario Config",
            "RVR Wi-Fi Config",
        )
        self.rvr_nav_button.setVisible(True)

        self.run_nav_button = self.addSubInterface(
            self.run_page,
            FluentIcon.PLAY,
            "Test",
            position=NavigationItemPosition.BOTTOM,
        )
        self.run_nav_button.setVisible(True)

        self.report_nav_button = self.addSubInterface(
            self.report_page,
            FluentIcon.DOCUMENT,
            "Reports",
            position=NavigationItemPosition.BOTTOM,
        )
        self.report_nav_button.setVisible(True)

        self.last_report_dir = None

        self.about_page = AboutPage(self)
        self.about_nav_button = self.addSubInterface(
            self.about_page,
            FluentIcon.INFO,
            "About",
            position=NavigationItemPosition.BOTTOM,
        )
        self.about_nav_button.setVisible(True)

        self._nav_logged_out_states = {
            self.case_nav_button: True,
            self.rvr_nav_button: False,
            self.run_nav_button: True,
            self.report_nav_button: False,
            self.about_nav_button: True,
        }
        self._nav_logged_in_states = dict(self._nav_logged_out_states)
        self._apply_nav_enabled(self._nav_logged_out_states)
        self.setCurrentIndex(self.login_page)

        # Backward compatibility fields
        self._run_nav_button = self.run_nav_button
        self._rvr_nav_button = self.rvr_nav_button
        self._rvr_route_key = None
        self._nav_button_clicked_log_slot = None
        self._runner_finished_slot = None
        self._rvr_visible = False

        # Enable Mica effect on Windows 11
        self.setMicaEffectEnabled(True)

    def _apply_nav_enabled(self, states: dict) -> None:
        """Batch set navigation buttons enabled states."""
        for btn, enabled in states.items():
            if btn and not sip.isdeleted(btn):
                btn.setEnabled(bool(enabled))

    # ------------------------------------------------------------------
    def _on_login_result(self, success: bool, message: str, payload: dict) -> None:
        logging.info(
            "MainWindow: sign-in finished success=%s message=%s payload=%s",
            success,
            message,
            payload,
        )
        if success:
            self._active_account = dict(payload)
            self._apply_nav_enabled(self._nav_logged_in_states)
            self.setCurrentIndex(self.case_config_page)
        else:
            self._active_account = None
            self._apply_nav_enabled(self._nav_logged_out_states)
            self.setCurrentIndex(self.login_page)

    def _on_logout_requested(self) -> None:
        logging.info("MainWindow: user requested sign-out (active_account=%s)", self._active_account)
        self._apply_nav_enabled(self._nav_logged_out_states)
        self.setCurrentIndex(self.login_page)
        self._active_account = None
        self.login_page.set_status_message("Signed out. Please sign in again.", state="info")

    def show_rvr_wifi_config(self):
        """Show RVR Wi-Fi config page in navigation (idempotent: make visible if already added)."""
        # If it exists: do not add twice, just show
        if self._rvr_nav_button and not sip.isdeleted(self._rvr_nav_button):
            if self.rvr_wifi_config_page is None or sip.isdeleted(self.rvr_wifi_config_page):
                self.rvr_wifi_config_page = RvrWifiConfigPage(self.case_config_page)
            # Ensure page is in the stack
            if self.stackedWidget.indexOf(self.rvr_wifi_config_page) == -1:
                self.stackedWidget.addWidget(self.rvr_wifi_config_page)
            self._rvr_nav_button.setVisible(True)
            self._rvr_visible = True
            logging.debug("show_rvr_wifi_config: reuse nav item; setVisible(True)")
            return

        # First-time add
        nav = getattr(self, "navigationInterface", None)
        nav_items = []
        if nav:
            nav_items = [getattr(btn, "text", lambda: "")() for btn in nav.findChildren(QAbstractButton)]
        logging.debug(
            "show_rvr_wifi_config start: page id=%s nav items=%s",
            id(self.rvr_wifi_config_page),
            nav_items,
        )

        if self.rvr_wifi_config_page is None or sip.isdeleted(self.rvr_wifi_config_page):
            self.rvr_wifi_config_page = RvrWifiConfigPage(self.case_config_page)
        if self.rvr_wifi_config_page and not sip.isdeleted(self.rvr_wifi_config_page) and hasattr(
                self.rvr_wifi_config_page, "reload_csv"):
            self.rvr_wifi_config_page.reload_csv()

        # If a stale routeKey exists from last time, remove before re-adding
        rk = (
            self._rvr_route_key
            or getattr(self.rvr_wifi_config_page, "objectName", lambda: None)()
        )
        for attr in ("_interfaces", "_routes"):
            mapping = getattr(self, attr, None)
            if mapping and rk in mapping:
                try:
                    mapping.pop(rk, None)
                    logging.debug(
                        "show_rvr_wifi_config: removed stale %s[%s] before re-add", attr, rk
                    )
                except Exception as e:
                    logging.warning(
                        "show_rvr_wifi_config: failed to remove %s[%s]: %s", attr, rk, e
                    )

        self._rvr_nav_button = self._add_interface(
            self.rvr_wifi_config_page,
            FluentIcon.WIFI,
            "RVR Scenario Config",
            "RVR Wi-Fi Config",
        )
        if not self._rvr_nav_button:
            logging.warning(
                "addSubInterface returned None (duplicate routeKey or internal reject)",
            )
            QMessageBox.critical(
                self,
                "Error",
                "Failed to add RVR Wi-Fi Config page. Please check logs.",
            )
            self._rvr_visible = False
            return

        self._rvr_route_key = self._rvr_nav_button.property("routeKey") or self.rvr_wifi_config_page.objectName()
        logging.debug("show_rvr_wifi_config: routeKey=%s", self._rvr_route_key)
        # Make visible after first add
        self._rvr_nav_button.setVisible(True)
        # Ensure in stack
        if self.stackedWidget.indexOf(self.rvr_wifi_config_page) == -1:
            self.stackedWidget.addWidget(self.rvr_wifi_config_page)
        self._rvr_visible = True

        # Slide animation and switch to RVR config page
        try:
            width = self.stackedWidget.width()
            page = self.rvr_wifi_config_page
            if page:
                page.move(width, 0)
                self.setCurrentIndex(page)
                anim = QPropertyAnimation(page, b"pos", self)
                anim.setDuration(200)
                anim.setStartValue(QPoint(width, 0))
                anim.setEndValue(QPoint(0, 0))
                anim.setEasingCurve(QEasingCurve.OutCubic)

                def _reset_pos():
                    page.move(0, 0)

                anim.finished.connect(_reset_pos)
                anim.start()
                self._rvr_slide_anim = anim
        except Exception as e:
            logging.warning("show_rvr_wifi_config animation failed: %s", e)

    def hide_rvr_wifi_config(self):
        """Hide RVR Wi-Fi config page from navigation (do not remove to avoid routeKey residue)."""
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
        self.setCurrentIndex(self.case_config_page)
        QCoreApplication.processEvents()

        if page:
            page.show()
            page.raise_()
            anim = QPropertyAnimation(page, b"pos", self)
            anim.setDuration(200)
            anim.setStartValue(QPoint(0, 0))
            anim.setEndValue(QPoint(width, 0))
            anim.setEasingCurve(QEasingCurve.OutCubic)

            def _after():
                page.move(0, 0)
                page.hide()
                if self._rvr_nav_button and not sip.isdeleted(self._rvr_nav_button):
                    self._rvr_nav_button.setVisible(False)
                    logging.debug("hide_rvr_wifi_config: setVisible(False) for nav item")
                self._rvr_visible = False
                logging.debug("hide_rvr_wifi_config end: page=%s", self.rvr_wifi_config_page)

            anim.finished.connect(_after)
            anim.start()
            self._rvr_slide_anim = anim
        else:
            if self._rvr_nav_button and not sip.isdeleted(self._rvr_nav_button):
                self._rvr_nav_button.setVisible(False)
                logging.debug("hide_rvr_wifi_config: setVisible(False) for nav item")
            self._rvr_visible = False
            logging.debug("hide_rvr_wifi_config end: page=%s", self.rvr_wifi_config_page)

    def _detach_sub_interface(self, page):
        """Detach the given page from navigation, best-effort for different QFluent versions."""
        nav = getattr(self, "navigationInterface", None)
        if not nav or not page or sip.isdeleted(page):
            return False

        # Prefer official APIs (try in order, finally removeWidget(page))
        for name in ("removeSubInterface", "removeInterface", "removeItem", "removeWidget"):
            func = getattr(nav, name, None)
            if callable(func):
                try:
                    func(page)  # remove by page
                    return True
                except Exception:
                    pass

        # Fallback: remove any child with the same routeKey (not always QAbstractButton)
        try:
            from PyQt5.QtWidgets import QWidget
            rk = getattr(page, "objectName", lambda: None)() or "rvrWifiConfigPage"
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
        widget = args[0] if args else kwargs.get("interface") or kwargs.get("widget")
        if widget is None or sip.isdeleted(widget):
            raise RuntimeError("_add_interface called with a None/invalid widget")
        logging.debug("_add_interface: adding %s", widget)
        btn = self.addSubInterface(*args, **kwargs)
        nav = getattr(self, "navigationInterface", None)
        nav_count = len(nav.findChildren(QAbstractButton)) if nav else 0
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
        nav = getattr(self, "navigationInterface", None)

        rk = (
            route_key
            or (nav_button.property("routeKey") if nav_button else None)
            or getattr(page, "objectName", lambda: None)()
        )
        removed = False
        try:
            # 1) Prefer FluentWindow.removeSubInterface
            func = getattr(self, "removeSubInterface", None)
            if callable(func):
                removed = bool(func(page))
            # 2) Fallback: navigationInterface.removeItem
            elif nav and rk:
                func = getattr(nav, "removeItem", None)
                if callable(func):
                    removed = bool(func(rk))
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
        if rk:
            try:
                if hasattr(self, "_interfaces"):
                    self._interfaces.pop(rk, None)
                    logging.debug(
                        ">>> _remove_interface: removed %s from self._interfaces", rk
                    )
                if hasattr(self, "_routes"):
                    self._routes.pop(rk, None)
                    logging.debug(
                        ">>> _remove_interface: removed %s from self._routes", rk
                    )
            except Exception as e:
                logging.warning(
                    ">>> _remove_interface: failed to clean routeKey mapping: %s", e
                )

    # ==== DEBUG: deep nav/router/stack introspection ====
    def _debug_nav_state(self, tag: str):
        logging.debug("\n===== DEBUG NAV STATE [%s] =====", tag)
        nav = getattr(self, "navigationInterface", None)
        if not nav:
            logging.debug("navigationInterface = None")
            return

        # 1) Detect available methods (we care how removeX is named)
        def _has(obj, name):
            try:
                return callable(getattr(obj, name, None))
            except Exception:
                return False

        nav_methods = [
            n
            for n in (
                "removeItem",
                "removeWidget",
                "removeButton",
                "removeSubInterface",
                "removeInterface",
                "addItem",
                "addWidget",
            )
            if _has(nav, n)
        ]
        fw_methods = [n for n in ("removeSubInterface", "addSubInterface") if _has(self, n)]
        logging.debug("nav methods: %s", nav_methods)
        logging.debug("FluentWindow methods: %s", fw_methods)

        # 2) List children likely to be nav buttons
        try:
            btns = nav.findChildren(QAbstractButton)
        except Exception:
            btns = []
        logging.debug("QAbstractButton count: %s", len(btns))
        for i, b in enumerate(btns):
            try:
                cls = b.metaObject().className()
            except Exception:
                cls = type(b).__name__
            props = {}
            for k in ("routeKey", "text", "objectName"):
                try:
                    if k == "text":
                        v = b.text()
                    else:
                        v = b.property(k)
                except Exception:
                    v = None
                props[k] = v
            logging.debug("  [BTN#%s] id=%s class=%s props=%s", i, id(b), cls, props)

        # 3) Find any QWidget with a routeKey property
        try:
            from PyQt5.QtWidgets import QWidget
            widgets = nav.findChildren(QWidget)
        except Exception:
            widgets = []
        rk_widgets = []
        for w in widgets:
            try:
                rk = w.property("routeKey")
            except Exception:
                rk = None
            if rk:
                rk_widgets.append(w)
        logging.debug("widgets-with-routeKey count: %s", len(rk_widgets))
        for i, w in enumerate(rk_widgets):
            try:
                cls = w.metaObject().className()
            except Exception:
                cls = type(w).__name__
            logging.debug(
                "  [RK#%s] id=%s class=%s routeKey=%s objName=%s",
                i,
                id(w),
                cls,
                w.property("routeKey"),
                w.objectName(),
            )

        # 4) Router state (best-effort, names vary)
        router = getattr(nav, "router", None)
        if router:
            logging.debug("router exists: %s", type(router).__name__)
            for key in ("stackHistories", "currentKey", "history", "routeView"):
                try:
                    val = getattr(router, key, None)
                    if callable(val):
                        val = val()
                    logging.debug("  router.%s = %s", key, val)
                except Exception:
                    pass
            for key in ("routes", "_routes", "routeTable", "routeMap"):
                try:
                    routes = getattr(router, key, None)
                    if routes:
                        try:
                            keys = list(routes.keys()) if hasattr(routes, "keys") else routes
                        except Exception:
                            keys = routes
                        logging.debug("  router.%s keys = %s", key, keys)
                except Exception:
                    pass
        else:
            logging.debug("router = None")

        # 5) StackedWidget contents
        try:
            count = self.stackedWidget.count()
        except Exception:
            count = -1
        logging.debug("stackedWidget count: %s", count)
        try:
            for i in range(count):
                w = self.stackedWidget.widget(i)
                try:
                    cls = w.metaObject().className()
                except Exception:
                    cls = type(w).__name__
                logging.debug(
                    "  [STACK#%s] id=%s class=%s objName=%s",
                    i,
                    id(w),
                    cls,
                    w.objectName(),
                )
        except Exception:
            pass

        # 6) Our pointers
        logging.debug("self._rvr_visible = %s", getattr(self, "_rvr_visible", None))
        logging.debug("self._rvr_nav_button = %s", getattr(self, "_rvr_nav_button", None))
        logging.debug("self._rvr_route_key = %s", getattr(self, "_rvr_route_key", None))
        logging.debug(
            "self.rvr_wifi_config_page = %s", getattr(self, "rvr_wifi_config_page", None)
        )
        logging.debug("===== END DEBUG NAV STATE =====\n")

    # ==== DEBUG END ====

    def clear_run_page(self):
        if self.run_page and not sip.isdeleted(self.run_page):
            runner = getattr(self.run_page, "runner", None)
            if runner and self._runner_finished_slot:
                with suppress(Exception):
                    runner.finished.disconnect(self._runner_finished_slot)
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
        if hasattr(self.case_config_page, "run_btn"):
            self.case_config_page.run_btn.setEnabled(True)

    def _set_nav_buttons_enabled(self, enabled: bool):
        """Keep nav buttons enabled and optionally tweak styles."""
        nav = getattr(self, "navigationInterface", None)
        if not nav:
            return
        buttons = nav.findChildren(QAbstractButton)
        for btn in buttons:
            # Keep run button visible
            if btn is self._run_nav_button:
                btn.setVisible(True)
            btn.setEnabled(True)
            btn.setStyleSheet("font-family: Verdana;")

    def center_window(self):
        # Center window on the primary screen
        screen_geometry = QGuiApplication.primaryScreen().availableGeometry()
        window_geometry = self.frameGeometry()
        center_point = screen_geometry.center()
        window_geometry.moveCenter(center_point)
        self.move(window_geometry.topLeft())

    def setCurrentIndex(self, page_widget, ssid: str | None = None, passwd: str | None = None):
        try:
            if page_widget is self.rvr_wifi_config_page and (ssid or passwd):
                if hasattr(self.rvr_wifi_config_page, "set_router_credentials"):
                    self.rvr_wifi_config_page.set_router_credentials(ssid or "", passwd or "")
            current = self.stackedWidget.currentWidget()
            if current is not page_widget:
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
                    fade_out.finished.connect(lambda: current.setGraphicsEffect(None))
                self.stackedWidget.setCurrentWidget(page_widget)
                if page_widget:
                    effect_in = QGraphicsOpacityEffect(page_widget)
                    page_widget.setGraphicsEffect(effect_in)
                    fade_in = QPropertyAnimation(effect_in, b"opacity", page_widget)
                    fade_in.setDuration(200)
                    fade_in.setStartValue(0.0)
                    fade_in.setEndValue(1.0)
                    fade_in.setEasingCurve(QEasingCurve.OutCubic)
                    fade_in.start()
                    self._fade_in = fade_in
                    fade_in.finished.connect(lambda: page_widget.setGraphicsEffect(None))
                logging.debug("Switched widget to %s", page_widget)
        except Exception as e:
            logging.error("Failed to set current widget: %s", e)

    def on_run(self, case_path, display_case_path, config):
        self.case_config_page.lock_for_running(True)
        if getattr(self, "rvr_wifi_config_page", None):
            self.rvr_wifi_config_page.set_readonly(True)
        try:
            if self.run_page:
                with suppress(Exception):
                    self.run_page.reset()

            # Update RunPage info
            self.run_page.case_path = case_path
            self.run_page.display_case_path = self.run_page._calc_display_path(
                case_path, display_case_path
            )
            if hasattr(self.run_page, "case_path_label"):
                self.run_page.case_path_label.setText(self.run_page.display_case_path)
            self.run_page.config = config

            # Show run page
            self.run_nav_button.setVisible(True)
            self.run_nav_button.setEnabled(True)
            if self.stackedWidget.indexOf(self.run_page) == -1:
                self.stackedWidget.addWidget(self.run_page)
            self.switchTo(self.run_page)
            self.case_config_page.lock_for_running(True)
            if hasattr(self.rvr_wifi_config_page, "set_readonly"):
                self.rvr_wifi_config_page.set_readonly(True)
            # Start test
            self.run_page.run_case()
            runner = getattr(self.run_page, "runner", None)
            if runner:
                def _on_runner_finished():
                    self.case_config_page.lock_for_running(False)
                    if getattr(self, "rvr_wifi_config_page", None):
                        self.rvr_wifi_config_page.set_readonly(False)
                    # Keep RVR nav button enabled when needed to review logs
                    if self.rvr_nav_button and not sip.isdeleted(self.rvr_nav_button):
                        is_perf = self.case_config_page._is_performance_case(
                            getattr(self.run_page, "case_path", "")
                        )
                        self.rvr_nav_button.setEnabled(is_perf)

                self._runner_finished_slot = _on_runner_finished
                runner.finished.connect(self._runner_finished_slot)

            logging.info("Switched to RunPage: %s", self.run_page)
        except Exception as e:
            logging.error("on_run failed: %s", e, exc_info=True)
            QMessageBox.critical(self, "Error", f"Unable to run: {e}")
            self.case_config_page.lock_for_running(False)
            if getattr(self, "rvr_wifi_config_page", None):
                self.rvr_wifi_config_page.set_readonly(False)
            if self._run_nav_button and not sip.isdeleted(self._run_nav_button):
                self._run_nav_button.setEnabled(False)
                self._run_nav_button.setVisible(False)

    def show_case_config(self):
        self.setCurrentIndex(self.case_config_page)
        logging.info("Switched to CaseConfigPage")

    def stop_run_and_show_case_config(self):
        self.setCurrentIndex(self.case_config_page)
        QCoreApplication.processEvents()
        self.case_config_page.lock_for_running(False)
        if getattr(self, "rvr_wifi_config_page", None):
            self.rvr_wifi_config_page.set_readonly(False)
        if self._run_nav_button and not sip.isdeleted(self._run_nav_button):
            self._run_nav_button.setEnabled(False)
        self.case_config_page.lock_for_running(False)
        if hasattr(self.rvr_wifi_config_page, "set_readonly"):
            self.rvr_wifi_config_page.set_readonly(False)
        if self.rvr_nav_button and not sip.isdeleted(self.rvr_nav_button):
            is_perf = self.case_config_page._is_performance_case(
                getattr(self.run_page, "case_path", "")
            )
            self.rvr_nav_button.setEnabled(is_perf)
        logging.info("Switched to CaseConfigPage")

    # --- Reports ---
    def enable_report_page(self, report_dir: str) -> None:
        """Enable report page and set current report directory.

        Called when runner notifies that report_dir.mkdir(...) succeeded.
        """
        try:
            self.last_report_dir = str(Path(report_dir).resolve())
            if hasattr(self, "report_page") and self.report_page:
                case_path = getattr(self.run_page, "case_path", "")
                self.report_page.set_case_context(case_path or None)
                self.report_page.set_report_dir(self.last_report_dir)
            if hasattr(self, "report_nav_button") and self.report_nav_button and not sip.isdeleted(self.report_nav_button):
                self.report_nav_button.setEnabled(True)
                self.report_nav_button.setVisible(True)
        except Exception:
            pass


sys.excepthook = log_exception
import multiprocessing
import sys, os, logging, subprocess as _sp

# Windows only; hide subprocess console windows (can disable with WIFI_TEST_HIDE_MP_CONSOLE=0)
if sys.platform.startswith("win") and os.environ.get("WIFI_TEST_HIDE_MP_CONSOLE", "1") == "1":
    _orig_Popen = _sp.Popen

    def _patched_Popen(*args, **kwargs):
        try:
            # Add CREATE_NO_WINDOW and hide window
            flags = kwargs.get("creationflags", 0) | 0x08000000  # CREATE_NO_WINDOW
            kwargs["creationflags"] = flags
            if kwargs.get("startupinfo") is None:
                from subprocess import STARTUPINFO, STARTF_USESHOWWINDOW, SW_HIDE
                si = STARTUPINFO()
                si.dwFlags |= STARTF_USESHOWWINDOW
                si.wShowWindow = SW_HIDE
                kwargs["startupinfo"] = si
        except Exception as e:
            logging.debug("mp-console patch noop: %s", e)
        return _orig_Popen(*args, **kwargs)

    _sp.Popen = _patched_Popen
    logging.debug("Installed mp-console hide patch for Windows")

multiprocessing.freeze_support()

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    try:
        app = QApplication(sys.argv)
        setTheme(Theme.DARK)
        # font = QFont("Verdana", 22)
        # QGuiApplication.setFont(font)
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    finally:
        cleanup_temp_dir()
    # Example to run tests (kept commented for reference):
    # import datetime
    # import random
    # import os
    # timestamp = datetime.datetime.now().strftime("%Y.%m.%d_%H.%M.%S")
    # report_dir = os.path.join('report', timestamp)
    # testcase = "src/test/performance/test_wifi_peak_throughtput.py"
    # pytest.main(['-v','-s',testcase,f"--resultpath={report_dir}"])
