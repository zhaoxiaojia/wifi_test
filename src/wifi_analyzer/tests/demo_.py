#!/usr/bin/env python 
# encoding: utf-8 
'''
@author: chao.li
@contact: chao.li@amlogic.com
@software: pycharm
@file: demo_.py
@time: 8/11/2025 11:52 AM 
@desc: 
'''


# -*- coding: utf-8 -*-
import os, subprocess, time, glob, pytest
from pathlib import Path

@pytest.fixture(scope="function")
def capture(tmp_path):
    outdir = Path("captures")
    outdir.mkdir(exist_ok=True)
    # 你可以从 env 传入网卡名
    iface = os.getenv("WIFI_IFACE", "wlan0")
    case_id = "pytest_case"
    start = ["sudo","./scripts/capture_start.sh", iface, case_id, str(outdir)]
    subprocess.run(start, check=True)
    yield
    subprocess.run(["sudo","./scripts/capture_stop.sh", str(outdir)], check=True)

    latest = Path(outdir, ".latest").read_text().strip()
    print(f"[pytest] pcap: {latest}")
