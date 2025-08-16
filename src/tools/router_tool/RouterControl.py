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

from src.tools.yamlTool import yamlTool


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

class ConfigError(Exception):
    def __str__(self):
        return 'element error'


class RouterTools(RouterControl):
    '''

        router tools

        load router info from csv than generate init to channge router setting

        router_info : 路由器品牌_路由器型号
        display : if senlium runs silenty



    '''

    # 操作 网页 页面 滚动  js 命令
    SCROL_JS = 'arguments[0].scrollIntoView();'

    # asus router setup value
    BAND_LIST = ['2.4G', '5G']
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

    def __init__(self, router_info, display=True, address: str | None = None):
        """初始化路由器控制对象

        Parameters
        ----------
        router_info: str
            路由器信息，格式为 ``品牌_型号``
        display: bool
            是否显示浏览器界面
        address: str | None
            路由器网关地址，如果为空则使用默认值
        """

        # 路由器品牌
        self.router_type = router_info.split("_")[0]
        # 路由器完整信息
        self.router_info = router_info
        # 路由器 各控件 元素 配置文件
        self.yaml_info = yamlTool(os.getcwd() + f'\\config\\router_xpath\\{self.router_type.split("_")[0]}_xpath.yaml')
        # self.yaml_info = yamlTool(fr'D:\PycharmProjects\wifi_test\config\router_xpath\{self.router_type}_xpath.yaml')
        # 元素配置文件 根节点
        self.xpath = self.yaml_info.get_note(self.router_type)

        # 路由器登录地址，优先使用传入参数，其次使用预设默认值
        default_address = {
            'xiaomi': '192.168.31.1',
            'asus': '192.168.50.1',
            'h3c': '192.168.4.1',
            'linksys': '192.168.3.1',
            'netgear': '192.168.9.1',
            'tplink': '192.168.5.1',
            'zte': '192.168.2.1'
        }.get(self.router_type, '192.168.1.1')
        self.address = address or default_address
        logging.info(self.address)
        self.ping_address = self.address

        # 全局等待3秒 （当driver 去查询 控件时生效）

        logging.info('*' * 80)
        logging.info(f'* Router {self.router_info}')
        logging.info('*' * 80)

    def scroll_to(self, target):
        self.driver.execute_script(self.SCROL_JS, target)

    def login(self):
        '''
        login in router
        @return:
        '''
        # 实例 driver 用于对浏览器进行操作
        self.option = webdriver.ChromeOptions()
        # if display == True:
        self.option.add_argument("--start-maximized")  # 窗口最大化
        self.option.add_experimental_option("detach", True)  # 不自动关闭浏览器
        # self.service = Service(executable_path=r"C:\Users\yu.zeng\ChromeWebDriver\chromedriver.exe")
        self.driver = webdriver.Chrome(options=self.option)
        # else:
        # self.option.add_argument(argument='headless')
        # self.driver = webdriver.Chrome(options=self.option)
        self.driver.implicitly_wait(3)


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

    def change_authentication(self, mode):
        '''
        change authentication
        @param index: should be html source code
        @return:
        '''
        select = Select(self.driver.find_element(
            By.XPATH, self.xpath['authentication_element'][self.router_info]))
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

    def change_passwd(self, passwd):
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
