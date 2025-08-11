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
from src.tools.router_tool.Xiaomi.Xiaomiax3600Control import Xiaomiax3600Control
from src.tools.router_tool.Xiaomi.XiaomiBe7000Control import XiaomiBe7000Control

router_list = {'asusax86u': Asusax86uControl, 'asusax88u': Asusax88uControl, 'asusax5400': Asusax5400Control,
          'asusax6700': Asusax6700Control, 'xiaomibe7000': XiaomiBe7000Control,
          'xiaomiax3600': Xiaomiax3600Control}

def get_router(router_name):

    if router_name not in router_list.keys(): raise ValueError("Doesn't support this router")
    return router_list[router_name]()
