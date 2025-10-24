# build.spec
import os
import sys
# 鍦╞uild.spec椤堕儴娣诲姞
def get_requirements():
    with open('requirements.txt', 'r', encoding='utf-8') as f:
        # 杩囨护娉ㄩ噴鍜岀┖琛岋紝鎻愬彇搴撳悕锛堝拷鐣ョ増鏈彿锛?
        return [line.strip().split('==')[0] for line in f if line.strip() and not line.startswith('#')]

requirements = get_requirements()
a = Analysis(
    ['main.py'],  # 鍏ュ彛鏂囦欢
    pathex=['.'],
    binaries=[],
    datas=[
        ('src/pytest.ini', 'src'),
        ('src/test', 'src/test'),
        ('config/performance_test_csv', 'config/performance_test_csv'),
        ('config/tool_config.yaml', 'config'),
    ],
    hiddenimports=[
        # 鎵嬪姩娣诲姞PyQt5鍜岃嚜瀹氫箟妯″潡鐨勯殣钘忎緷璧?
        'PyQt5',
        'PyQt5.QtWidgets',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'qfluentwidgets',
        'matplotlib',
        'matplotlib.backends',
        'matplotlib.backends.backend_pdf',  # 瑙ｅ喅褰撳墠鎶ラ敊
        'matplotlib.backends.backend_agg',  # 甯哥敤鍚庣锛屼竴骞舵坊鍔?
        'matplotlib.figure',  # 鍙兘鐢ㄥ埌鐨勭粯鍥炬牳蹇冩ā鍧?
        'serial',  # 鏍稿績妯″潡
        'serial.tools',  # 宸ュ叿妯″潡锛堝鏋滅敤鍒帮級
        'serial.tools.list_ports',  # 甯哥敤瀛愭ā鍧楋紙濡傛灉鐢ㄥ埌锛?
        # 纭繚椤圭洰涓紩鐢?serial 鐨勬ā鍧椾篃琚寘鍚?
        'src.tools.connect_tool.serial_tool',
        'pymysql',  # ensure PyInstaller bundles pymysql
        'pymysql.cursors',
        'pytest',
        'pytest_html',
        'pytest_html.plugin',  # pytest-html鐨勬牳蹇冩彃浠舵ā鍧?
        'pytest_reportlog',    # 鍙兘鍏宠仈鐨勬姤鍛婃ā鍧?
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
        'src.ui.windows_case_config',
        'src.ui.run',

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
    upx=True,                          # 浣跨敤UPX鍘嬬缉
    runtime_tmpdir=None,
    icon='wifi.ico'                # 鍙€夊浘鏍?
)

