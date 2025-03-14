# _*_ coding:utf-8 _*_
# 依赖pysnmp 请自行安装(可以使用命令 pip install pysnmp)
import logging
import os
import subprocess
import sys
import time

from pysnmp.entity import engine
import pysnmp
from tools.yamlTool import yamlTool

from pysnmp.hlapi import *
from pysnmp.proto import rfc1902


# global enter_key
# enter_key = '1.3.6.1.4.1.23280.9.1.2'


# class PowerCtrl:
#     ENTER_KEY = '1.3.6.1.4.1.23280.8.1.2'
#
#     def __init__(self, sDevIp):
#         if self.validate_ip(sDevIp):
#             logging.info(f"Power Control IP Address: {sDevIp}")
#             self.devip = sDevIp
#         else:
#             raise ValueError("Invalid IP address")
#         print(self.devip)
#
#     @staticmethod
#     def validate_ip(ip_str):
#         parts = ip_str.split('.')
#         if len(parts) != 4:
#             return False
#         try:
#             return all(0 <= int(x) <= 255 for x in parts)
#         except ValueError:
#             return False
#
#     @staticmethod
#     def validate_Sock(nSock):
#         return 1 <= nSock <= 8
#
#     def get_value(self, soid):
#         iterator = getCmd(
#             SnmpEngine(),
#             CommunityData('pudinfo', mpModel=0),
#             UdpTransportTarget((self.devip, 161)),
#             ContextData(),
#             ObjectType(ObjectIdentity(soid))
#         )
#         for errorIndication, errorStatus, errorIndex, varBinds in iterator:
#             if errorIndication:
#                 raise Exception(f"SNMP Error: {errorIndication}")
#             elif errorStatus:
#                 raise Exception(f"SNMP Error: {errorStatus.prettyPrint()}")
#             else:
#                 return varBinds[0][1].prettyPrint()  # 兼容 Python 3.x
#
#     def get_deviceName(self):
#         return self.get_value('1.3.6.1.2.1.1.1.0')
#
#     def get_totalVoltage(self):
#         return float(self.get_value('1.3.6.1.4.1.23280.6.1.2.1')) / 10
#
#     def get_totalCurrent(self):
#         return float(self.get_value('1.3.6.1.4.1.23280.6.1.3.1')) / 100
#
#     def get_totalPower(self):
#         return float(self.get_value('1.3.6.1.4.1.23280.6.1.4.1')) / 1000
#
#     def get_totalEnergy(self):
#         return float(self.get_value('1.3.6.1.4.1.23280.6.1.8.1')) / 1000
#
#     def get_temprature(self):
#         return float(self.get_value(self.ENTER_KEY + '.4.6.0')) / 10
#
#     def get_humidity(self):
#         return float(self.get_value(self.ENTER_KEY + '.4.7.0')) / 10
#
#     def switch(self, sock, onoff):
#         if not self.validate_Sock(sock):
#             print('Invalid sock!')
#             return None
#         sOId = f'.1.3.6.1.4.1.23280.9.1.2.{sock}'
#         state = 1 if onoff else 2
#
#         iterator = setCmd(
#             SnmpEngine(),
#             CommunityData('pudinfo', mpModel=0),
#             UdpTransportTarget((self.devip, 161)),
#             ContextData(),
#             ObjectType(ObjectIdentity(sOId), Integer(state))
#         )
#         for errorIndication, errorStatus, errorIndex, varBinds in iterator:
#             if errorIndication:
#                 return f"Error: {errorIndication}"
#             elif errorStatus:
#                 return f"SNMP Error: {errorStatus.prettyPrint()}"
#             return "Success"
#
#     def get_status(self, sock):
#         if not self.validate_Sock(sock):
#             print('Invalid sock!')
#             return None
#         sOId = f'.1.3.6.1.4.1.23280.8.1.2.{sock}'
#         return self.get_value(sOId)
#
#     def dark(self):
#         for i in range(1, 9):
#             self.switch(i, False)


class power_ctrl:
    SWITCH_CMD = 'snmpset -v1 -c private {} .1.3.6.1.4.1.23280.9.1.2.{} i {}'
    SET_CMD = 'snmpset -v1 -c private {} 1.3.6.1.4.1.23273.4.4{}.0 i 255'

    def __init__(self):
        self.config = yamlTool(os.path.join(os.getcwd(), 'config/config.yaml'))
        self.power_ctrl = self.config.get_note('power_relay')
        self.ip_list = list(self.power_ctrl.keys())
        self.ctrl = self._handle_env_data()

    def _handle_env_data(self):
        temp = []
        for k, v in self.power_ctrl.items():
            if v:
                for i in v:
                    temp.append((k, i))
        return temp

    @staticmethod
    def check_output(cmd):
        try:
            info = subprocess.check_output(cmd, shell=True)
            logging.info(info)
            return info
        except subprocess.CalledProcessError as e:
            logging.error(f"Command failed: {e}")
            return None

    def switch(self, ip, port, status):
        logging.info(f'Setting power relay: {ip} port {port} {"on" if status == 1 else "off"}')
        cmd = self.SWITCH_CMD.format(ip, port, status)
        self.check_output(cmd)

    def set_all(self, status):
        for k in ['192.168.200.3', '192.168.200.3', '192.168.200.5', '192.168.200.6']:
            cmd = self.SET_CMD.format(k, 0 if status else 1)
            self.check_output(cmd)

    def shutdown(self):
        logging.info('Shutting down all relays')
        self.set_all(False)

    # def poweron(self):
    #     logging.info('Powering on all relays')
    #     self.set_all(True)

# s = PowerCtrl("192.168.50.230")
# s.switch(2, True)
# s.dark()
# s.survival(1)
# print(s.get_status(1))
# time.sleep(1)
# print("start on")
# s.switch(1, True)
# print(s.get_status(2))

# s = power_ctrl()
# s.switch('192.168.200.4',4,1)
