#!/usr/bin/env python 
# encoding: utf-8 
'''
@author: chao.li
@contact: chao.li@amlogic.com
@software: pycharm
@file: windows_case_config.py
@time: 2025/7/22 21:49
@desc:
'''
from __future__ import annotations

import os
import sys
from pathlib import Path
import yaml

from PyQt5.QtCore import (
    Qt,
    QSignalBlocker,
    QTimer,
    QDir,
    QSortFilterProxyModel,
    QModelIndex
)
from PyQt5.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QFormLayout,
    QGroupBox,
    QLabel,
    QFileSystemModel
)

from qfluentwidgets import (
    CardWidget,
    TreeView,
    LineEdit,
    PushButton,
    ComboBox,
    FluentIcon,
    TextEdit,
    InfoBar,
    InfoBarPosition,
    ScrollArea
)


class TestFileFilterModel(QSortFilterProxyModel):
    def filterAcceptsRow(self, source_row, source_parent):
        index = self.sourceModel().index(source_row, 0, source_parent)
        file_name = self.sourceModel().fileName(index)
        is_dir = self.sourceModel().isDir(index)

        # 过滤 __pycache__ 文件夹 和 __init__.py 文件
        if is_dir and file_name == "__pycache__":
            return False
        if not is_dir:
            if not file_name.startswith("test_") or not file_name.endswith(".py"):
                return False
            if file_name == "__init__.py":
                return False
        return True

    def hasChildren(self, parent: QModelIndex) -> bool:
        """修复文件夹无法展开的问题：即使子项被过滤，也认为目录有子节点"""
        src_parent = self.mapToSource(parent)
        # 原始模型中的节点是否是目录
        if not self.sourceModel().isDir(src_parent):
            return False
        # 强制认为目录有子项（即便都被过滤了）
        return True


class CaseConfigPage(CardWidget):
    """用例配置主页面"""

    def __init__(self, on_run_callback):
        super().__init__()
        self.setObjectName("caseConfigPage")
        self.on_run_callback = on_run_callback

        # -------------------- load yaml --------------------
        if hasattr(sys, "_MEIPASS"):
            bundle_path = Path(sys._MEIPASS) / "config" / "config.yaml"
            if bundle_path.exists():
                self.config_path = bundle_path.resolve()
            else:
                self.config_path = (Path.cwd() / "config" / "config.yaml").resolve()
        else:
            self.config_path = (Path.cwd() / "config" / "config.yaml").resolve()
        self.config: dict = self._load_config()
        # -------------------- state --------------------
        self._refreshing = False
        self._pending_path: str | None = None
        self.field_widgets: dict[str, QWidget] = {}

        # -------------------- layout --------------------
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(20)

        # ----- left: case tree -----
        self.case_tree = TreeView(self)
        self.case_tree.setFixedWidth(400)
        self._init_case_tree(
            os.path.abspath(os.path.join(os.path.dirname(__file__), "../test"))
        )
        main_layout.addWidget(self.case_tree, 3)

        # ----- right: parameters & run button -----
        scroll_area = ScrollArea(self)
        scroll_area.setWidgetResizable(True)
        container = QWidget()
        right = QVBoxLayout(container)
        self.form = QFormLayout()
        right.addLayout(self.form)

        self.run_btn = PushButton("运行", self)
        self.run_btn.setIcon(FluentIcon.PLAY)
        self.run_btn.clicked.connect(self.on_run)
        right.addWidget(self.run_btn)
        scroll_area.setWidget(container)
        main_layout.addWidget(scroll_area, 4)

        # render form fields from yaml
        self.render_all_fields()

        # connect signals AFTER UI ready
        self.case_tree.clicked.connect(self.on_case_tree_clicked)
        self.case_tree.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        QTimer.singleShot(0, lambda: self.apply_case_logic(""))

    def _init_case_tree(self, root_dir: str) -> None:
        self.fs_model = QFileSystemModel(self.case_tree)
        root_index = self.fs_model.setRootPath(root_dir)  # ← use return value
        self.fs_model.setNameFilters(["test_*.py"])
        # show directories regardless of filter
        self.fs_model.setNameFilterDisables(True)
        self.fs_model.setFilter(
            QDir.Filter.AllDirs | QDir.Filter.NoDotAndDotDot | QDir.Filter.Files
        )

        self.proxy_model = TestFileFilterModel()
        self.proxy_model.setSourceModel(self.fs_model)
        self.case_tree.setModel(self.proxy_model)
        self.case_tree.setRootIndex(self.proxy_model.mapFromSource(root_index))

        # 隐藏非名称列
        self.case_tree.header().hide()
        for col in range(1, self.fs_model.columnCount()):
            self.case_tree.hideColumn(col)

    def _load_config(self) -> dict:
        if not self.config_path.exists():
            QTimer.singleShot(
                0,
                lambda: InfoBar.warning(
                    title="提示",
                    content="未找到配置文件",
                    parent=self,
                    position=InfoBarPosition.TOP,
                ),
            )
            return {}
        try:
            with self.config_path.open("r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}

            app_base = self._get_application_base()
            changed = False
            path = config.get("text_case", "")
            if path:
                abs_path = Path(path)
                if not abs_path.is_absolute():
                    abs_path = app_base / abs_path
                abs_path = abs_path.resolve()
                if abs_path.exists():
                    try:
                        rel_path = abs_path.relative_to(app_base)
                    except ValueError:
                        config["text_case"] = ""
                        changed = True
                    else:
                        rel_str = rel_path.as_posix()
                        if rel_str != path:
                            config["text_case"] = rel_str
                            changed = True
                else:
                    config["text_case"] = ""
                    changed = True
            else:
                config["text_case"] = ""

            if changed:
                try:
                    with self.config_path.open("w", encoding="utf-8") as wf:
                        yaml.safe_dump(config, wf, allow_unicode=True, sort_keys=False, width=4096)
                except Exception as exc:
                    QTimer.singleShot(
                        0,
                        lambda: InfoBar.error(
                            title="错误",
                            content=f"保存配置失败: {exc}",
                            parent=self,
                            position=InfoBarPosition.TOP,
                        ),
                    )
            return config
        except Exception as exc:
            QTimer.singleShot(
                0,
                lambda: InfoBar.error(
                    title="错误",
                    content=f"读取配置失败: {exc}",
                    parent=self,
                    position=InfoBarPosition.TOP,
                ),
            )
            return {}

    def _save_config(self):
        try:
            with self.config_path.open("w", encoding="utf-8") as f:
                yaml.safe_dump(self.config, f, allow_unicode=True, sort_keys=False, width=4096)
            self.config = self._load_config()
            QTimer.singleShot(
                0,
                lambda: InfoBar.success(
                    title="提示",
                    content="配置已保存", 
                    parent=self,
                    position=InfoBarPosition.TOP,
                ),
            )
        except Exception as exc:
            QTimer.singleShot(
                0,
                lambda: InfoBar.error(
                    title="错误",
                    content=f"保存配置失败: {exc}",
                    parent=self,
                    position=InfoBarPosition.TOP,
                ),
            )

    def _get_application_base(self) -> Path:
        """获取应用根路径"""
        base = (
            Path(sys._MEIPASS) / "src"
            if hasattr(sys, "_MEIPASS")
            else Path(__file__).resolve().parent.parent
        )
        return base.resolve()

    def _resolve_case_path(self, path: str | Path) -> Path:
        """将相对用例路径转换为绝对路径"""
        if not path:
            return Path()
        p = Path(path)
        base = Path(self._get_application_base())
        return str(p) if p.is_absolute() else str((base / p).resolve())


    def on_connect_type_changed(self, type_str):
        """
        切换连接方式时，仅展示对应参数组
        """
        self.adb_group.setVisible(type_str == "adb")
        self.telnet_group.setVisible(type_str == "telnet")

    def on_rf_model_changed(self, model_str):
        """
        切换rf_solution.model时，仅展示当前选项参数
        现在只有XIN-YI，如果有别的model，添加隐藏/显示逻辑
        """
        # 当前只有XIN-YI，后续有其它model可以加if-else
        self.xin_group.setVisible(model_str == "XIN-YI")
        self.rc4_group.setVisible(model_str == "RC4DAT-8G-95")
        self.rack_group.setVisible(model_str == "RADIORACK-4-220")

    # 添加到类里：响应 Tool 下拉，切换子参数可见性
    def on_rvr_tool_changed(self, tool: str):
        """选择 iperf / ixchariot 时，动态显示对应子参数"""
        self.rvr_iperf_group.setVisible(tool == "iperf")
        self.rvr_ix_group.setVisible(tool == "ixchariot")

    def on_serial_enabled_changed(self, text: str):
        self.serial_cfg_group.setVisible(text == "True")

    def render_all_fields(self):
        """
        自动渲染config.yaml中的所有一级字段。
        控件支持 LineEdit / ComboBox（可扩展 Checkbox）。
        字段映射到 self.field_widgets，方便后续操作。
        """
        for key, value in self.config.items():
            if key == "text_case":
                group = QGroupBox("Test Case")
                group.setStyleSheet(
                    "QGroupBox{border:1px solid #d0d0d0;border-radius:4px;margin-top:6px;}"
                    "QGroupBox::title{left:8px;padding:0 3px;}")
                vbox = QVBoxLayout(group)
                self.test_case_edit = LineEdit(self)
                self.test_case_edit.setText(value or "")  # 默认值
                self.test_case_edit.setReadOnly(True)  # 只读，由左侧树刷新
                vbox.addWidget(self.test_case_edit)
                self.form.insertRow(0, group)  # ← 插到最上面
                self.field_widgets["text_case"] = self.test_case_edit
                continue
            if key == "connect_type":
                group = QGroupBox("连接方式")
                vbox = QVBoxLayout(group)
                self.connect_type_combo = ComboBox(self)
                self.connect_type_combo.addItems(["adb", "telnet"])
                self.connect_type_combo.setCurrentText(value.get('type', 'adb'))
                self.connect_type_combo.currentTextChanged.connect(self.on_connect_type_changed)
                vbox.addWidget(self.connect_type_combo)
                # 只为每个子类型建独立的参数区
                self.adb_group = QWidget()
                adb_vbox = QVBoxLayout(self.adb_group)
                self.adb_device_edit = LineEdit(self)
                self.adb_device_edit.setPlaceholderText("adb.device")
                adb_vbox.addWidget(QLabel("ADB Device:"))
                adb_vbox.addWidget(self.adb_device_edit)

                self.telnet_group = QWidget()
                telnet_vbox = QVBoxLayout(self.telnet_group)
                self.telnet_ip_edit = LineEdit(self)
                self.telnet_ip_edit.setPlaceholderText("telnet.ip")
                telnet_vbox.addWidget(QLabel("Telnet IP:"))
                telnet_vbox.addWidget(self.telnet_ip_edit)
                # 只添加到布局，隐藏未选中的
                vbox.addWidget(self.adb_group)
                vbox.addWidget(self.telnet_group)
                self.form.addRow(group)
                # 初始化
                self.adb_device_edit.setText(value.get("adb", {}).get("device", ""))
                self.telnet_ip_edit.setText(value.get("telnet", {}).get("ip", ""))
                self.on_connect_type_changed(self.connect_type_combo.currentText())
                self.field_widgets["connect_type.type"] = self.connect_type_combo
                self.field_widgets["connect_type.adb.device"] = self.adb_device_edit
                self.field_widgets["connect_type.telnet.ip"] = self.telnet_ip_edit
                continue
            if key == "rf_solution":
                group = QGroupBox("RF Solution")
                vbox = QVBoxLayout(group)
                # -------- 下拉：选择型号 --------
                self.rf_model_combo = ComboBox(self)
                self.rf_model_combo.addItems(["XIN-YI", "RC4DAT-8G-95", "RADIORACK-4-220"])
                self.rf_model_combo.setCurrentText(value.get("model", "XIN-YI"))
                self.rf_model_combo.currentTextChanged.connect(self.on_rf_model_changed)
                vbox.addWidget(QLabel("Model:"))
                vbox.addWidget(self.rf_model_combo)

                # ========== ① XIN-YI 参数区（目前无额外字段，可放提醒文字） ==========
                self.xin_group = QWidget()
                xin_box = QVBoxLayout(self.xin_group)
                xin_box.addWidget(QLabel("XIN-YI 当前无需额外配置"))
                vbox.addWidget(self.xin_group)

                # ========== ② RC4DAT-8G-95 参数区 ==========
                self.rc4_group = QWidget()
                rc4_box = QVBoxLayout(self.rc4_group)
                rc4_cfg = value.get("RC4DAT-8G-95", {})
                self.rc4_vendor_edit = LineEdit(self)
                self.rc4_product_edit = LineEdit(self)
                self.rc4_ip_edit = LineEdit(self)
                self.rc4_vendor_edit.setPlaceholderText("idVendor")
                self.rc4_product_edit.setPlaceholderText("idProduct")
                self.rc4_ip_edit.setPlaceholderText("ip_address")
                self.rc4_vendor_edit.setText(str(rc4_cfg.get("idVendor", "")))
                self.rc4_product_edit.setText(str(rc4_cfg.get("idProduct", "")))
                self.rc4_ip_edit.setText(rc4_cfg.get("ip_address", ""))
                rc4_box.addWidget(QLabel("idVendor:"));
                rc4_box.addWidget(self.rc4_vendor_edit)
                rc4_box.addWidget(QLabel("idProduct:"));
                rc4_box.addWidget(self.rc4_product_edit)
                rc4_box.addWidget(QLabel("IP 地址:"));
                rc4_box.addWidget(self.rc4_ip_edit)
                vbox.addWidget(self.rc4_group)

                # ========== ③ RADIORACK-4-220 参数区 ==========
                self.rack_group = QWidget()
                rack_box = QVBoxLayout(self.rack_group)
                rack_cfg = value.get("RADIORACK-4-220", {})
                self.rack_ip_edit = LineEdit(self)
                self.rack_ip_edit.setPlaceholderText("ip_address")
                self.rack_ip_edit.setText(rack_cfg.get("ip_address", ""))
                rack_box.addWidget(QLabel("IP 地址:"))
                rack_box.addWidget(self.rack_ip_edit)
                vbox.addWidget(self.rack_group)

                # -------- 通用字段：step --------
                self.rf_step_edit = LineEdit(self)
                self.rf_step_edit.setPlaceholderText("rf step (逗号分隔) : 0,50")
                self.rf_step_edit.setText(",".join(map(str, value.get("step", []))))
                vbox.addWidget(QLabel("Step:"))
                vbox.addWidget(self.rf_step_edit)

                # ---- 加入表单 & 初始化可见性 ----
                self.form.addRow(group)
                self.on_rf_model_changed(self.rf_model_combo.currentText())

                # ---- 注册控件 ----
                self.field_widgets["rf_solution.model"] = self.rf_model_combo
                self.field_widgets["rf_solution.RC4DAT-8G-95.idVendor"] = self.rc4_vendor_edit
                self.field_widgets["rf_solution.RC4DAT-8G-95.idProduct"] = self.rc4_product_edit
                self.field_widgets["rf_solution.RC4DAT-8G-95.ip_address"] = self.rc4_ip_edit
                self.field_widgets["rf_solution.RADIORACK-4-220.ip_address"] = self.rack_ip_edit
                self.field_widgets["rf_solution.step"] = self.rf_step_edit
                continue  # 跳过后面的通用字段处理
            if key == "rvr":
                group = QGroupBox("RVR 配置")  # 外层分组
                vbox = QVBoxLayout(group)
                # Tool 下拉
                self.rvr_tool_combo = ComboBox(self)
                self.rvr_tool_combo.addItems(["iperf", "ixchariot"])
                self.rvr_tool_combo.setCurrentText(value.get("tool", "iperf"))
                self.rvr_tool_combo.currentTextChanged.connect(self.on_rvr_tool_changed)
                vbox.addWidget(QLabel("Tool:"))
                vbox.addWidget(self.rvr_tool_combo)

                # ----- iperf 子组 -----
                self.rvr_iperf_group = QWidget()
                iperf_box = QVBoxLayout(self.rvr_iperf_group)

                self.iperf_version_combo = ComboBox(self)
                self.iperf_version_combo.addItems(["iperf", "iperf3"])
                self.iperf_version_combo.setCurrentText(
                    value.get("iperf", {}).get("version", "iperf"))
                self.iperf_path_edit = LineEdit(self)
                self.iperf_path_edit.setPlaceholderText("iperf 路径 (DUT)")
                self.iperf_path_edit.setText(value.get("iperf", {}).get("path", ""))

                iperf_box.addWidget(QLabel("Version:"))
                iperf_box.addWidget(self.iperf_version_combo)
                iperf_box.addWidget(QLabel("Path:"))
                iperf_box.addWidget(self.iperf_path_edit)
                vbox.addWidget(self.rvr_iperf_group)

                # ----- ixchariot 子组 -----
                self.rvr_ix_group = QWidget()
                ix_box = QVBoxLayout(self.rvr_ix_group)
                self.ix_path_edit = LineEdit(self)
                self.ix_path_edit.setPlaceholderText("IxChariot 安装路径")
                self.ix_path_edit.setText(value.get("ixchariot", {}).get("path", ""))
                ix_box.addWidget(self.ix_path_edit)
                vbox.addWidget(self.rvr_ix_group)

                # ----- 其它通用字段 -----
                self.pair_edit = LineEdit(self)
                self.pair_edit.setPlaceholderText("pair")
                self.pair_edit.setText(str(value.get("pair", "")))

                self.repeat_combo = LineEdit()
                self.repeat_combo.setText(str(value.get("repeat", 0)))

                vbox.addWidget(QLabel("Pair:"))
                vbox.addWidget(self.pair_edit)
                vbox.addWidget(QLabel("Repeat:"))
                vbox.addWidget(self.repeat_combo)

                # 加入表单
                self.form.addRow(group)

                # 字段注册（供启用/禁用和收集参数用）
                self.field_widgets["rvr.tool"] = self.rvr_tool_combo
                self.field_widgets["rvr.iperf.version"] = self.iperf_version_combo
                self.field_widgets["rvr.iperf.path"] = self.iperf_path_edit
                self.field_widgets["rvr.ixchariot.path"] = self.ix_path_edit
                self.field_widgets["rvr.pair"] = self.pair_edit
                self.field_widgets["rvr.repeat"] = self.repeat_combo

                # 根据当前 Tool 值隐藏/显示子组
                self.on_rvr_tool_changed(self.rvr_tool_combo.currentText())
                continue  # 跳过默认 LineEdit 处理

                # ---------- 其余简单字段 ----------
            if key == "corner_angle":
                group = QGroupBox("Corner Angle")
                vbox = QVBoxLayout(group)

                # —— IP 地址 ——
                self.corner_ip_edit = LineEdit(self)
                self.corner_ip_edit.setPlaceholderText("ip_address")
                self.corner_ip_edit.setText(value.get("ip_address", ""))  # 默认值

                # —— 角度步进 ——
                self.corner_step_edit = LineEdit(self)
                self.corner_step_edit.setPlaceholderText("step (逗号分隔，如 0,361)")
                self.corner_step_edit.setText(",".join(map(str, value.get("step", []))))

                vbox.addWidget(QLabel("IP 地址:"))
                vbox.addWidget(self.corner_ip_edit)
                vbox.addWidget(QLabel("Step:"))
                vbox.addWidget(self.corner_step_edit)

                # 加入表单
                self.form.addRow(group)

                # 注册控件（用于启用/禁用、保存回 YAML）
                self.field_widgets["corner_angle.ip_address"] = self.corner_ip_edit
                self.field_widgets["corner_angle.step"] = self.corner_step_edit
                continue  # 跳过后面的通用处理
            if key == "router":
                group = QGroupBox("Router")
                vbox = QVBoxLayout(group)

                self.router_name_combo = ComboBox(self)
                self.router_name_combo.addItems([
                    "asusax86u", "asusax88u", "asusax5400",
                    "asusax6700", "xiaomiredax6000", "xiaomiax3000"
                ])
                self.router_name_combo.setCurrentText(value.get("name", "xiaomiax3000"))
                self.ssid_2g_edit = LineEdit(self)
                self.ssid_2g_edit.setPlaceholderText("2.4G SSID")
                self.ssid_2g_edit.setText(value.get("ssid_2g", ""))
                self.passwd_2g_edit = LineEdit(self)
                self.passwd_2g_edit.setPlaceholderText("2.4G 密码(空=开放网络)")
                self.passwd_2g_edit.setText(value.get("passwd_2g", ""))
                self.ssid_5g_edit = LineEdit(self)
                self.ssid_5g_edit.setPlaceholderText("5G SSID")
                self.ssid_5g_edit.setText(value.get("ssid_5g", ""))
                self.passwd_5g_edit = LineEdit(self)
                self.passwd_5g_edit.setPlaceholderText("5G 密码(空=开放网络)")
                self.passwd_5g_edit.setText(value.get("passwd_5g", ""))

                vbox.addWidget(QLabel("Name:"))
                vbox.addWidget(self.router_name_combo)
                vbox.addWidget(QLabel("SSID 2G:"))
                vbox.addWidget(self.ssid_2g_edit)
                vbox.addWidget(QLabel("Password 2G:"))
                vbox.addWidget(self.passwd_2g_edit)
                vbox.addWidget(QLabel("SSID 5G:"))
                vbox.addWidget(self.ssid_5g_edit)
                vbox.addWidget(QLabel("Password 5G:"))
                vbox.addWidget(self.passwd_5g_edit)
                self.form.addRow(group)

                # 注册控件
                self.field_widgets["router.name"] = self.router_name_combo
                self.field_widgets["router.ssid_2g"] = self.ssid_2g_edit
                self.field_widgets["router.passwd_2g"] = self.passwd_2g_edit
                self.field_widgets["router.ssid_5g"] = self.ssid_5g_edit
                self.field_widgets["router.passwd_5g"] = self.passwd_5g_edit
                continue  # ← 继续下一顶层 key
            if key == "serial_port":
                group = QGroupBox("Serial Port")
                vbox = QVBoxLayout(group)

                # 开关（True/False 下拉，同一套保存逻辑即可）
                self.serial_enable_combo = ComboBox(self)
                self.serial_enable_combo.addItems(["False", "True"])
                self.serial_enable_combo.setCurrentText(
                    str(value.get("status", False))
                )
                self.serial_enable_combo.currentTextChanged.connect(
                    self.on_serial_enabled_changed
                )
                vbox.addWidget(QLabel("Enable:"))
                vbox.addWidget(self.serial_enable_combo)

                # —— 子参数区 ——（默认隐藏，开关=True 时可见）
                self.serial_cfg_group = QWidget()
                cfg_box = QVBoxLayout(self.serial_cfg_group)

                self.serial_port_edit = LineEdit(self)
                self.serial_port_edit.setPlaceholderText("port (e.g. COM5)")
                self.serial_port_edit.setText(value.get("port", ""))

                self.serial_baud_edit = LineEdit(self)
                self.serial_baud_edit.setPlaceholderText("baud (e.g. 115200)")
                self.serial_baud_edit.setText(str(value.get("baud", "")))

                cfg_box.addWidget(QLabel("Port:"))
                cfg_box.addWidget(self.serial_port_edit)
                cfg_box.addWidget(QLabel("Baud:"))
                cfg_box.addWidget(self.serial_baud_edit)

                vbox.addWidget(self.serial_cfg_group)
                self.form.addRow(group)

                # 初始化显隐
                self.on_serial_enabled_changed(self.serial_enable_combo.currentText())

                # 注册控件
                self.field_widgets["serial_port.status"] = self.serial_enable_combo
                self.field_widgets["serial_port.port"] = self.serial_port_edit
                self.field_widgets["serial_port.baud"] = self.serial_baud_edit
                continue
            # ------- 默认处理：创建 LineEdit 保存未覆盖字段 -------
            group = QGroupBox(key)
            vbox = QVBoxLayout(group)
            edit = LineEdit(self)
            edit.setText(str(value) if value is not None else "")
            vbox.addWidget(edit)
            self.form.addRow(group)
            self.field_widgets[key] = edit
    def populate_case_tree(self, root_dir):
        """
        遍历 test 目录，只将 test_ 开头的 .py 文件作为节点加入树结构。
        其它 py 文件不显示。
        """
        from PyQt5.QtGui import QStandardItemModel, QStandardItem
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(['请选择测试用例'])  # 可选，设置表头显示

        # 正确设置根节点为 'test' 或实际目录名
        root_item = QStandardItem(os.path.basename(root_dir))
        root_item.setData(root_dir)

        def add_items(parent_item, dir_path):
            for fname in sorted(os.listdir(dir_path)):
                print(f'fname {fname}')
                if fname == '__pycache__' or fname.startswith('.'):
                    continue
                path = os.path.join(dir_path, fname)
                if os.path.isdir(path):
                    dir_item = QStandardItem(fname)
                    dir_item.setData(path)
                    parent_item.appendRow(dir_item)
                    add_items(dir_item, path)
                elif os.path.isfile(path):
                    file_item = QStandardItem(fname)
                    file_item.setData(path)
                    parent_item.appendRow(file_item)

        add_items(root_item, root_dir)
        model.appendRow(root_item)
        self.case_tree.setModel(model)
        # 展开根节点
        self.case_tree.expand(model.index(0, 0))

    def on_case_tree_clicked(self, proxy_idx):
        """
        proxy_idx: 用户在界面点击到的索引（始终是代理模型的）
        """
        model = self.case_tree.model()

        # —— 用源索引只负责取真实文件路径 ——
        source_idx = (
            model.mapToSource(proxy_idx)
            if isinstance(model, QSortFilterProxyModel) else proxy_idx
        )
        path = self.fs_model.filePath(source_idx)
        base = Path(self._get_application_base())
        display_path = os.path.relpath(path, base)

        # ---------- 目录：只负责展开/折叠 ----------
        if os.path.isdir(path):
            if self.case_tree.isExpanded(proxy_idx):
                self.case_tree.collapse(proxy_idx)
            else:
                self.case_tree.expand(proxy_idx)
            self.set_fields_editable(set())
            return

        # ---------- 非 test_*.py 直接禁用 ----------
        if not (os.path.isfile(path)
                and os.path.basename(path).startswith("test_")
                and path.endswith(".py")):
            self.set_fields_editable(set())
            return

        if hasattr(self, "test_case_edit"):
            self.test_case_edit.setText(display_path)

        # ---------- 有效用例 ----------
        if self._refreshing:
            self._pending_path = path
            return
        self.apply_case_logic(path)

    def get_editable_fields(self, case_path):
        """
        根据用例名返回哪些字段可以编辑。
        你可以完善/替换成自己的判断规则。
        """
        basename = os.path.basename(case_path)
        print(f'tesecase name {basename}')
        editable = set()
        # 永远让 connect_type 可编辑
        editable |= {
            "connect_type.type",
            "connect_type.adb.device",
            "connect_type.telnet.ip",
            "connect_type.telnet.wildcard",
            "router.name",
            "router.ssid_2g",
            "router.passwd_2g",
            "router.ssid_5g",
            "router.passwd_5g",
            "serial_port.status",
            "serial_port.port",
            "serial_port.baud"
        }
        if basename == "test_compatibility.py":
            editable |= {"fpga", "power_relay"}
        if "rvr" in basename:
            editable |= {
                "rvr", "rvr.tool", "rvr.iperf.version", "rvr.iperf.path", "rvr.ixchariot.path",
                "rvr.pair", "rvr.repeat",
                "rf_solution.model",
                "rf_solution.RC4DAT-8G-95.idVendor",
                "rf_solution.RC4DAT-8G-95.idProduct",
                "rf_solution.RC4DAT-8G-95.ip_address",
                "rf_solution.RADIORACK-4-220.ip_address",
                "rf_solution.step"
            }
        if "rvo" in basename:
            editable |= {
                "corner_angle",
                "corner_angle.ip_address",
                "corner_angle.step"
            }
        # 如果你需要所有字段都可编辑，直接 return set(self.field_widgets.keys())
        return editable

    def set_fields_editable(self, editable_fields: set[str]) -> None:
        """批量控制字段可编辑状态（高效且不触发级联信号）"""
        # 暂停窗口刷新，提升批量操作速度
        self.setUpdatesEnabled(False)
        try:
            for key, widget in self.field_widgets.items():
                desired = key in editable_fields
                if widget.isEnabled() == desired:
                    continue  # 状态没变就别动

                # 屏蔽 widget 自己的信号，避免 setEnabled 时触发槽函数
                with QSignalBlocker(widget):
                    widget.setEnabled(desired)
        finally:
            self.setUpdatesEnabled(True)
            self.update()  # 确保一次性刷新到屏幕

    def apply_case_logic(self, case_path):
        """
        选中用例后自动控制字段可编辑性和填充值。
        """
        if self._refreshing:
            # 极少见：递归进入，直接丢弃
            return

        # ---------- 进入刷新 ----------
        self._refreshing = True
        self.case_tree.setEnabled(False)  # 锁定用例树
        self.setUpdatesEnabled(False)  # 暂停全局重绘

        try:
            editable = self.get_editable_fields(case_path)
            self.set_fields_editable(editable)
        finally:
            # ---------- 刷新结束 ----------
            self.setUpdatesEnabled(True)
            self.case_tree.setEnabled(True)
            self._refreshing = False

        # 若用户在刷新过程中又点了别的用例，延迟 0 ms 处理它
        if self._pending_path:
            path = self._pending_path
            self._pending_path = None
            QTimer.singleShot(0, lambda: self.apply_case_logic(path))

    def on_run(self):
        # 将字段值更新到 self.config（保持结构）
        for key, widget in self.field_widgets.items():
            # key 可能是 'connect_type.adb.device' → 拆成层级
            parts = key.split('.')
            ref = self.config
            for part in parts[:-1]:
                ref = ref.setdefault(part, {})  # 保证嵌套结构存在
            leaf = parts[-1]

            if isinstance(widget, LineEdit):
                val = widget.text()
                # 判断当前字段是否为 list 且不是字符串形式表示的
                old_val = ref.get(leaf)
                if isinstance(old_val, list):
                    # 判断是否是纯数字，如果都是数字，则保留为 int，否则保留字符串
                    items = [x.strip() for x in val.split(',') if x.strip()]
                    if all(i.isdigit() for i in items):
                        ref[leaf] = [int(i) for i in items]
                    else:
                        ref[leaf] = items
                else:
                    val = val.strip()
                    if len(parts) >= 2 and parts[-2] == "router" and leaf.startswith("passwd") and not val:
                        ref[leaf] = ""  # 空密码表示开放网络
                    else:
                        ref[leaf] = val
            elif isinstance(widget, ComboBox):
                text = widget.currentText()
                ref[leaf] = True if text == 'True' else False if text == 'False' else text
        case_path = self.field_widgets["text_case"].text().strip()
        base = Path(self._get_application_base())

        # 默认将现有路径解析成 POSIX 字符串
        case_path = Path(case_path).as_posix() if case_path else ""
        abs_case_path = (
            (base / case_path).resolve().as_posix() if case_path else ""

        )

        # 若树状视图中选择了有效用例，则覆盖默认路径
        proxy_idx = self.case_tree.currentIndex()
        model = self.case_tree.model()
        src_idx = (
            model.mapToSource(proxy_idx)
            if isinstance(model, QSortFilterProxyModel)
            else proxy_idx
        )
        selected_path = self.fs_model.filePath(src_idx)
        if os.path.isfile(selected_path) and selected_path.endswith(".py"):
            abs_path = Path(selected_path).resolve()
            display_path = os.path.relpath(abs_path, base)
            case_path = Path(display_path).as_posix()

            abs_case_path = abs_path.as_posix()

        # 将最终运行的用例路径写入配置（尽量保持相对路径）
        self.config["text_case"] = case_path
        # 保存配置
        self._save_config()
        if os.path.isfile(abs_case_path) and abs_case_path.endswith(".py"):
            self.on_run_callback(abs_case_path, case_path, self.config)
        else:
            InfoBar.warning(
                title="提示",
                content="请选择一个测试用例后再运行",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=1800
            )
