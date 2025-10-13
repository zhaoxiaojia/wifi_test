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
    def __init__(self, path: Union[str, Path]):
        resolved = Path(path)
        if not resolved.is_absolute():
            resolved = get_config_base() / resolved
        self.path = resolved
        self.parsed_yaml_file = self._load_file()

    def _load_file(self) -> dict:
        for encoding in ("utf-8", "gbk"):
            try:
                with self.path.open(encoding=encoding) as stream:
                    return yaml.load(stream, Loader=yaml.FullLoader) or {}
            except UnicodeDecodeError:
                continue
            except Exception as exc:  # pragma: no cover - I/O 依赖环境
                logging.error("Failed to load yaml %s: %s", self.path, exc)
                break
        return {}

    def get_note(self, note):
        return self.parsed_yaml_file.get(note)

# print(coco.get_note('router'))
# # {'name': 'asusac68u'}
# print(coco.get_note('router')['name'])
# # asusac68u
# print(coco.get_note('wifi'))
# # [{'band': 'autotest2g', 'ssid': 12345678, 'wireless_mode': 'N only', 'channel': 1, 'bandwidth': '40 MHz', 'security_mode': 'WPA2-Personal'}, {'band': 'autotest2g', 'ssid': 12345678, 'wireless_mode': 'N only', 'channel': 6, 'bandwidth': '40 MHz', 'security_mode': 'WPA2-Personal'}]
# print(coco.get_note('wifi')[0]['band'])
# # autotest2g
