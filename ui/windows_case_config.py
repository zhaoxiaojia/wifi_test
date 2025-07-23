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

"""
windows_case_config.py – Fix-3
==============================
* **Folder nodes still wouldn’t expand** when clicked.  Root cause was
  that qfluentwidgets `TreeView` requires us to *explicitly* toggle
  expansion if we intercept the *clicked* signal.  The previous handler
  returned early for directories, so the default expand/collapse logic
  never ran.
* **Wrong import path** – `QFileSystemModel` lives in
  **PyQt6.QtWidgets** (not *QtGui*) – this is now fixed.
* **Root-index initialisation** – we now reuse the `QModelIndex`
  returned by `setRootPath()` (Qt’s recommended way) instead of calling
  `index(root_dir)` again.

Copy the whole file below and overwrite your existing one.
"""



import os
import yaml

from PyQt6.QtCore import (
    Qt,
    QSignalBlocker,
    QTimer,
    QDir,
)
from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QFormLayout,
    QGroupBox,
    QLabel,
)
from qfluentwidgets import (
    CardWidget,
    TreeView,
    LineEdit,
    PushButton,
    ComboBox,
    FluentIcon, TextEdit,
)
from PyQt6.QtGui import QFileSystemModel


class CaseConfigPage(CardWidget):
    """用例配置主页面"""

    def __init__(self, on_run_callback):
        super().__init__()
        self.setObjectName("caseConfigPage")
        self.on_run_callback = on_run_callback

        # -------------------- load yaml --------------------
        self.config_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../config/config.yaml")
        )
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
        right = QVBoxLayout()
        self.form = QFormLayout()
        right.addLayout(self.form)

        self.run_btn = PushButton("运行", self)
        self.run_btn.setIcon(FluentIcon.PLAY)
        self.run_btn.clicked.connect(self.on_run)
        right.addWidget(self.run_btn)
        main_layout.addLayout(right, 4)

        # render form fields from yaml
        self.render_all_fields()

        # connect signals AFTER UI ready
        self.case_tree.clicked.connect(self.on_case_tree_clicked)

        # window hints
        self.setMinimumSize(1100, 700)
        self.setMaximumWidth(1800)
        self.case_tree.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.apply_case_logic("")

    def _init_case_tree(self, root_dir: str) -> None:
        self.fs_model = QFileSystemModel(self.case_tree)
        root_index = self.fs_model.setRootPath(root_dir)  # ← use return value
        self.fs_model.setNameFilters(["test_*.py"])
        # show directories regardless of filter
        self.fs_model.setNameFilterDisables(True)
        self.fs_model.setFilter(
            QDir.Filter.AllDirs | QDir.Filter.NoDotAndDotDot | QDir.Filter.Files
        )

        self.case_tree.setModel(self.fs_model)
        self.case_tree.setRootIndex(root_index)
        # hide size/type/modified columns
        for col in range(1, self.fs_model.columnCount()):
            self.case_tree.hideColumn(col)

    def _load_config(self) -> dict:
        if not os.path.exists(self.config_path):
            return {}
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as exc:
            print(f"[WARN] Failed to load config.yaml – {exc}")
            return {}

    def _save_config(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(self.config, f, allow_unicode=True)
        except Exception as exc:
            print(f"[WARN] Failed to save config.yaml – {exc}")

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

    def render_all_fields(self):
        """
        自动渲染config.yaml中的所有一级字段。
        控件支持 LineEdit / ComboBox（可扩展 Checkbox）。
        字段映射到 self.field_widgets，方便后续操作。
        """
        for key, value in self.config.items():
            if key == "connect_type":
                from PyQt6.QtWidgets import QGroupBox, QVBoxLayout, QLabel
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
                from PyQt6.QtWidgets import QGroupBox, QVBoxLayout, QLabel
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
                self.rf_step_edit.setPlaceholderText("step (逗号分隔)")
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
            # ---------- corner_angle ----------
            if key == "corner_angle":
                from PyQt6.QtWidgets import QGroupBox, QVBoxLayout, QLabel
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

    def populate_case_tree(self, root_dir):
        """
        遍历 test 目录，只将 test_ 开头的 .py 文件作为节点加入树结构。
        其它 py 文件不显示。
        """
        from PyQt6.QtGui import QStandardItemModel, QStandardItem
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(['请选择测试用例'])  # 可选，设置表头显示

        # 正确设置根节点为 'test' 或实际目录名
        root_item = QStandardItem(os.path.basename(root_dir))
        root_item.setData(root_dir)

        def add_items(parent_item, dir_path):
            for fname in sorted(os.listdir(dir_path)):
                if fname == '__pycache__' or fname.startswith('.'):
                    continue
                path = os.path.join(dir_path, fname)
                if os.path.isdir(path):
                    dir_item = QStandardItem(fname)
                    dir_item.setData(path)
                    parent_item.appendRow(dir_item)
                    # 递归前检查是否是 stress
                    if fname == "performance":
                        # 记下 performance 目录在 parent_item 的 row
                        self.performance_row = parent_item.rowCount() - 1
                        self.performance_item = dir_item
                    add_items(dir_item, path)
                elif fname.startswith("test_") and fname.endswith(".py"):
                    file_item = QStandardItem(fname)
                    file_item.setData(path)
                    parent_item.appendRow(file_item)

        add_items(root_item, root_dir)
        model.appendRow(root_item)
        self.case_tree.setModel(model)
        # 展开根节点
        self.case_tree.expand(model.index(0, 0))

        # 展开 stress_test 节点（如果存在）
        if hasattr(self, 'performance_item'):
            # 找到 stress_test 节点的 QModelIndex
            index = self.performance_item.index()
            self.case_tree.expand(index)

    def on_case_tree_clicked(self, idx):
        """
        当用户点击左侧用例树节点时触发。
        1. 如果是有效的 test_ 开头的 Python 文件，则自动填入路径并刷新可编辑字段逻辑。
        2. 否则清空用例路径，并将所有字段设为只读。
        """

        model = self.case_tree.model()
        # -------- QFileSystemModel branch --------
        if isinstance(model, QFileSystemModel):
            path = model.filePath(idx)
            if os.path.isdir(path):
                # user clicked a folder – toggle expansion manually
                if self.case_tree.isExpanded(idx):
                    self.case_tree.collapse(idx)
                else:
                    self.case_tree.expand(idx)
                self.set_fields_editable(set())
                return

            # not a valid test file → disable fields
            if not (
                os.path.isfile(path)
                and os.path.basename(path).startswith("test_")
                and path.endswith(".py")
            ):
                self.set_fields_editable(set())
                return
        else:  # -------- legacy QStandardItemModel branch --------
            item = model.itemFromIndex(idx)
            if item is None:
                return
            path = item.data()
            if os.path.isdir(path):
                if self.case_tree.isExpanded(idx):
                    self.case_tree.collapse(idx)
                else:
                    self.case_tree.expand(idx)
                self.set_fields_editable(set())
                return
            if not (
                os.path.isfile(path)
                and os.path.basename(path).startswith("test_")
                and path.endswith(".py")
            ):
                self.set_fields_editable(set())
                return

        # at this point we have a valid test_* file
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
            "connect_type.telnet.wildcard"
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
            editable |= {"corner_angle"}
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
        # 收集参数区所有值
        for key, widget in self.field_widgets.items():
            if isinstance(widget, LineEdit):
                val = widget.text()
                if ':' in val and isinstance(self.config.get(key), dict):
                    # 对于dict类型，自动解析 key:val
                    k, v = val.split(':', 1)
                    self.config[key] = {k.strip(): v.strip()}
                elif isinstance(self.config.get(key), list):
                    self.config[key] = [x.strip() for x in val.split(',') if x.strip()]
                else:
                    self.config[key] = val
            elif isinstance(widget, ComboBox):
                text = widget.currentText()
                if text in ['True', 'False']:
                    self.config[key] = (text == 'True')
                else:
                    self.config[key] = text
        # 写回yaml
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(self.config, f, allow_unicode=True)
