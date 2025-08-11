#!/usr/bin/env python 
# encoding: utf-8 
'''
@author: chao.li
@contact: chao.li@amlogic.com
@software: pycharm
@file: run.py 
@time: 8/11/2025 11:52 AM 
@desc: 
'''


# -*- coding: utf-8 -*-
import argparse, glob, json
from pathlib import Path

from src.wifi_analyzer.analyzer.tshark_extract import load_fields_map, run_tshark_tsv
from src.wifi_analyzer.analyzer.event_builder import build_events
from src.wifi_analyzer.analyzer.checks_psk import check_psk
from src.wifi_analyzer.analyzer.checks_sae import check_sae
from src.wifi_analyzer.analyzer.checks_eap import check_eap_enterprise
from src.wifi_analyzer.report.gen_report import render_html

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pcap", required=True, help="pcap/pcapng 文件或通配符")
    ap.add_argument("--mode", choices=["psk","sae","eap"], required=True)
    ap.add_argument("--ssid", default="")
    ap.add_argument("--pairwise", default="")
    ap.add_argument("--group", default="")
    ap.add_argument("--akm", default="")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    matches = sorted(glob.glob(args.pcap))
    if not matches:
        raise SystemExit(f"No pcap found: {args.pcap}")
    pcap = matches[-1]  # 取最新

    fields = load_fields_map()
    rows = run_tshark_tsv(pcap, fields)
    events = build_events(rows)

    verdicts = []
    if args.mode == "psk":
        verdicts += check_psk(events, args.ssid, args.pairwise, args.group, args.akm or "PSK")
    elif args.mode == "sae":
        verdicts += check_sae(events, args.ssid)
        # SAE 后续 4WH 仍可复用 PSK 的握手一致性检查
        verdicts += [v for v in check_psk(events, args.ssid, args.pairwise or "CCMP", args.group or "CCMP", args.akm or "SAE") if v[0]!="PASS"]
    elif args.mode == "eap":
        verdicts += check_eap_enterprise(events)
        # EAP 成功后 4WH 合法性
        verdicts += [v for v in check_psk(events, args.ssid, args.pairwise or "CCMP", args.group or "CCMP", args.akm or "") if v[0]!="PASS"]

    ctx = {
        "title": "Wi-Fi 流程与协议一致性报告",
        "pcap": pcap,
        "mode": args.mode.upper(),
        "ssid": args.ssid,
        "events": events,
        "verdicts": verdicts
    }
    tpl = str(Path(__file__).parent.parent / "report" / "templates" / "base.html")
    render_html(tpl, args.out, ctx)
    print(f"[report] generated -> {args.out}")

if __name__ == "__main__":
    main()
