#!/usr/bin/env python 
# encoding: utf-8 
'''
@author: chao.li
@contact: chao.li@amlogic.com
@software: pycharm
@file: checks_eap.py 
@time: 8/11/2025 11:51 AM 
@desc: 
'''


# -*- coding: utf-8 -*-
from typing import List, Dict, Any

def check_eap_enterprise(events: List[Dict[str, Any]]):
    verdicts = []
    # 检测 EAP 成功路径：出现 EAP-Success，随后进入 4WH
    has_eap = any(e["type"] == "EAP" for e in events)
    if not has_eap:
        verdicts.append(("FAIL", "未检测到 EAP 会话"))
        return verdicts

    eap_success = any((e.get("eap_success") in ("1","True","true")) for e in events)
    if not eap_success:
        verdicts.append(("FAIL", "未检测到 EAP-Success（可能证书/配置错误）"))
        return verdicts

    has_4wh = any(e["type"].startswith("4WH-") for e in events)
    if not has_4wh:
        verdicts.append(("FAIL", "EAP 成功后未触发 4 次握手"))
    else:
        verdicts.append(("PASS", "EAP 基线通过：EAP 成功并进入 4 次握手"))
    return verdicts
