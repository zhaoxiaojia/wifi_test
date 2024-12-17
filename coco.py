# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : coco.py
# Time       ：2023/7/26 13:51
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""
from inspect import Signature


# 不允许类实例化
class NoInstance(type):
    def __call__(self, *args, **kwargs):
        raise TypeError("Disable instance")


class User(metaclass=NoInstance):
    pass


# user = User()
# Traceback (most recent call last):
#   File "D:\PycharmProjects\wifi_test\coco.py", line 22, in <module>
#     user = User()
#   File "D:\PycharmProjects\wifi_test\coco.py", line 15, in __call__
#     raise TypeError("Disable instance")
# TypeError: Disable instance

import time


# 单例模式
class Singleton(type):  # 单例模式-定制的元类
    def __init__(self, *args, **kwargs):
        # print(f'__init__ {time.asctime()}')
        self.__instance = None  # 添加一个私有属性，用于保存唯一的实例对象
        super().__init__(*args, **kwargs)

    def __call__(self, *args, **kwargs):  # 控制类调用
        # print(f'__call__ {time.asctime()}')
        if self.__instance is None:
            self.__instance = super().__call__(*args, **kwargs)  # 不存在
            return self.__instance
        else:
            return self.__instance


class User(metaclass=Singleton):
    def __init__(self):
        print("创建用户")


# user1 = User()
# user2 = User()
#
# print(user1 is user2)

# 根据属性缓存对象


import weakref


class Cached(type):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__cache = weakref.WeakValueDictionary()  # 添加一个缓存字典

    def __call__(self, *args, **kwargs):
        if args in self.__cache:  # 通过 参数组合查询缓存字典中有没有对应的对象
            return self.__cache[args]
        else:
            obj = super().__call__(*args)  # 创建对象
            print('-' * 40)
            print(obj)
            print(type(obj))
            print('-' * 40)
            self.__cache[args] = obj  # 根据参数组合（元祖类型）到缓存字典
            return obj


class User(metaclass=Cached):
    def __init__(self, name):
        print("创建用户({!r})".format(name))
        self.name = name


# a = User('coco')


class TestCaseType(type):
    def __new__(cls, name, bases, attrs):
        print('name', name)
        print('bases', bases)
        print('attrs', attrs)

        if {'priority', 'timeout', 'owner', 'status', 'run_test'} - set(attrs.keys()):
            raise TypeError('测试用例类必须包含priority,status,owner,timeout属性并实现run_test方法')
        return super().__new__(cls, name, bases, attrs)


class TestA(metaclass=TestCaseType):
    priority = 'P1'
    timeout = 10
    owner = 'coco'
    status = 'ready'
    # run_test = True


# a = TestA()

class Field:  # 数据库字段
    def __init__(self, name, column_type, primary_key=False):
        self.name = name
        self.column_type = column_type
        self.primary_type = primary_key

    def __str__(self):
        return '<{}:{}>'.format(self.__class__.__name__, self.name)


class StringField(Field):  # 字符串类型字典-对应varchar
    def __init__(self, name, primary_key=False):
        super().__init__(name, 'varchar(100)', primary_key)


class IntegerField(Field):  # 整型字典-对应bigint
    def __init__(self, name, primary_key=False):
        super().__init__(name, 'bigint', primary_key)


class ModelMate(type):  # 元类
    def __new__(cls, name, bases, attrs):
        if name == 'Model':
            return super().__new__(cls, name, bases, attrs)

        table_name = attrs.get('__table__', name.lower())  # 如果类中包含table_name属性，则以该属性作为声明
        mappings = {}
        fields = []
        primary_key = None

        for k, v in attrs.items():
            if isinstance(v, Field):
                mappings[k] = v
                if v.primary_type:
                    if primary_key:
                        raise RuntimeError(f'Duplicate primary key for field: {k}')  # 只允许一个Field声明为主键
                    primary_key = k
                else:
                    fields.append(k)
        if not primary_key:
            raise RuntimeError(f'Primary key not found for table: {table_name}')  # 不允许没有主键

        for k in mappings.keys():
            attrs.pop(k)

        attrs['__table__'] = table_name
        attrs['__mapping__'] = mappings
        attrs['__fields__'] = fields
        attrs['__primary_key__'] = primary_key

        return super().__new__(cls, name, bases, attrs)


class Model(metaclass=ModelMate):  # 数据模型-对应一张数据库表
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def save(self):  # 对象保存方法-对应数据库表插入数据
        fields = []
        params = []
        args = []

        for k, v in self.__mappings__.items():
            if v.primary_type:
                continue
            fields.append(v.name)
            params.append('?')
            args.append(getattr(self, k, None))
        sql = f"INSERT INFO {self.__table__} {','.join(fields)} VALUES ({','.join(params)})"
        print('SQL:', sql)
        print('ARGS:', args)
