#!/usr/bin/env python 
# encoding: utf-8 
'''
@author: chao.li
@contact: chao.li@amlogic.com
@software: pycharm
@file: XiaomiRedax6000Control.py 
@time: 2024/12/2 11:20 
@desc: 
'''

import logging
import time
from collections import namedtuple

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from tools.router_tool.RouterConfig import ConfigError
from tools.router_tool.RouterControl import RouterTools
from tools.router_tool.Xiaomi.XiaomiRouterConfig import XiaomiRouterConfig


class XiaomiRedax3000Control:
    BAND_2 = '2.4 GHz'
    BAND_5 = '5 GHz'

    def __init__(self):
        self.router_control = RouterTools('xiaomi_ax3000', display=True)

    def login(self):
        # try:
        self.router_control.driver.get(self.router_control.address)
        # input passwd
        self.router_control.driver.find_element(By.ID, self.router_control.xpath['password_element']).click()
        self.router_control.driver.find_element(By.ID, self.router_control.xpath['password_element']).send_keys(
            self.router_control.xpath['passwd'])
        # click login
        self.router_control.driver.find_element(By.ID, self.router_control.xpath['signin_element']).click()
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
        logging.info('Try to set router')
        try:
            self.login()
            self.router_control.driver.find_element(By.XPATH, '//*[@id="bd"]/div[2]/div/div[1]/div[1]/a').click()
            # Wireless - Profession
            wait = WebDriverWait(driver=self.router_control.driver, timeout=5, poll_frequency=0.5)
            wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="wifiset24"]/div[1]')))

            if router.band == self.BAND_5:
                wait_for = self.router_control.driver.find_element(By.XPATH, '//*[@id="bd"]/div[4]/div[1]/h3')
                self.router_control.scroll_to(wait_for)

            # 修改 ssid
            if router.ssid:
                if self.BAND_2 == router.band:
                    target = 'ssid_2g'
                else:
                    target = 'ssid_5g'
                self.router_control.driver.find_element(
                    By.XPATH, self.router_control.xpath['ssid_element'][target]).clear()
                self.router_control.driver.find_element(
                    By.XPATH, self.router_control.xpath['ssid_element'][target]).send_keys(router.ssid)

            hide_2g = self.router_control.driver.find_element(
                By.ID, self.router_control.xpath['hide_ssid']['hide_2g'])
            hide_5g = self.router_control.driver.find_element(
                By.ID, self.router_control.xpath['hide_ssid']['hide_5g'])

            if self.BAND_2 == router.band:
                target = hide_2g
            else:
                target = hide_5g
            # 修改隐藏
            if router.hide_ssid:
                if router.hide_ssid == '是' and not target.is_selected():
                    target.click()
                if router.hide_ssid == '否' and target.is_selected():
                    target.click()
            else:
                if target.is_selected():
                    target.click()
            # 修改 authentication_method
            if router.authentication_method:
                try:
                    index = XiaomiRouterConfig.AUTHENTICATION_METHOD_DICT[router.authentication_method]
                except ConfigError:
                    raise ConfigError('authentication method element error')
                target = 'authentication_method_2g' if self.BAND_2 == router.band else 'authentication_method_5g'
                self.router_control.driver.find_element(
                    By.XPATH, self.router_control.xpath['authentication_method_select_element'][target]).click()
                # //*[@id="dummydata"]/a[3]/span
                self.router_control.driver.find_element(
                    By.XPATH, self.router_control.xpath['authentication_method_regu_element'].format(index)).click()

            # 修改密码
            if router.wpa_passwd:
                if self.BAND_2 == router.band:
                    target = 'passwd_2g'
                else:
                    target = 'passwd_5g'
                self.router_control.driver.find_element(
                    By.XPATH, self.router_control.xpath['passwd_element'][target]).clear()
                self.router_control.driver.find_element(
                    By.XPATH, self.router_control.xpath['passwd_element'][target]).send_keys(router.wpa_passwd)

            if router.channel:
                channel = str(router.channel)
                try:
                    if router.band == '2.4 GHz':
                        index = XiaomiRouterConfig.CHANNEL_2_DICT[channel]
                        target = 'channel_2g'
                    else:
                        index = XiaomiRouterConfig.CHANNEL_5_DICT[channel]
                        target = 'channel_5g'
                except KeyError:
                    raise ConfigError('channel element error')

                self.router_control.driver.find_element(
                    By.XPATH, self.router_control.xpath['channel_select_element'][target]).click()
                wait_for = self.router_control.driver.find_element(
                    By.XPATH, self.router_control.xpath['channel_regu_element'].format(index))
                self.router_control.scroll_to(wait_for)
                time.sleep(1)
                wait_for.click()

                try:
                    self.router_control.driver.find_element(By.XPATH, "/html/body/div[1]/div/div[3]/div/a").click()
                except Exception:
                    ...

            # 修改 bandwidth
            if router.bandwidth:
                if router.band == self.BAND_2:
                    target_dict = XiaomiRouterConfig.BANDWIDTH_2_LIST
                    target = 'bandwidth_2g'
                else:
                    target_dict = XiaomiRouterConfig.BANDWIDTH_5_LIST
                    target = 'bandwidth_5g'
                if router.bandwidth not in target_dict: raise ConfigError('bandwidth element error')
                self.router_control.driver.find_element(
                    By.XPATH, self.router_control.xpath['bandwidth_select_element'][target]).click()
                time.sleep(1)
                select_list = self.router_control.driver.find_element(By.ID, 'dummydata')
                lis = select_list.find_elements(By.TAG_NAME, 'span')
                if len(lis) > 1:
                    index = [i.text for i in lis].index(router.bandwidth) + 1
                    self.router_control.driver.find_element(
                        By.XPATH, self.router_control.xpath['bandwidth_element'].format(index)).click()

            time.sleep(5)
            # 点击apply
            # if self.BAND_2 == router.band:
            #     target = 'apply_2g'
            # else:
            #     target = 'apply_5g'
            wait_for = self.router_control.driver.find_element(
                By.XPATH, self.router_control.xpath['apply_element']['apply_5g'])
            self.router_control.scroll_to(wait_for)
            wait_for.click()
            self.router_control.driver.find_element(By.XPATH, '/html/body/div[1]/div/div[3]/div/a[1]/span').click()
            try:
                if ('需要30秒请等待...' in self.router_control.driver.
                        find_element(By.XPATH, '/html/body/div[1]/div/div[2]/div/p').text):
                    logging.info('Need wait 30 seconds')
                    time.sleep(30)
                else:
                    logging.info('Need wait 75 seconds')
                    time.sleep(75)

            except Exception as e:
                logging.info(e)
            time.sleep(3)
            # 修改wiremode
            if router.wireless_mode:
                wifi6_switch = self.router_control.driver.find_element(By.XPATH,
                                                                       '/html/body/div[1]/div[2]/div[4]/div[1]/div/a')
                self.router_control.scroll_to(wifi6_switch)
                if wifi6_switch.get_attribute("data-on") != {'11ax': '0', '11ac': '1'}[router.wireless_mode]:
                    wifi6_switch.click()
                    time.sleep(15)

            logging.info('Router setting done')
            return True
        except Exception as e:
            logging.info('Router change setting with error')
            logging.info(e)
            return False
        finally:
            self.router_control.driver.quit()

# fields = ['serial', 'band', 'ssid', 'wireless_mode', 'channel', '
# control.reboot_router()
