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
from pathlib import Path
import yaml
import logging
from dataclasses import dataclass, field
from src.tools.router_tool.router_factory import router_list
from src.util.constants import Paths, RouterConst
from src.util.constants import get_config_base, get_src_base
from src.tools.config_loader import load_config
from PyQt5.QtCore import (
    Qt,
    QSignalBlocker,
    QTimer,
    QDir,
    QSortFilterProxyModel,
    QModelIndex,
    pyqtSignal,
)

from PyQt5.QtWidgets import (
    QSizePolicy,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QFileSystemModel,
    QCheckBox
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


@dataclass
class EditableInfo:
    """描述某个用例的可编辑字段及相关 UI 使能状态"""
    fields: set[str] = field(default_factory=set)
    enable_csv: bool = False
    enable_rvr_wifi: bool = False


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

    routerInfoChanged = pyqtSignal()
    csvFileChanged = pyqtSignal(str)

    def __init__(self, on_run_callback):
        super().__init__()
        self.setObjectName("caseConfigPage")
        self.on_run_callback = on_run_callback

        # -------------------- load yaml --------------------
        self.config_path = (Path(Paths.CONFIG_DIR) / "config.yaml").resolve()
        self.config: dict = self._load_config()
        # -------------------- state --------------------
        self._refreshing = False
        self._pending_path: str | None = None
        self.field_widgets: dict[str, QWidget] = {}
        self.router_ssid_2g = ""
        self.router_ssid_5g = ""
        self.selected_csv_path: str | None = None
        # -------------------- layout --------------------
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(5, 5, 5, 5)
        # ----- left: case tree -----
        self.case_tree = TreeView(self)
        self.case_tree.setFixedWidth(300)
        self._init_case_tree(Path(self._get_application_base()) / "test")
        main_layout.addWidget(self.case_tree, 3)

        # ----- right: parameters & run button -----
        scroll_area = ScrollArea(self)
        scroll_area.setWidgetResizable(True)
        container = QWidget()
        right = QVBoxLayout(container)
        right.setContentsMargins(5, 5, 5, 5)
        right.setSpacing(5)
        self._columns_widget = QWidget()
        cols = QHBoxLayout(self._columns_widget)
        cols.setSpacing(8)
        cols.setContentsMargins(0, 0, 0, 0)
        self._left_col = QVBoxLayout()
        self._left_col.setSpacing(8)
        self._left_col.setAlignment(Qt.AlignTop)
        self._right_col = QVBoxLayout()
        self._right_col.setSpacing(8)
        self._right_col.setAlignment(Qt.AlignTop)
        cols.addLayout(self._left_col, 1)
        cols.addLayout(self._right_col, 1)
        right.addWidget(self._columns_widget)
        self.run_btn = PushButton("Test", self)
        self.run_btn.setIcon(FluentIcon.PLAY)
        self.run_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.run_btn.clicked.connect(self.on_run)
        right.addWidget(self.run_btn)
        scroll_area.setWidget(container)
        main_layout.addWidget(scroll_area, 4)
        self._col_weight = [0, 0]
        # render form fields from yaml
        self.render_all_fields()
        self.routerInfoChanged.connect(self._update_csv_options)
        self._update_csv_options()
        # connect signals AFTER UI ready
        self.case_tree.clicked.connect(self.on_case_tree_clicked)
        self.case_tree.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        QTimer.singleShot(0, lambda: self.get_editable_fields(""))

    def _is_performance_case(self, abs_case_path) -> bool:
        """
        判断 abs_case_path 是否位于 test/performance 目录（任何层级都算）。
        不依赖工程根路径，只看路径片段。
        """
        logging.debug("Checking performance case path: %s", abs_case_path)
        if not abs_case_path:
            logging.debug("_is_performance_case: empty path -> False")
            return False
        try:
            from pathlib import Path
            p = Path(abs_case_path).resolve()
            # 检查父链中是否出现 .../test/performance
            for node in (p, *p.parents):
                if node.name == "performance" and node.parent.name == "test":
                    logging.debug("_is_performance_case: True")
                    return True
                logging.debug("_is_performance_case: False")
            return False
        except Exception as e:
            logging.error("_is_performance_case exception: %s", e)
            return False

    def _init_case_tree(self, root_dir: Path) -> None:
        self.fs_model = QFileSystemModel(self.case_tree)
        root_index = self.fs_model.setRootPath(str(root_dir))  # ← use return value
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
                    title="Error",
                    content="Failed to find config",
                    parent=self,
                    position=InfoBarPosition.TOP,
                ),
            )
            return {}
        try:
            load_config.cache_clear()
            config = load_config(refresh=True) or {}

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
                        lambda exc=exc: InfoBar.error(
                            title="Error",
                            content=f"Failed to write config: {exc}",
                            parent=self,
                            position=InfoBarPosition.TOP,
                        ),
                    )
            return config
        except Exception as exc:
            QTimer.singleShot(
                0,
                lambda exc=exc: InfoBar.error(
                    title="Error",
                    content=f"Failed to load config : {exc}",
                    parent=self,
                    position=InfoBarPosition.TOP,
                ),
            )
            return {}

    def _save_config(self):
        logging.debug("[save] path=%s data=%s", self.config_path, self.config)
        try:
            with self.config_path.open("w", encoding="utf-8") as f:
                yaml.safe_dump(self.config, f, allow_unicode=True, sort_keys=False, width=4096)
                logging.info("Configuration saved")
            self.config = self._load_config()
            QTimer.singleShot(
                0,
                lambda: InfoBar.success(
                    title="Hint",
                    content="Configuration has been saved",
                    parent=self,
                    position=InfoBarPosition.TOP,
                ),
            )
        except Exception as exc:
            logging.error("[save] failed: %s", exc)
            QTimer.singleShot(
                0,
                lambda exc=exc: InfoBar.error(
                    title="Error",
                    content=f"Failed to save config : {exc}",
                    parent=self,
                    position=InfoBarPosition.TOP,
                ),
            )

    def _get_application_base(self) -> Path:
        """获取应用根路径"""
        return Path(get_src_base()).resolve()

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

    def _load_router_wifi_info(self, name: str):
        cfg = self.config.get("router", {})
        if cfg.get("name") == name:
            self.router_ssid_2g = cfg.get("ssid_2g", f"{name}_2g")
            self.router_ssid_5g = cfg.get("ssid_5g", f"{name}_5g")
        else:
            self.router_ssid_2g = f"{name}_2g"
            self.router_ssid_5g = f"{name}_5g"

    def get_router_wifi_info(self):
        return (
            self.router_ssid_2g,
            self.router_ssid_5g,
        )

    def on_router_changed(self, name: str):
        self._load_router_wifi_info(name)
        self.ssid_2g_edit.setText(self.router_ssid_2g)
        self.ssid_5g_edit.setText(self.router_ssid_5g)
        self.routerInfoChanged.emit()

    def _update_csv_options(self):
        """根据路由器名称刷新 CSV 下拉框"""
        if not hasattr(self, "csv_combo"):
            return
        router_name = ""
        if hasattr(self, "router_name_combo"):
            router_name = self.router_name_combo.currentText().lower()
        base_dir = get_config_base() / "performance_test_csv"
        if "asus" in router_name:
            csv_dir = base_dir / "asus"
        elif "xiaomi" in router_name:
            csv_dir = base_dir / "xiaomi"
        else:
            csv_dir = None
        logging.debug("_update_csv_options router=%s dir=%s", router_name, csv_dir)
        with QSignalBlocker(self.csv_combo):
            self.csv_combo.clear()
            if csv_dir and csv_dir.exists():
                for csv_file in sorted(csv_dir.glob("*.csv")):
                    logging.debug("found csv: %s", csv_file)
                    # qfluentwidgets.ComboBox 在 Qt5 和 Qt6 下对 userData 的处理不一致，
                    # 直接通过 addItem(text, userData) 可能导致无法获取到数据。
                    # 因此先添加文本，再显式设置 UserRole 数据，确保 itemData 能正确返回文件路径。
                    self.csv_combo.addItem(csv_file.name)
                    idx = self.csv_combo.count() - 1
                    self.csv_combo.setItemData(idx, str(csv_file.resolve()))
                self.csv_combo.setCurrentIndex(-1)
        self.selected_csv_path = None

    def _estimate_group_weight(self, group: QWidget) -> int:
        """粗略估算分组高度：以输入型子控件数量为权重"""
        from PyQt5.QtWidgets import (
            QLineEdit, QComboBox, QTextEdit, QSpinBox, QDoubleSpinBox, QCheckBox
        )
        inputs = group.findChildren((QLineEdit, QComboBox, QTextEdit, QSpinBox, QDoubleSpinBox, QCheckBox))
        return max(1, len(inputs))

    def _add_group(self, group: QWidget, weight: int | None = None):
        """把 group 放到当前更“轻”的一列"""
        w = self._estimate_group_weight(group) if weight is None else weight
        ci = 0 if self._col_weight[0] <= self._col_weight[1] else 1
        (self._left_col if ci == 0 else self._right_col).addWidget(group)
        self._col_weight[ci] += w

    def render_all_fields(self):
        """
        自动渲染config.yaml中的所有一级字段。
        控件支持 LineEdit / ComboBox（可扩展 Checkbox）。
        字段映射到 self.field_widgets，方便后续操作。
        """
        for i, (key, value) in enumerate(self.config.items()):
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
                self._add_group(group)
                self.field_widgets["text_case"] = self.test_case_edit
                continue
            if key == "connect_type":
                group = QGroupBox("Control Type")
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
                self._add_group(group)
                # 初始化
                self.adb_device_edit.setText(value.get("adb", {}).get("device", ""))
                self.telnet_ip_edit.setText(value.get("telnet", {}).get("ip", ""))
                self.on_connect_type_changed(self.connect_type_combo.currentText())
                self.field_widgets["connect_type.type"] = self.connect_type_combo
                self.field_widgets["connect_type.adb.device"] = self.adb_device_edit
                self.field_widgets["connect_type.telnet.ip"] = self.telnet_ip_edit
                continue
            if key == "fpga":
                group = QGroupBox("FPGA")
                vbox = QVBoxLayout(group)
                self.fpga_chip_combo = ComboBox(self)
                self.fpga_chip_combo.addItems(RouterConst.FPGA_CONFIG.keys())
                self.fpga_if_combo = ComboBox(self)
                self.fpga_if_combo.addItems(RouterConst.INTERFACE_CONFIG)
                chip_default, if_default = "W2", "SDIO"
                if isinstance(value, str) and "_" in value:
                    chip_default, if_default = value.split("_", 1)
                    chip_default = chip_default.upper()
                    if_default = if_default.upper()
                self.fpga_chip_combo.setCurrentText(chip_default)
                self.fpga_if_combo.setCurrentText(if_default)
                vbox.addWidget(QLabel("Chip:"))
                vbox.addWidget(self.fpga_chip_combo)
                vbox.addWidget(QLabel("Interface:"))
                vbox.addWidget(self.fpga_if_combo)
                self._add_group(group)
                self.field_widgets["fpga"] = group
                continue
            if key == "rf_solution":
                group = QGroupBox("Attenuator")
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
                xin_box.addWidget(QLabel("SH - New Wi-Fi full-wave anechoic chamber "))
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
                rc4_box.addWidget(QLabel("IP address :"));
                rc4_box.addWidget(self.rc4_ip_edit)
                vbox.addWidget(self.rc4_group)

                # ========== ③ RADIORACK-4-220 参数区 ==========
                self.rack_group = QWidget()
                rack_box = QVBoxLayout(self.rack_group)
                rack_cfg = value.get("RADIORACK-4-220", {})
                self.rack_ip_edit = LineEdit(self)
                self.rack_ip_edit.setPlaceholderText("ip_address")
                self.rack_ip_edit.setText(rack_cfg.get("ip_address", ""))
                rack_box.addWidget(QLabel("IP address :"))
                rack_box.addWidget(self.rack_ip_edit)
                vbox.addWidget(self.rack_group)

                # -------- 通用字段：step --------
                self.rf_step_edit = LineEdit(self)
                self.rf_step_edit.setPlaceholderText("rf step; such as  0,50")
                self.rf_step_edit.setText(",".join(map(str, value.get("step", []))))
                vbox.addWidget(QLabel("Step:"))
                vbox.addWidget(self.rf_step_edit)

                # ---- 加入表单 & 初始化可见性 ----
                self._add_group(group)
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
                group = QGroupBox("RVR Config")  # 外层分组
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

                self.iperf_path_edit = LineEdit(self)
                self.iperf_path_edit.setPlaceholderText("iperf path (DUT)")
                self.iperf_path_edit.setText(value.get("iperf", {}).get("path", ""))
                iperf_box.addWidget(QLabel("Path:"))
                iperf_box.addWidget(self.iperf_path_edit)

                self.iperf_server_edit = LineEdit(self)
                self.iperf_server_edit.setPlaceholderText("iperf -s command")
                self.iperf_server_edit.setText(value.get("iperf", {}).get("server_cmd", ""))
                iperf_box.addWidget(QLabel("Server cmd:"))
                iperf_box.addWidget(self.iperf_server_edit)

                self.iperf_client_edit = LineEdit(self)
                self.iperf_client_edit.setPlaceholderText("iperf -c command")
                self.iperf_client_edit.setText(value.get("iperf", {}).get("client_cmd", ""))
                iperf_box.addWidget(QLabel("Client cmd:"))
                iperf_box.addWidget(self.iperf_client_edit)
                vbox.addWidget(self.rvr_iperf_group)

                # ----- ixchariot 子组 -----
                self.rvr_ix_group = QWidget()
                ix_box = QVBoxLayout(self.rvr_ix_group)
                # CSV 选择框
                vbox.addWidget(QLabel("Select config csv file"))
                self.csv_combo = ComboBox(self)
                self.csv_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                self.csv_combo.setEnabled(False)
                # currentIndexChanged 在选择相同项时不会触发，activated 每次用户点击都会触发
                self.csv_combo.currentIndexChanged.connect(self.on_csv_changed)
                self.csv_combo.activated.connect(self.on_csv_activated)
                vbox.addWidget(self.csv_combo)

                self.ix_path_edit = LineEdit(self)
                self.ix_path_edit.setPlaceholderText("IxChariot path")
                self.ix_path_edit.setText(value.get("ixchariot", {}).get("path", ""))
                ix_box.addWidget(self.ix_path_edit)
                vbox.addWidget(self.rvr_ix_group)

                # ----- 其它通用字段 -----
                self.repeat_combo = LineEdit()
                self.repeat_combo.setText(str(value.get("repeat", 0)))

                vbox.addWidget(QLabel("Repeat:"))
                vbox.addWidget(self.repeat_combo)
                self.rvr_threshold_edit = LineEdit()
                self.rvr_threshold_edit.setPlaceholderText("throughput threshold")
                self.rvr_threshold_edit.setText(str(value.get("throughput_threshold", 0)))

                vbox.addWidget(QLabel("Throughput threshold:"))
                vbox.addWidget(self.rvr_threshold_edit)
                # 加入表单
                self._add_group(group)

                # 字段注册（供启用/禁用和收集参数用）
                self.field_widgets["rvr.tool"] = self.rvr_tool_combo
                self.field_widgets["rvr.iperf.path"] = self.iperf_path_edit
                self.field_widgets["rvr.iperf.server_cmd"] = self.iperf_server_edit
                self.field_widgets["rvr.iperf.client_cmd"] = self.iperf_client_edit
                self.field_widgets["rvr.ixchariot.path"] = self.ix_path_edit
                self.field_widgets["rvr.repeat"] = self.repeat_combo
                self.field_widgets["rvr.throughput_threshold"] = self.rvr_threshold_edit
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
                self.corner_step_edit.setPlaceholderText("step; such as 0,361")
                self.corner_step_edit.setText(",".join(map(str, value.get("step", []))))

                vbox.addWidget(QLabel("IP address:"))
                vbox.addWidget(self.corner_ip_edit)
                vbox.addWidget(QLabel("Step:"))
                vbox.addWidget(self.corner_step_edit)

                # 加入表单
                self._add_group(group)

                # 注册控件（用于启用/禁用、保存回 YAML）
                self.field_widgets["corner_angle.ip_address"] = self.corner_ip_edit
                self.field_widgets["corner_angle.step"] = self.corner_step_edit
                continue  # 跳过后面的通用处理
            if key == "router":
                group = QGroupBox("Router")
                vbox = QVBoxLayout(group)

                self.router_name_combo = ComboBox(self)
                self.router_name_combo.addItems(router_list.keys())
                self.router_name_combo.setCurrentText(value.get("name", "xiaomiax3000"))
                self.ssid_2g_edit = LineEdit(self)
                self.ssid_2g_edit.setPlaceholderText("2.4G SSID")
                self.ssid_2g_edit.setText(value.get("ssid_2g", ""))
                self.ssid_5g_edit = LineEdit(self)
                self.ssid_5g_edit.setPlaceholderText("5G SSID")
                self.ssid_5g_edit.setText(value.get("ssid_5g", ""))

                vbox.addWidget(QLabel("Name:"))
                vbox.addWidget(self.router_name_combo)
                vbox.addWidget(QLabel("SSID 2G:"))
                vbox.addWidget(self.ssid_2g_edit)
                vbox.addWidget(QLabel("SSID 5G:"))
                vbox.addWidget(self.ssid_5g_edit)
                self._add_group(group)
                # 注册控件
                self.field_widgets["router.name"] = self.router_name_combo
                self.field_widgets["router.ssid_2g"] = self.ssid_2g_edit
                self.field_widgets["router.ssid_5g"] = self.ssid_5g_edit
                self.router_name_combo.currentTextChanged.connect(self.on_router_changed)
                self.on_router_changed(self.router_name_combo.currentText())
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
                self._add_group(group)

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
            self._add_group(group)
            self.field_widgets[key] = edit

    def populate_case_tree(self, root_dir):
        """
        遍历 test 目录，只将 test_ 开头的 .py 文件作为节点加入树结构。
        其它 py 文件不显示。
        """
        from PyQt5.QtGui import QStandardItemModel, QStandardItem
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(['Pls select test case '])  # 可选，设置表头显示

        # 正确设置根节点为 'test' 或实际目录名
        root_item = QStandardItem(os.path.basename(root_dir))
        root_item.setData(root_dir)

        def add_items(parent_item, dir_path):
            for fname in sorted(os.listdir(dir_path)):
                logging.debug("fname %s", fname)
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
        try:
            display_path = os.path.relpath(path, base)
        except ValueError:
            display_path = path
        logging.debug("on_case_tree_clicked path=%s display=%s", path, display_path)
        logging.debug("on_case_tree_clicked is_performance=%s", self._is_performance_case(path))
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
        self.get_editable_fields(path)

    def _compute_editable_info(self, case_path) -> EditableInfo:
        """根据用例名与路径返回可编辑字段以及相关 UI 使能状态"""
        basename = os.path.basename(case_path)
        logging.debug("testcase name %s", basename)
        logging.debug("_compute_editable_info case_path=%s basename=%s", case_path, basename)
        peak_keys = {
            "rvr",
            "rvr.tool",
            "rvr.iperf.path",
            "rvr.iperf.server_cmd",
            "rvr.iperf.client_cmd",
            "rvr.ixchariot.path",
            "rvr.repeat",
        }
        rvr_keys = peak_keys | {
            "rvr.throughput_threshold",
        }
        info = EditableInfo()
        # 永远让 connect_type 可编辑
        info.fields |= {
            "connect_type.type",
            "connect_type.adb.device",
            "connect_type.telnet.ip",
            "connect_type.telnet.wildcard",
            "router.name",
            "router.ssid_2g",
            "router.ssid_5g",
            "serial_port.status",
            "serial_port.port",
            "serial_port.baud",
            "fpga",
        }
        if basename == "test_compatibility.py":
            info.fields |= {"Power relay"}
        if basename == "test_wifi_peak_throughput.py":
            info.fields |= peak_keys
        if self._is_performance_case(case_path):
            info.fields |= rvr_keys
            info.enable_csv = True
            info.enable_rvr_wifi = True
        if "rvo" in basename:
            info.fields |= {
                "corner_angle",
                "corner_angle.ip_address",
                "corner_angle.step",
            }
        if "rvr" in basename:
            info.fields |= {
                "rf_solution.step",
                "rf_solution.model",
                "rf_solution.RC4DAT-8G-95.idVendor",
                "rf_solution.RC4DAT-8G-95.idProduct",
                "rf_solution.RC4DAT-8G-95.ip_address",
                "rf_solution.RADIORACK-4-220.ip_address",
            }
            # 根据路径判断是否需要启用 CSV 与 RVR WiFi 配置
            base = Path(self._get_application_base())
            perf_dir = (base / "test" / "performance").resolve()
            case_abs = Path(case_path).resolve() if case_path else None
            logging.debug("_compute_editable_info perf_dir=%s case_abs=%s", perf_dir, case_abs)
            if case_abs and perf_dir in case_abs.parents:
                info.enable_csv = True
            info.enable_rvr_wifi = True
            logging.debug(
            "_compute_editable_info enable_csv=%s enable_rvr_wifi=%s",
            info.enable_csv,
            info.enable_rvr_wifi,
        )
        # 如果你需要所有字段都可编辑，直接 return EditableInfo(set(self.field_widgets.keys()), True, True)
        return info

    def get_editable_fields(self, case_path) -> EditableInfo:
        """选中用例后控制字段可编辑性并返回相关信息"""
        logging.debug("get_editable_fields case_path=%s", case_path)
        if self._refreshing:
            # 极少见：递归进入，直接丢弃
            logging.debug("get_editable_fields: refreshing, return empty")
            return EditableInfo()

        # ---------- 进入刷新 ----------
        self._refreshing = True
        self.case_tree.setEnabled(False)  # 锁定用例树
        self.setUpdatesEnabled(False)  # 暂停全局重绘

        try:
            info = self._compute_editable_info(case_path)
            logging.debug("get_editable_fields enable_csv=%s", info.enable_csv)
            # 若 csv 下拉框尚未创建，则视为不支持 CSV 功能
            if info.enable_csv and not hasattr(self, "csv_combo"):
                info.enable_csv = False
            self.set_fields_editable(info.fields)
        finally:
            # ---------- 刷新结束 ----------
            self.setUpdatesEnabled(True)
            self.case_tree.setEnabled(True)
            self._refreshing = False

        main_window = self.window()
        if hasattr(main_window, "setCurrentIndex"):
            main_window.setCurrentIndex(main_window.case_config_page)

        if info.enable_rvr_wifi:
            ssid = ""
            passwd = ""
            ssid_widget = self.field_widgets.get("router.ssid")
            if isinstance(ssid_widget, LineEdit):
                ssid = ssid_widget.text()
            passwd_widget = self.field_widgets.get("router.wpa_passwd")
            if isinstance(passwd_widget, LineEdit):
                passwd = passwd_widget.text()
            if hasattr(main_window, "show_rvr_wifi_config"):
                main_window.show_rvr_wifi_config()
        else:
            if hasattr(main_window, "hide_rvr_wifi_config"):
                main_window.hide_rvr_wifi_config()
        if hasattr(self, "csv_combo"):
            if info.enable_csv:
                self.csv_combo.setEnabled(True)
            else:
                with QSignalBlocker(self.csv_combo):
                    self.csv_combo.setCurrentIndex(-1)
                self.csv_combo.setEnabled(False)
                self.selected_csv_path = None
        else:
            self.selected_csv_path = None
            logging.debug("csv_combo disabled")
        # 若用户在刷新过程中又点了别的用例，延迟 0 ms 处理它
        if self._pending_path:
            path = self._pending_path
            self._pending_path = None
            QTimer.singleShot(0, lambda: self.get_editable_fields(path))
        return info

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

    def on_csv_activated(self, index: int) -> None:
        """用户手动点击同一项时也需要重新加载"""
        logging.debug("on_csv_activated index=%s", index)
        self.on_csv_changed(index, force=True)

    def on_csv_changed(self, index: int, force: bool = False) -> None:
        """记录当前选择的 CSV 文件路径并发出信号"""
        if index < 0:
            self.selected_csv_path = None
            return
        # 明确使用 UserRole 获取数据，避免在不同 Qt 版本下默认角色不一致
        data = self.csv_combo.itemData(index)
        logging.debug("on_csv_changed index=%s data=%s", index, data)
        new_path = str(Path(data).resolve()) if data else None
        if not force and new_path == self.selected_csv_path:
            return
        self.selected_csv_path = new_path
        logging.debug("selected_csv_path=%s", self.selected_csv_path)
        self.csvFileChanged.emit(self.selected_csv_path or "")

    def on_run(self):
        logging.info(
            "[on_run] start case=%s csv=%s config=%s",
            self.field_widgets['text_case'].text().strip(),
            self.selected_csv_path,
            self.config,
        )
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
            elif isinstance(widget, QCheckBox):
                ref[leaf] = widget.isChecked()
        chip = self.fpga_chip_combo.currentText()
        interface = self.fpga_if_combo.currentText()
        self.config["fpga"] = f"{chip}_{interface}"
        base = Path(self._get_application_base())
        case_path = self.field_widgets["text_case"].text().strip()
        # 默认将现有路径解析成 POSIX 字符串
        case_path = Path(case_path).as_posix() if case_path else ""
        abs_case_path = (
            (base / case_path).resolve().as_posix() if case_path else ""
        )
        logging.debug("[on_run] before performance check abs_case_path=%s csv=%s", abs_case_path,
                      self.selected_csv_path)
        # 先将当前用例路径及 CSV 选择写入配置
        self.config["text_case"] = case_path
        if self.selected_csv_path:
            base_cfg = get_config_base()
            try:
                rel_csv = os.path.relpath(Path(self.selected_csv_path).resolve(), base_cfg)
            except ValueError:
                rel_csv = Path(self.selected_csv_path).resolve().as_posix()
            self.config["csv_path"] = Path(rel_csv).as_posix()
        else:
            self.config.pop("csv_path", None)
        logging.debug("[on_run] after performance check abs_case_path=%s csv=%s", abs_case_path, self.selected_csv_path)
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
            # 更新配置中的用例路径
        self.config["text_case"] = case_path
        # 保存配置
        logging.debug("[on_run] before _save_config")
        self._save_config()
        logging.debug("[on_run] after _save_config")
        try:
            if self._is_performance_case(abs_case_path) and not getattr(self, "selected_csv_path", None):
                try:
                    # 如果你工程里有 InfoBar（QFluentWidgets），用这个更友好
                    InfoBar.warning(
                        title="Hint",
                        content="This is a performance test. Please select a CSV file before running.",
                        parent=self,
                        position=InfoBarPosition.TOP,
                        duration=3000
                    )
                except Exception:
                    # 没有 InfoBar 就退化到标准对话框
                    from PyQt5.QtWidgets import QMessageBox
                    QMessageBox.warning(
                        self,
                        "Hint",
                        "This is a performance test.\nPlease select a CSV file before running."
                    )
                return
        except Exception:
            # 兜底避免因为路径解析等异常导致崩溃
            pass

        if os.path.isfile(abs_case_path) and abs_case_path.endswith(".py"):
            self.on_run_callback(abs_case_path, case_path, self.config)
        else:
            InfoBar.warning(
                title="Hint",
                content="Pls select a test case before test",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=1800
            )
