#!/usr/bin/env python 
# -*- coding: utf-8 -*-
# @Time    : 2022/3/15 17:02
# @Author  : chao.li
# @Site    :
# @File    : yamlTool.py
# @Software: PyCharm
import logging
from pathlib import Path
from typing import Union
import yaml
from src.util.constants import get_config_base
'''
yaml 格式现在校验网站
https://www.bejson.com/validators/yaml_editor/
'''


class yamlTool:
    def __init__(self, path: Union[str, Path, None] = None):
        if path is None:
            path = get_config_base() / "config.yaml"
        else:
            path = Path(path)
            if not path.is_absolute():
                path = get_config_base() / path
        self.path = path
        with open(self.path, encoding="gbk") as a_yaml_file:
            # 解析yaml
            self.parsed_yaml_file = yaml.load(a_yaml_file, Loader=yaml.FullLoader)

    def get_note(self, note):
        return self.parsed_yaml_file.get(note)

# print(coco.get_note('router'))
# # {'name': 'asusac68u'}
# print(coco.get_note('router')['name'])
# # asusac68u
# print(coco.get_note('wifi'))
# # [{'band': 'autotest2g', 'ssid': 12345678, 'wireless_mode': 'N only', 'channel': 1, 'bandwidth': '40 MHz', 'authentication': 'WPA2-Personal'}, {'band': 'autotest2g', 'ssid': 12345678, 'wireless_mode': 'N only', 'channel': 6, 'bandwidth': '40 MHz', 'authentication': 'WPA2-Personal'}]
# print(coco.get_note('wifi')[0]['band'])
# # autotest2g
