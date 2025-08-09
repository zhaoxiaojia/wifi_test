# !/usr/bin/env python
# -*-coding:utf-8 -*-

import sys
import os
from pathlib import Path
import traceback
import logging

from contextlib import suppress

sys.path.insert(0, str(Path(__file__).parent))
from PyQt5.QtWidgets import QApplication
from qfluentwidgets import FluentIcon, FluentWindow, NavigationItemPosition
from src.ui.windows_case_config import CaseConfigPage
from src.ui.rvr_wifi_config import RvrWifiConfigPage
from src.ui.run import RunPage
from qfluentwidgets import setTheme, Theme
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtCore import QCoreApplication


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

        # 添加侧边导航（页面，图标，标题，描述）
        self.addSubInterface(
            self.case_config_page, FluentIcon.SETTING, "用例配置", "Case Config"
        )
        # 初始不展示 RVR Wi-Fi 配置页
        # 可加更多页面，比如“历史记录”“关于”等

        # FluentWindow自带自定义颜色与主题
        setTheme(Theme.LIGHT)  # 或 Theme.LIGHT
        # self.setMicaEffectEnabled(True)  # Win11下生效毛玻璃

    def show_rvr_wifi_config(self):
        """在导航栏中显示 RVR Wi-Fi 配置页"""
        if hasattr(self.rvr_wifi_config_page, "reload_csv"):
            self.rvr_wifi_config_page.reload_csv()
        if self.stackedWidget.indexOf(self.rvr_wifi_config_page) == -1:
            self.addSubInterface(
                self.rvr_wifi_config_page,
                FluentIcon.WIFI,
                "RVR Wi-Fi配置",
                "RVR Wi-Fi Config",
            )

    def hide_rvr_wifi_config(self):
        """从导航栏移除 RVR Wi-Fi 配置页"""
        self._remove_interface(self.rvr_wifi_config_page)

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

    def _remove_interface(self, widget):
        """移除堆叠窗口和导航项中的页面"""
        for i in reversed(range(self.stackedWidget.count())):
            w = self.stackedWidget.widget(i)
            if w is widget or w.__class__ == widget.__class__:
                self.stackedWidget.removeWidget(w)
                w.setParent(None)
                w.deleteLater()
        QCoreApplication.processEvents()
        with suppress(Exception):
            self.removeSubInterface(widget)

    def clear_run_page(self):
        if self.run_page:
            with suppress(Exception):
                self.run_page.cleanup()
            self._remove_interface(self.run_page)
            print("RunPage cleared!")

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
            self.stackedWidget.setCurrentWidget(page_widget)
            print(f"FluentWindow.setCurrentWidget({page_widget}) success")
        except Exception as e:
            print(f"FluentWindow.setCurrentWidget error: {e}")

    def on_run(self, case_path, display_case_path, config):
        self.clear_run_page()
        # 传递主窗口自身作为RunPage的父窗口
        self.run_page = RunPage(case_path, display_case_path, config, self.show_case_config, parent=self)
        # 确保添加到导航栏和堆叠窗口
        self.addSubInterface(
            self.run_page,
            FluentIcon.PLAY,
            "运行",
            position=NavigationItemPosition.BOTTOM
        )
        # 强制刷新堆叠窗口并切换（移除QTimer，直接同步切换）
        if self.stackedWidget.indexOf(self.run_page) == -1:
            self.stackedWidget.addWidget(self.run_page)
        # 直接切换，不使用延迟
        if self.run_page:  # 额外检查对象是否有效
            self.switchTo(self.run_page)
        print("Switched to RunPage:", self.run_page)

    def show_case_config(self):
        self.setCurrentIndex(self.case_config_page)
        QCoreApplication.processEvents()  # 强制事件刷新
        self.clear_run_page()
        print("Switched to CaseConfigPage")


def get_base_dir():
    """返回程序所在的基础目录（打包后是 exe 所在目录）"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)  # 打包后的路径
    else:
        return os.path.dirname(os.path.dirname(__file__))  # 开发时的项目根目录


# 关键路径定义
BASE_DIR = get_base_dir()
CONFIG_DIR = os.path.join(BASE_DIR, "config")  # 共享的 config 目录
RES_DIR = os.path.join(BASE_DIR, "res")  # 共享的 res 目录

sys.excepthook = log_exception

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
    # import datetime
    # import random
    # import os
    # timestamp = datetime.datetime.now().strftime("%Y.%m.%d_%H.%M.%S")
    # report_dir = os.path.join('report', timestamp)
    # # testcase = "src/test/project/roku/UI/Connectivity Doctor/test_T6473243.py"
    # testcase = "src/test/performance/test_wifi_peak_throughtput.py"
    # pytest.main(['-v','-s',testcase,f"--resultpath={report_dir}"])
