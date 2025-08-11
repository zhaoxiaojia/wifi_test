#!/usr/bin/env python 
# encoding: utf-8 
'''
@author: chao.li
@contact: chao.li@amlogic.com
@software: pycharm
@file: checks_psk.py 
@time: 8/11/2025 11:51 AM 
@desc: 
'''


# -*- coding: utf-8 -*-
from typing import List, Dict, Any

def check_psk(events: List[Dict[str, Any]], ssid: str, pairwise: str, group: str, akm: str):
    verdicts = []

    # 1) RSN IE / AKM / 密码套件
    rsn_seen = False
    for e in events:
        if e["type"] in ("ASSOC_REQ", "ASSOC_RESP") and (e["ssid"] == ssid or ssid == ""):
            rsn_seen = True
            if pairwise and pairwise not in (e["pairwise"] or ""):
                verdicts.append(("FAIL", f"Pairwise 不匹配: 期望 {pairwise}, 实际 {e['pairwise']} (frame {e['no']})"))
            if group and group not in (e["group"] or ""):
                verdicts.append(("FAIL", f"Group 不匹配: 期望 {group}, 实际 {e['group']} (frame {e['no']})"))
            if akm and akm not in (e["akm"] or ""):
                verdicts.append(("FAIL", f"AKM 不匹配: 期望 {akm}, 实际 {e['akm']} (frame {e['no']})"))
    if not rsn_seen:
        verdicts.append(("WARN", "未在关联阶段看到 RSN IE/套件字段（可能抓包侧未捕获）"))

    # 2) 4 次握手顺序（1→2→3→4）
    seq = [e for e in events if e["type"].startswith("4WH-")]
    seq_types = [e["type"] for e in seq]
    if not seq:
        verdicts.append(("FAIL", "未检测到 4 次握手"))
    else:
        order = "".join(t[-1] for t in seq_types)  # e.g., '1234...'
        if "1" not in order or "4" not in order:
            verdicts.append(("FAIL", f"4 次握手不完整: {seq_types}"))
        else:
            # 简单递增检查（允许重试）
            first1 = order.find("1")
            last4 = order.rfind("4")
            if not (first1 < last4):
                verdicts.append(("FAIL", f"4 次握手顺序异常: {seq_types}"))

    # 3) Replay Counter 单调递增（仅粗检）
    rc_list = [int(e["eapol_replay"]) for e in events if e["type"].startswith("4WH-") and (e["eapol_replay"] or "").isdigit()]
    if rc_list and any(rc_list[i] > rc_list[i+1] for i in range(len(rc_list)-1)):
        verdicts.append(("FAIL", f"Replay Counter 非单调: {rc_list}"))

    # 4) MIC 存在性（2 / 3 / 4 应有 MIC）
    mic_missing = [e["no"] for e in events if e["type"] in ("4WH-2","4WH-3","4WH-4") and not e["eapol_mic"]]
    if mic_missing:
        verdicts.append(("FAIL", f"握手报文缺少 MIC: frames {mic_missing}"))

    if not verdicts:
        verdicts.append(("PASS", "WPA2-PSK 基线检查通过"))
    return verdicts
