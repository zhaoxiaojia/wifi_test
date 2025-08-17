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
)
import sip
from qfluentwidgets import FluentIcon, FluentWindow, NavigationItemPosition
from src.ui.windows_case_config import CaseConfigPage
from src.ui.rvr_wifi_config import RvrWifiConfigPage
from src.ui.run import RunPage
from qfluentwidgets import setTheme, Theme
from PyQt5.QtGui import QGuiApplication,QFont
from PyQt5.QtCore import QCoreApplication, QPropertyAnimation, QEasingCurve
from src.util.constants import Paths
from src.util.constants import Paths, cleanup_temp_dir

# 确保工作目录为可执行文件所在目录
os.chdir(Paths.BASE_DIR)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def log_exception(exc_type, exc_value, exc_tb):
    logging.error("".join(traceback.format_exception(exc_type, exc_value, exc_tb)))


class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FAE-QA  Wi-Fi Test Tool")
        screen = QGuiApplication.primaryScreen().availableGeometry()
        width = int(screen.width() * 0.8)
        height = int(screen.height() * 0.8)
        self.resize(width, height)
        self.setMinimumSize(width, height)
        self.center_window()
        self.show()

        # 页面实例化
        self.case_config_page = CaseConfigPage(self.on_run)
        self.rvr_wifi_config_page = RvrWifiConfigPage(self.case_config_page)
        self.run_page = None  # 运行窗口动态加载
        self._run_nav_button = None  # 记录 RunPage 的导航按钮
        self._nav_button_clicked_log_slot = None

        # 添加侧边导航（页面，图标，标题，描述）
        self.addSubInterface(
            self.case_config_page, FluentIcon.SETTING, "Config Setup", "Case Config"
        )
        # 初始不展示 RVR Wi-Fi 配置页
        # 可加更多页面，比如“历史记录”“关于”等

        # FluentWindow自带自定义颜色与主题
        setTheme(Theme.DARK)  #
        # self.setMicaEffectEnabled(True)  # Win11下生效毛玻璃

    def show_rvr_wifi_config(self):
        """在导航栏中显示 RVR Wi-Fi 配置页"""
        nav = getattr(self, "navigationInterface", None)
        nav_items = []
        if nav:
            nav_items = [getattr(btn, "text", lambda: "")() for btn in nav.findChildren(QAbstractButton)]
        print("show_rvr_wifi_config start: page id=", id(self.rvr_wifi_config_page), "nav items=", nav_items)
        # 页面可能已被删除，需重新实例化
        if self.rvr_wifi_config_page is None or sip.isdeleted(self.rvr_wifi_config_page):
            self.rvr_wifi_config_page = RvrWifiConfigPage(self.case_config_page)
        if hasattr(self.rvr_wifi_config_page, "reload_csv"):
            self.rvr_wifi_config_page.reload_csv()
        if self.stackedWidget.indexOf(self.rvr_wifi_config_page) == -1:
            self._add_interface(
                self.rvr_wifi_config_page,
                FluentIcon.WIFI,
                "RVR Scenario Config",
                "RVR Wi-Fi Config",
            )

    def hide_rvr_wifi_config(self):
        """从导航栏移除 RVR Wi-Fi 配置页"""
        print(
            "hide_rvr_wifi_config start: page=",
            self.rvr_wifi_config_page,
            "current=",
            self.stackedWidget.currentWidget(),
        )
        if self.rvr_wifi_config_page and not sip.isdeleted(self.rvr_wifi_config_page):
            # 切换到 CaseConfigPage，避免删除正在显示的页面
            self.setCurrentIndex(self.case_config_page)
            QCoreApplication.processEvents()
            self._remove_interface(self.rvr_wifi_config_page)
        nav = getattr(self, "navigationInterface", None)
        nav_count = len(nav.findChildren(QAbstractButton)) if nav else 0
        print("hide_rvr_wifi_config after remove: nav count=", nav_count)
        self.rvr_wifi_config_page = None
        print("hide_rvr_wifi_config end: page=", self.rvr_wifi_config_page)

    def removeSubInterface(self, page):
        """Remove the given page from the navigation if possible."""
        if hasattr(self, "navigationInterface"):
            for name in ("removeSubInterface", "removeInterface", "removeItem"):
                func = getattr(self.navigationInterface, name, None)
                if callable(func):
                    try:
                        func(page)
                        return
                    except Exception:
                        pass
        # Fallback: detach widget
        if hasattr(page, "setParent"):
            page.setParent(None)

    def _add_interface(self, *args, **kwargs):
        widget = args[0] if args else kwargs.get("widget")
        print("_add_interface: adding", widget)
        self.addSubInterface(*args, **kwargs)
        nav = getattr(self, "navigationInterface", None)
        nav_count = len(nav.findChildren(QAbstractButton)) if nav else 0
        stack_count = self.stackedWidget.count()
        print(
            "_add_interface: nav count=", nav_count, "stack count=", stack_count
        )

    def _remove_interface(self, widget):
        """移除堆叠窗口和导航项中的页面"""
        if not widget or sip.isdeleted(widget):
            return

        print(
            "_remove_interface start: widget=",
            widget,
            "current=",
            self.stackedWidget.currentWidget(),
        )
        nav = getattr(self, "navigationInterface", None)

        buttons = []
        if nav:
            buttons = [
                btn
                for btn in nav.findChildren(QAbstractButton)
                if any(
                    getattr(btn, attr, None) is widget
                    for attr in ("widget", "page", "targetWidget", "contentWidget")
                )
            ]
        for btn in buttons:
            with suppress(Exception):
                btn.clicked.disconnect()
                logging.debug(
                    "Disconnected nav button clicked id=%s for widget id=%s",
                    id(btn),
                    id(widget),
                )

        with suppress(Exception):
            logging.info(
                "Removing from navigationInterface id=%s", id(widget) if widget else None
            )
            self.removeSubInterface(widget)
            logging.info(
                "Removed from navigationInterface id=%s", id(widget) if widget else None
            )

        if nav:
            leftover = [
                btn
                for btn in nav.findChildren(QAbstractButton)
                if any(
                    getattr(btn, attr, None) is widget
                    for attr in ("widget", "page", "targetWidget", "contentWidget")
                )
            ]
            assert not leftover, "Navigation button not fully removed"

        for i in reversed(range(self.stackedWidget.count())):
            w = self.stackedWidget.widget(i)
            if w is widget or w.__class__ == widget.__class__:
                self.stackedWidget.removeWidget(w)
                w.setParent(None)
                w.deleteLater()
        QCoreApplication.processEvents()
        idx = self.stackedWidget.indexOf(widget)
        assert idx == -1, "Widget still exists in stackedWidget"
        nav_after = len(nav.findChildren(QAbstractButton)) if nav else 0
        print(
            "_remove_interface end: nav count=",
            nav_after,
            "stack count=",
            self.stackedWidget.count(),
            "rvr_wifi_config_page=",
            self.rvr_wifi_config_page,
        )
        logging.info("_remove_interface end id=%s index=%s", id(widget), idx)

    def clear_run_page(self):
        if self.run_page and not sip.isdeleted(self.run_page):

            with suppress(Exception):
                self.run_page.cleanup()
            if self._run_nav_button and self._nav_button_clicked_log_slot:
                with suppress(Exception):
                    self._run_nav_button.clicked.disconnect(self._nav_button_clicked_log_slot)
                    logging.info(
                        "Disconnected nav button clicked for RunPage id=%s",
                        id(self.run_page),
                    )
            self._remove_interface(self.run_page)
        self.run_page = None
        if self._run_nav_button:
            with suppress(Exception):
                self._run_nav_button.clicked.disconnect()
            nav = getattr(self, "navigationInterface", None)
            if nav:
                with suppress(Exception):
                    for name in ("removeWidget", "removeItem", "removeButton"):
                        func = getattr(nav, name, None)
                        if callable(func):
                            try:
                                func(self._run_nav_button)
                                break
                            except Exception:
                                pass
            self._run_nav_button.setParent(None)
            self._run_nav_button.deleteLater()
            self._run_nav_button = None
        logging.info("RunPage cleared")


    def _set_nav_buttons_enabled(self, enabled: bool):
        """启用或禁用除 RunPage 外的导航按钮"""
        nav = getattr(self, "navigationInterface", None)
        if not nav:
            return
        buttons = nav.findChildren(QAbstractButton)
        for btn in buttons:
            if btn is self._run_nav_button:
                continue
            btn.setEnabled(enabled)
            btn.setStyleSheet(
                "color: gray; font-family: Verdana;" if not enabled else "font-family: Verdana;"
            )

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
        stack_idx = self.stackedWidget.indexOf(self.run_page) if self.run_page else None
        logging.info(
            "on_run start id=%s isdeleted=%s index=%s",
            id(self.run_page) if self.run_page else None,
            sip.isdeleted(self.run_page) if self.run_page else None,
            stack_idx,
        )
        self.clear_run_page()
        # 传递主窗口自身作为RunPage的父窗口
        self.run_page = RunPage(
            case_path,
            display_case_path,
            config,
            parent=self,
        )
        # 确保添加到导航栏和堆叠窗口
        logging.info("Adding RunPage to navigationInterface id=%s", id(self.run_page))
        self.addSubInterface(
            self.run_page,
            FluentIcon.PLAY,
            "Test",
            position=NavigationItemPosition.BOTTOM
        )
        buttons = self.navigationInterface.findChildren(QAbstractButton)
        self._run_nav_button = buttons[-1] if buttons else None

        self._set_nav_buttons_enabled(False)
        # 强制刷新堆叠窗口并切换（移除QTimer，直接同步切换）
        if self.stackedWidget.indexOf(self.run_page) == -1:
            self.stackedWidget.addWidget(self.run_page)
        # 直接切换，不使用延迟
        if self.run_page:  # 额外检查对象是否有效
            self.switchTo(self.run_page)
        # 统一通过 run_case 启动测试
        self.run_page.run_case()
        runner = getattr(self.run_page, "runner", None)
        if runner:
            runner.finished.connect(lambda: self._set_nav_buttons_enabled(True))
        logging.info("Switched to RunPage: %s", self.run_page)
        stack_idx = self.stackedWidget.indexOf(self.run_page) if self.run_page else None
        logging.info(
            "on_run end id=%s isdeleted=%s index=%s",
            id(self.run_page) if self.run_page else None,
            sip.isdeleted(self.run_page) if self.run_page else None,
            stack_idx,
        )

    def show_case_config(self):
        self.setCurrentIndex(self.case_config_page)
        logging.info("Switched to CaseConfigPage")

    def stop_run_and_show_case_config(self):
        self.setCurrentIndex(self.case_config_page)
        QCoreApplication.processEvents()  # 强制事件刷新
        self._set_nav_buttons_enabled(True)
        logging.info("Switched to CaseConfigPage")


sys.excepthook = log_exception
import multiprocessing

multiprocessing.freeze_support()
if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        QGuiApplication.setFont(QFont("Verdana"))
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
