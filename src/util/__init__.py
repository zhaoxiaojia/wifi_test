# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/8/27 14:43
# @Author  : chao.li
# @File    : __init__.py.py

from typing import Any, Iterable

from .constants import Paths, RouterConst, RokuConst

__all__ = ["Paths", "RouterConst", "RokuConst", "parse_host_list"]


def parse_host_list(raw: Any) -> tuple[str, ...]:
    """Split comma-delimited host inputs into a de-duplicated tuple."""

    if raw is None:
        return ()

    if isinstance(raw, str):
        corpus = raw.replace("，", ",").split(",")
    elif isinstance(raw, Iterable):
        corpus = list(raw)
    else:
        return ()

    hosts: list[str] = []
    seen: set[str] = set()
    for entry in corpus:
        text = str(entry).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        hosts.append(text)
    return tuple(hosts)
