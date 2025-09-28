#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""华硕 AX88U 路由器控制实现."""

from __future__ import annotations

from src.tools.router_tool.AsusRouter.AsusTelnetNvramControl import AsusTelnetNvramControl


class Asusax88uControl(AsusTelnetNvramControl):
    """ASUS AX88U 通过 Telnet/NVRAM 的控制实现."""

    def __init__(self, address: str | None = None):
        super().__init__('asus_88u', display=True, address=address)
