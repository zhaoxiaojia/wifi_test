#!/usr/bin/env python 
# encoding: utf-8 
'''
@author: chao.li
@contact: chao.li@amlogic.com
@software: pycharm
@file: pytest_redact.py 
@time: 8/12/2025 4:40 PM 
@desc: 
'''

# src/common/pytest_redact.py
from __future__ import annotations
import re
import sys
from pathlib import Path

import pytest


class RedactAbsPaths:
    """
    把输出中的绝对路径打码为 [app]/...（含 traceback、失败摘要等）
    """

    def __init__(self, base: Path, placeholder: str = "[app]"):
        # 统一成绝对规范路径，避免大小写/分隔符差异
        self.base = str(base.resolve())
        self.placeholder = placeholder
        # 兼容 Windows 反斜杠 & 大小写
        self._norm = lambda s: str(Path(s)).replace("\\", "/")

        # 正则：匹配以 base 开头的绝对路径
        b = re.escape(self._norm(self.base))
        self._rx = re.compile(b + r"(/)?", re.IGNORECASE)

    def _scrub(self, text: str) -> str:
        return self._rx.sub(self.placeholder + ("/" if "/" in text else "\\"), self._norm(text))

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item, call):
        outcome = yield
        rep = outcome.get_result()

        # 1) 堆栈/失败长文本
        if getattr(rep, "longrepr", None):
            try:
                # 若是复杂对象，直接替换成“打码后的字符串版”
                rep.longrepr = self._scrub(str(rep.longrepr))
            except Exception:
                pass

        # 2) 失败摘要左侧的 (path, lineno, domain)
        try:
            path, lineno, domain = rep.location
            rep.location = (self._scrub(str(path)), lineno, domain)
        except Exception:
            pass

    def pytest_report_header(self, config):
        # 收集时的 nodeid 也会被 rootdir 处理；这里再保险替换一下当前工作目录
        return f"Output paths redacted to '{self.placeholder}'"


def install_redactor_for_current_process():
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return RedactAbsPaths(base)
