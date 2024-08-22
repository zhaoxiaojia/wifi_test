#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/1/16
# @Author  : Yu.Zeng
# @Site    :
# @File    : NetgearR6100Control.py
# @Software: PyCharm

import logging
from collections import namedtuple
from time import sleep

from pykeyboard import PyKeyboard
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.wait import WebDriverWait

from tools.router_tool.NetgearR6100Config import NetgearR6100Config
from tools.router_tool.RouterConfig import ConfigError
from tools.router_tool.RouterControl import RouterTools


class NetgearR6100Control():
    def __init__(self):
        self.router_control = RouterTools('netgear_R6100', display=True)
        self.keyboard = PyKeyboard()

    def login(self):
        try:
            self.router_control.driver.get(self.router_control.address)
            self.keyboard.type_string(self.router_control.xpath["account"])  # 输入账号
            # self.keyboard.tap_key(self.keyboard.enter_key)  # 按enter，如果默认输入法是英文，请注销此行
            sleep(1)
            self.keyboard.tap_key(self.keyboard.tab_key)  # 按tab键切换到密码输入框
            self.keyboard.type_string(self.router_control.xpath["passwd"])  # 输入密码
            sleep(1)
            self.keyboard.tap_key(self.keyboard.enter_key)  # 按enter登录
        except:
            ...
        sleep(5)  # 该页面登录加载过慢，等待5秒

    def change_setting(self, router):
        '''
        set up wifi envrioment
        @param router: Router instance
        @return: status : boolean
        '''
        logging.info('Try to set router')
        try:
            self.login()
            self.router_control.driver.find_element(By.ID, self.router_control.xpath["wireless_mode_element"]).click()
            self.router_control.driver.switch_to.frame(self.router_control.xpath["wireless_mode_frame"])
            # 等待应用按键元素
            WebDriverWait(driver=self.router_control.driver, timeout=10).until(
                EC.presence_of_element_located((By.XPATH, self.router_control.xpath["apply_element"])))
            # change band
            if (router.band):
                if router.band not in NetgearR6100Config.BAND_LIST: raise ConfigError('band element error')
                if '2' in router.band:
                    el = self.router_control.driver.find_element(By.XPATH, self.router_control.xpath['ssid_element_2g'])
                    if not el.is_selected():
                        el.click()
                else:
                    el = self.router_control.driver.find_element(By.XPATH, self.router_control.xpath['ssid_element_5g'])
                    if not el.is_selected():
                        el.click()
            # change ssid
            if (router.ssid):
                try:
                    if router.band == '2.4 GHz':
                        ssid_text_element = self.router_control.xpath['ssid_text_element_2g']
                        ssid_text = self.router_control.driver.find_element(By.XPATH, ssid_text_element)
                        ssid_text.clear()
                        ssid_text.send_keys(router.ssid)
                    else:
                        ssid_text_element = self.router_control.xpath['ssid_text_element_5g']
                        ssid_text = self.router_control.driver.find_element(By.XPATH, ssid_text_element)
                        ssid_text.clear()
                        ssid_text.send_keys(router.ssid)
                except KeyError:
                    raise ConfigError('ssid element error')
            # change channel
            if (router.channel):
                channel = str(router.channel)
                try:
                    if router.band == '2.4 GHz':
                        channel_value = NetgearR6100Config.CHANNEL_2_DICT[channel]
                        channel_element = self.router_control.xpath['channel_select_element']['channel_for_2g']
                    else:
                        channel_value = NetgearR6100Config.CHANNEL_5_DICT[channel]
                        channel_element = self.router_control.xpath['channel_select_element']['channel_for_5g']
                except KeyError:
                    raise ConfigError('channel element error')
                channel_select = Select(self.router_control.driver.find_element(By.XPATH, channel_element))
                channel_select.select_by_value(channel_value)
            # change wireless mode
            if (router.wireless_mode):
                try:
                    if router.band == '2.4 GHz':
                        # 如果wireless mode非54Mbps，需先选择非wep安全选项才能修改wireless mode
                        if router.wireless_mode != '54Mbps':
                            authentication_method_element = self.router_control.xpath['authentication_for_2G_element']
                            self.router_control.driver.find_element(By.XPATH, authentication_method_element[
                                router.authentication_method]).click()
                        mode_value = NetgearR6100Config.WIRELESS_MODE_2_DICT[router.wireless_mode]
                        mode_element = self.router_control.xpath['mode_select_element']['mode_for_2g']
                    else:
                        mode_value = NetgearR6100Config.WIRELESS_MODE_5_DICT[router.wireless_mode]
                        mode_element = self.router_control.xpath['mode_select_element']['mode_for_5g']
                except KeyError:
                    raise ConfigError('wireless_mode element error')
                mode_select = Select(self.router_control.driver.find_element(By.XPATH, mode_element))
                mode_select.select_by_value(mode_value)
            # # change authentication_method
            if (router.authentication_method):
                try:
                    if router.band == '2.4 GHz':
                        authentication_method_element = self.router_control.xpath['authentication_for_2G_element']
                    else:
                        authentication_method_element = self.router_control.xpath['authentication_for_5G_element']
                except KeyError:
                    raise ConfigError('authentication_method element error')
                if self.router_control.element_is_selected(authentication_method_element[
                                                               router.authentication_method]):
                    pass
                else:
                    self.router_control.driver.find_element(By.XPATH, authentication_method_element[
                        router.authentication_method]).click()
            # set authentication_password
            if (router.wpa_passwd):
                try:
                    if router.band == '2.4 GHz':
                        element_for_2g = self.router_control.xpath['passwd_input_element']['passwd_for_2g']
                        password_2g_text = self.router_control.driver.find_element(By.XPATH, element_for_2g)
                        password_2g_text.clear()
                        password_2g_text.send_keys(router.wpa_passwd)
                    else:
                        element_for_5g = self.router_control.xpath['passwd_input_element']['passwd_for_5g']
                        password_5g_text = self.router_control.driver.find_element(By.XPATH, element_for_5g)
                        password_5g_text.clear()
                        password_5g_text.send_keys(router.wpa_passwd)
                except KeyError:
                    raise ConfigError('wpa_passwd element error')
            # set wep encrypt and password
            if (router.wep_encrypt):
                try:
                    encryption_byte_value = NetgearR6100Config.WEP_ENCRYPT_DICT[router.wep_encrypt]
                    encryption_byte_element = self.router_control.xpath['wep_encryption_byte']
                    encryption_select = Select(
                        self.router_control.driver.find_element(By.XPATH, encryption_byte_element))
                    encryption_select.select_by_value(encryption_byte_value)
                    encryption_passwd_element = self.router_control.xpath['wep_encryption_passwd']
                    encryption_passwd_text = self.router_control.driver.find_element(By.XPATH,
                                                                                     encryption_passwd_element)
                    encryption_passwd_text.clear()
                    encryption_passwd_text.send_keys(router.wep_passwd)
                except KeyError:
                    raise ConfigError('wep encrypt and password element error')
            # set up done
            self.router_control.driver.find_element(By.XPATH, self.router_control.xpath['apply_element']).click()
            # 循环处理alert弹窗
            while EC.alert_is_present()(self.router_control.driver):
                EC.alert_is_present()(self.router_control.driver).accept()
            # 等待设置完成
            cancel = WebDriverWait(driver=self.router_control.driver, timeout=60).until(
                EC.presence_of_element_located((By.XPATH, '/html/body/form/div[2]/table/tbody/tr/td/input[1]')))
            cancel.click()  # 退出无线设置
            sleep(2)
            logging.info('Router setting done')
            return True
        except Exception as e:
            logging.info('Router change setting with error')
            logging.info(e)
            return False
        finally:
            self.router_control.driver.quit()
            sleep(2)


# fields = ['serial', 'band', 'ssid', 'wireless_mode', 'channel', 'bandwidth',
#           'authentication_method', 'wpa_passwd', 'test_type', 'wep_encrypt',
#           'passwd_index', 'wep_passwd', 'protect_frame', 'wpa_encrypt', 'hide_ssid']
# Router = namedtuple('Router', fields, defaults=[None, ] * len(fields))
# router = Router(serial='1', band='2.4 GHz', ssid='NETGEAR_2G', wireless_mode='54Mbps', channel='AUTO',
#                 bandwidth='', wpa_passwd='', wep_encrypt='', wep_passwd='',
#                 authentication_method='None', hide_ssid="否")
# router = Router(serial='2', band='2.4 GHz', ssid='NETGEAR_2G', wireless_mode='54Mbps', channel='1',
#                 bandwidth='', wpa_passwd='', wep_encrypt='wep-64', wep_passwd='12345',
#                 authentication_method='WEP', hide_ssid="否")
# router = Router(serial='3', band='2.4 GHz', ssid='NETGEAR_2G', wireless_mode='54Mbps', channel='2',
#                 bandwidth='', wpa_passwd='', wep_encrypt='wep-128', wep_passwd='12345678901234567890123456',
#                 authentication_method='WEP', hide_ssid="否")
# router = Router(serial='4', band='2.4 GHz', ssid='NETGEAR_2G', wireless_mode='300Mbps', channel='5',
#                 bandwidth='', wpa_passwd='abc12345', wep_encrypt='', wep_passwd='',
#                 authentication_method='WPA/WPA2', hide_ssid="否")
# router = Router(serial='5', band='5 GHz', ssid='NETGEAR_5G+', wireless_mode='192Mbps', channel='40',
#                 bandwidth='', wpa_passwd='12345678', wep_encrypt='', wep_passwd='',
#                 authentication_method='WPA2', hide_ssid="否")
# control = NetgearR6100Control()
# control.change_setting(router)
# control.reboot_router()
