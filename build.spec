# build.spec
import os
import sys
def get_requirements():
    with open('requirements.txt', 'r', encoding='utf-8') as f:
        return [line.strip().split('==')[0] for line in f if line.strip() and not line.startswith('#')]

requirements = get_requirements()
a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('src/pytest.ini', 'src'),
        ('src/test', 'src/test'),
        ('config/performance_test_csv', 'config/performance_test_csv'),
        ('config/config_basic.yaml', 'config'),
        ('config/config_performance.yaml', 'config'),
        ('config/config_stability.yaml', 'config'),
        ('config/config_compatibility.yaml', 'config'),
        ('config/config_tool.yaml', 'config'),
        ('config/config_toolbar.yaml', 'config'),
    ],
    hiddenimports=[
        'PyQt5',
        'PyQt5.QtWidgets',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'qfluentwidgets',
        'matplotlib',
        'matplotlib.backends',
        'matplotlib.backends.backend_pdf',
        'matplotlib.backends.backend_agg',
        'matplotlib.figure',
        'serial',
        'serial.tools',
        'serial.tools.list_ports',
        'src.tools.connect_tool.serial_tool',
        'pymysql',  # ensure PyInstaller bundles pymysql
        'pymysql.cursors',
        'pytest',
        'pytest_html',
        'pytest_html.plugin',
        'pytest_reportlog',
        'pytest-repeat',
        'pytest_dependency',
        'allure-pytest',
        'selenium',
        'selenium.webdriver',
        'selenium.webdriver.common',
        'selenium.webdriver.common.by',
        'selenium.webdriver.support.expected_conditions',
        'selenium.webdriver.support',
        'selenium.webdriver.support.ui',
        'selenium.webdriver.support.ui.WebDriverWait',
        'selenium.webdriver.chrome',
        *requirements,
        'src.ui.run',
        'xlrd'
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)
a.datas += Tree('src', prefix='src')
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
    upx=True,
    runtime_tmpdir=None,
    icon='res/logo/wifi.ico'
)
