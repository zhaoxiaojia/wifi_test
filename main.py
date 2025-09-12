# !/usr/bin/env python
# -*-coding:utf-8 -*-

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
from qfluentwidgets import setTheme, Theme
from PyQt5.QtGui import QGuiApplication, QFont
from PyQt5.QtCore import (
    QCoreApplication,
    QPropertyAnimation,
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
)
from src.util.constants import Paths
from src.util.constants import Paths, cleanup_temp_dir

# 确保工作目录为可执行文件所在目录
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

        # 页面实例化
        self.case_config_page = CaseConfigPage(self.on_run)
        self.rvr_wifi_config_page = RvrWifiConfigPage(self.case_config_page)
        self.run_page = RunPage("", parent=self)
        # 确保初始运行页为空布局
        self.run_page.reset()
        # 报告页：默认置灰，等待 report_dir 创建后启用
        self.report_page = ReportPage(self)
        # 导航按钮引用
        self.case_nav_button = self.addSubInterface(
            self.case_config_page, FluentIcon.SETTING, "Config Setup", "Case Config"
        )
        self.case_nav_button.setVisible(True)
        self.case_nav_button.setEnabled(True)
        self.rvr_nav_button = self.addSubInterface(
            self.rvr_wifi_config_page,
            FluentIcon.WIFI,
            "RVR Scenario Config",
            "RVR Wi-Fi Config",
        )
        self.rvr_nav_button.setVisible(True)
        self.rvr_nav_button.setEnabled(False)
        self.run_nav_button = self.addSubInterface(
            self.run_page,
            FluentIcon.PLAY,
            "Test",
            position=NavigationItemPosition.BOTTOM,
        )
        self.run_nav_button.setVisible(True)
        # 默认启用运行页按钮，便于直接查看
        self.run_nav_button.setEnabled(True)

        # 报告页导航按钮：默认不可用
        self.report_nav_button = self.addSubInterface(
            self.report_page,
            FluentIcon.DOCUMENT,
            "Reports",
            position=NavigationItemPosition.BOTTOM,
        )
        self.report_nav_button.setVisible(True)
        self.report_nav_button.setEnabled(False)
        self.last_report_dir = None

        # 兼容旧属性
        self._run_nav_button = self.run_nav_button
        self._rvr_nav_button = self.rvr_nav_button
        self._rvr_route_key = None
        self._nav_button_clicked_log_slot = None
        self._runner_finished_slot = None
        self._rvr_visible = False

        # 可加更多页面，比如“历史记录”“关于”等
        self.setMicaEffectEnabled(True)  # Win11下生效毛玻璃

    def show_rvr_wifi_config(self):
        """在导航栏中显示 RVR Wi-Fi 配置页（幂等：已存在则只显示）"""
        # 已存在的场景：不再二次 add，只改可见性
        if self._rvr_nav_button and not sip.isdeleted(self._rvr_nav_button):
            if self.rvr_wifi_config_page is None or sip.isdeleted(self.rvr_wifi_config_page):
                self.rvr_wifi_config_page = RvrWifiConfigPage(self.case_config_page)
            # 确保页在堆叠里
            if self.stackedWidget.indexOf(self.rvr_wifi_config_page) == -1:
                self.stackedWidget.addWidget(self.rvr_wifi_config_page)
            self._rvr_nav_button.setVisible(True)
            self._rvr_visible = True
            logging.debug("show_rvr_wifi_config: reuse nav item; setVisible(True)")
            return

        # 走首次添加（保持你原有逻辑）
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

        # 可能存在上次未清理干净的 routeKey，需要在重新添加前先移除
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
        # 首次添加后，显式可见（保险）
        self._rvr_nav_button.setVisible(True)
        # 确保页在堆叠
        if self.stackedWidget.indexOf(self.rvr_wifi_config_page) == -1:
            self.stackedWidget.addWidget(self.rvr_wifi_config_page)
        self._rvr_visible = True

        # 启动滑动动画并切换到 RVR 配置页
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
        """从导航栏隐藏 RVR Wi-Fi 配置页（不删除，避免 routeKey 残留）"""
        if not self._rvr_visible:
            return
        logging.debug(
            "hide_rvr_wifi_config start: page=%s current=%s",
            self.rvr_wifi_config_page,
            self.stackedWidget.currentWidget(),
        )

        width = self.stackedWidget.width()
        page = self.rvr_wifi_config_page

        # 切回安全页，并保持当前页可见以执行滑动动画
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

        # 优先尝试各种官方接口（注意顺序，最后补上 removeWidget(page)）
        for name in ("removeSubInterface", "removeInterface", "removeItem", "removeWidget"):
            func = getattr(nav, name, None)
            if callable(func):
                try:
                    func(page)  # ← 关键：按 page 移除
                    return True
                except Exception:
                    pass

        # 兜底：暴力把同 routeKey 的部件从树上摘掉（不同版本可能不是 QAbstractButton）
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
            # ① 优先使用 FluentWindow.removeSubInterface 删除导航条目
            func = getattr(self, "removeSubInterface", None)
            if callable(func):
                removed = bool(func(page))
            # ② 退而求其次，调用 navigationInterface.removeItem
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

        # ③ 仅在确认导航项已移除后再删除 nav_button
        if nav_button and not sip.isdeleted(nav_button):
            with suppress(Exception):
                nav_button.clicked.disconnect()
            with suppress(Exception):
                nav_button.setParent(None)

        # ④ 从堆栈里移走页面（你原来就有）
        if page and not sip.isdeleted(page):
            with suppress(Exception):
                self.stackedWidget.removeWidget(page)

        QCoreApplication.processEvents()

        # ⑤ 统一清空指针
        self._rvr_nav_button = None
        self._rvr_route_key = None
        self.rvr_wifi_config_page = None

        # ⑥ 清除 FluentWindow 内部的 routeKey 映射（必须）
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

        # 1) 可用方法探测（我们关心 removeX 接口到底叫什么）
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

        # 2) 列出“看得到的可能是导航按钮的孩子”
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

        # 3) 再撒一网：找所有 QWidget 子代里“带 routeKey 属性的家伙”（有的不是 QAbstractButton）
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

        # 4) Router 栈/路由表（不同版本字段名不同，做 best-effort 打印）
        router = getattr(nav, "router", None)
        if router:
            logging.debug("router exists: %s", type(router).__name__)
            # 尝试打印常见成员
            for key in ("stackHistories", "currentKey", "history", "routeView"):
                try:
                    val = getattr(router, key, None)
                    if callable(val):
                        val = val()
                    logging.debug("  router.%s = %s", key, val)
                except Exception:
                    pass
            # 尝试打印 routes（map）
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

        # 5) StackedWidget 里到底有谁
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

        # 6) 我们自己的指针状态
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
        """保持导航按钮启用，并根据需要调整样式"""
        nav = getattr(self, "navigationInterface", None)
        if not nav:
            return
        buttons = nav.findChildren(QAbstractButton)
        for btn in buttons:
            # 运行页按钮始终保持可见
            if btn is self._run_nav_button:
                btn.setVisible(True)
            btn.setEnabled(True)
            btn.setStyleSheet("font-family: Verdana;")
    def center_window(self):
        # 获取屏幕的几何信息
        screen_geometry = QGuiApplication.primaryScreen().availableGeometry()
        # 获取窗口的几何信息
        window_geometry = self.frameGeometry()
        # 计算屏幕中心位置
        center_point = screen_geometry.center()
        # 将窗口中心移动到屏幕中心
        window_geometry.moveCenter(center_point)
        # 确保窗口顶部不会超出屏幕
        self.move(window_geometry.topLeft())

    def setCurrentIndex(self, page_widget, ssid: str | None = None, passwd: str | None = None):
        # print("setCurrentIndex dir:", dir(self))
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

            # 更新 RunPage 信息
            self.run_page.case_path = case_path
            self.run_page.display_case_path = self.run_page._calc_display_path(
                case_path, display_case_path
            )
            if hasattr(self.run_page, "case_path_label"):
                self.run_page.case_path_label.setText(self.run_page.display_case_path)
            self.run_page.config = config

            # 显示运行页
            self.run_nav_button.setVisible(True)
            self.run_nav_button.setEnabled(True)
            if self.stackedWidget.indexOf(self.run_page) == -1:
                self.stackedWidget.addWidget(self.run_page)
            self.switchTo(self.run_page)
            self.case_config_page.lock_for_running(True)
            if hasattr(self.rvr_wifi_config_page, "set_readonly"):
                self.rvr_wifi_config_page.set_readonly(True)
            # 启动测试
            self.run_page.run_case()
            runner = getattr(self.run_page, "runner", None)
            if runner:
                def _on_runner_finished():
                    self.case_config_page.lock_for_running(False)
                    if getattr(self, "rvr_wifi_config_page", None):
                        self.rvr_wifi_config_page.set_readonly(False)
                    # 保留运行页导航按钮状态，以便随时查看日志
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
            QMessageBox.critical(self, "Error", f"Unable to run ：{e}")
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
        QCoreApplication.processEvents()  # 强制事件刷新
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
                self.report_page.set_report_dir(self.last_report_dir)
            if hasattr(self, "report_nav_button") and self.report_nav_button and not sip.isdeleted(self.report_nav_button):
                self.report_nav_button.setEnabled(True)
                self.report_nav_button.setVisible(True)
        except Exception:
            pass


sys.excepthook = log_exception
import multiprocessing
import sys, os, logging, subprocess as _sp

# 仅在 Windows 生效；加环境开关，必要时可关闭（WIFI_TEST_HIDE_MP_CONSOLE=0）
if sys.platform.startswith("win") and os.environ.get("WIFI_TEST_HIDE_MP_CONSOLE", "1") == "1":
    _orig_Popen = _sp.Popen


    def _patched_Popen(*args, **kwargs):
        try:
            # 叠加 CREATE_NO_WINDOW，并隐藏窗口
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
    # import datetime
    # import random
    # import os
    # timestamp = datetime.datetime.now().strftime("%Y.%m.%d_%H.%M.%S")
    # report_dir = os.path.join('report', timestamp)
    # # testcase = "src/test/project/roku/UI/Connectivity Doctor/test_T6473243.py"
    # testcase = "src/test/performance/test_wifi_peak_throughtput.py"
    # pytest.main(['-v','-s',testcase,f"--resultpath={report_dir}"])
