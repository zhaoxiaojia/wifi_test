# src/ui/view/config/function_config_form.py
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QButtonGroup, QListWidget, QTableWidget,
                             QTableWidgetItem, QSpacerItem,
                             QListWidgetItem, QAbstractItemView, QCheckBox, QSizePolicy, QLabel, QFileDialog,
                             QMessageBox, QPushButton, QHeaderView)
from qfluentwidgets import PushButton, CardWidget, ComboBox, FluentIcon as FIcon
from pathlib import Path
from PyQt5.QtCore import Qt, QEvent, QSize
from PyQt5.QtGui import QFont, QColor, QPalette
import yaml
import re, os
from pathlib import Path
import pandas as pd
from datetime import datetime
from src.util.constants import get_config_base

# 在 config_function.py 顶部添加
from PyQt5.QtWidgets import QStyledItemDelegate, QApplication
from PyQt5.QtCore import Qt, QRect
from PyQt5.QtGui import QPainter, QColor
from src.ui.view import FormListPage


class FunctionConfigForm(QWidget):
    """STB 功能测试配置表单组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.test_script_items = []

        self.all_rows = []
        self.priority_options = set()
        self.tag_options = set()
        self.module_options = set()
        # 新增test_type相关变量
        self.test_type_options = set()
        self.current_test_type = "Typical Channels"

        self.setup_ui()
        self.load_test_case_files()

        self.priority_combo.currentTextChanged.connect(self.apply_filters)
        self.tag_combo.currentTextChanged.connect(self.apply_filters)
        self.module_combo.currentTextChanged.connect(self.apply_filters)
        self.test_type_combo.currentTextChanged.connect(self.apply_filters)  # 新增
        self.select_all_checkbox.stateChanged.connect(self._on_select_all_changed)
        self.reset_btn.clicked.connect(self.on_reset_clicked)

    def setup_ui(self):
        """Set up the UI."""
        self.setObjectName("functionConfigForm")
        # 主布局：垂直布局，填满整个 widget
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ===== 使用 CardWidget 包裹内容以匹配 compatibility 风格 =====
        card = CardWidget(self)
        card.setObjectName("functionConfigCard")  # 可选：用于自定义样式
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)  # 内边距，与 compatibility 风格一致
        card_layout.setSpacing(12)

        # 标题
        title_label = QLabel("Function Case Selection")
        title_label.setStyleSheet("font-size: 10pt; font-weight: normal; color: #e0e0e0;")
        title_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        card_layout.addWidget(title_label)

        # ===== 过滤栏：专业优化版 =====
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(8)  # 缩小间距，更紧凑
        filter_layout.setContentsMargins(0, 10, 0, 10)  # 上下留白

        # Filter 总标签
        filter_label = QLabel("Filter:", self)
        filter_label.setFixedWidth(80)
        filter_label.setFixedHeight(25)
        LABEL_STYLE = """
            background-color: #2a2a2a;
            border: 1px solid #555;
            border-radius: 4px;
            padding: 3px 5px;
            color: white;
            font-size: 9pt;
        """
        filter_label.setStyleSheet(LABEL_STYLE)
        filter_layout.addWidget(filter_label)
        spacer1 = QSpacerItem(20, 0, QSizePolicy.Fixed, QSizePolicy.Minimum)
        filter_layout.addItem(spacer1)

        # Priority 组合
        priority_label = QLabel("Priority:", self)
        priority_label.setFixedWidth(80)
        priority_label.setFixedHeight(25)
        priority_label.setStyleSheet(LABEL_STYLE)
        filter_layout.addWidget(priority_label)

        self.priority_combo = ComboBox(self)
        self.priority_combo.addItems(["All"])
        self.priority_combo.setFixedWidth(80)
        self.priority_combo.setFixedHeight(25)
        self.priority_combo.setStyleSheet("""
            background-color: #2a2a2a;
            border: 1px solid #555;
            border-radius: 4px;
            padding: 3px;
            color: white;
            font-size: 9pt;
            text-align: left;
        """)
        filter_layout.addWidget(self.priority_combo)
        spacer2 = QSpacerItem(20, 0, QSizePolicy.Fixed, QSizePolicy.Minimum)
        filter_layout.addItem(spacer2)

        # Test_Module 组合
        module_label = QLabel("Module:", self)
        module_label.setStyleSheet(LABEL_STYLE)
        module_label.setFixedWidth(80)
        module_label.setFixedHeight(25)
        filter_layout.addWidget(module_label)

        self.module_combo = ComboBox(self)
        self.module_combo.addItems(["All"])
        self.module_combo.setFixedWidth(120)
        self.module_combo.setFixedHeight(25)
        self.module_combo.setStyleSheet("""
            background-color: #2a2a2a;
            border: 1px solid #555;
            border-radius: 4px;
            padding: 3px;
            color: white;
            font-size: 9pt;
            text-align: left;
        """)
        filter_layout.addWidget(self.module_combo)
        spacer3 = QSpacerItem(20, 0, QSizePolicy.Fixed, QSizePolicy.Minimum)
        filter_layout.addItem(spacer3)

        # Tag 组合
        tag_label = QLabel("Tag:", self)
        tag_label.setStyleSheet(LABEL_STYLE)
        tag_label.setFixedWidth(80)
        tag_label.setFixedHeight(25)
        filter_layout.addWidget(tag_label)

        self.tag_combo = ComboBox(self)
        self.tag_combo.addItems(["All"])
        self.tag_combo.setFixedWidth(120)
        self.tag_combo.setFixedHeight(25)
        self.tag_combo.setStyleSheet("""
            background-color: #2a2a2a;
            border: 1px solid #555;
            border-radius: 4px;
            padding: 3px;
            color: white;
            font-size: 9pt;
            text-align: left;
        """)
        filter_layout.addWidget(self.tag_combo)

        spacer4 = QSpacerItem(20, 0, QSizePolicy.Fixed, QSizePolicy.Minimum)
        filter_layout.addItem(spacer4)

        # ===== 新增：Test Type 组合 =====
        test_type_label = QLabel("Test Type:", self)
        test_type_label.setStyleSheet(LABEL_STYLE)
        test_type_label.setFixedWidth(100)
        test_type_label.setFixedHeight(25)
        filter_layout.addWidget(test_type_label)

        self.test_type_combo = ComboBox(self)
        self.test_type_combo.addItems(["Typical Channels", "Full Channels"])
        self.test_type_combo.setFixedWidth(140)
        self.test_type_combo.setFixedHeight(25)
        self.test_type_combo.setStyleSheet("""
            background-color: #2a2a2a;
            border: 1px solid #555;
            border-radius: 4px;
            padding: 3px;
            color: white;
            font-size: 9pt;
            text-align: left;
        """)
        filter_layout.addWidget(self.test_type_combo)

        spacer_test_type = QSpacerItem(20, 0, QSizePolicy.Fixed, QSizePolicy.Minimum)
        filter_layout.addItem(spacer_test_type)

        # Select All button
        self.select_all_checkbox = QCheckBox("Select All", self)
        self.select_all_checkbox.setChecked(True)
        filter_layout.addWidget(self.select_all_checkbox)
        self.select_all_checkbox.setFixedWidth(100)
        self.select_all_checkbox.setFixedHeight(25)
        spacer = QSpacerItem(12, 0, QSizePolicy.Fixed, QSizePolicy.Minimum)
        filter_layout.addItem(spacer)

        # --- Reset 按钮 ---
        self.reset_btn = PushButton("Reset")
        self.reset_btn.setIcon(FIcon.SYNC.icon())
        self.reset_btn.setFixedSize(80, 20)  # 宽高
        self.reset_btn.setPalette(QPalette(Qt.white))

        # --- Save Test Plan 按钮 ---
        self.save_plan_btn = PushButton("Save Test Plan")
        self.save_plan_btn.setIcon(FIcon.SAVE.icon())
        self.save_plan_btn.setFixedSize(120, 20)

        # --- Load Test Plan 按钮 ---
        self.load_plan_btn = PushButton("Load Test Plan")
        self.load_plan_btn.setIcon(FIcon.FOLDER.icon())
        self.load_plan_btn.setFixedSize(120, 20)
        for btn in [self.reset_btn, self.save_plan_btn, self.load_plan_btn]:
            btn.setIconSize(QSize(16, 16))
            btn.setFixedHeight(28)
            btn.setContentsMargins(6, 0, 6, 0)

        self.reset_btn.setFixedWidth(90)
        self.save_plan_btn.setFixedWidth(160)
        self.load_plan_btn.setFixedWidth(160)

        filter_layout.addWidget(self.reset_btn)
        spacer_right6 = QSpacerItem(20, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
        filter_layout.addItem(spacer_right6)

        filter_layout.addWidget(self.save_plan_btn)
        filter_layout.addWidget(self.load_plan_btn)

        card_layout.addLayout(filter_layout)

        # ===== 表格区域 =====
        headers = ["TCID", "Priority", "Tag", "Module", "Description", "Script"]
        self.list_widget = FormListPage(
            headers=headers,
            rows=[],  # 初始空
            checkable=True,  # ← 启用勾选列！
            parent=self
        )
        self.list_widget.setSizePolicy(
            self.list_widget.sizePolicy().horizontalPolicy(),
            self.list_widget.sizePolicy().verticalPolicy()
        )
        card_layout.addWidget(self.list_widget, 1)

        # === 新增：通过 .table 访问内部 TableWidget ===
        table = self.list_widget.table  # ← 关键！获取内部表格
        header = table.horizontalHeader()

        # 允许用户拖动调整列宽
        header.setSectionResizeMode(QHeaderView.Interactive)

        # 设置各列初始宽度
        initial_widths = {
            "TCID": 200,
            "Priority": 60,
            "Tag": 160,
            "Module": 160,
            "Description": 680,  # 给描述留足空间
            "Script": 500
        }

        for i, col_name in enumerate(headers):
            width = initial_widths.get(col_name, 100)
            table.setColumnWidth(i + (1 if self.list_widget.checkable else 0), width)

        # 让最后一列自动拉伸（可选）
        header.setStretchLastSection(True)

        # 将卡片添加到主布局
        main_layout.addWidget(card)

        self.save_plan_btn.clicked.connect(self.on_save_plan_clicked)
        self.load_plan_btn.clicked.connect(self.on_load_plan_clicked)

    def load_test_case_files(self, target_dirs=None):
        """
        从指定文件夹的 test_config.yaml 中加载测试用例。
        此函数假设每个 target_dir 下都有一个 test_config.yaml 文件，
        且该文件的 'scripts' 列表完整定义了该目录下的所有用例。

        Args:
            target_dirs (list[str], optional): 要加载的目标文件夹列表（相对于 test/function/）。
                                              如果为 None，则尝试加载所有直接子目录。
        """
        from pathlib import Path
        import yaml

        current_file = Path(__file__).resolve()
        test_project_root = current_file.parent.parent.parent.parent / "test" / "function"

        # --- 确定要加载的目录 ---
        if not test_project_root.exists():
            # Function test cases were removed during repo slim-down; keep UI alive.
            dirs_to_load = []
        elif target_dirs is None:
            # 回退逻辑：加载 function 下所有直接子目录
            dirs_to_load = [d for d in test_project_root.iterdir() if d.is_dir()]
        else:
            # 加载指定的目录，并进行路径规范化
            normalized_dirs = []
            for d in target_dirs:
                # 将 "android", "./android", "android/" 等统一规范化为 "android"
                clean_dir_name = Path(d).name
                normalized_dirs.append(clean_dir_name)
            dirs_to_load = [test_project_root / d for d in normalized_dirs]

        all_rows = []
        self.priority_options.clear()
        self.tag_options.clear()
        self.module_options.clear()
        self.test_type_options.clear()

        # --- 遍历每个目标目录，读取其 YAML 配置 ---
        for folder_path in dirs_to_load:
            if not folder_path.exists():
                continue

            config_path = folder_path / "test_config.yaml"
            if not config_path.exists():
                continue

            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
            except Exception as e:
                continue

            scripts = config.get("scripts", [])
            if not isinstance(scripts, list):
                continue

            # --- 处理 YAML 中的每个脚本条目 ---
            for script in scripts:
                if not isinstance(script, dict):
                    continue

                # 提取字段
                tcid = str(script.get("TCID", ""))
                priority = str(script.get("priority", "P2"))
                module = str(script.get("module", ""))
                description = str(script.get("description", ""))
                # 关键：script_path 是相对于 test/function/ 的路径
                script_path = str(script.get("path", ""))
                tag = str(script.get("Tag", ""))

                # 跳过无效行
                if not script_path:
                    continue

                # 收集筛选选项
                if priority:
                    self.priority_options.add(priority)
                if tag:
                    self.tag_options.add(tag)
                if module:
                    self.module_options.add(module)

                # 构建行数据
                row_data = {
                    "TCID": tcid,
                    "Priority": priority,
                    "Module": module,
                    "Tag": tag,
                    "Description": description,
                    "Script": script_path,  # 这个路径将用于后续执行和保存计划
                    "_checked": True
                }
                all_rows.append(row_data)

        # --- 更新 UI ---
        self.all_rows = all_rows
        self.list_widget.set_rows(all_rows)

        # 更新筛选下拉框
        self.priority_combo.clear()
        self.priority_combo.addItems(["All"] + sorted(self.priority_options))
        self.module_combo.clear()
        self.module_combo.addItems(["All"] + sorted(self.module_options))
        self.tag_combo.clear()
        self.tag_combo.addItems(["All"] + sorted(self.tag_options))
        # Test Type 下拉框已经在 setup_ui 中初始化

    def get_case_config(self) -> dict:
        """返回所有被勾选的脚本路径"""
        selected_paths = []
        for row in self.list_widget.rows:
            if row.get("_checked", False):  # ← 关键：读 _checked 字段
                selected_paths.append(row["Script"])
        return {"selected_files": selected_paths}

    def load_test_files(self):
        """从 test_config.yaml 加载测试脚本"""
        self.test_script_items = []
        # self.file_list.clear()
        # 定位到 project 目录下的 test_config.yaml
        current_file = Path(__file__).resolve()
        src_dir = Path(__file__).parent.parent.parent.parent.resolve()
        config_path = (src_dir / "test" / "function" / "test_config.yaml").resolve()
        # config_path = Path(r"D:\wifi_test12\src\test\function\test_config.yaml")
        if not config_path.exists():
            item = QListWidgetItem("❌ test_config.yaml not found!")
            self.file_list.addItem(item)
            return
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
        except Exception as e:
            item = QListWidgetItem(f"❌ Load Error: {e}")
            self.file_list.addItem(item)
            return
        scripts = config.get("scripts", [])
        self.all_script_items = []  # 保存所有脚本元数据，用于动态过滤
        if not isinstance(scripts, list):
            item = QListWidgetItem("❌ 'scripts' is not a list in test_config.yaml!")
            self.file_list.addItem(item)
            return
        for idx, script in enumerate(scripts):
            if not isinstance(script, dict):
                continue  # 跳过非字典项
            path = script.get("path", "").strip()
            priority = script.get("priority", "P2")
            # === 关键修改：读取 'suite' 字段（单数），并转为 set ===
            suite_name = script.get("suite", "")  # 注意：是 'suite' 不是 'suites'
            suites_set = {suite_name} if suite_name else set()
            # ✅ 增加路径有效性检查
            if not path or not path.endswith(".py") or not path.startswith("stb/"):
                continue

            clean_path = path.replace("\\", '/')
            display_path = f'function/{clean_path}'
            meta = {
                'display_path': display_path,
                'priority': priority,
                'suites': suites_set,  # 用于后续过滤
                'original_path': path
            }
            self.all_script_items.append(meta)
        self.apply_filters()

    def get_config(self) -> dict:
        # 获取优先级
        priority = "All"
        for btn in self.priority_buttons.buttons():
            if btn.isChecked():
                priority = btn.text()
                break
        # 获取选中的模块
        selected_modules = []
        for cb in self.module_checkboxes:
            if cb.isChecked():
                selected_modules.append(cb.text())
        # 获取选中的文件
        selected_files = []
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item.checkState() == Qt.Checked:
                selected_files.append(item.text())
        return {
            "test_priority": priority,
            "wifi_modules": selected_modules,
            "selected_files": selected_files,
        }

    def set_config(self, config: dict):
        # 设置优先级
        target_priority = config.get("test_priority", "All")
        for btn in self.priority_buttons.buttons():
            if btn.text() == target_priority:
                btn.setChecked(True)
                break
        # 模块和文件列表暂不反向设置（可按需扩展）
        pass

    def on_load_plan_clicked(self):
        """槽函数：当 'Load Test Plan' 按钮被点击时调用"""
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        from pathlib import Path
        import pandas as pd

        # 1. 确定默认打开目录
        default_dist_dir = get_config_base()
        if not default_dist_dir.exists():
            default_dist_dir = Path.home()

        # 2. 打开文件选择对话框
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Test Plan",
            str(default_dist_dir),
            "Excel Files (*.xlsx)"
        )
        if not file_path:
            return

        try:
            # 3. 读取 Excel 文件
            df = pd.read_excel(file_path)

            # 获取脚本路径
            selected_script_paths = []
            test_type_from_file = "All"  # 默认值

            if "Script Path" in df.columns:
                selected_script_paths = df["Script Path"].dropna().astype(str).tolist()

            # 获取Test Type（如果存在）
            if "Test Type" in df.columns and not df["Test Type"].isna().all():
                # 取第一个非空值作为test type
                test_type_series = df["Test Type"].dropna()
                if not test_type_series.empty:
                    test_type_from_file = str(test_type_series.iloc[0])

            # 4. 更新Test Type ComboBox
            if test_type_from_file in ["Typical Channels", "Full Channels"]:
                self.test_type_combo.setCurrentText(test_type_from_file)

            # 5. 先将所有行设为未勾选
            for row in self.all_rows:
                row["_checked"] = False

            # 6. 根据 Excel 内容勾选匹配的行
            found_count = 0
            selected_set = set(selected_script_paths)
            for row in self.all_rows:
                if row["Script"] in selected_set:
                    row["_checked"] = True
                    found_count += 1

            # 7. 刷新 UI（应用当前筛选条件 + 更新勾选状态）
            self.apply_filters()

            # 8. 保存最后加载的路径
            config_base = get_config_base()
            config_base.mkdir(exist_ok=True)
            last_plan_file = config_base / "last_function_plan.txt"
            with open(last_plan_file, 'w', encoding='utf-8') as f:
                f.write(str(Path(file_path).resolve()))

            # 9. 用户反馈
            QMessageBox.information(
                self,
                "Load Successful",
                f"Successfully loaded {found_count} out of {len(selected_script_paths)} test cases\n"
                f"Test Type: {test_type_from_file}\n"
                f"From: {file_path}"
            )

        except Exception as e:
            error_msg = f"Failed to load test plan: {e}"
            QMessageBox.critical(self, "Load Error", error_msg)

    def apply_filters(self):
        """根据ComboBox的选择过滤显示行"""
        selected_priority = self.priority_combo.currentText()
        selected_module = self.module_combo.currentText()
        selected_tag = self.tag_combo.currentText()
        selected_test_type = self.test_type_combo.currentText()

        # 保存当前test type选择
        self.current_test_type = selected_test_type

        filtered_rows = []
        for row in self.all_rows:
            # Priority 过滤
            if selected_priority != "All" and row["Priority"] != selected_priority:
                continue
            # Tag 过滤
            if selected_tag != "All" and row["Tag"] != selected_tag:
                continue
            # Module 过滤
            if selected_module != "All" and row["Module"] != selected_module:
                continue
            # Test Type 过滤（如果有Test_Type字段）
            if selected_test_type != "All" and "Test_Type" in row:
                if row["Test_Type"] != selected_test_type:
                    continue
            filtered_rows.append(row)

        # 直接更新 FormListPage
        self.list_widget.set_rows(filtered_rows)

    def on_save_plan_clicked(self):
        """槽函数：当 'Save Test Plan' 按钮被点击时调用"""
        # 1. 收集当前所有被勾选的完整行数据
        selected_rows = []
        for row in self.list_widget.rows:
            if row.get("_checked", False):
                # 提取所有需要的字段，保持与 UI 列一致
                # 修改字段顺序：将Test Type放在Priority之后、Tag之前
                selected_rows.append({
                    "TCID": row.get("TCID", ""),
                    "Priority": row.get("Priority", ""),
                    "Test Type": self.current_test_type,  # 移动到这里：Priority之后
                    "Tag": row.get("Tag", ""),  # Tag在Test Type之后
                    "Module": row.get("Module", ""),
                    "Description": row.get("Description", ""),
                    "Script Path": row.get("Script", ""),
                })

        if not selected_rows:
            return

        # 2. 打开文件保存对话框
        default_dist_dir = get_config_base()
        default_dist_dir.mkdir(exist_ok=True)
        default_filename = f"Function_test_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        default_filepath = default_dist_dir / default_filename

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Test Plan",
            str(default_filepath),
            "Excel Files (*.xlsx)"
        )
        if not file_path:
            return
        if not file_path.lower().endswith('.xlsx'):
            file_path += '.xlsx'

        # 3. 创建并保存
        try:
            from src.util.report.excel.plan import write_plan
            from src.util.report.excel.schemas import PLAN_COLS

            # 修改列顺序：将Test Type放在Priority之后、Tag之前
            column_order = [
                PLAN_COLS.TCID,
                PLAN_COLS.PRIORITY,
                "Test Type",  # 新增：放在Priority之后
                PLAN_COLS.TAG,  # Tag在Test Type之后
                PLAN_COLS.MODULE,
                PLAN_COLS.DESCRIPTION,
                PLAN_COLS.SCRIPT_PATH,
            ]
            write_plan(file_path, rows=selected_rows, column_order=column_order)

            # 保存最后路径
            config_base = get_config_base()
            config_base.mkdir(exist_ok=True)
            last_plan_file = config_base / "last_function_plan.txt"
            with open(last_plan_file, 'w', encoding='utf-8') as f:
                f.write(str(Path(file_path).resolve()))

            # 可选：弹出成功提示
            QMessageBox.information(self, "Save Successful", f"Test plan saved to:\n{file_path}")

        except Exception as e:
            error_msg = f"Failed to save test plan: {e}"
            QMessageBox.critical(self, "Save Error", error_msg)

    def _on_select_all_changed(self, state):
        """Handle 'Select All' checkbox toggle."""
        check_state = (state == Qt.Checked)

        # update all_rows
        for row in self.all_rows:
            row["_checked"] = check_state

        # refresh
        self.apply_filters()

    def on_reset_clicked(self):
        """重置所有筛选条件，并恢复所有用例为勾选状态"""
        # 0. 调用无参数的 load_test_case_files 来加载所有子目录
        self.load_test_case_files()

        # 1. 重置 ComboBox 为 "All"
        self.priority_combo.setCurrentText("All")
        self.module_combo.setCurrentText("All")
        self.tag_combo.setCurrentText("All")
        self.test_type_combo.setCurrentText("All")  # 新增

        # 2. 将所有行设为勾选
        for row in self.all_rows:
            row["_checked"] = True

        # 3. 刷新表格（显示全部且全选）
        self.list_widget.set_rows(self.all_rows)

    def load_cases_from_dirs(self, target_dirs: list[str]):
        """
        根据外部传入的目录列表，动态加载并显示对应的测试用例。

        Args:
            target_dirs (list[str]): 要加载的目录名称列表，例如 ["region"] 或 ["android"]。
        """
        self.load_test_case_files(target_dirs=target_dirs)
