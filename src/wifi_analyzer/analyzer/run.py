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
import argparse, glob, json,shutil
from pathlib import Path

from src.wifi_analyzer.analyzer.tshark_extract import load_fields_map, run_tshark_tsv
from src.wifi_analyzer.analyzer.event_builder import build_events
from src.wifi_analyzer.analyzer.checks_psk import check_psk
from src.wifi_analyzer.analyzer.checks_sae import check_sae
from src.wifi_analyzer.analyzer.checks_eap import check_eap_enterprise
from src.wifi_analyzer.report.gen_report import render_html

def have_tshark() -> bool:
    return shutil.which("tshark") is not None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pcap", help="pcap/pcapng 文件或通配符")
    ap.add_argument("--mode", choices=["psk","sae","eap"], required=True)
    ap.add_argument("--ssid", default="")
    ap.add_argument("--pairwise", default="")
    ap.add_argument("--group", default="")
    ap.add_argument("--akm", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--backend", choices=["auto","tshark","scapy","json"], default="auto",
                    help="提取后端：auto|tshark|scapy|json")
    ap.add_argument("--json", default="", help="当 --backend json 时，提供 .jsonl 路径")
    args = ap.parse_args()

    # 选择 pcap
    pcap = ""
    if args.pcap:
        matches = sorted(glob.glob(args.pcap))
        if not matches:
            raise SystemExit(f"No pcap found: {args.pcap}")
        pcap = matches[-1]  # 取最新

    # 选择 rows 来源
    rows = None
    backend_used = None

    if args.backend == "auto":
        if have_tshark() and pcap:
            fields = load_fields_map()
            rows = run_tshark_tsv(pcap, fields)
            backend_used = "tshark"
        else:
            try:
                from backend_scapy import have_scapy, run_scapy_extract  # type: ignore
                if have_scapy() and pcap:
                    rows = run_scapy_extract(pcap)
                    backend_used = "scapy"
            except Exception:
                pass
        if rows is None:
            raise SystemExit("auto 模式下未找到可用后端：请安装 Wireshark/tshark 或 `pip install scapy`；"
                             "或使用 --backend json --json your.jsonl")
    elif args.backend == "tshark":
        if not pcap:
            raise SystemExit("--backend tshark 需要提供 --pcap")
        fields = load_fields_map()
        rows = run_tshark_tsv(pcap, fields)
        backend_used = "tshark"
    elif args.backend == "scapy":
        if not pcap:
            raise SystemExit("--backend scapy 需要提供 --pcap")
        from src.wifi_analyzer.analyzer.backend_scapy import run_scapy_extract  # type: ignore
        rows = run_scapy_extract(pcap)
        backend_used = "scapy"
    elif args.backend == "json":
        if not args.json:
            raise SystemExit("--backend json 需要提供 --json 路径")
        from backend_json import load_rows_from_jsonl  # type: ignore
        rows = load_rows_from_jsonl(args.json)
        backend_used = "json"

    events = build_events(rows)

    verdicts = []
    if args.mode == "psk":
        verdicts += check_psk(events, args.ssid, args.pairwise, args.group, args.akm or "PSK")
    elif args.mode == "sae":
        verdicts += check_sae(events, args.ssid)
        verdicts += [v for v in check_psk(events, args.ssid, args.pairwise or "CCMP", args.group or "CCMP", args.akm or "SAE") if v[0]!="PASS"]
    elif args.mode == "eap":
        verdicts += check_eap_enterprise(events)
        verdicts += [v for v in check_psk(events, args.ssid, args.pairwise or "CCMP", args.group or "CCMP", args.akm or "") if v[0]!="PASS"]

    ctx = {
        "title": f"Wi-Fi 流程与协议一致性报告（backend={backend_used}）",
        "pcap": pcap or args.json,
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
