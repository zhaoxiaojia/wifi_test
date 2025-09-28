#!/usr/bin/env python 
# encoding: utf-8 
'''
@author: chao.li
@contact: chao.li@amlogic.com
@software: pycharm
@file: router_factory.py 
@time: 2024/12/17 14:08 
@desc: 
'''

from src.tools.router_tool.AsusRouter.Asusax86uControl import Asusax86uControl
from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from src.tools.router_tool.AsusRouter.Asusax88uProControl import Asusax88uProControl
from src.tools.router_tool.AsusRouter.Asusax5400Control import Asusax5400Control
from src.tools.router_tool.AsusRouter.Asusax6700Control import Asusax6700Control
from src.tools.router_tool.Xiaomi.Xiaomiax3600Control import Xiaomiax3600Control
from src.tools.router_tool.Xiaomi.XiaomiBe7000Control import XiaomiBe7000Control
from src.tools.config_loader import load_config

router_list = {
    'asusax86u': Asusax86uControl,
    'asusax88u': Asusax88uControl,
    'asusax88upro': Asusax88uProControl,
    # 'asusax5400': Asusax5400Control,
    # 'asusax6700': Asusax6700Control,
    'xiaomibe7000': XiaomiBe7000Control,
    'xiaomiax3600': Xiaomiax3600Control,
}


def get_router(router_name: str, address: str | None = None):
    """根据路由器名称获取对应控制对象

    Parameters
    ----------
    router_name: str
        路由器名称
    address: str | None
        指定的网关地址，若为空则尝试从配置文件读取
    """

    if router_name not in router_list:
        raise ValueError("Doesn't support this router")

    if address is None:
        try:
            cfg = load_config(refresh=True)
            cfg_router = cfg.get('router', {})
            if cfg_router.get('name') == router_name:
                address = cfg_router.get('address')
        except Exception:
            address = None

    return router_list[router_name](address)
