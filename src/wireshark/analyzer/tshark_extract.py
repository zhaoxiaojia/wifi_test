#!/usr/bin/env python 
# encoding: utf-8 
'''
@author: chao.li
@contact: chao.li@amlogic.com
@software: pycharm
@file: tshark_extract.py 
@time: 8/11/2025 11:50 AM 
@desc: 
'''

# -*- coding: utf-8 -*-
import json
import subprocess
import csv
from pathlib import Path

def load_fields_map():
    here = Path(__file__).parent
    fm = json.loads((here / "fields_map.json").read_text(encoding="utf-8"))
    fields = fm["common"] + fm["mgt"] + fm["eapol"] + fm["eap"]
    # 去重并保持顺序
    seen, ordered = set(), []
    for f in fields:
        if f not in seen:
            seen.add(f); ordered.append(f)
    return ordered

def run_tshark_tsv(pcap_path: str, fields: list[str]) -> list[dict]:
    # 仅保留与状态有关的帧，减少体积
    display_filter = (
        "eapol || eap || wlan_mgt || "
        "wlan.fc.type_subtype==0x0b || "  # auth
        "wlan.fc.type_subtype==0x00 || "  # assoc-req
        "wlan.fc.type_subtype==0x01 || "  # assoc-resp
        "wlan.fc.type_subtype==0x20"      # disassoc/deauth（部分版本）
    )
    cmd = [
        "tshark", "-r", pcap_path, "-Y", display_filter,
        "-T", "fields", "-E", "header=y", "-E", "separator=\t", "-E", "quote=d", "-E", "occurrence=f"
    ]
    for f in fields:
        cmd += ["-e", f]

    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if res.returncode != 0:
        raise RuntimeError(f"tshark failed: {res.stderr}")

    reader = csv.DictReader(res.stdout.splitlines(), delimiter="\t")
    rows = []
    for row in reader:
        rows.append({k: v for k, v in row.items()})
    return rows
