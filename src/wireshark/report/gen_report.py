#!/usr/bin/env python 
# encoding: utf-8 
'''
@author: chao.li
@contact: chao.li@amlogic.com
@software: pycharm
@file: gen_report.py 
@time: 8/11/2025 11:51 AM 
@desc: 
'''


# -*- coding: utf-8 -*-
from pathlib import Path
from typing import List, Tuple, Dict, Any

def render_html(template_path: str, dst_path: str, context: Dict[str, Any]):
    # 极简模板渲染（不引第三方）
    tpl = Path(template_path).read_text(encoding="utf-8")

    # 处理 {% for ... %} ... {% endfor %}（只支持一层）
    def render_loop(block: str, key: str, rows):
        out = []
        for row in rows:
            s = block
            # 展开 e.xxx 访问
            if isinstance(row, dict):
                for k, v in row.items():
                    s = s.replace("{{ e."+k+" }}", str(v))
            else:
                pass
            # 展开 [level, msg] / tuple
            if isinstance(row, (list, tuple)) and len(row)==2:
                s = s.replace("{{ level }}", str(row[0]))
                s = s.replace("{{ msg }}", str(row[1]))
                s = s.replace("{{ level|lower }}", str(row[0]).lower())
            out.append(s)
        return "".join(out)

    import re
    # 渲染 verdicts
    m = re.search(r"{% for level, msg in verdicts %}(.+?){% endfor %}", tpl, flags=re.S)
    if m:
        block = m.group(1)
        tpl = tpl.replace(m.group(0), render_loop(block, "verdicts", context.get("verdicts", [])))
    # 渲染 events (e)
    m = re.search(r"{% for e in events %}(.+?){% endfor %}", tpl, flags=re.S)
    if m:
        block = m.group(1)
        tpl = tpl.replace(m.group(0), render_loop(block, "events", context.get("events", [])))

    # 单值占位
    for k, v in context.items():
        if isinstance(v, (str, int, float)):
            tpl = tpl.replace("{{ "+k+" }}", str(v))

    Path(dst_path).parent.mkdir(parents=True, exist_ok=True)
    Path(dst_path).write_text(tpl, encoding="utf-8")
