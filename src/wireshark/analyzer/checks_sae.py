#!/usr/bin/env python 
# encoding: utf-8 
'''
@author: chao.li
@contact: chao.li@amlogic.com
@software: pycharm
@file: checks_sae.py 
@time: 8/11/2025 11:51 AM 
@desc: 
'''

# -*- coding: utf-8 -*-
from typing import List, Dict, Any

def check_sae(events: List[Dict[str, Any]], ssid: str):
    verdicts = []

    # PMF 必须开启（SAE 要求 MFP，可从关联响应/RSN Capabilities 判断）
    pmf_ok = False
    for e in events:
        if e["type"] in ("ASSOC_RESP", "ASSOC_REQ"):
            req = (e["pmf_req"] or "0") in ("1","True","true")
            cap = (e["pmf_cap"] or "0") in ("1","True","true")
            if req or cap:
                pmf_ok = True
                break
    if not pmf_ok:
        verdicts.append(("FAIL", "WPA3-SAE 期望 PMF/MFP，但未检测到相应能力位"))

    # AKM=SAE
    akm_ok = any(("SAE" in (e["akm"] or "")) for e in events if e["type"] in ("ASSOC_REQ","ASSOC_RESP"))
    if not akm_ok:
        verdicts.append(("FAIL", "未检测到 AKM=SAE"))

    # 后续 4WH 与 PSK 共用规则（PMK 已建立后触发）
    if not verdicts:
        verdicts.append(("PASS", "WPA3-SAE 基线（含 PMF & AKM=SAE）通过"))
    return verdicts
