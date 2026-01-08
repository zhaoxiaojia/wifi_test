# src/ui/view/config/function_config_form.py
from PyQt5.QtWidgets import ( QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QGroupBox, QRadioButton, QButtonGroup, QListWidget, QListWidgetItem, QAbstractItemView, QCheckBox, QSizePolicy, QLabel, QFileDialog, QMessageBox)
from qfluentwidgets import BodyLabel, PrimaryPushButton
from pathlib import Path
from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtGui import QFont, QColor
import yaml
import re, os
from pathlib import Path
import pandas as pd
from datetime import datetime
from src.util.constants import get_config_base

class FunctionConfigForm(QWidget):
    """STB 功能测试配置表单组件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

        self.save_plan_btn = PrimaryPushButton("Save Test Plan")
        self.save_plan_btn.clicked.connect(self.on_save_plan_clicked)
        self.load_plan_btn = PrimaryPushButton("Load Test Plan")
        self.load_plan_btn.clicked.connect(self.on_load_plan_clicked)

    def setup_ui(self):
        """Set up the UI."""
        self.setObjectName("functionConfigForm")
        # 主布局：垂直布局，填满整个 widget
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        # 标题：移除默认边距
        title_label = QLabel("Function Case Selection")
        title_label.setStyleSheet("""
        QLabel {
            font-size: 14px;
            font-weight: bold;
            padding: 0px;
            margin: 0px;
        }
        """)
        title_label.setContentsMargins(0, 0, 0, 0)
        title_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        main_layout.addWidget(title_label)
        # 分割器：左右可调
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(0)  # 消除分割器手柄宽度
        splitter.setContentsMargins(0, 0, 0, 0)
        # ===== 左侧：测试配置 =====
        left_widget = QWidget()
        left_widget.setStyleSheet("padding: 0px; margin: 0px;")
        left_widget.setContentsMargins(0, 0, 0, 0)
        # 设置左侧宽度约束，防止被挤压
        left_widget.setMinimumWidth(220)
        left_widget.setMaximumWidth(300)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)
        left_layout.setAlignment(Qt.AlignTop)
        # Test Priority
        priority_group = QGroupBox("Test Priority")
        priority_group.setStyleSheet("""
        QGroupBox {
            padding: 0px;
            margin: 0px;
            border: 1px solid #ccc;
            font-weight: bold;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 5px;
            margin: 0px;
        }
        """)
        priority_layout = QVBoxLayout(priority_group)
        priority_layout.setContentsMargins(8, 20, 8, 8)  # 调整内边距
        self.priority_buttons = QButtonGroup(self)
        for text in ["All", "P1", "P2", "P3"]:
            rb = QRadioButton(text)
            self.priority_buttons.addButton(rb)
            priority_layout.addWidget(rb)
        self.priority_buttons.buttons()[0].setChecked(True)
        left_layout.addWidget(priority_group)
        for rb in self.priority_buttons.buttons():
            rb.toggled.connect(self.apply_filters)
        # WiFi Test Module (多选)
        module_group = QGroupBox("WiFi Test Suite")
        module_group.setStyleSheet("""
        QGroupBox {
            padding: 0px;
            margin: 0px;
            border: 1px solid #ccc;
            font-weight: bold;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 5px;
            margin: 0px;
        }
        """)
        module_layout = QVBoxLayout(module_group)
        module_layout.setContentsMargins(8, 20, 8, 8)  # 调整内边距
        self.module_checkboxes = []
        modules = ["Status Check", "SSID", "Mode", "Channel", "Bandwidth", "Security Mode"]
        for name in modules:
            cb = QCheckBox(name)
            module_layout.addWidget(cb)
            self.module_checkboxes.append(cb)
        for cb in self.module_checkboxes:
            cb.setChecked(True)
        left_layout.addWidget(module_group)
        for cb in self.module_checkboxes:
            cb.stateChanged.connect(self.apply_filters)
        splitter.addWidget(left_widget)
        # ===== 右侧：文件列表 =====
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(12, 0, 12, 8)
        right_layout.setSpacing(8)
        file_label = BodyLabel("Test Script")
        right_layout.addWidget(file_label)
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.file_list.setAlternatingRowColors(True)
        right_layout.addWidget(self.file_list, 1)  # stretch factor 为 1，占据剩余空间
        # ===== 右侧底部：操作按钮 =====
        # 创建两个按钮（仅保留 Save Plan 和 Reset）
        self.save_plan_btn = PrimaryPushButton("Save Plan")
        self.reset_btn = PrimaryPushButton("Reset")
        self.load_plan_btn = PrimaryPushButton("Load Test Plan")

        # 连接信号到槽（目前是占位符，后面需要实现具体逻辑）
        self.save_plan_btn.clicked.connect(self.on_save_plan_clicked)
        self.reset_btn.clicked.connect(self.on_reset_clicked)
        self.load_plan_btn.clicked.connect(self.on_load_plan_clicked)

        # 创建一个水平布局来容纳按钮（每行两个，现在只有一行）
        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        button_row.addWidget(self.save_plan_btn)
        button_row.addWidget(self.load_plan_btn)
        button_row.addWidget(self.reset_btn)

        # 将水平布局添加到右侧的垂直布局中
        right_layout.addLayout(button_row)
        splitter.addWidget(right_widget)
        # 设置初始比例和 stretch factor
        splitter.setSizes([250, 400])
        splitter.setStretchFactor(0, 0)  # 左侧不扩展
        splitter.setStretchFactor(1, 1)  # 右侧可扩展
        # 将 splitter 添加到主布局，stretch factor 为 1 占据剩余空间
        main_layout.addWidget(splitter, 1)
        # 加载文件
        self.load_test_files()

    def load_test_files(self):
        """从 test_config.yaml 加载测试脚本"""
        self.file_list.clear()
        # 定位到 project 目录下的 test_config.yaml
        current_file = Path(__file__).resolve()
        src_dir = Path(__file__).parent.parent.parent.parent.resolve()
        config_path = (src_dir / "test" / "project" / "test_config.yaml").resolve()
        #config_path = Path(r"D:\wifi_test12\src\test\project\test_config.yaml")
        # print(f"📍 路径: {config_path}")
        # print(f"🔍 exists(): {config_path.exists()}")
        # print(f"📄 is_file(): {config_path.is_file()}")
        # # print(f"📍 路径: {config_path}")
        # print(f"🔍 exists(): {config_path.exists()}")
        # 现在不会报错了
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
                print(f"⚠️ Skip invalid path: {path}")
                continue
            normalized_path = path.replace("\\", "/")
            display_path = f"project/{normalized_path}"
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

    # --- 在 FunctionConfigForm 类中新增方法 ---
    def on_load_plan_clicked(self):
        """槽函数：当 'Load Test Plan' 按钮被点击时调用"""
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        from pathlib import Path
        import pandas as pd

        # 1. 确定默认打开目录 (dist/)
        default_dist_dir = get_config_base()
        #default_dist_dir = project_root / "dist"

        if not default_dist_dir.exists():
            default_dist_dir = Path.home()  # 如果 dist 不存在，回退到用户主目录

        # 2. 打开文件选择对话框
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Test Plan",
            str(default_dist_dir),
            "Excel Files (*.xlsx)"
        )

        if not file_path:
            return  # 用户取消了操作

        try:
            # 3. 读取 Excel 文件
            df = pd.read_excel(file_path)
            if "Script Path" not in df.columns:
                raise ValueError("Excel file must contain a 'Script Path' column.")

            selected_script_paths = df["Script Path"].dropna().tolist()

            # 4. 构建一个快速查找字典，用于匹配 test_config.yaml 中的脚本
            # 假设 self.all_script_items 已经通过 load_test_files() 加载
            script_meta_dict = {meta['original_path']: meta for meta in getattr(self, 'all_script_items', [])}

            # 5. 重置所有复选框为未选中状态
            for i in range(self.file_list.count()):
                item = self.file_list.item(i)
                item.setCheckState(Qt.Unchecked)

            # 6. 遍历 Excel 中的脚本，如果在 test_config.yaml 中找到，则勾选
            found_count = 0
            for script_path in selected_script_paths:
                if script_path in script_meta_dict:
                    # 我们需要在 UI 列表中找到对应的项并勾选
                    # 由于 apply_filters 会根据当前筛选条件显示/隐藏项，
                    # 最可靠的方式是重新应用过滤器，并在过程中标记应勾选的项。
                    pass  # 我们将在下一步处理

            # 7. 【关键】为了正确勾选，我们需要临时记住要勾选的路径
            self._paths_to_check_on_load = set(selected_script_paths) & set(script_meta_dict.keys())
            found_count = len(self._paths_to_check_on_load)

            # 8. 重新应用过滤器，这会刷新列表，并在 apply_filters 中处理勾选
            self.apply_filters()

            # 9. 清理临时变量
            delattr(self, '_paths_to_check_on_load')

            # 10. 保存 last_function_plan.txt
            config_base = get_config_base()
            config_base.mkdir(exist_ok=True)

            last_plan_file = config_base / "last_function_plan.txt"
            with open(last_plan_file, 'w', encoding='utf-8') as f:
                f.write(str(Path(file_path).resolve()))

            # 11. 给用户反馈
            QMessageBox.information(
                self,
                "Load Successful",
                f"Successfully loaded {found_count} out of {len(selected_script_paths)} test cases from:\n{file_path}"
            )
            print(f"✅ Test plan loaded from: {file_path}")
            print(f"📝 Last function plan path saved to: {last_plan_file}")

        except Exception as e:
            error_msg = f"Failed to load test plan: {e}"
            print(f"❌ {error_msg}")
            QMessageBox.critical(self, "Load Error", error_msg)

    def apply_filters(self):
        #self.file_list.clear()
        # 获取当前选择的优先级
        selected_priority = "All"
        for btn in self.priority_buttons.buttons():
            if btn.isChecked():
                selected_priority = btn.text()
                break
        # 获取当前选中的测试套件
        selected_suites = set()
        for cb in self.module_checkboxes:
            if cb.isChecked():
                selected_suites.add(cb.text())  # "Status Check", "Mode"
        # 清空列表
        self.file_list.clear()

        # --- 260105 新增：检查是否存在待勾选的路径 ---
        paths_to_check = getattr(self, '_paths_to_check_on_load', None)

        # 过滤并添加
        for meta in getattr(self, 'all_script_items', []):
            # --- 新增：防御性检查 ---
            raw_display_path = meta.get('display_path', '')
            if not isinstance(raw_display_path, str):
                raw_display_path = str(raw_display_path)
            display_path = raw_display_path.strip()
            # 跳过明显无效的路径
            if not display_path or display_path == "project/":
                print(f"⚠️ Warning: Skipping invalid display_path: '{raw_display_path}'")
                continue
            # 优先级匹配
            if selected_priority != "All" and meta['priority'] != selected_priority:
                continue
            # 套件匹配：只要有一个选中 suite 在脚本的 suites 中即可
            if selected_suites and not (selected_suites & meta['suites']):
                continue

            item = QListWidgetItem(meta['display_path'])
            # 🟩 关键修复：显式设置前景色（文字）和背景色
            item.setForeground(QColor(255, 255, 255))  # 白色文字
            item.setBackground(QColor(42, 42, 42))  # 深灰色背景（#2a2a2a）
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)

            # item.setCheckState(Qt.Checked)
            # item.setData(Qt.UserRole, meta)
            # self.file_list.addItem(item)
            # item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            # item.setCheckState(Qt.Checked)  # 可选：存 meta 供后续使用
            # --- 关键修改：根据上下文决定初始勾选状态 ---
            if paths_to_check is not None:
                # 处于 "Load Plan" 流程中
                is_checked = meta['original_path'] in paths_to_check
            else:
                # 正常流程（如 Reset 或初始加载），默认全选
                is_checked = True

            item.setCheckState(Qt.Checked if is_checked else Qt.Unchecked)
            item.setData(Qt.UserRole, meta)
            self.file_list.addItem(item)

    def on_save_plan_clicked(self):
        """槽函数：当 'Save Plan' 按钮被点击时调用"""
        # 1. 收集当前所有被勾选的文件路径
        selected_paths = []
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item.checkState() == Qt.Checked:
                meta = item.data(Qt.UserRole)
                original_path = meta.get('original_path', '')
                if original_path:
                    selected_paths.append(original_path)
        if not selected_paths:
            print("No test files are selected to save.")
            return
        # 2. 打开文件保存对话框
        # --- 关键修改1: 确定默认的“起始目录”为项目根目录下的 dist ---
        default_dist_dir = get_config_base()
        default_dist_dir.mkdir(exist_ok=True)  # 确保 dist 目录存在
        # --- 关键修改2: 弹出保存对话框 ---
        default_filename = f"Function_test_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        default_filepath = default_dist_dir / default_filename
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Test Plan",  # 对话框标题
            str(default_filepath),  # 默认路径和文件名
            "Excel Files (*.xlsx)"  # 文件过滤器
        )
        if not file_path:  # 用户点击了取消
            return
        # 3. 确保文件扩展名为 .xlsx
        if not file_path.lower().endswith('.xlsx'):
            file_path += '.xlsx'
        # 4. 创建 DataFrame 并保存为 Excel
        try:
            data = []
            for path in selected_paths:
                case_name = Path(path).stem.replace("test_", "")
                data.append({
                    "Script Path": path,
                    "Case Name": case_name,
                    "Status": "Pending",
                    "Duration (s)": "",
                    "Log/Report": ""
                })
            df = pd.DataFrame(data)
            df.to_excel(file_path, index=False, engine='openpyxl')
            print(f"✅ Test plan saved successfully to: {file_path}")
            # TODO: 可以在这里弹出一个成功的提示框 (QMessageBox)

            # --- 关键新增：保存路径到 last_function_plan.txt ---
            config_base = get_config_base()
            config_base.mkdir(exist_ok=True)  # 确保 config 目录存在
            last_plan_file = config_base / "last_function_plan.txt"
            with open(last_plan_file, 'w', encoding='utf-8') as f:
                f.write(str(Path(file_path).resolve()))
            print(f"📝 Last function plan path saved to: {last_plan_file}")

        except Exception as e:
            print(f"❌ Failed to save test plan: {e}")
            # TODO: 可以在这里弹出一个错误提示框 (QMessageBox)



    def on_reset_clicked(self):
        """槽函数：当 'Reset' 按钮被点击时调用"""
        print("Reset clicked!")
        # 重置功能就是重新从 test_config.yaml 加载所有脚本，并恢复所有勾选状态
        self.load_test_files()

    # --- 移除了 _on_plan_finished 方法 ---
