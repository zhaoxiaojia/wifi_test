# src/test/wifi/conftest.py

import pytest
import os
from pathlib import Path
from src.util.constants import load_config
from src.tools.connect_tool.duts.android import android


@pytest.fixture
def wifi_adb_device():
    """Provide Android device for Wi-Fi tests."""
    cfg = load_config(refresh=True)
    serial = cfg.get("connect_type", {}).get("Android", {}).get("device")
    if not serial:
        pytest.fail("Missing Android.device in config")

    logdir = Path(os.getenv("PYTEST_REPORT_DIR", "./report"))
    logdir.mkdir(exist_ok=True)

    dut = android(serialnumber=serial, logdir=str(logdir))
    yield dut, serial, logdir

    # Teardown: 回主界面（Wi-Fi 测试通用清理）
    os.system(f"adb -s {serial} shell input keyevent KEYCODE_HOME")