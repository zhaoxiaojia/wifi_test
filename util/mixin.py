#!/usr/bin/env python 
# encoding: utf-8 
'''
@author: chao.li
@contact: chao.li@amlogic.com
@software: pycharm
@file: mixin.py 
@time: 2025/2/13 13:42 
@desc: 
'''

import json


class json_mixin:
    def to_dict(self):
        return self.__convert_dict(self.__dict__)

    def to_json(self):
        return json.dumps(self.to_dict())

    def __convert_dict(self, attrs: dict):
        result = {}
        for key, value in attrs.items():
            result[key] = self.__convert_value(value)
        return result

    def __convert_value(self, value):
        if isinstance(value, dict):
            return self.__convert_dict(value)
        elif isinstance(value, list):
            return [self.__convert_value(v) for v in value]
        elif hasattr(value, '__dict__'):
            return self.__convert_dict(value.__dict__)
        else:
            return value
