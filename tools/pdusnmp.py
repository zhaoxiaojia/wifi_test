# _*_ coding:utf-8 _*_
# 依赖pysnmp 请自行安装(可以使用命令 pip install pysnmp)
import logging
import time

from pysnmp.entity import engine
from pysnmp.entity.rfc3413.oneliner import cmdgen
from pysnmp.proto import rfc1902

# global enter_key
# enter_key = '1.3.6.1.4.1.23280.9.1.2'


class PowerCtrl:
    ENTER_KEY = '1.3.6.1.4.1.23280.8.1.2'

    def __init__(self, sDevIp):
        self.snmpEngine = engine.SnmpEngine()
        if self.validate_ip(sDevIp):
            logging.info(f"power crt ip address: {sDevIp}")
            self.devip = sDevIp
        print(self.devip)

    def validate_ip(self, ip_str):
        sep = ip_str.split('.')
        if len(sep) != 4:
            return False
        for i, x in enumerate(sep):
            try:
                int_x = int(x)
                if int_x < 0 or int_x > 255:
                    return False
            except:
                return False
        return True

    def validate_Sock(self, nSock):
        if (nSock <= 0 or nSock > 8):
            return False
        return True

    def get_value(self, soid):
        cg = cmdgen.CommandGenerator(self.snmpEngine)
        errorIndication, errorStatus, errorIndex, varBinds = cg.getCmd(
            cmdgen.CommunityData('pudinfo', 'public', 0),
            cmdgen.UdpTransportTarget((self.devip, 161)), soid)
        sResult = varBinds[0][1]
        return sResult

    # 获取设备名称
    def get_deviceName(self):
        devName = self.get_value('.1.3.6.1.2.1.1.1.0')
        devName.asOctets().decode('unicode_escape', 'ignore')
        return devName

    # 获取总电压
    def get_totalVoltage(self):
        value = self.get_value('.1.3.6.1.4.1.23280.6.1.2.1')
        rt_value = float(value) / 10
        return rt_value

    # 获取总电流
    def get_totalCurrent(self):
        value = self.get_value('.1.3.6.1.4.1.23280.6.1.3.1')
        rt_value = float(value) / 100
        return rt_value

    # 获取总功率
    def get_totalPower(self):
        value = self.get_value('.1.3.6.1.4.1.23280.6.1.4.1')
        rt_value = float(value) / 1000
        return rt_value

    # 获取总电能
    def get_totalEnergy(self):
        value = self.get_value('.1.3.6.1.4.1.23280.6.1.8.1')
        rt_value = float(value) / 1000
        return rt_value

    # 获取温度
    def get_temprature(self):
        value = self.get_value(self.ENTER_KEY + '.4.6.0')
        rt_value = float(value) / 10
        return rt_value

    # 获取湿度
    def get_humidity(self):
        value = self.get_value(self.ENTER_KEY + '.4.7.0')
        rt_value = float(value) / 10
        return rt_value

    # 打开或关闭指定插口
    def switch(self, sock, onoff):
        if self.validate_Sock(sock) == False:
            print('invalid sock!')
            return None
        sOId = '.1.3.6.1.4.1.23280.9.1.2.%d' % (sock)
        if onoff == True:
            state = 1
        else:
            state = 2
        cg = cmdgen.CommandGenerator(self.snmpEngine)
        errorIndication, errorStatus, errorIndex, varBinds = cg.setCmd(
            cmdgen.CommunityData('pudinfo', 'private', 0),
            cmdgen.UdpTransportTarget((self.devip, 161)),
            (sOId, rfc1902.Integer(state)))

        return errorStatus

    # 获取插口状态 1-关闭 2-开启
    def get_status(self, sock):
        if self.validate_Sock(sock) == False:
            print('invalid sock!')
            return None
        sOId = '.1.3.6.1.4.1.23280.8.1.2.%d' % (sock)
        # print("sOId:{0}".format(sOId))
        cg = cmdgen.CommandGenerator(self.snmpEngine)
        errorIndication, errorStatus, errorIndex, varBinds = cg.getCmd(
            cmdgen.CommunityData('pudinfo', 'public', 0),
            cmdgen.UdpTransportTarget((self.devip, 161)), sOId)
        # print(varBinds)
        # print(varBinds[0])
        sResult = varBinds[0][1]
        # print(sResult)
        return sResult
        # if sResult == b'on':
        #   return 0
        # elif sResult == b'off':
        #   return 1

        # return errorStatus

    # 获取指定插口电流
    def get_electric(self, nsock):
        if self.validate_Sock(nsock) == False:
            print('invalid sock!')
            return None
        sOId = '.1.3.6.1.4.1.23280.8.1.4.%d' % (nsock)
        value = self.get_value(sOId)
        rt_value = float(value) / 100
        return rt_value

    # 获取指定插口电能
    def get_energy(self, nSock):
        if self.validate_Sock(nSock) == False:
            print('invalid sock!')
            return None
        sOId = self.ENTER_KEY + '.4.%d.0' % (31 + nSock)
        value = self.get_value(sOId)
        rt_value = float(value) / 100
        return rt_value

    # 获取指定插口电压
    def get_voltage(self, nsock):
        if self.validate_Sock(nsock) == False:
            print('invalid sock!')
            return None
        sOId = '.1.3.6.1.4.1.23280.8.1.3.%d' % (nsock)
        value = str(self.get_value(sOId))
        rt_value = float(value) / 10
        return rt_value

    # 获取指定插口名称
    def get_sockName(self, nSock):
        if self.validate_Sock(nSock) == False:
            print('invalid sock!')
            return None
        sOId = '.1.3.6.1.4.1.23273.4' + '.%d.1' % (7 + nSock)
        value = self.get_value(sOId).asOctets().decode('unicode_escape', 'ignore')
        return value

    # 仅保留指定端口上电
    def survival(self,nSock):
        for i in range(1,9):
            if i == nSock:
                self.switch(i, True)
                continue
            self.switch(i,False)

    # 关闭所有端口电源
    def dark(self):
        for i in range(1,9):
            self.switch(i,False)

s = PowerCtrl("192.168.50.230")
s.switch(2, True)
# s.dark()
# s.survival(1)
# print(s.get_status(1))
# time.sleep(1)
# print("start on")
# s.switch(1, True)
# print(s.get_status(2))
