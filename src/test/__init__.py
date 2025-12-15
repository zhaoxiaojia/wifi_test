import csv
import logging
from pathlib import Path

import pytest
from src.tools.router_tool.Router import Router
from src.util.constants import load_config
from src.util.constants import get_config_base, RouterConst


def get_testdata(router):
    config = load_config(refresh=True) or {}
    config_base = get_config_base()
    router_name = config.get('router', {}).get('name', '')
    csv_path = config.get('csv_path')

    if csv_path:
        csv_path = Path(csv_path)
        if not csv_path.is_absolute():
            csv_path = config_base / csv_path
    else:
        csv_path = config_base / "performance_test_csv" / "rvr_wifi_setup.csv"

    pc_ip, dut_ip = "", ""
    # 读取 测试配置
    test_data = []
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = [j for j in reader]
            for i in rows[1:]:
                if not i:
                    continue
                stripped_i = [field.strip() for field in i]
                test_data.append(Router(*stripped_i))
    except FileNotFoundError:
        raise FileNotFoundError(
            f"CSV file not found at {csv_path}. Please check router name '{router_name}'."
        )
    return test_data
