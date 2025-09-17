#!/usr/bin/env python 
# -*- coding: utf-8 -*-
# @Time    : 2022/3/22 16:17
# @Author  : chao.li
# @Site    :
# @File    : Asusax88uControl.py
# @Software: PyCharm


import logging
import time
from src.tools.connect_tool import TelnetTool
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from src.tools.router_tool.RouterControl import ConfigError
from src.tools.router_tool.AsusRouter.AsusBaseControl import AsusBaseControl


class Asusax88uControl(AsusBaseControl):
    '''
    Asus ac88u router

    Attributes:

    rvr
    0,2.4G, AX86U-2G,11ax ,6,40 MHz ,  Open System , ,rx,TCP,13 ,10 10
    '''
    MODE_PARAM = {
        'Open System': 'openowe',
        'Shared Key': 'shared',
        'WPA2-Personal': 'psk2',
        'WPA3-Personal': 'sae',
        'WPA/WPA2-Personal': 'pskpsk2',
        'WPA2/WPA3-Personal': 'psk2sae',
        # 'WPA2-Enterprise': '6',
        # 'WPA/WPA2-Enterprise': '7',
    }



    def __init__(self, address: str | None = None):
        super().__init__('asus_88u', display=True, address=address)
        self.host = self.address
        self.port = 23
        self.prompt = b':/tmp/home/root#'  # 命令提示符
        self.telnet = TelnetTool(self.host)

    def _init_telnet(self):
        """初始化Telnet连接并登录"""
        self.telnet.login("admin", str(self.xpath['passwd']), self.prompt)

    def _ensure_telnet(self):
        """确保Telnet连接可用，必要时尝试重新登录"""
        if not self.telnet.is_connected():
            try:
                self.telnet.login("admin", str(self.xpath['passwd']), self.prompt)
            except Exception as e:
                logging.error(f"Telnet login exception: {e}")
        if not self.telnet.is_connected():
            raise ConnectionError("Telnet连接不可用")

    def telnet_write(self, cmd, max_retries=3):
        """使用已建立的Telnet连接执行命令（修复：复用连接）"""
        logging.info("Executing command: %s", cmd)
        retries = 0
        while retries < max_retries:
            try:
                self._ensure_telnet()
                output = self.telnet.checkoutput(cmd)
                if output and "error" in output.lower():
                    logging.warning(f"Command error: {output}")
                return output
            except Exception as e:
                logging.warning(f"Connection error, retrying ({retries + 1}/{max_retries}): {e}")
                self.telnet.close()
                retries += 1
        logging.error(f"Failed to execute command after {max_retries} retries")
        return None

    def kill_telnet_connections(self):
        """强制终止路由器上的Telnet相关进程，释放端口"""
        try:
            self._ensure_telnet()
            # 终止所有Telnet服务进程（包括残留连接）
            output = self.telnet.checkoutput("killall telnetd")
            logging.info("Terminate telnetd output: %s", output)
            time.sleep(2)
            # restart telnet service
            output = self.telnet.checkoutput("telnetd")
            logging.info("Restart telnetd output: %s", output)
            logging.info("Telnet connection released, port 23 available")
        except Exception as e:
            logging.error(f"Kill telnet connections failed: {e}")
            self.telnet.close()

    def quit(self):
        try:
            self._ensure_telnet()
            self.telnet.execute_cmd("exit")
        except Exception as e:
            logging.error(f"Telnet quit failed: {e}")
        finally:
            self.telnet.close()

    def set_2g_ssid(self, ssid):
        cmd = 'nvram set wl0_ssid={};'
        self.telnet_write(cmd.format(ssid))

    def set_5g_ssid(self, ssid):
        cmd = 'nvram set wl1_ssid={};'
        self.telnet_write(cmd.format(ssid))

    def set_2g_wireless(self, mode):
        cmd = {
            'auto': 'nvram set wl0_he_features=0;nvram set wl0_nmode_x=0;',
            '11n': 'nvram set wl0_he_features=0;nvram set wl0_nmode_x=1;',
            '11g': 'nvram set wl0_he_features=0;nvram set wl0_nmode_x=5;',
            '11b': 'nvram set wl0_he_features=0;nvram set wl0_nmode_x=6;',
            '11ax': 'nvram set wl0_he_features=31;nvram set wl0_nmode_x=9;nvram set wl0_vhtmode=2;',
            'Legacy': 'nvram set wl0_he_features=0;nvram set wl0_nmode_x=2;',
        }
        if mode not in self.WIRELESS_2:
            raise ConfigError('wireless element error')
        self.telnet_write(cmd[mode])

    def set_5g_wireless(self, mode):
        cmd = {
            'auto': 'nvram set wl1_he_features=0;nvram set wl1_nmode_x=0;',
            '11a': 'nvram set wl1_he_features=0;nvram set wl1_nmode_x=7;',
            '11ac': 'nvram set wl1_he_features=0;nvram set wl1_nmode_x=3;',
            '11ax': 'nvram set wl1_he_features=7;nvram set wl1_nmode_x=9;nvram set wl1_vhtmode=2;',
            'Legacy': 'nvram set wl1_he_features=0;nvram set wl1_nmode_x=2;',
        }
        if mode not in self.WIRELESS_5:
            raise ConfigError('wireless element error')
        self.telnet_write(cmd[mode])

    def set_2g_password(self, passwd):
        cmd = 'nvram set wl0_wpa_psk={};'
        self.telnet_write(cmd.format(passwd))

    def set_5g_password(self, passwd):
        cmd = 'nvram set wl1_wpa_psk={};'
        self.telnet_write(cmd.format(passwd))

    def set_2g_authentication(self, method):
        cmd = 'nvram set wl0_auth_mode_x={};'
        mode_list = self.AUTHENTICATION_METHOD if method != 'Legacy' \
            else self.AUTHENTICATION_METHOD_LEGCY
        if method not in mode_list:
            raise ConfigError('security protocol method element error')
        self.telnet_write(cmd.format(self.MODE_PARAM[method]))
        if method == 'Open System':
            self.set_2g_wep_encrypt('None')

    def set_5g_authentication(self, method):
        cmd = 'nvram set wl1_auth_mode_x={};'
        mode_list = self.AUTHENTICATION_METHOD if method != 'Legacy' \
            else self.AUTHENTICATION_METHOD_LEGCY
        if method not in mode_list:
            raise ConfigError('security protocol method element error')
        self.telnet_write(cmd.format(self.MODE_PARAM[method]))
        if method == 'Open System':
            self.set_5g_wep_encrypt('None')

    def set_2g_channel(self, channel):
        cmd = 'nvram set wl0_chanspec={};'
        channel = str(channel)
        if channel not in self.CHANNEL_2:
            raise ConfigError('channel element error')
        channel = 0 if channel == 'auto' else channel
        self.telnet_write(cmd.format(channel))

    def set_5g_channel(self, channel):
        cmd = 'nvram set wl1_chanspec={}/80;'
        channel = str(channel)
        if channel not in self.CHANNEL_5:
            raise ConfigError('channel element error')
        channel = 0 if channel == 'auto' else channel
        self.telnet_write(cmd.format(channel))

    def set_2g_bandwidth(self, width):
        cmd = 'nvram set wl0_bw={};'
        if width not in self.BANDWIDTH_2:
            raise ConfigError('bandwidth element error')
        self.telnet_write(cmd.format(self.BANDWIDTH_2.index(width)))

    def set_5g_bandwidth(self, width):
        cmd = 'nvram set wl1_bw={};'
        if width not in self.BANDWIDTH_5: raise ConfigError('bandwidth element error')
        self.telnet_write(cmd.format(self.BANDWIDTH_5.index(width)))

    def set_2g_wep_encrypt(self, encrypt):
        cmd = 'nvram set wl0_wep_x={};nvram set w1_wep_x={};'
        if encrypt not in self.WEP_ENCRYPT:
            raise ConfigError('wep encrypt elemenr error')
        # passwd_wep
        index = '1' if '64' in encrypt else '2'
        index = '0' if encrypt == 'None' else index
        self.telnet_write(cmd.format(index, index))

    def set_5g_wep_encrypt(self, encrypt):
        cmd = 'nvram set wl1_wep_x={};nvram set w1_wep_x={};'
        if encrypt not in self.WEP_ENCRYPT:
            raise ConfigError('wep encrypt elemenr error')
        # passwd_wep
        index = '1' if '64' in encrypt else '2'
        index = '0' if encrypt == 'None' else index
        self.telnet_write(cmd.format(index, index))

    def set_2g_wep_passwd(self, passwd):
        cmd = 'nvram set wl0_key1={};'
        self.telnet_write(cmd.format(passwd))

    def set_5g_wep_passwd(self, passwd):
        cmd = 'nvram set wl1_key1={};'
        self.telnet_write(cmd.format(passwd))

    def commit(self):
        self.telnet_write('nvram commit;')
        time.sleep(1)
        self.telnet_write('restart_wireless;')
        time.sleep(5)

    def change_setting(self, router):
        '''
        set up wifi envrioment
        @param router: Router instance
        @return: status : boolean
        '''

        if router.ssid:
            self.set_2g_ssid(router.ssid) if '2' in router.band else self.set_5g_ssid(router.ssid)

        # 修改 wireless_mode
        if router.wireless_mode:
            self.set_2g_wireless(router.wireless_mode) if '2' in router.band else self.set_5g_wireless(router.wireless_mode)

        # 修改 password
        if router.password:
            self.set_2g_password(router.password) if '2' in router.band else self.set_5g_password(
                router.password)

        # 修改 security_mode
        if router.security_mode:
            self.set_2g_authentication(router.security_mode) if '2' in router.band else self.set_5g_authentication(router.security_mode)

        # 修改channel
        if router.channel:
            self.set_2g_channel(router.channel) if '2' in router.band else self.set_5g_channel(router.channel)

        # 修改 bandwidth
        if router.bandwidth:
            self.set_2g_bandwidth(router.bandwidth) if '2' in router.band else self.set_5g_bandwidth(router.bandwidth)

        # 修改 wep_encrypt
        if router.wep_encrypt:
            self.set_2g_wep_encrypt(router.wep_encrypt) if '2' in router.band else self.set_5g_wep_encrypt(
                router.wep_encrypt)

        # 修改 wep_passwd
        # if router.wep_passwd:
        #     self.set_2g_wep_passwd(router.wep_passwd) if '2' in router.band else self.set_5g_wep_passwd(
        #         router.wep_passwd)

        self.commit()
        time.sleep(3)
        logging.info('Router setting done')
        return True





# ['Open System', 'WPA2-Personal', 'WPA3-Personal', 'WPA/WPA2-Personal', 'WPA2/WPA3-Personal',
#                              'WPA2-Enterprise', 'WPA/WPA2-Enterprise']
# fields = ['serial', 'band', 'ssid', 'wireless_mode', 'channel', 'bandwidth', 'security_mode',
#           'password', 'test_type', 'protocol_type', 'wep_encrypt', 'wep_passwd',
#           'hide_ssid', 'hide_type', 'wpa_encrypt', 'passwd_index', 'protect_frame',
#           'smart_connect', 'country_code']
# from collections import namedtuple
#
# ssid = 'coco'
# passwd = '12345678'
# Router = namedtuple('Router', fields, defaults=[None, ] * len(fields))
# router = Router(band='5G', ssid=ssid, wireless_mode='11ax', channel='36', bandwidth='80 MHz',
#                 authentication='WPA2-Personal', password='12345678', country_code="欧洲")
# control = Asusax88uControl("192.168.5.1")
# control.change_country(router)
# control.quit()
# control.change_setting(router)
# control.quit()
# # control.change_country(router)
# # control.router_control.reboot_router()
