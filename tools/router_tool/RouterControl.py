#!/usr/bin/env python 
# -*- coding: utf-8 -*-
# @Time    : 2021/12/30 11:05
# @Author  : chao.li
# @Site    :
# @File    : router_tool.py
# @Software: PyCharm

import logging
import os
import time
from abc import ABCMeta, abstractmethod

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from tools.yamlTool import yamlTool


class RouterControl(metaclass=ABCMeta):

    def __init__(self):
        ...

    @abstractmethod
    def login(self):
        '''
        login in router
        :return: None
        '''
        ...

    @abstractmethod
    def change_setting(self, router):
        '''
        change the router setting
        @param router: router info
        @return:
        '''
        ...

    @abstractmethod
    def reboot_router(self):
        '''
        reboot router
        @return:
        '''
        ...


# option = webdriver.ChromeOptions()
# option.add_argument(argument='headless')
# option.add_argument("--start-maximized")  # 窗口最大化
# option.add_experimental_option("detach", True)  # 不自动关闭浏览器
# service = Service(executable_path=r"C:\Users\yu.zeng\ChromeWebDriver\chromedriver.exe")


class RouterTools(RouterControl):
    '''

        router tools

        load router info from csv than generate init to channge router setting

        router_info : 路由器品牌_路由器型号
        display : if senlium runs silenty



    '''

    # 操作 网页 页面 滚动  js 命令
    SCROL_JS = 'arguments[0].scrollIntoView();'

    def __init__(self, router_info, display=False):
        # 路由器品牌
        self.router_type = router_info.split("_")[0]
        # 路由器完整信息
        self.router_info = router_info
        # 路由器 各控件 元素 配置文件
        # self.yaml_info = yamlTool(os.getcwd() + f'\\config\\{self.router_type.split("_")[0]}_xpath.yaml')
        self.yaml_info = yamlTool(f'D:\PycharmProjects\wifi_test\config\{self.router_type}_xpath.yaml')
        # 元素配置文件 根节点

        self.xpath = self.yaml_info.get_note(self.router_type)
        # print(self.xpath['address'])
        # print(router_info.split("_")[1])

        # 路由器登录 地址
        self.address = self.xpath['address'][router_info.split("_")[1]]
        # 实例 driver 用于对浏览器进行操作
        self.option = webdriver.ChromeOptions()
        if display == True:
            self.option.add_argument("--start-maximized")  # 窗口最大化
            self.option.add_experimental_option("detach", True)  # 不自动关闭浏览器
            # self.service = Service(executable_path=r"C:\Users\yu.zeng\ChromeWebDriver\chromedriver.exe")
            self.driver = webdriver.Chrome(options=self.option)
        else:
            self.option.add_argument(argument='headless')
            self.driver = webdriver.Chrome(options=self.option)

        # 全局等待3秒 （当driver 去查询 控件时生效）
        self.driver.implicitly_wait(3)

    def scroll_to(self, target):
        self.driver.execute_script(self.SCROL_JS, target)

    def login(self):
        '''
        login in router
        @return:
        '''
        try:
            # driver 连接 登录地址
            self.driver.get(self.address)
            # input username
            self.driver.find_element(By.ID, self.xpath['username_element']).click()
            self.driver.find_element(By.ID, self.xpath['username_element']).send_keys(self.xpath['account'])
            # input passwd
            self.driver.find_element(By.NAME, self.xpath['password_element']).click()
            self.driver.find_element(By.NAME, self.xpath['password_element']).send_keys(self.xpath['passwd'])
            # click login
            self.driver.find_element(By.XPATH, self.xpath['signin_element'][self.router_info]).click()
            # wait for login in done
            WebDriverWait(driver=self.driver, timeout=10, poll_frequency=0.5).until(
                EC.presence_of_element_located((By.ID, self.xpath['signin_done_element'])))
            time.sleep(1)
        except Exception as e:
            logging.info(e)

    def change_setting(self, router):
        ...

    def reboot_router(self):
        '''
        reboot router
        @return:
        '''
        self.driver.execute_script('reboot()')
        self.driver.switch_to.alert.accept()

        element = {'asus_86u': self.xpath['wait_reboot_element']['asus_86u'],
                   'asus_88u': self.xpath['wait_reboot_element']['asus_88u'],
                   'asus_5400': self.xpath['wait_reboot_element']['asus_5400'],
                   }
        WebDriverWait(self.driver, 180).until(
            EC.visibility_of_element_located((By.XPATH, element[self.router_info]))
        )
        self.driver.quit()

    def change_band(self, band):
        '''
        select band
        @param band:
        @return:
        '''
        bind_select = Select(self.driver.find_element(By.XPATH, self.xpath['band_element']))
        bind_select.select_by_visible_text(band)

        # assert bind_select.first_selected_option.text == band, "Band not selected"

    def change_wireless_mode(self, mode):
        '''
        select mode
        @param mode:
        @return:
        '''
        wireless_mode_select = Select(
            self.driver.find_element(By.XPATH, self.xpath['wireless_mode_element'][self.router_info]))
        wireless_mode_select.select_by_visible_text(mode)
        assert wireless_mode_select.first_selected_option.text == mode, "Wireless mode not selected"

    def change_ssid(self, ssid):
        '''
        set ssid
        @param ssid:
        @return:
        '''
        ssid_element = self.driver.find_element(By.ID, self.xpath['ssid_element'])
        self.driver.execute_script(f'arguments[0].value = "{ssid}"', ssid_element)
        assert ssid_element.get_attribute('value') == ssid, "Set ssid error"
        # self.driver.find_element(By.ID, self.xpath['ssid_element']).clear()
        # self.driver.find_element(By.ID, self.xpath['ssid_element']).send_keys(ssid)

    def change_hide_ssid(self, status):
        ...

    def change_channel(self, channel):
        '''
        change channel
        @param index: should be html source code
        @return:
        '''
        # self.driver.find_element(By.XPATH, self.xpath['channel_regu_element'][self.router_info].format(index)).click()
        select = Select(
            self.driver.find_element(By.XPATH, self.xpath['channel_element'][self.router_info]))
        select.select_by_visible_text(channel)
        # if index not in select_info:
        #     logging.warning("Doesn't support this channel")
        #     self.driver.find_element(By.XPATH, self.xpath['channel_element'][self.router_info].format(1)).click()
        #     return

        assert select.first_selected_option.text == channel, "Channel not selected"

    def change_bandwidth(self, bandwidth):
        '''
        select bandwith
        @param bandwith:
        @return:
        '''
        bandwidth_select = Select(self.driver.find_element(By.XPATH, self.xpath['bandwidth_element']))
        bandwidth_select.select_by_visible_text(bandwidth)

        assert bandwidth_select.first_selected_option.text == bandwidth, "Band width mode not selected"

    def change_authentication_method(self, mode):
        '''
        change authentication_method
        @param index: should be html source code
        @return:
        '''
        select = Select(self.driver.find_element(
            By.XPATH, self.xpath['authentication_method_element'][self.router_info]))
        select.select_by_visible_text(mode)

        assert select.first_selected_option.text == mode, "Authentication mode not selected"

    def change_wep_encrypt(self, text):
        '''
        change wep encrypt
        @param index:
        @return:
        '''
        select = Select(self.driver.find_element(
            By.XPATH, self.xpath['wep_encrypt_regu_element'][self.router_info].format(text)))
        select.select_by_visible_text(text)

        assert select.first_selected_option.text == text, "Wep encrypt not selected"

    def change_wpa_encrypt(self, encrpyt):
        '''
        change wpa encrypt
        @param index:
        @return:
        '''
        select = Select(self.driver.find_element(By.XPATH, self.xpath['wpa_encrypt_element']))
        select.select_by_visible_text(encrpyt)

        assert select.first_selected_option.text == encrpyt, "Wpa encrpyt not selected"

    def change_passwd_index(self, index):
        '''
        change passwd index
        @param passwd_index: should be html source code
        @return:
        '''

        select = Select(self.driver.find_element(By.XPATH, self.xpath['passwd_index_element'][self.router_info]))
        select.select_by_visible_text(index)

        assert select.first_selected_option.text == index, "Password index not selected"

    def change_wep_passwd(self, passwd):
        '''
        change wep passwd
        @param passwd:
        @return:
        '''
        element = self.driver.find_element(By.ID, self.xpath['wep_passwd_element'])
        element.click()
        element.clear()
        element.send_keys(passwd)

        assert element.get_property('value') == passwd, "Wep password set error"

    def change_wpa_passwd(self, passwd):
        '''
        change wpa passwd
        @param passwd:
        @return:
        '''

        element = self.driver.find_element(By.XPATH, self.xpath['wpa_passwd_element'][self.router_info])
        element.click()
        element.clear()
        element.send_keys(passwd)

        assert element.get_property('value') == passwd, "Wpa password set error"

    def change_protect_frame(self, frame):
        '''
        change protect frame
        @param frame: should be html source code
        @return:
        '''
        bind_select = Select(
            self.driver.find_element(By.XPATH, self.xpath['protect_frame_element'][self.router_info]))
        bind_select.select_by_visible_text(frame)

        assert bind_select.first_selected_option.text == frame, "Protect frame not selected"

    def apply_setting(self):
        '''
        click apply button
        @return:
        '''
        self.driver.find_element(By.ID, self.xpath['apply_element']).click()

    def click_alert(self):
        try:
            self.driver.switch_to.alert.accept()
        except Exception as e:
            ...

    def wait_setting_done(self):
        WebDriverWait(self.driver, 20).until_not(
            #     //*[@id="loadingBlock"]/tbody/tr/td[2]
            EC.visibility_of_element_located((By.XPATH, self.xpath['setting_load_element']))
        )
        time.sleep(2)

    def element_is_selected(self, xpath):
        element = self.driver.find_element(By.XPATH, xpath)
        if element.is_selected():
            return True
        else:
            return False

    # def __del__(self):
    #     self.driver.quit()
