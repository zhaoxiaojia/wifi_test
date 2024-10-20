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
from collections import namedtuple

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from tools.connect_tool.telnet_tool import TelnetInterface
from tools.router_tool.AsusRouter.AsusRouterConfig import Asusax88uConfig
from tools.router_tool.RouterConfig import ConfigError
from tools.router_tool.RouterControl import RouterTools

nvram_cmd = {
    '2.4 GHz': {
        'ssid': 'nvram set wl0_ssid={}',
        'channel': 'nvram set wl0_chanspec={}',
        'band': 'nvram set wl0_bw={}',
        'authentication_method': 'nvram set wl0_auth_mode_x={}',
        'passwd': 'nvram set wl0_wpa_psk={}'
    },

    '5 GHz': {
        'ssid': 'nvram set wl1_ssid={}',
        'channel': 'nvram set wl1_chanspec={}/80',
        'band': 'nvram set wl1_bw={}',
        'authentication_method': 'nvram set wl1_auth_mode_x={}',
        'passwd': 'nvram set wl1_wpa_psk={}'
    },
    'commit': 'nvram commit;service restart_wireless'
}


class Asusax88uControl():
    '''
    Asus ac88u router

    Attributes:

    '''

    def __init__(self):
        super().__init__()
        self.router_control = RouterTools('asus_88u', display=True)
        self.tn = telnetlib.Telnet("192.168.50.1", 23)
        self.tn.read_until(b'RT-AX86U login:')
        self.tn.write("admin".encode('ascii') + b'\n')
        self.tn.read_until(b'Password:')
        self.tn.write("12345678".encode("ascii") + b'\n')

    def telnet_write(self,cmd):
        self.tn.write(cmd.encode("ascii")+b'\n')

    # def login(self):
    #     '''
    #     login in router
    #     :return: None
    #     '''
    #     self.driver = webdriver.Chrome()
    #     self.driver.get(self.ADDRESS)
    #     self.driver.find_element(By.ID, 'login_username').send_keys(self.ACCOUNT)
    #     self.driver.find_element(By.NAME, 'login_passwd').click()
    #     self.driver.find_element(By.NAME, 'login_passwd').send_keys(self.PASSWD)
    #     self.driver.find_element(By.XPATH, '//*[@id="login_filed"]/div[8]').click()
    #
    #     # 等待加载成功
    #     WebDriverWait(driver=self.driver, timeout=10, poll_frequency=0.5).until(
    #         EC.presence_of_element_located((By.ID, 'helpname')))
    #     time.sleep(1)

    def change_setting(self, router):
        '''
        set up wifi envrioment
        @param router: Router instance
        @return: status : boolean
        '''
        # logging.info('Try to set router')
        try:
            self.router_control.login()
            nvram = nvram_cmd[router.band]
            # WebDriverWait(driver=self.router_control.driver, timeout=5,poll_frequency=0.8).until(
            #     EC.presence_of_element_located((By.CSS_SELECTOR, "a[onclick^='goToPage(16, 0, this);']")))
            content_table = self.router_control.driver.find_element(By.XPATH, "/html/body/table")
            content_table.find_element(By.XPATH, '//*[@id="Advanced_Wireless_Content_menu"]').click()

            # Wireless - General
            WebDriverWait(driver=self.router_control.driver, timeout=5, poll_frequency=0.5).until(
                EC.presence_of_element_located((By.ID, 'FormTitle')))

            smart_connect_style = self.router_control.driver.find_element(
                By.ID, 'smartcon_rule_link').value_of_css_property('display')

            if (router.smart_connect and smart_connect_style == 'none') or (
                    not router.smart_connect and smart_connect_style == 'table-cell'):
                self.router_control.driver.find_element(
                    By.ID,
                    self.router_control.xpath['smart_connect_element'][self.router_control.router_info]).click()

            # 修改 band
            if router.band and not router.smart_connect:
                if router.band not in Asusax88uConfig.BAND_LIST: raise ConfigError('band element error')
                self.router_control.change_band(router.band)

            # 修改 wireless_mode
            if router.wireless_mode and not router.smart_connect:
                try:
                    if router.band == '2.4 GHz':
                        assert router.wireless_mode in Asusax88uConfig.WIRELESS_2_MODE
                    else:
                        assert router.wireless_mode in Asusax88uConfig.WIRELESS_5_MODE
                except ConfigError:
                    raise ConfigError('channel element error')
                if router.wireless_mode == 'AX only':
                    index = '1'
                    if router.band == '2.4 GHz':
                        router = router._replace(wireless_mode='自动')
                else:
                    index = '2'
                self.router_control.change_wireless_mode(router.wireless_mode)
                # if router.wireless_mode == 'AX only':
                try:
                    self.router_control.driver.find_element(
                        By.XPATH,
                        self.router_control.xpath['wireless_ax_element'][self.router_control.router_info].format(
                            index),
                    ).click()
                except Exception as e:
                    ...
            # 修改 ssid 是否隐藏
            if router.hide_ssid:
                if router.hide_ssid == '是':
                    self.router_control.driver.find_element(By.XPATH, ".//input[@type='radio' and @value='1']").click()
                elif router.hide_ssid == '否':
                    self.router_control.driver.find_element(By.XPATH, ".//input[@type='radio' and @value='0']").click()
            else:
                self.router_control.driver.find_element(By.XPATH, ".//input[@type='radio' and @value='0']").click()


            # 修改 wep_encrypt
            if router.wep_encrypt:
                if router.wep_encrypt not in Asusax88uConfig.WEP_ENCRYPT: raise ConfigError('wep encrypt elemenr error')
                self.router_control.change_wep_encrypt(router.wep_encrypt)

            # 修改 wpa_encrypt
            if router.wpa_encrypt:
                if router.wpa_encrypt not in Asusax88uConfig.WPA_ENCRYPT: raise ConfigError('wpa encrypt elemenr error')
                self.router_control.change_wpa_encrypt(router.wpa_encrypt)

            # 修改 passwd_index
            # //*[@id="WLgeneral"]/tbody/tr[17]/td/select/option[1]
            if router.passwd_index:
                if router.passwd_index not in Asusax88uConfig.PASSWD_INDEX_DICT: raise ConfigError(
                    'passwd index element error')
                self.router_control.change_passwd_index(router.passwd_index)

            # 修改 wep_passwd
            if router.wep_passwd:
                self.router_control.change_wep_passwd(router.wep_passwd)

            # 修改 受保护的管理帧
            # //*[@id="WLgeneral"]/tbody/tr[26]/td/select/option[1]
            if router.protect_frame:
                self.router_control.change_protect_frame(router.protect_frame)

            time.sleep(5)

            # 点击apply
            self.router_control.apply_setting()
            try:
                self.router_control.driver.switch_to.alert.accept()
                self.router_control.driver.switch_to.alert.accept()

            except Exception as e:
                ...
            try:
                if router.hide_ssid == '是':
                    self.router_control.driver.find_element(By.XPATH, "/html/body/div[4]/div/div[3]/div[1]").click()
            except Exception as e:
                ...
            # /html/body/div[4]/div/div[3]/div[1]
            WebDriverWait(self.router_control.driver, 20).until_not(
                #     //*[@id="loadingBlock"]/tbody/tr/td[2]
                EC.visibility_of_element_located((By.XPATH, '//*[@id="loadingBlock"]/tbody/tr/td[2]'))
            )
            time.sleep(2)

            # 修改 ssid
            if router.ssid:
                # self.router_control.change_ssid(router.ssid)
                self.telnet_write(nvram['ssid'].format(router.ssid))

            # 修改 wpa_passwd
            if router.wpa_passwd:
                # self.router_control.change_wpa_passwd(router.wpa_passwd)
                self.telnet_write(nvram['passwd'].format(router.wpa_passwd))

            # 修改 authentication_method
            if router.authentication_method:
                param = {
                    'Open System': 'open',
                    'WPA2-Personal': 'psk2',
                    'WPA3-Personal': 'aes',
                }

                if router.smart_connect:
                    if router.wireless_mode != '自动':
                        logging.warning(" The authentication method can only be automatic")
                    router = router._replace(wireless_mode='自动')
                mode_list = Asusax88uConfig.AUTHENTICATION_METHOD_DICT.keys() if router.wireless_mode != 'Legacy' \
                    else Asusax88uConfig.AUTHENTICATION_METHOD_LEGCY_DICT.keys()
                if router.authentication_method not in mode_list:
                    raise ConfigError('authentication method element error')
                self.telnet_write(nvram['authentication_method'].format(param[router.authentication_method]))
                # self.router_control.change_authentication_method(router.authentication_method)

            if router.channel and not router.smart_connect:
                channel = str(router.channel)
                channel_list = Asusax88uConfig.CHANNEL_2_DICT.keys() if router.band == '2.4 GHz' \
                    else Asusax88uConfig.CHANNEL_5_DICT.keys()
                if channel not in channel_list: raise ConfigError('channel element error')
                # //*[@id="WLgeneral"]/tbody/tr[11]/td/select/option[22]
                # self.router_control.change_channel(channel)
                self.telnet_write(nvram['channel'].format(channel))

            # 修改 bandwidth
            if router.bandwidth and not router.smart_connect:
                band_list = {'2.4 GHz': Asusax88uConfig.BANDWIDTH_2_LIST, '5 GHz': Asusax88uConfig.BANDWIDTH_5_LIST}[
                    router.band]
                if router.bandwidth not in band_list: raise ConfigError('bandwidth element error')
                # self.router_control.change_bandwidth(router.bandwidth)
                self.telnet_write(nvram['band'].format(band_list.index(router.bandwidth)))
            self.telnet_write(nvram_cmd['commit'])

            logging.info('Router setting done')
            return True
        except Exception as e:
            except_type, except_value, except_traceback = sys.exc_info()
            except_file = os.path.split(except_traceback.tb_frame.f_code.co_filename)[1]
            exc_dict = {
                "报错类型": except_type,
                "报错信息": except_value,
                "报错文件": except_file,
                "报错行数": except_traceback.tb_lineno,
            }
            logging.info(f'{exc_dict}')
            return False

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


# fields = ['serial', 'band', 'ssid', 'wireless_mode', 'channel', 'bandwidth', 'authentication_method',
#           'wpa_passwd', 'test_type', 'protocol_type', 'wep_encrypt', 'wep_passwd',
#           'hide_ssid', 'hide_type', 'wpa_encrypt', 'passwd_index', 'protect_frame',
#           'smart_connect', 'country_code']
# ssid = 'ATC_ASUS_AX88U_2G'
# passwd = '12345678'
# Router = namedtuple('Router', fields, defaults=[None, ] * len(fields))
# router = Router(band='2.4 GHz', ssid=ssid, wireless_mode='Legacy', channel='11', bandwidth='20 MHz',
#                 authentication_method='WPA2-Personal', wpa_passwd="12345678", protect_frame="停用")
# control = Asusax88uControl()
#
# control.change_setting(router)
# # control.change_country(router)
# # control.router_control.reboot_router()
