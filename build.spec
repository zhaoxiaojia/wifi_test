# build.spec
import os
import sys
# 在build.spec顶部添加
def get_requirements():
    with open('requirements.txt', 'r', encoding='utf-8') as f:
        # 过滤注释和空行，提取库名（忽略版本号）
        return [line.strip().split('==')[0] for line in f if line.strip() and not line.startswith('#')]

requirements = get_requirements()
a = Analysis(
    ['src/main.py'],  # 入口文件
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=[
        # 手动添加PyQt5和自定义模块的隐藏依赖
        'PyQt5',
        'PyQt5.QtWidgets',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'qfluentwidgets',
        'matplotlib',
        'matplotlib.backends',
        'matplotlib.backends.backend_pdf',  # 解决当前报错
        'matplotlib.backends.backend_agg',  # 常用后端，一并添加
        'matplotlib.figure',  # 可能用到的绘图核心模块
        'serial',  # 核心模块
        'serial.tools',  # 工具模块（如果用到）
        'serial.tools.list_ports',  # 常用子模块（如果用到）
        # 确保项目中引用 serial 的模块也被包含
        'src.tools.connect_tool.serial_tool',
        'pytest_html',
        'pytest_html.plugin',  # pytest-html的核心插件模块
        'pytest_reportlog',    # 可能关联的报告模块
        'selenium',
        'selenium.webdriver',
        'selenium.webdriver.common',
        'selenium.webdriver.common.by',
        'selenium.webdriver.support.expected_conditions',
        'selenium.webdriver.support',
        'selenium.webdriver.support.ui',
        'selenium.webdriver.support.ui.WebDriverWait',
        'selenium.webdriver.support.expected_conditions'
        'selenium.webdriver.chrome',
        *requirements,
        'src.ui.windows_case_config',
        'src.ui.run',

    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False
)
pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='FAE-QA-WIFI',
    console=True,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,                          # 使用UPX压缩
    runtime_tmpdir=None,
    icon='wifi.ico'                # 可选图标
)