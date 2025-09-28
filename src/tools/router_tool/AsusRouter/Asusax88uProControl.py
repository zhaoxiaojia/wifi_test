#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""华硕 AX88U Pro 路由器控制实现."""

from __future__ import annotations

from src.tools.router_tool.AsusRouter.AsusTelnetNvramControl import AsusTelnetNvramControl


class Asusax88uProControl(AsusTelnetNvramControl):
    """ASUS AX88U Pro 通过 Telnet/NVRAM 的控制实现."""

    CHANNEL_5 = ['auto', '36', '40', '44', '48', '52', '56', '60', '64', '100', '104', '108', '112', '116',
                 '120', '124', '128', '132', '136', '140', '144', '149', '153', '157', '161', '165', '169',
                 '173', '177']

    def __init__(self, address: str | None = None):
        super().__init__('asus_88u_pro', display=True, address=address)
