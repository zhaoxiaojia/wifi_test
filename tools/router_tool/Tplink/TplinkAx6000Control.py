#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2022/10/31 10:03
# @Author  : chao.li
# @Site    :
# @File    : TplinkAx6000Control.py
# @Software: PyCharm

import logging
import re
import time
from collections import namedtuple

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait
from tools.router_tool.RouterControl import RouterTools,ConfigError
from tools.router_tool.Tplink.TplinkConfig import TplinkAx6000Config


class TplinkAx6000Control:

    BAND_2 = '2.4 GHz'
    BAND_5 = '5 GHz'

    def __init__(self):
        self.router_control = RouterTools('tplink_ax6000', display=True)
        # self.router_control.driver.maximize_window()
        self.type = 'ax6000'

    def login(self):
        # try:
        self.router_control.driver.get(self.router_control.address)
        # input passwd
        self.router_control.driver.find_element(By.ID, self.router_control.xpath['password_element'][self.type]).click()
        self.router_control.driver.find_element(By.ID,
                                                self.router_control.xpath['password_element'][self.type]).send_keys(
            self.router_control.xpath['passwd'])
        # click login
        self.router_control.driver.find_element(By.XPATH,
                                                self.router_control.xpath['signin_element'][self.type]).click()
        # wait for login in done
        WebDriverWait(driver=self.router_control.driver, timeout=10, poll_frequency=0.5).until(
            EC.presence_of_element_located((By.ID, self.router_control.xpath['signin_done_element'])))
        # except NoSuchElementException as e:
        #     ...
        time.sleep(1)


    def change_setting(self, router):
        '''
        set up wifi envrioment
        @param router: Router instance
        @return: status : boolean
        '''

        def confirm():
            try:
                self.router_control.driver.find_element(By.ID, 'Confirm').find_element(By.ID, "hsConf") \
                    .find_element(By.CSS_SELECTOR, '#hsConf > input.subBtn.ok').click()
            except Exception as e:
                ...

        logging.info('Try to set router')
        try:
            self.login()
            WebDriverWait(driver=self.router_control.driver, timeout=5, poll_frequency=0.5).until(
                EC.presence_of_element_located((By.ID, 'netStateLCon')))

            if router.band not in TplinkAx6000Config.BAND_LIST:
                raise ConfigError('band key error')

            # 切换 路由设置
            self.router_control.driver.find_element(By.ID, 'routerSetMbtn').click()
            self.router_control.driver.find_element(By.ID, 'wireless2G_rsMenu').click()

            if '5' in router.band:
                # //*[@id="hcCo"]/div[6]/label
                select_element = self.router_control.driver.find_element(
                    By.XPATH, '//*[@id="hcCo"]/div[6]/label')
                self.router_control.scroll_to(select_element)

            # 修改 ssid
            if (router.ssid):

                if '2' in router.band:
                    ssid_input = self.router_control.driver.find_element(
                        By.ID, self.router_control.xpath['ssid_element_2g'][self.type])
                    ssid_input.click()
                    time.sleep(1)
                    ssid_input.clear()
                    ssid_input.clear()
                    ssid_input.send_keys(router.ssid)
                else:
                    ssid_input = self.router_control.driver.find_element(
                        By.ID, self.router_control.xpath['ssid_element_5g'])
                    ssid_input.click()
                    time.sleep(1)
                    ssid_input.clear()
                    ssid_input.clear()
                    ssid_input.send_keys(router.ssid)


            # 修改 ssid 是否隐藏
            if '2' in router.band:
                select = self.router_control.driver.find_element(By.ID, 'ssidBrd')
            else:
                select = self.router_control.driver.find_element(By.ID, 'ssidBrd5g')

            if (router.hide_ssid):
                if (router.hide_ssid == '是') and select.is_selected():
                    select.click()
                if (router.hide_ssid == '否') and not select.is_selected():
                    select.click()
            else:
                if not select.is_selected():
                    select.click()

            # 修改密码
            if (router.wpa_passwd):
                if '2' in router.band:
                    target_element = 'passwd_2g'
                else:
                    target_element = 'passwd_5g'
                self.router_control.driver.find_element(
                    By.ID, self.router_control.xpath['wpa_passwd'][target_element]).click()
                self.router_control.driver.find_element(
                    By.ID, self.router_control.xpath['wpa_passwd'][target_element]).clear()
                self.router_control.driver.find_element(
                    By.ID, self.router_control.xpath['wpa_passwd'][target_element]).send_keys(router.wpa_passwd)

            time.sleep(2)
            if (router.authentication_method):
                try:
                    index = TplinkAx6000Config.AUTHENTICATION_METHOD_DICT[router.authentication_method]
                except ConfigError:
                    raise ConfigError('authentication method key error')

                if '2' in router.band:
                    target_element = 'authtication_2g'
                else:
                    target_element = 'authtication_5g'
                wait_for = self.router_control.driver.find_element(
                    By.XPATH, self.router_control.xpath['authentication_method_select_element'][target_element])
                self.router_control.scroll_to(wait_for)
                wait_for.click()
                self.router_control.driver.find_element(
                    By.XPATH, self.router_control.xpath['authentication_method_regu_element'][
                        target_element].format(index)).click()

            # 修改 channel
            if (router.channel):
                channel = str(router.channel)
                try:
                    channel_index = {self.BAND_2: TplinkAx6000Config.CHANNEL_2_DICT,
                                     self.BAND_5: TplinkAx6000Config.CHANNEL_5_DICT}[router.band][channel]
                except Exception:
                    raise ConfigError('channel key error')
                if router.band == self.BAND_2:
                    select_list = self.router_control.driver.find_element(
                        By.XPATH, self.router_control.xpath['channel_select_element'][self.type]['channel_2g'])
                    self.router_control.scroll_to(select_list)
                    select_list.click()
                    select_element = self.router_control.driver.find_element(
                        By.XPATH, self.router_control.xpath['channel_regu_element']['channel_2g'].format(
                            channel_index))
                    self.router_control.scroll_to(select_element)
                    select_element.click()
                else:
                    select_list = self.router_control.driver.find_element(
                        By.XPATH, self.router_control.xpath['channel_select_element'][self.type]['channel_5g'])
                    self.router_control.scroll_to(select_list)
                    select_list.click()
                    select_element = self.router_control.driver.find_element(
                        By.XPATH, self.router_control.xpath['channel_regu_element']['channel_5g'].format(
                            channel_index))
                    self.router_control.scroll_to(select_element)
                    select_element.click()

            # 修改 wireless_mode
            if (router.wireless_mode):
                if '2' in router.band:
                    target_dict = TplinkAx6000Config.WIRELESS_MODE_2G_DICT
                    target_element = 'mode_2g'
                else:
                    target_dict = TplinkAx6000Config.WIRELESS_MODE_5G_DICT
                    target_element = 'mode_5g'
                if router.wireless_mode not in target_dict: raise ConfigError(
                    'wireless mode key error')
                index = target_dict[router.wireless_mode]
                wait_for = self.router_control.driver.find_element(
                    By.XPATH, self.router_control.xpath['wireless_mode_select_element'][self.type][target_element])
                self.router_control.scroll_to(wait_for)
                wait_for.click()
                self.router_control.driver.find_element(
                    By.XPATH,
                    self.router_control.xpath['wireless_mode_element'][self.type][target_element].format(index)).click()

            # 修改 bandwidth
            try:
                if (router.bandwidth):
                    if '2' in router.band:
                        target_dict = TplinkAx6000Config.BANDWIDTH_2_DICT
                        target_element = 'bandwidth_2g'
                    else:
                        target_dict = TplinkAx6000Config.BANDWIDTH_5_DICT
                        target_element = 'bandwidth_5g'
                    if router.bandwidth not in target_dict: raise ConfigError('bandwidth element error')
                    index = target_dict[router.bandwidth]
                    self.router_control.driver.find_element(
                        By.XPATH, self.router_control.xpath['bandwidth_select_element'][target_element]).click()
                    select_xpath = self.router_control.xpath['bandwidth_element'][self.type][target_element]

                    select_list = self.router_control.driver.find_element(By.XPATH, select_xpath[:-7])
                    if select_list.text:
                        lis = select_list.find_elements(By.TAG_NAME, 'li')
                        index = [i.get_attribute('title') for i in lis].index(router.bandwidth) + 1
                        print(router.bandwidth)
                        print(index)
                        wair_for = self.router_control.driver.find_element(
                            By.XPATH, select_xpath.format(index))
                        self.router_control.scroll_to(wait_for)
                        wair_for.click()
            except NotImplementedError:
                logging.info('Select element is disabled !!')

            time.sleep(5)
            # 点击apply
            if '2' in router.band:
                apply_element = 'apply_2g'
            else:
                apply_element = 'apply_5g'

            wait_for = self.router_control.driver.find_element(
                By.ID, self.router_control.xpath['apply_element'][self.type][apply_element])
            self.router_control.scroll_to(wait_for)
            wait_for.click()

            if re.findall(r'52|56|64|60', router.channel):
                confirm()
            if '5' in router.band and '20MHz' == router.bandwidth:
                confirm()
            try:
                WebDriverWait(self.router_control.driver, 30).until_not(
                    EC.visibility_of_element_located(
                        (By.ID, self.router_control.xpath['apply_element'][apply_element])))
            except Exception:
                ...

            time.sleep(2)
            logging.info('Router setting done')
            return True
        except Exception as e:
            logging.info('Router change setting with error')
            logging.info(e)
            return False
        finally:
            self.router_control.driver.quit()


# fields = ['band', 'ssid', 'wireless_mode', 'channel', 'bandwidth', 'authentication_method',
#           'wpa_passwd', 'test_type', 'wep_encrypt', 'passwd_index', 'wep_passwd', 'protect_frame',
#           'wpa_encrypt', 'hide_ssid']
# Router = namedtuple('Router', fields, defaults=[None, ] * len(fields))
# router = Router(band='5 GHz', ssid='Tplinkax6000_5G_123', wireless_mode='11a/n mixed', channel='52',
#                 bandwidth='20MHz', authentication_method='WPA2-PSK/WPA3-SAE', wpa_passwd='amlogic_wifi123@')
# control = TplinkAx6000Control()
# control.change_setting(router)
# control.reboot_router()
