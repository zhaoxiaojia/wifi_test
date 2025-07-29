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
from src.tools.router_tool.AsusRouter.Asusax5400Control import Asusax5400Control
from src.tools.router_tool.AsusRouter.Asusax6700Control import Asusax6700Control
from src.tools.router_tool.Xiaomi.Xiaomiax3000Control import Xiaomiax3000Control
from src.tools.router_tool.Xiaomi.XiaomiRedax6000Control import \
    XiaomiRedax6000Control


def get_router(router_name):
    router = {'asusax86u': Asusax86uControl, 'asusax88u': Asusax88uControl, 'asusax5400': Asusax5400Control,
              'asusax6700': Asusax6700Control, 'xiaomiredax6000': XiaomiRedax6000Control,
              'xiaomiax3000': Xiaomiax3000Control}
    if router_name not in router.keys(): raise ValueError("Doesn't support this router")
    return router[router_name]()
