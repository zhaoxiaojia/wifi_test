# !/usr/bin/env python
# -*-coding:utf-8 -*-

import sys
import os
from pathlib import Path
import traceback
import logging

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from PyQt5.QtWidgets import QApplication
from qfluentwidgets import FluentIcon, FluentWindow, NavigationItemPosition
from src.ui.windows_case_config import CaseConfigPage
from src.ui.run import RunPage
from qfluentwidgets import setTheme, Theme
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtCore import QTimer, QCoreApplication


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
            # 强制彻底移除所有 RunPage（防止 Qt 内部引用悬挂）
            for i in reversed(range(self.stackedWidget.count())):
                widget = self.stackedWidget.widget(i)
                # 防止多余实例
                if widget is self.run_page or widget.__class__.__name__ == "RunPage":
                    print(f"remove RunPage from stackedWidget: {widget}")
                    self.stackedWidget.removeWidget(widget)
                    widget.setParent(None)
                    widget.deleteLater()
            QCoreApplication.processEvents()  # 保证deleteLater执行

            # 从导航栏彻底移除
            try:
                self.removeSubInterface(self.run_page)
            except Exception as e:
                print(f"removeSubInterface error: {e}")

            # 断开所有信号和线程
            if hasattr(self.run_page, "runner") and self.run_page.runner:
                runner = self.run_page.runner
                try:
                    runner.log_signal.disconnect(self.run_page._append_log)
                except Exception:
                    pass
                try:
                    runner.progress_signal.disconnect(self.run_page.update_progress)
                except Exception:
                    pass
                try:
                    runner.finished.disconnect()
                except Exception:
                    pass
                try:
                    if runner.isRunning():
                        runner.stop()
                        if not runner.wait(3000):
                            runner.quit()
                            if not runner.wait(1000):
                                print("runner thread did not finish in time")
                except Exception:
                    pass

            self.run_page = None
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

    def setCurrentIndex(self, page_widget):
        # print("setCurrentIndex dir:", dir(self))
        try:
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
RES_DIR = os.path.join(BASE_DIR, "res")       # 共享的 res 目录

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
    # timestamp = f"{timestamp}_{random.randint(1000, 9999)}"
    # report_dir = os.path.join('report', timestamp)
    # testcase = "src/test/project/roku/UI/Connectivity Doctor/test_T6473243.py"
    # pytest.main(['-v','-s',testcase,f"--resultpath={report_dir}"])