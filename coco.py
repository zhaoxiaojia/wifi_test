# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : coco.py
# Time       ：2023/7/26 13:51
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import random


class emploee:
    __name = 65

    def __init__(self, age):
        emploee.__name += 1
        self.name = chr(emploee.__name)
        self.age = age
        self.ability = 100 - self.age

    def doWork(self):
        self.ability -= 5

    def __str__(self):
        return f'Name {self.name} Age {self.age} Ability {self.ability}'


class boss:
    employeelist = []

    def __init__(self):
        self.money = random.randrange(40000, 50000)
        self.work = random.randrange(200, 250)

    def startWork(self):
        print(f'{self.work} remaining')
        while boss.employeelist:
            self.work -= boss.employeelist.pop().ability
            if self.work < 0:
                print('Work done')
                return False
        if self.work > 0:
            print(f'{self.work} remaining,pls hire more staff')
        return True

    def addEmployee(self, employee):
        print(f'hire employee {employee.name}')
        self.money -= 5000
        boss.employeelist.append(employee)

    @classmethod
    def endWork(cls):
        for i in cls.employeelist:
            print(i)


a = emploee(30)
b = emploee(40)
c = emploee(50)

bo = boss()
bo.addEmployee(a)
bo.addEmployee(b)
bo.addEmployee(c)
while bo.startWork():
    bo.addEmployee(a)
