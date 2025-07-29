# !/usr/bin/env python
# -*-coding:utf-8 -*-


import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from PyQt5.QtWidgets import QApplication
from qfluentwidgets import FluentIcon, FluentWindow, NavigationItemPosition
from src.ui.windows_case_config import CaseConfigPage
from src.ui.run import RunPage
from qfluentwidgets import setTheme, Theme
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtCore import QTimer


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
            # 1. 先断开所有可能的信号连接（防止残留事件）
            try:
                # 断开RunPage自身的所有信号
                self.run_page.disconnect()
            except TypeError:
                pass  # 无连接时忽略

            # 2. 从导航栏移除（更彻底的方式）
            try:
                # 直接使用removeSubInterface方法移除
                self.removeSubInterface(self.run_page)
            except Exception as e:
                print(f"移除导航项时出错: {e}")
            # 3. 从堆叠窗口移除
            index = self.stackedWidget.indexOf(self.run_page)
            if index != -1:
                self.stackedWidget.removeWidget(self.run_page)

            # 4. 断开所有信号连接
            if hasattr(self.run_page, "runner") and self.run_page.runner:
                runner = self.run_page.runner
                try:
                    runner.log_signal.disconnect(self.run_page._append_log)
                except (TypeError, RuntimeError):
                    pass
                try:
                    runner.progress_signal.disconnect(self.run_page.update_progress)
                except (TypeError, RuntimeError):
                    pass
                try:
                    runner.finished.disconnect()
                except (TypeError, RuntimeError):
                    pass
                # 停止线程
                if runner.isRunning():
                    runner.stop()
                    runner.wait()  # 等待线程真正结束
            # 5. 强制销毁并清除引用
            self.run_page.setParent(None)  # 先解除父对象关联
            self.run_page.deleteLater()
            self.run_page = None  # 关键：清除引用

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
        self.clear_run_page()
        # 传递主窗口自身作为RunPage的父窗口
        self.run_page = RunPage(case_path, config, self.show_case_config, parent=self)
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
        # print("show_case_config dir:", dir(self))
        self.clear_run_page()
        self.setCurrentIndex(self.case_config_page)
        print("Switched to CaseConfigPage")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
