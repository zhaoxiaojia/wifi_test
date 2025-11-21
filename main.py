# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""Main entry point for the FAE‑QA Wi‑Fi Test Tool.

This module bootstraps the graphical user interface for the Wi‑Fi test
application.  It defines a :class:`MainWindow` class derived from
``qfluentwidgets.FluentWindow`` that orchestrates navigation between the
login page, configuration pages, test execution page and report page.  The
window is initialised with animated geometry and opacity transitions to
provide a smooth user experience.  Top‑level functions and classes
include:

* ``log_exception`` – a helper to capture and log unhandled exceptions
  raised from Qt slots.
* ``MainWindow`` – the primary application window that manages pages,
  navigation buttons and authentication state.

When run as a script, this module constructs a QApplication, instantiates
``MainWindow`` and enters the Qt event loop.
"""

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
from src.ui import SIDEBAR_PAGE_LABELS, SIDEBAR_PAGE_KEYS
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

# NOTE: The following annotations are used for module‑level variables.  They
# provide descriptive metadata alongside type information using
# ``typing.Annotated``.  Import ``Annotated`` here so that global
# assignments can be documented inline later in the file.
from typing import Annotated

# Ensure working directory equals executable directory
os.chdir(Paths.BASE_DIR)


def log_exception(exc_type, exc_value, exc_tb) -> None:
    """Write an unhandled exception to the application log.

    This function is intended to be registered via
    ``sys.excepthook`` or passed to Qt's exception handling hooks.  It
    formats the exception tuple into a single string and emits it via
    the :mod:`logging` subsystem at error level.

    Parameters
    ----------
    exc_type:
        The exception class being handled.
    exc_value:
        The exception instance.
    exc_tb:
        A traceback object describing where the exception occurred.

    Returns
    -------
    None
    """
    logging.error("".join(traceback.format_exception(exc_type, exc_value, exc_tb)))

class MainWindow(FluentWindow):
    """Main application window for the Wi‑Fi Test Tool.

    The :class:`MainWindow` class encapsulates all user‑facing UI logic.
    It manages the creation and placement of pages (login, case config,
    RVR Wi‑Fi config, run, report and about), controls navigation button
    visibility based on authentication state, and triggers animations when
    pages are shown or hidden.  Slots prefixed with ``_on_`` respond to
    signals emitted from child widgets, while methods beginning with
    ``_`` implement reusable UI behaviours such as enabling/disabling
    navigation buttons or adding/removing interfaces from the navigation
    stack.
    """

    def __init__(self) -> None:
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

        self.rvr_wifi_config_page = RvrWifiConfigPage()
        # Note: legacy `case_config_page` attribute removed in favor of
        # `rvr_wifi_config_page`. Callers should use the new attribute.
        self.run_page = RunPage("", parent=self)
        # Ensure run page starts empty
        self.run_page.reset()
        # Report page (disabled until report_dir created)
        self.report_page = ReportPage(self)

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
            self.rvr_wifi_config_page,
            FluentIcon.SETTING,
        )
        self.case_nav_button.setVisible(True)

        # RVR Wi‑Fi / scenario configuration
        self.rvr_nav_button = self._create_sidebar_button(
            "case",
            self.rvr_wifi_config_page,
            FluentIcon.WIFI,
        )
        self.rvr_nav_button.setVisible(True)

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
            self.report_page,
            FluentIcon.DOCUMENT,
            position=NavigationItemPosition.BOTTOM,
        )
        self.report_nav_button.setVisible(True)

        self.last_report_dir = None

        self.about_page = AboutPage(self)
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
            "config": self.rvr_wifi_config_page,
            "case": self.rvr_wifi_config_page,
            "run": self.run_page,
            "report": self.report_page,
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
            self.sidebar_nav_buttons["config"]: True,
            self.sidebar_nav_buttons["case"]: False,
            self.sidebar_nav_buttons["run"]: True,
            self.sidebar_nav_buttons["report"]: False,
            self.sidebar_nav_buttons["about"]: True,
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

    def _create_sidebar_button(
        self,
        key: str,
        page,
        icon,
        *,
        position: NavigationItemPosition | None = None,
    ):
        """Create a navigation button based on a logical sidebar key.

        The ``key`` must be one of ``SIDEBAR_PAGE_KEYS`` and is mapped to a
        human‑readable label via :data:`SIDEBAR_PAGE_LABELS`.  This keeps
        variable names (all lower‑case with underscores) decoupled from the
        user‑visible text shown in the sidebar.
        """
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
        """Enable or disable multiple navigation buttons in one call.

        Iterate through a mapping of navigation buttons to boolean flags and
        call ``setEnabled`` on each button that still exists.  This helper
        centralises the logic for toggling entire groups of navigation
        controls when a user signs in or out.

        Parameters
        ----------
        states:
            A mapping whose keys are navigation button instances and whose
            values indicate whether the button should be enabled (truthy) or
            disabled (falsy).

        Returns
        -------
        None
        """
        for btn, enabled in states.items():
            if btn and not sip.isdeleted(btn):
                btn.setEnabled(bool(enabled))

    # ------------------------------------------------------------------
    def _on_login_result(self, success: bool, message: str, payload: dict) -> None:
        """Handle completion of a login attempt.

        This slot is connected to the ``loginResult`` signal from
        :class:`~src.ui.company_login.CompanyLoginPage`.  If authentication
        succeeds, the user's account details are recorded and the
        navigation buttons appropriate for a logged‑in user are enabled,
        after which the interface switches to the case configuration page.
        On failure, the active account is cleared and the interface returns
        to the login page.

        Parameters
        ----------
        success:
            Indicates whether the sign‑in attempt succeeded.
        message:
            A human‑readable message describing the outcome of the login.
        payload:
            A dictionary containing account metadata returned on success.

        Returns
        -------
        None
        """
        logging.info(
            "MainWindow: sign‑in finished success=%s message=%s payload=%s",
            success,
            message,
            payload,
        )
        if success:
            self._active_account = dict(payload)
            self._apply_nav_enabled(self._nav_logged_in_states)
            self.setCurrentIndex(self.rvr_wifi_config_page)
        else:
            self._active_account = None
            self._apply_nav_enabled(self._nav_logged_out_states)
            self.setCurrentIndex(self.login_page)

    def _on_logout_requested(self) -> None:
        """Respond to a user‑initiated sign‑out.

        This slot is connected to the ``logoutRequested`` signal from
        :class:`CompanyLoginPage`.  It resets navigation to the login page,
        disables buttons that require authentication and clears the
        ``_active_account`` state.  A status message is displayed on the
        login page to inform the user of the sign‑out.

        Returns
        -------
        None
        """
        logging.info("MainWindow: user requested sign‑out (active_account=%s)", self._active_account)
        self._apply_nav_enabled(self._nav_logged_out_states)
        self.setCurrentIndex(self.login_page)
        self._active_account = None
        self.login_page.set_status_message("Signed out. Please sign in again.", state="info")

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
        """Slide the RVR Wi‑Fi configuration page out of view and hide its navigation button.

        When the user deselects the RVR configuration, this method gently
        animates the page off the screen to the right and toggles the
        corresponding navigation button's visibility.  Unlike
        :meth:`_remove_interface`, the page instance and route key remain
        registered with the navigation controller so that it can be shown
        again later without re‑instantiating or re‑registering the page.
        If the page has already been hidden or does not exist, the call
        performs no action.

        Returns
        -------
        None
        """
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
        page = getattr(self, "rvr_wifi_config_page", None)
        if page is None or sip.isdeleted(page):
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
        nav = getattr(self, "navigationInterface", None)
        nav_items = []
        if nav:
            nav_items = [getattr(btn, "text", lambda: "")() for btn in nav.findChildren(QAbstractButton)]
        logging.debug(
            "show_rvr_wifi_config start: page id=%s nav items=%s",
            id(page),
            nav_items,
        )
        route_key = self._rvr_route_key or getattr(page, "objectName", lambda: None)()
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
        for attr in ("_interfaces", "_routes"):
            mapping = getattr(self, attr, None)
            if not mapping:
                continue
            try:
                if mapping.pop(route_key, None) is not None:
                    logging.debug("show_rvr_wifi_config: removed stale %s[%s]", attr, route_key)
            except Exception as exc:
                logging.warning(
                    "show_rvr_wifi_config: failed to remove %s[%s]: %s",
                    attr,
                    route_key,
                    exc,
                )

    def _detach_sub_interface(self, page):
        """Disconnect a page from the Fluent navigation system.

        QFluentWidgets has evolved over time and the public API for
        removing pages varies between versions.  This helper performs a
        best‑effort removal by probing for several removal methods on
        the current navigation interface (``removeSubInterface``,
        ``removeInterface``, ``removeItem``, ``removeWidget``) and
        invoking the first one that succeeds.  Should those APIs be
        unavailable, the function falls back to manually scanning the
        navigation widget for any child widget whose ``routeKey``
        matches the given page, disconnecting and deleting it if found.

        Parameters
        ----------
        page:
            The widget instance to detach from the navigation hierarchy.

        Returns
        -------
        bool
            ``True`` if a removal operation was performed, ``False`` if no
            suitable API was found or no matching widget existed.
        """
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
        """Wrapper around :meth:`addSubInterface` that logs diagnostic information.

        This helper centralises the checks and diagnostics around
        dynamically inserting new pages into the navigation stack.  It
        validates that the first positional argument (or the ``interface``/``widget``
        keyword argument) is a live widget before attempting to add it.
        After calling :meth:`addSubInterface`, it logs the number of
        navigation buttons and stacked widgets for troubleshooting.
        Should ``addSubInterface`` return ``None``, a warning is emitted
        because this typically signals that a duplicate route key has been
        supplied or that the framework rejected the addition.

        Parameters
        ----------
        *args:
            Positional arguments forwarded verbatim to
            :meth:`addSubInterface`.  The first positional argument is
            expected to be the widget to add.
        **kwargs:
            Keyword arguments forwarded verbatim to
            :meth:`addSubInterface`.  The ``interface`` or ``widget`` key
            may be used to specify the page to add.

        Returns
        -------
        QAbstractButton | None
            The navigation button created by the framework, or ``None`` if
            the framework refused to create one.
        """
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
        """Remove a page and its navigation entry from the UI.

        This method orchestrates the removal of a previously added page from
        both the navigation interface and the stacked widget.  It first
        attempts to invoke the appropriate removal method exposed by the
        framework (preferring :meth:`removeSubInterface` on the
        :class:`FluentWindow` instance, then falling back to
        ``navigationInterface.removeItem``).  If the removal fails an
        exception is raised.  After successful removal, associated
        navigation buttons are disconnected and dereferenced, the page is
        detached from the stacked widget, and internal state pointers
        tracking the RVR configuration page are reset.  Any lingering
        route key entries in the framework's internal dictionaries are
        also cleaned up to avoid collisions on subsequent adds.

        Parameters
        ----------
        page:
            The widget instance representing the page to remove.
        route_key:
            Optional explicit route key associated with the page; if not
            provided, it is inferred from ``nav_button`` or the
            ``objectName`` of ``page``.
        nav_button:
            Optional navigation button tied to the page; if provided it
            will be disconnected and dereferenced after removal.

        Returns
        -------
        None

        Raises
        ------
        RuntimeError
            If the removal via the underlying framework fails.
        """
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
        self._cleanup_route(rk)

    def _walk_nav_state(self) -> dict[str, object]:
        """Collect diagnostic navigation data for logging."""
        nav = getattr(self, "navigationInterface", None)
        data: dict[str, object] = {
            "nav": nav,
            "nav_methods": [],
            "fw_methods": [],
            "buttons": [],
            "stack": [],
            "routes": {},
            "interfaces": {},
        }
        if not nav:
            return data

        def _has(obj, name):
            try:
                return callable(getattr(obj, name, None))
            except Exception:
                return False

        data["nav_methods"] = [
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
        data["fw_methods"] = [n for n in ("removeSubInterface", "addSubInterface") if _has(self, n)]
        try:
            data["buttons"] = nav.findChildren(QAbstractButton)
        except Exception:
            data["buttons"] = []
        stack_widgets = []
        try:
            count = self.stackedWidget.count()
            for i in range(count):
                stack_widgets.append(self.stackedWidget.widget(i))
        except Exception:
            stack_widgets = []
        data["stack"] = stack_widgets
        if hasattr(self, "_routes"):
            data["routes"] = dict(getattr(self, "_routes", {}))
        if hasattr(self, "_interfaces"):
            data["interfaces"] = dict(getattr(self, "_interfaces", {}))
        return data

    # ==== DEBUG: deep nav/router/stack introspection ====
    def _debug_nav_state(self, tag: str):
        """Dump diagnostic information about the navigation stack.

        This utility prints a tree of information to the logger at
        DEBUG level.  It enumerates available removal methods on the
        navigation controller, lists each navigation button along with
        its class and properties, shows any QWidget with a ``routeKey``
        property, inspects router internals such as history and route
        tables, and prints out all widgets present in the stacked
        container.  Finally it logs the internal state variables
        controlling the RVR Wi‑Fi page.  Use this to troubleshoot
        navigation issues or understand the internal state of QFluent
        components at runtime.

        Parameters
        ----------
        tag:
            A short label included in the log output to distinguish
            multiple debug dumps.

        Returns
        -------
        None
        """
        info = self._walk_nav_state()
        logging.debug("\n===== DEBUG NAV STATE [%s] =====", tag)
        nav = info.get("nav")
        if not nav:
            logging.debug("navigationInterface = None")
            return

        logging.debug("nav methods: %s", info.get("nav_methods"))
        logging.debug("FluentWindow methods: %s", info.get("fw_methods"))

        # 2) List children likely to be nav buttons
        btns = info.get("buttons", []) or []
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
        """Reset the RunPage and disconnect any associated event hooks.

        When tests are completed or aborted, the RunPage may retain
        connections to long‑running worker threads or button click
        handlers.  This method cleans up those references: it
        disconnects the runner's ``finished`` signal, disconnects the
        navigation button click logger slot, and invokes the page's
        :meth:`RunPage.reset` method to clear any state.  It then
        processes pending Qt events and re‑enables the ``run_btn`` on the
        case configuration page so that the user can start a new run.

        Returns
        -------
        None
        """
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
        if hasattr(self.rvr_wifi_config_page, "run_btn"):
            self.rvr_wifi_config_page.run_btn.setEnabled(True)

    def _set_nav_buttons_enabled(self, enabled: bool):
        """Enable all navigation buttons and optionally adjust their appearance.

        Regardless of the ``enabled`` parameter, this method currently
        forces every navigation button to be both visible and enabled
        because the underlying FluentWidgets framework may disable
        buttons when switching pages.  It also sets a specific font
        family on the buttons to maintain visual consistency with the
        Verdana font used elsewhere in the application.  Future
        enhancements could respect the ``enabled`` flag and apply
        customised styling based on state.

        Parameters
        ----------
        enabled:
            Placeholder parameter reserved for future use when dynamic
            enabling/disabling of buttons is implemented.  Currently
            ignored.

        Returns
        -------
        None
        """
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
        """Center this window on the primary monitor.

        Computes the geometry of the available desktop workspace and
        translates the window's frame geometry so that its centre aligns
        with the centre of the screen.  This ensures that the main
        application window appears in the middle of the screen when
        initially shown or when explicitly invoked.

        Returns
        -------
        None
        """
        # Center window on the primary screen
        screen_geometry = QGuiApplication.primaryScreen().availableGeometry()
        window_geometry = self.frameGeometry()
        center_point = screen_geometry.center()
        window_geometry.moveCenter(center_point)
        self.move(window_geometry.topLeft())

    def setCurrentIndex(self, page_widget, ssid: str | None = None, passwd: str | None = None):
        """Switch the active page with a cross‑fade animation.

        This override of :meth:`FluentWindow.setCurrentIndex` changes the
        currently displayed widget in the stacked container while
        performing a fade‑out on the outgoing widget and a fade‑in on
        the incoming widget.  When the RVR Wi‑Fi configuration page is
        the target and Wi‑Fi credentials are supplied, those credentials
        are passed to the page before it becomes visible.  Errors
        encountered during the transition are logged but not re‑raised.

        Parameters
        ----------
        page_widget:
            The widget instance to display.
        ssid:
            Optional Wi‑Fi SSID to pre‑populate in the RVR Wi‑Fi config
            page when it becomes active.
        passwd:
            Optional Wi‑Fi password to pre‑populate in the RVR Wi‑Fi
            config page when it becomes active.

        Returns
        -------
        None
        """
        try:
            if page_widget is self.rvr_wifi_config_page and (ssid or passwd):
                if hasattr(self.rvr_wifi_config_page, "set_router_credentials"):
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

    def on_run(self, case_path, display_case_path, config):
        """Kick off execution of a test case and display the run page.

        When the user clicks the "Run" button on the case configuration
        page, this slot locks down configuration inputs, copies the
        selected case path and settings into the run page, and adds the
        run page to the stacked widget if necessary.  It then invokes
        :meth:`RunPage.run_case` to start the test run.  A callback is
        connected to the runner's ``finished`` signal to unlock the UI
        when execution completes and to re‑enable the RVR navigation
        button if the case is a performance test.

        Parameters
        ----------
        case_path:
            Filesystem path to the Python test module to execute.
        display_case_path:
            User‑friendly representation of ``case_path`` (e.g.,
            truncated base name) for display in the run page.
        config:
            Arbitrary configuration object passed down to the run page
            and ultimately to the test runner.

        Returns
        -------
        None
        """
        if hasattr(self.rvr_wifi_config_page, "config_ctl"):
            self.rvr_wifi_config_page.config_ctl.lock_for_running(True)
        if getattr(self, "rvr_wifi_config_page", None):
            self.rvr_wifi_config_page.set_readonly(True)
        try:
            self._trigger_run(case_path, display_case_path, config)
        except Exception as e:
            logging.error("on_run failed: %s", e, exc_info=True)
            QMessageBox.critical(self, "Error", f"Unable to run: {e}")
            if hasattr(self.rvr_wifi_config_page, "config_ctl"):
                self.rvr_wifi_config_page.config_ctl.lock_for_running(False)
            if getattr(self, "rvr_wifi_config_page", None):
                self.rvr_wifi_config_page.set_readonly(False)
            if self._run_nav_button and not sip.isdeleted(self._run_nav_button):
                self._run_nav_button.setEnabled(False)
                self._run_nav_button.setVisible(False)

    def _trigger_run(self, case_path, display_case_path, config) -> None:
        """Populate the RunPage state and start executing the selected case."""
        if self.run_page:
            with suppress(Exception):
                self.run_page.reset()
        self.run_page.case_path = case_path
        self.run_page.display_case_path = self.run_page._calc_display_path(
            case_path, display_case_path
        )
        if hasattr(self.run_page, "case_path_label"):
            self.run_page.case_path_label.setText(self.run_page.display_case_path)
        self.run_page.config = config

        self.run_nav_button.setVisible(True)
        self.run_nav_button.setEnabled(True)
        if self.stackedWidget.indexOf(self.run_page) == -1:
            self.stackedWidget.addWidget(self.run_page)
        self.switchTo(self.run_page)
        if hasattr(self.rvr_wifi_config_page, "set_readonly"):
            self.rvr_wifi_config_page.set_readonly(True)

        self.run_page.run_case()
        runner = getattr(self.run_page, "runner", None)
        if runner:

            def _on_runner_finished():
                if hasattr(self.rvr_wifi_config_page, "config_ctl"):
                    self.rvr_wifi_config_page.config_ctl.lock_for_running(False)
                if getattr(self, "rvr_wifi_config_page", None):
                    self.rvr_wifi_config_page.set_readonly(False)
                if self.rvr_nav_button and not sip.isdeleted(self.rvr_nav_button):
                    case_path = getattr(self.run_page, "case_path", "")
                    config_ctl = getattr(self.rvr_wifi_config_page, "config_ctl", None)
                    is_perf = (
                        config_ctl.is_performance_case(case_path)
                        if config_ctl is not None
                        else False
                    )
                    self.rvr_nav_button.setEnabled(bool(is_perf))

            self._runner_finished_slot = _on_runner_finished
            runner.finished.connect(self._runner_finished_slot)

        logging.info("Switched to RunPage: %s", self.run_page)

    def show_case_config(self):
        """Switch to the case configuration page.

        This convenience method simply calls :meth:`setCurrentIndex` with
        the case configuration page and logs the transition.  Exposed
        separately so that other components can request a return to the
        configuration page without needing access to the underlying
        stacked widget.

        Returns
        -------
        None
        """
        self.setCurrentIndex(self.rvr_wifi_config_page)

    def stop_run_and_show_case_config(self):
        """Abort a running test and return to the case configuration page.

        This method is called when the user requests to stop an ongoing
        test run.  It switches the stacked widget back to the case
        configuration page, processes any pending Qt events, unlocks
        previously disabled UI elements (including the RVR Wi‑Fi config
        page) and disables the run navigation button.  It also re‑enables
        the RVR navigation button only if the most recent case was a
        performance test, ensuring that the user can still access RVR
        logs after cancelling such a run.

        Returns
        -------
        None
        """
        self.setCurrentIndex(self.rvr_wifi_config_page)
        QCoreApplication.processEvents()
        if hasattr(self.rvr_wifi_config_page, "config_ctl"):
            self.rvr_wifi_config_page.config_ctl.lock_for_running(False)
        if getattr(self, "rvr_wifi_config_page", None):
            self.rvr_wifi_config_page.set_readonly(False)
        if self._run_nav_button and not sip.isdeleted(self._run_nav_button):
            self._run_nav_button.setEnabled(False)
        if hasattr(self, "rvr_wifi_config_page", "set_readonly"):
            self.rvr_wifi_config_page.set_readonly(False)
        if hasattr(self.rvr_wifi_config_page, "set_readonly"):
            self.rvr_wifi_config_page.set_readonly(False)
        if self.rvr_nav_button and not sip.isdeleted(self.rvr_nav_button):
            case_path = getattr(self.run_page, "case_path", "")
            config_ctl = getattr(self.rvr_wifi_config_page, "config_ctl", None)
            is_perf = (
                config_ctl.is_performance_case(case_path)
                if config_ctl is not None
                else False
            )
            self.rvr_nav_button.setEnabled(bool(is_perf))

    # --- Reports ---
    def enable_report_page(self, report_dir: str) -> None:
        """Activate the report viewing page after test execution.

        When the test runner finishes and creates a report directory,
        this method updates :attr:`last_report_dir` with the absolute
        path of that directory, populates the report page with context
        about the case that just ran, and enables the report navigation
        button.  Without invoking this function the reports page
        remains disabled and the user cannot review test results from
        within the application.

        Parameters
        ----------
        report_dir:
            Filesystem path pointing to the newly created report directory.

        Returns
        -------
        None
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
    # Preserve original subprocess.Popen so that it can be restored or
    # called from within the wrapper.  Annotate with ``Annotated`` to
    # describe its purpose.
    _orig_Popen: Annotated[callable, "Reference to the unmodified subprocess.Popen function"] = _sp.Popen

    def _patched_Popen(*args, **kwargs) -> _sp.Popen:
        """Launch a subprocess on Windows while suppressing console windows.

        On Windows platforms, Python's default :class:`subprocess.Popen`
        pops up a console window for each child process when run from a
        GUI application.  This wrapper modifies the ``creationflags`` and
        ``startupinfo`` arguments to create the process with no window
        displayed.  It delegates all other arguments to the original
        :func:`subprocess.Popen` preserved in
        :data:`_orig_Popen`.  If any exception is raised while
        adjusting the startup parameters, the wrapper logs the issue and
        proceeds to call :data:`_orig_Popen` without modification.

        Parameters
        ----------
        *args, **kwargs:
            Positional and keyword arguments accepted by
            :class:`subprocess.Popen`.  ``creationflags`` and
            ``startupinfo`` will be overridden to hide the console
            window.

        Returns
        -------
        subprocess.Popen
            The newly created Popen instance.
        """
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

    # Overwrite subprocess.Popen so that all subsequent calls use the patched version.
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
