#!/usr/bin/env python 
# -*- coding: utf-8 -*-
# @Time    : 2022/3/22 16:17
# @Author  : chao.li
# @Site    :
# @File    : Asusax88uControl.py
# @Software: PyCharm


import logging
import os
import sys
import telnetlib
import time
import pytest
from collections import namedtuple

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from tools.connect_tool.telnet_tool import TelnetInterface
from tools.router_tool.AsusRouter.AsusRouterConfig import Asusax88uConfig
from tools.router_tool.RouterConfig import ConfigError
from tools.router_tool.RouterControl import RouterTools
from tools.yamlTool import yamlTool


class Asusax88uControl():
    '''
    Asus ac88u router

    Attributes:

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

    def __init__(self):
        super().__init__()
        # self.router_control = RouterTools('asus_88u')
        if pytest.win_flag:
            self.yaml_info = yamlTool(os.getcwd() + f'\\config\\router_xpath\\asus_xpath.yaml')
        else:
            self.yaml_info = yamlTool(os.getcwd() + '/config/router_xpath/asus_xpath.yaml')
        # self.yaml_info = yamlTool(r'D:\PycharmProjects\wifi_test\config\router_xpath\asus_xpath.yaml')
        self.xpath = self.yaml_info.get_note('asus')
        self.tn = telnetlib.Telnet("192.168.50.1", 23)
        self.tn.read_until(b'login:')
        self.tn.write("admin".encode('ascii') + b'\n')
        self.tn.read_until(b'Password:')
        self.tn.write(str(self.xpath['passwd']).encode("ascii") + b'\n')

    def telnet_write(self, cmd):
        logging.info(cmd)
        try:
            self.tn.write(cmd.encode("ascii") + b'\n')
        except Exception:
            self.tn.open("192.168.50.1", 23)
            self.tn.write(cmd.encode("ascii") + b'\n')

    def set_2g_ssid(self, ssid):
        cmd = 'nvram set wl0_ssid={}'
        self.telnet_write(cmd.format(ssid))

    def set_5g_ssid(self, ssid):
        cmd = 'nvram set wl1_ssid={}'
        self.telnet_write(cmd.format(ssid))

    def set_2g_wireless(self, mode):
        cmd = {
            '自动': 'nvram set wl0_11ax=0;nvram set wl0_nmode_x=0',
            '11n': 'nvram set wl0_11ax=0;nvram set wl0_nmode_x=1',
            '11g': 'nvram set wl0_11ax=0;nvram set wl0_nmode_x=5',
            '11b': 'nvram set wl0_11ax=0;nvram set wl0_nmode_x=6',
            '11ax': 'nvram set wl0_11ax=1;nvram set wl0_nmode_x=9',
            'Legacy': 'nvram set wl0_11ax=0;nvram set wl0_nmode_x=2',
        }
        if mode not in Asusax88uConfig.WIRELESS_2_MODE:
            raise ConfigError('wireless elemenr error')
        self.telnet_write(cmd[mode])

    def set_5g_wireless(self, mode):
        cmd = {
            '自动': 'nvram set wl1_11ax=0;nvram set wl1_nmode_x=0',
            '11a': 'nvram set wl1_11ax=0;nvram set wl1_nmode_x=7',
            '11ac': 'nvram set wl1_11ax=0;nvram set wl1_nmode_x=3',
            '11ax': 'nvram set wl1_11ax=1;nvram set wl1_nmode_x=9',
            'Legacy': 'nvram set wl1_11ax=0;nvram set wl1_nmode_x=2',
        }
        if mode not in Asusax88uConfig.WIRELESS_5_MODE:
            raise ConfigError('wireless elemenr error')
        self.telnet_write(cmd[mode])

    def set_2g_wpa_passwd(self, passwd):
        cmd = 'nvram set wl0_wpa_psk={}'
        self.telnet_write(cmd.format(passwd))

    def set_5g_wpa_passwd(self, passwd):
        cmd = 'nvram set wl1_wpa_psk={}'
        self.telnet_write(cmd.format(passwd))

    def set_2g_authentication_method(self, method):
        cmd = 'nvram set wl0_auth_mode_x={}'
        mode_list = Asusax88uConfig.AUTHENTICATION_METHOD if method != 'Legacy' \
            else Asusax88uConfig.AUTHENTICATION_METHOD_LEGCY
        if method not in mode_list:
            raise ConfigError('authentication method element error')
        self.telnet_write(cmd.format(self.MODE_PARAM[method]))
        if method == 'Open System':
            self.set_2g_wep_encrypt('None')

    def set_5g_authentication_method(self, method):
        cmd = 'nvram set wl1_auth_mode_x={}'
        mode_list = Asusax88uConfig.AUTHENTICATION_METHOD if method != 'Legacy' \
            else Asusax88uConfig.AUTHENTICATION_METHOD_LEGCY
        if method not in mode_list:
            raise ConfigError('authentication method element error')
        self.telnet_write(cmd.format(self.MODE_PARAM[method]))
        if method == 'Open System':
            self.set_5g_wep_encrypt('None')

    def set_2g_channel(self, channel):
        cmd = 'nvram set wl0_chanspec={}'
        channel = str(channel)
        if channel not in Asusax88uConfig.CHANNEL_2:
            raise ConfigError('channel element error')
        channel = 0 if channel == '自动' else channel
        self.telnet_write(cmd.format(channel))

    def set_5g_channel(self, channel):
        cmd = 'nvram set wl1_chanspec={}/80'
        channel = str(channel)
        if channel not in Asusax88uConfig.CHANNEL_5:
            raise ConfigError('channel element error')
        channel = 0 if channel == '自动' else channel
        self.telnet_write(cmd.format(channel))

    def set_2g_bandwidth(self, width):
        cmd = 'nvram set wl0_bw={}'
        if width not in Asusax88uConfig.BANDWIDTH_2:
            raise ConfigError('bandwidth element error')
        self.telnet_write(cmd.format(Asusax88uConfig.BANDWIDTH_2.index(width)))

    def set_5g_bandwidth(self, width):
        cmd = 'nvram set wl1_bw={}'
        if width not in Asusax88uConfig.BANDWIDTH_5: raise ConfigError('bandwidth element error')
        self.telnet_write(cmd.format(Asusax88uConfig.BANDWIDTH_5.index(width)))

    def set_2g_wep_encrypt(self, encrypt):
        cmd = 'nvram set wl0_wep_x={};nvram set w1_wep_x={}'
        if encrypt not in Asusax88uConfig.WEP_ENCRYPT:
            raise ConfigError('wep encrypt elemenr error')
        # passwd_wep
        index = '1' if '64' in encrypt else '2'
        index = '0' if encrypt == 'None' else index
        self.telnet_write(cmd.format(index, index))

    def set_5g_wep_encrypt(self, encrypt):
        cmd = 'nvram set wl1_wep_x={};nvram set w1_wep_x={}'
        if encrypt not in Asusax88uConfig.WEP_ENCRYPT:
            raise ConfigError('wep encrypt elemenr error')
        # passwd_wep
        index = '1' if '64' in encrypt else '2'
        index = '0' if encrypt == 'None' else index
        self.telnet_write(cmd.format(index, index))

    def set_2g_wep_passwd(self, passwd):
        cmd = 'nvram set wl0_key1={}'
        self.telnet_write(cmd.format(passwd))

    def set_5g_wep_passwd(self, passwd):
        cmd = 'nvram set wl1_key1={}'
        self.telnet_write(cmd.format(passwd))

    def commit(self):
        self.telnet_write('nvram commit;service restart_wireless')

    def change_setting(self, router):
        '''
        set up wifi envrioment
        @param router: Router instance
        @return: status : boolean
        '''
        # logging.info('Try to set router')
        # try:
        # self.router_control.login()

        # content_table = self.router_control.driver.find_element(By.XPATH, "/html/body/table")
        # content_table.find_element(By.XPATH, '//*[@id="Advanced_Wireless_Content_menu"]').click()
        #
        # # Wireless - General
        # WebDriverWait(driver=self.router_control.driver, timeout=5, poll_frequency=0.5).until(
        #     EC.presence_of_element_located((By.ID, 'FormTitle')))
        #
        # smart_connect_style = self.router_control.driver.find_element(
        #     By.ID, 'smartcon_rule_link').value_of_css_property('display')
        #
        # if (router.smart_connect and smart_connect_style == 'none') or (
        #         not router.smart_connect and smart_connect_style == 'table-cell'):
        #     self.router_control.driver.find_element(
        #         By.ID,
        #         self.router_control.xpath['smart_connect_element'][self.router_control.router_info]).click()
        #
        # # 修改 band
        # if router.band and not router.smart_connect:
        #     if router.band not in Asusax88uConfig.BAND_LIST: raise ConfigError('band element error')
        #     self.router_control.change_band(router.band)
        #
        # # 修改 ssid 是否隐藏
        # if router.hide_ssid:
        #     if router.hide_ssid == '是':
        #         self.router_control.driver.find_element(By.XPATH, ".//input[@type='radio' and @value='1']").click()
        #     elif router.hide_ssid == '否':
        #         self.router_control.driver.find_element(By.XPATH, ".//input[@type='radio' and @value='0']").click()
        # else:
        #     self.router_control.driver.find_element(By.XPATH, ".//input[@type='radio' and @value='0']").click()
        #
        # # 修改 wpa_encrypt
        # if router.wpa_encrypt:
        #     if router.wpa_encrypt not in Asusax88uConfig.WPA_ENCRYPT: raise ConfigError('wpa encrypt elemenr error')
        #     self.router_control.change_wpa_encrypt(router.wpa_encrypt)
        #
        # # 修改 passwd_index
        # # //*[@id="WLgeneral"]/tbody/tr[17]/td/select/option[1]
        # if router.passwd_index:
        #     if router.passwd_index not in Asusax88uConfig.PASSWD_INDEX_DICT: raise ConfigError(
        #         'passwd index element error')
        #     self.router_control.change_passwd_index(router.passwd_index)
        #
        # # 修改 受保护的管理帧
        # # //*[@id="WLgeneral"]/tbody/tr[26]/td/select/option[1]
        # if router.protect_frame:
        #     self.router_control.change_protect_frame(router.protect_frame)
        #
        # time.sleep(5)
        #
        # # 点击apply
        # self.router_control.apply_setting()
        # try:
        #     self.router_control.driver.switch_to.alert.accept()
        #     self.router_control.driver.switch_to.alert.accept()
        #
        # except Exception as e:
        #     ...
        # try:
        #     if router.hide_ssid == '是':
        #         self.router_control.driver.find_element(By.XPATH, "/html/body/div[4]/div/div[3]/div[1]").click()
        # except Exception as e:
        #     ...
        # # /html/body/div[4]/div/div[3]/div[1]
        # WebDriverWait(self.router_control.driver, 20).until_not(
        #     #     //*[@id="loadingBlock"]/tbody/tr/td[2]
        #     EC.visibility_of_element_located((By.XPATH, '//*[@id="loadingBlock"]/tbody/tr/td[2]'))
        # )
        # time.sleep(2)

        # 修改 ssid
        if router.ssid:
            self.set_2g_ssid(router.ssid) if '2' in router.band else self.set_5g_ssid(router.ssid)

        # 修改 wireless_mode
        if router.wireless_mode and not router.smart_connect:
            self.set_2g_wireless(router.wireless_mode) if '2' in router.band else self.set_5g_wireless(
                router.wireless_mode)

        # 修改 wpa_passwd
        if router.wpa_passwd:
            self.set_2g_wpa_passwd(router.wpa_passwd) if '2' in router.band else self.set_2g_wpa_passwd(
                router.wpa_passwd)

        # 修改 authentication_method
        if router.authentication_method:
            self.set_2g_authentication_method(
                router.authentication_method) if '2' in router.band else self.set_5g_authentication_method(
                router.authentication_method)

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
                if router.country_code not in Asusax88uConfig.COUNTRY_CODE: raise ConfigError('country code error')
                self.router_control.driver.find_element(
                    By.XPATH, '//*[@id="Advanced_WAdvanced_Content_tab"]/span').click()
                WebDriverWait(driver=self.router_control.driver, timeout=5, poll_frequency=0.5).until(
                    EC.presence_of_element_located((By.ID, 'titl_desc')))
                index = Asusax88uConfig.COUNTRY_CODE[router.country_code]
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
# fields = ['serial', 'band', 'ssid', 'wireless_mode', 'channel', 'bandwidth', 'authentication_method',
#           'wpa_passwd', 'test_type', 'protocol_type', 'wep_encrypt', 'wep_passwd',
#           'hide_ssid', 'hide_type', 'wpa_encrypt', 'passwd_index', 'protect_frame',
#           'smart_connect', 'country_code']
# ssid = 'ATC_ASUS_AX88U_2G'
# passwd = '12345678'
# Router = namedtuple('Router', fields, defaults=[None, ] * len(fields))
# router = Router(band='2.4 GHz', ssid=ssid, wireless_mode='11ax', channel='11', bandwidth='20 MHz',
#                 authentication_method='WPA3-Personal',wpa_passwd='12345678')
# control = Asusax88uControl()
# control.change_setting(router)

# # control.change_country(router)
# # control.router_control.reboot_router()
