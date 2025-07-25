# !/usr/bin/env python
# -*-coding:utf-8 -*-


import json
import logging
import os
import shutil
import subprocess
import sys
import time

from PyQt5.QtWidgets import QApplication, QStackedWidget
from qfluentwidgets import FluentIcon, FluentWindow, NavigationItemPosition
from ui.windows_case_config import CaseConfigPage
from ui.run import RunPage
import pytest
from qfluentwidgets import setTheme, Theme
from PyQt5.QtGui import QGuiApplication

class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FAE-QA  Wi-Fi Test Tool")
        self.resize(1200, 1300)
        self.setMinimumSize(1200, 1300)
        self.center_window()

        # 页面实例化
        self.case_config_page = CaseConfigPage(self.on_run)
        self.run_page = None  # 运行窗口动态加载

        # 添加侧边导航（页面，图标，标题，描述）
        self.addSubInterface(
            self.case_config_page, FluentIcon.SETTING, "用例配置", "Case Config"
        )
        # 可加更多页面，比如“历史记录”“关于”等

        # FluentWindow自带自定义颜色与主题
        setTheme(Theme.LIGHT)  # 或 Theme.LIGHT
        # self.setMicaEffectEnabled(True)  # Win11下生效毛玻璃

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

    def clear_run_page(self):
        if self.run_page:
            try:
                self.removeSubInterface(self.run_page)
            except Exception as e:
                print("removeSubInterface failed:", e)
            # 千万不要手动 setParent(None) 或 deleteLater()
            self.run_page = None

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

    def setCurrentIndex(self, page_widget):
        # print("setCurrentIndex dir:", dir(self))
        try:
            self.stackedWidget.setCurrentWidget(page_widget)
            print(f"FluentWindow.setCurrentWidget({page_widget}) success")
        except Exception as e:
            print(f"FluentWindow.setCurrentWidget error: {e}")

    def on_run(self, case_path, config):
        # print("on_run dir:", dir(self))
        self.clear_run_page()
        self.run_page = RunPage(case_path, config, self.show_case_config)
        self.addSubInterface(
            self.run_page,
            FluentIcon.PLAY,
            "运行",
            position=NavigationItemPosition.BOTTOM
        )
        self.setCurrentIndex(self.run_page)
        print("Switched to RunPage:", self.run_page)

    def show_case_config(self):
        # print("show_case_config dir:", dir(self))
        self.clear_run_page()
        self.setCurrentIndex(self.case_config_page)
        print("Switched to CaseConfigPage")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
