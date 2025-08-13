#!/usr/bin/env python 
# encoding: utf-8 
'''
@author: chao.li
@contact: chao.li@amlogic.com
@software: pycharm
@file: event_builder.py 
@time: 8/11/2025 11:50 AM 
@desc: 
'''

# -*- coding: utf-8 -*-
from typing import List, Dict, Any

SUBTYPE_MAP = {
    "0x0b": "AUTH",  # Authentication
    "0x00": "ASSOC_REQ",  # Association Request
    "0x01": "ASSOC_RESP",  # Association Response
    "0x0a": "DISASSOC",  # (若无可忽略)
    "0x0c": "DEAUTH"  # (若无可忽略)
}


def safe_int(x: str, default=None):
    try:
        return int(x)
    except Exception:
        return default


def classify_eapol_msg(key_info_hex_or_dec: str, mic: str, replay: str) -> str:
    """
    优先使用 key_info 位推断消息编号；不同 tshark 版本 key_info 可能是十进制或十六进制。
    我们做一个保守推断：在后续代理模式校准中会切换到 Wireshark 的派生字段（若可用）。
    """
    if not key_info_hex_or_dec:
        return "EAPOL-KEY"
    try:
        ki = int(key_info_hex_or_dec, 0)  # 自动识别 "0x..." 或十进制
    except Exception:
        ki = safe_int(key_info_hex_or_dec, 0)

    KEY_ACK = 1 << 7
    KEY_MIC = 1 << 8
    INSTALL = 1 << 6
    SECURE = 1 << 9
    PAIRWISE = 1 << 3

    # 粗略推断（常见实现）：1/4 有 ACK 无 MIC；2/4 有 MIC 无 ACK；
    # 3/4 有 ACK 与 MIC，且 INSTALL/SECURE 常出现；4/4 有 MIC 与 SECURE，无 ACK。
    if (ki & KEY_ACK) and not (ki & KEY_MIC):
        return "4WH-1"
    if (ki & KEY_MIC) and not (ki & KEY_ACK):
        return "4WH-2"
    if (ki & KEY_ACK) and (ki & KEY_MIC):
        if (ki & INSTALL) or (ki & SECURE):
            return "4WH-3"
        return "4WH-3"
    if (ki & KEY_MIC) and (ki & SECURE) and not (ki & KEY_ACK):
        return "4WH-4"
    return "EAPOL-KEY"


def _infer_4wh_by_direction(events):
    # 找出仍标记为 EAPOL-KEY 的帧
    idx = [i for i, e in enumerate(events) if e.get("eapol_type") and e.get("type") == "EAPOL-KEY"]
    if not idx:
        return
    # 方向：AP->STA（sa==bssid）记为 'AP'；STA->AP（da==bssid）记为 'STA'
    seq = []
    for i in idx:
        e = events[i]
        dir_ = "AP" if (e.get("sa") and e.get("bssid") and e["sa"] == e["bssid"]) else (
            "STA" if (e.get("da") and e.get("bssid") and e["da"] == e["bssid"]) else "UNK")
        seq.append((i, dir_))
    # 按 1(AP)->2(STA)->3(AP)->4(STA) 推断，遇到 UNK 跳过
    need = ["AP", "STA", "AP", "STA"]
    k = 0
    for i, d in seq:
        if k >= 4:
            break
        if d == need[k]:
            events[i]["type"] = f"4WH-{k + 1}"
            k += 1
    # 若没有完整 1..4，不做强制；PSK 检查会给出“未检测到 4 次握手”提示
    return


def build_events(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    events = []
    for r in rows:
        evt = {
            "no": r.get("frame.number", ""),
            "ts": r.get("frame.time_epoch", ""),
            "sa": r.get("wlan.sa", ""),
            "da": r.get("wlan.da", ""),
            "bssid": r.get("wlan.bssid", ""),
            "subtype_raw": r.get("wlan.fc.type_subtype", ""),
            "ssid": r.get("wlan_mgt.ssid") or r.get("wlan_mgt.fixed.ssid") or "",
            "akm": r.get("rsn.akms.type", ""),
            "pairwise": r.get("rsn.pcs.list", ""),
            "group": r.get("rsn.gcs.type", ""),
            "pmf_req": r.get("rsn.capabilities.mgmt_frame_protection_required", ""),
            "pmf_cap": r.get("rsn.capabilities.mgmt_frame_protection_capable", ""),
            "eap_code": r.get("eap.code", ""),
            "eap_type": r.get("eap.type", ""),
            "eap_success": r.get("eap.success", ""),
            "eapol_type": r.get("eapol.type", ""),
            "eapol_key_type": r.get("eapol.keydes.type", ""),
            "eapol_key_info": r.get("eapol.keydes.key_info", ""),
            "eapol_replay": r.get("eapol.keydes.replay_counter", ""),
            "eapol_mic": r.get("eapol.keydes.mic", "")
        }

        st = evt["subtype_raw"]
        if st in SUBTYPE_MAP:
            evt["type"] = SUBTYPE_MAP[st]
        elif evt["eapol_type"]:
            # EAPOL-Key
            evt["type"] = classify_eapol_msg(evt["eapol_key_info"], evt["eapol_mic"], evt["eapol_replay"])
        elif evt["eap_code"]:
            evt["type"] = "EAP"
        else:
            evt["type"] = "OTHER"

        events.append(evt)
    # 按时间排序
    events.sort(key=lambda x: float(x["ts"] or 0.0))
    _infer_4wh_by_direction(events)
    return events
