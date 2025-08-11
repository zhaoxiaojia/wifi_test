#!/usr/bin/env python 
# -*- coding: utf-8 -*-
# @Time    : 2022/3/22 16:17
# @Author  : chao.li
# @Site    :
# @File    : Asusax88uControl.py
# @Software: PyCharm


import logging
import os
import telnetlib
import time

from urllib.parse import urlparse
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from src.tools.yamlTool import yamlTool
from src.tools.router_tool.RouterControl import ConfigError, RouterTools


class Asusax88uControl(RouterTools):
    '''
    Asus ac88u router

    Attributes:

    rvr
    0,2.4 GHz, AX86U-2G,11ax ,6,40 MHz ,  Open System , ,rx,TCP,13 ,10 10
    '''
    SCROL_JS = 'arguments[0].scrollIntoView();'

    # asus router setup value
    BAND_LIST = ['2.4 GHz', '5 GHz']
    BANDWIDTH_2 = ['20/40 MHz', '20 MHz', '40 MHz']
    BANDWIDTH_5 = ['20/40/80 MHz', '20 MHz', '40 MHz', '80 MHz']
    WIRELESS_2 = ['自动', '11b', '11g', '11n', '11ax', 'Legacy', 'N only']
    WIRELESS_5: list[str] = ['自动', '11a', '11ac', '11ax', 'Legacy', 'N/AC/AX mixed', 'AX only']

    AUTHENTICATION_METHOD = ['Open System', 'WPA2-Personal', 'WPA3-Personal', 'WPA/WPA2-Personal', 'WPA2/WPA3-Personal',
                             'WPA2-Enterprise', 'WPA/WPA2-Enterprise']

    AUTHENTICATION_METHOD_LEGCY = ['Open System', 'Shared Key', 'WPA2-Personal', 'WPA3-Personal',
                                   'WPA/WPA2-Personal', 'WPA2/WPA3-Personal', 'WPA2-Enterprise',
                                   'WPA/WPA2-Enterprise', 'Radius with 802.1x']

    PROTECT_FRAME = {
        '停用': 1,
        '非强制启用': 2,
        '强制启用': 3
    }

    WEP_ENCRYPT = ['None', 'WEP-64bits', 'WEP-128bits']

    WPA_ENCRYPT = {
        'AES': 1,
        'TKIP+AES': 2
    }

    PASSWD_INDEX_DICT = {
        '1': '1',
        '2': '2',
        '3': '3',
        '4': '4'
    }
    CHANNEL_2 = ['自动', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11']
    CHANNEL_5 = ['自动', '36', '40', '44', '48', '52', '56', '60', '64', '100', '104', '108', '112', '116', '120',
                 '124', '128', '132', '136', '140', '144', '149', '153', '157', '161', '165']
    COUNTRY_CODE = {
        '亚洲': '1',
        '中国 (默认值)': '2',
        '欧洲': '3',
        '韩国': '4',
        '俄罗斯': '5',
        '新加坡': '6',
        '美国': '7',
        '澳大利亚': '8'
    }
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
    CHANNEL_5_DICT = {
        '自动': '1',
        '36': '2',
        '40': '3',
        '44': '4',
        '48': '5',
        '52': '6',
        '56': '7',
        '60': '8',
        '64': '9',
        '149': '10',
        '153': '11',
        '157': '12',
        '161': '13',
    }

    def __init__(self):
        self.yaml_info = yamlTool(os.getcwd() + f'\\config\\router_xpath\\asus_xpath.yaml')
        self.xpath = self.yaml_info.get_note('asus')
        addr = self.xpath['address']['88u']
        self.host = urlparse(addr).hostname or addr
        self.port = 23
        self.prompt = b'admin@RT-AX88U-D8C0:/tmp/home/root#'  # 命令提示符
        self.tn = None

    def _init_telnet(self):
        """初始化Telnet连接并登录"""
        tn = telnetlib.Telnet(self.host, self.port, timeout=10)
        tn.read_until(b'login:')
        tn.write("admin".encode('ascii') + b'\n')
        tn.read_until(b'Password:')
        tn.write(str(self.xpath['passwd']).encode("ascii") + b'\n')
        tn.read_until(self.prompt)  # 等待登录成功
        return tn

    def telnet_write(self, cmd, max_retries=3):
        """使用已建立的Telnet连接执行命令（修复：复用连接）"""
        logging.info(f"Executing command: {cmd}")
        print(f"Executing command: {cmd}")
        retries = 0
        while retries < max_retries:
            try:
                if self.tn is None:
                    self.tn = self._init_telnet()
                self.tn.write(cmd.encode('ascii') + b'\n')  # 发送命令
                output = self.tn.read_until(self.prompt, timeout=10).decode('ascii', errors='ignore')
                if "error" in output.lower():
                    logging.warning(f"Command error: {output}")
                return output
            except Exception as e:
                logging.warning(f"Connection error, retrying ({retries + 1}/{max_retries}): {e}")
                retries += 1
                if self.tn is not None:
                    self.tn.close()
                    self.tn = None
        return None

    def kill_telnet_connections(self):
        """强制终止路由器上的Telnet相关进程，释放端口"""
        try:
            # 终止所有Telnet服务进程（包括残留连接）
            output = self.telnet_write("killall telnetd\n")
            logging.info(f"终止Telnet进程输出: {output}")
            time.sleep(2)  # 等待进程终止

            # 重新启动Telnet服务
            output = self.telnet_write("telnetd\n")
            logging.info(f"重启Telnet服务输出: {output}")
            print("Telnet连接已释放，端口23可用")
        except Exception as e:
            print(f"执行命令失败（可能已无法建立连接）: {e}")

    def quit(self):
        try:
            if self.tn:
                self.tn.write(b"exit\n")
                logging.info(self.tn.read_all().decode('ascii'))
        except Exception as e:
            logging.info("Error: %s", str(e))

    def set_2g_ssid(self, ssid):
        cmd = 'nvram set wl0_ssid={};'
        self.telnet_write(cmd.format(ssid))

    def set_5g_ssid(self, ssid):
        cmd = 'nvram set wl1_ssid={};'
        self.telnet_write(cmd.format(ssid))

    def set_2g_wireless(self, mode):
        cmd = {
            '自动': 'nvram set wl0_11ax=0;nvram set wl0_nmode_x=0;',
            '11n': 'nvram set wl0_11ax=0;nvram set wl0_nmode_x=1;',
            '11g': 'nvram set wl0_11ax=0;nvram set wl0_nmode_x=5;',
            '11b': 'nvram set wl0_11ax=0;nvram set wl0_nmode_x=6;',
            '11ax': 'nvram set wl0_11ax=1;nvram set wl0_nmode_x=9;',
            'Legacy': 'nvram set wl0_11ax=0;nvram set wl0_nmode_x=2;',
        }
        if mode not in self.WIRELESS_2:
            raise ConfigError('wireless elemenr error')
        self.telnet_write(cmd[mode])

    def set_5g_wireless(self, mode):
        cmd = {
            '自动': 'nvram set wl1_11ax=0;nvram set wl1_nmode_x=0;',
            '11a': 'nvram set wl1_11ax=0;nvram set wl1_nmode_x=7;',
            '11ac': 'nvram set wl1_11ax=0;nvram set wl1_nmode_x=3;',
            '11ax': 'nvram set wl1_11ax=1;nvram set wl1_nmode_x=9;',
            'Legacy': 'nvram set wl1_11ax=0;nvram set wl1_nmode_x=2;',
        }
        if mode not in self.WIRELESS_5:
            raise ConfigError('wireless elemenr error')
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
            raise ConfigError('authentication method element error')
        self.telnet_write(cmd.format(self.MODE_PARAM[method]))
        if method == 'Open System':
            self.set_2g_wep_encrypt('None')

    def set_5g_authentication(self, method):
        cmd = 'nvram set wl1_auth_mode_x={};'
        mode_list = self.AUTHENTICATION_METHOD if method != 'Legacy' \
            else self.AUTHENTICATION_METHOD_LEGCY
        if method not in mode_list:
            raise ConfigError('authentication method element error')
        self.telnet_write(cmd.format(self.MODE_PARAM[method]))
        if method == 'Open System':
            self.set_5g_wep_encrypt('None')

    def set_2g_channel(self, channel):
        cmd = 'nvram set wl0_chanspec={};'
        channel = str(channel)
        if channel not in self.CHANNEL_2:
            raise ConfigError('channel element error')
        channel = 0 if channel == '自动' else channel
        self.telnet_write(cmd.format(channel))

    def set_5g_channel(self, channel):
        cmd = 'nvram set wl1_chanspec={}/80;'
        channel = str(channel)
        if channel not in self.CHANNEL_5:
            raise ConfigError('channel element error')
        channel = 0 if channel == '自动' else channel
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
            self.set_2g_wireless(router.wireless_mode) if '2' in router.band else self.set_5g_wireless(
                router.wireless_mode)

        # 修改 password
        if router.password:
            self.set_2g_password(router.password) if '2' in router.band else self.set_5g_password(
                router.password)

        # 修改 authentication
        if router.authentication:
            self.set_2g_authentication(
                router.authentication) if '2' in router.band else self.set_5g_authentication(
                router.authentication)

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
        if router.wep_passwd:
            self.set_2g_wep_passwd(router.wep_passwd) if '2' in router.band else self.set_5g_wep_passwd(
                router.wep_passwd)

        self.commit()
        time.sleep(3)
        logging.info('Router setting done')
        return True

    def change_country(self, router):
        try:
            self.router_control.login()
            self.router_control.driver.find_element(By.ID, 'Advanced_Wireless_Content_menu').click()
            # Wireless - General
            WebDriverWait(driver=self.router_control.driver, timeout=5, poll_frequency=0.5).until(
                EC.presence_of_element_located((By.ID, 'FormTitle')))
            # 修改 国家码
            if router.country_code:
                if router.country_code not in self.COUNTRY_CODE: raise ConfigError('country code error')
                self.router_control.driver.find_element(
                    By.XPATH, '//*[@id="Advanced_WAdvanced_Content_tab"]/span').click()
                WebDriverWait(driver=self.router_control.driver, timeout=5, poll_frequency=0.5).until(
                    EC.presence_of_element_located((By.ID, 'titl_desc')))
                index = self.COUNTRY_CODE[router.country_code]
                # logging.info(self.router_control.xpath['country_code_element'][self.router_control.router_info].format(index))
                self.router_control.driver.find_element(
                    By.XPATH,
                    self.router_control.xpath['country_code_element'][self.router_control.router_info].format(
                        index)).click()
                self.router_control.driver.find_element(
                    By.XPATH,
                    '/html/body/form/table/tbody/tr/td[3]/div/table/tbody/tr/td/table/tbody/tr/td/div[9]/input').click()
                try:
                    self.router_control.driver.switch_to.alert.accept()
                    self.router_control.driver.switch_to.alert.accept()
                except Exception as e:
                    ...
                WebDriverWait(driver=self.router_control.driver, timeout=60, poll_frequency=0.5).until(
                    EC.presence_of_element_located((By.XPATH, '/html/body/form/div/div/div[1]/div[2]')))
        except Exception as e:
            logging.info('country code set with error')


# ['Open System', 'WPA2-Personal', 'WPA3-Personal', 'WPA/WPA2-Personal', 'WPA2/WPA3-Personal',
#                              'WPA2-Enterprise', 'WPA/WPA2-Enterprise']
# fields = ['serial', 'band', 'ssid', 'wireless_mode', 'channel', 'bandwidth', 'authentication',
#           'password', 'test_type', 'protocol_type', 'wep_encrypt', 'wep_passwd',
#           'hide_ssid', 'hide_type', 'wpa_encrypt', 'passwd_index', 'protect_frame',
#           'smart_connect', 'country_code']
# ssid = 'coco'
# passwd = '12345678'
# Router = namedtuple('Router', fields, defaults=[None, ] * len(fields))
# router = Router(band='5 GHz', ssid=ssid, wireless_mode='11ax', channel='36', bandwidth='80 MHz',
#                 authentication='WPA2-Personal', password='12345678')
# control = Asusax88uControl()
# control.change_setting(router)
# control.quit()
# # control.change_country(router)
# # control.router_control.reboot_router()
