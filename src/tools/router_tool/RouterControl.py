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
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.common.exceptions import NoAlertPresentException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
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
# option.add_argument("--start-maximized")  # 绐楀彛鏈€澶у寲
# option.add_experimental_option("detach", True)  # 涓嶈嚜鍔ㄥ叧闂祻瑙堝櫒
# service = Service(executable_path=r"C:\Users\yu.zeng\ChromeWebDriver\chromedriver.exe")

class ConfigError(Exception):
    def __str__(self):
        return 'element error'


class RouterTools(RouterControl):
    '''

        router tools

        load router info from csv than generate init to channge router setting

        router_info : 璺敱鍣ㄥ搧鐗宊璺敱鍣ㄥ瀷鍙?
        display : if senlium runs silenty



    '''

    # 鎿嶄綔 缃戦〉 椤甸潰 婊氬姩  js 鍛戒护
    SCROL_JS = 'arguments[0].scrollIntoView();'

    # asus router setup value
    BAND_LIST = ['2.4G', '5G']
    BANDWIDTH_2 = ['20/40 MHz', '20 MHz', '40 MHz']
    BANDWIDTH_5 = ['20/40/80 MHz', '20 MHz', '40 MHz', '80 MHz']
    WIRELESS_2 = ['auto', '11b', '11g', '11n', '11ax']
    WIRELESS_5: list[str] = ['auto', '11a', '11ac', '11ax']

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
    CHANNEL_2 = ['auto', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11']
    CHANNEL_5 = ['auto', '36', '40', '44', '48', '52', '56', '60', '64', '100', '104', '108', '112', '116', '120',
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
        """鍒濆鍖栬矾鐢卞櫒鎺у埗瀵硅薄

        Parameters
        ----------
        router_info: str
            璺敱鍣ㄤ俊鎭紝鏍煎紡涓?``鍝佺墝_鍨嬪彿``
        display: bool
            鏄惁鏄剧ず娴忚鍣ㄧ晫闈?
        address: str | None
            璺敱鍣ㄧ綉鍏冲湴鍧€锛屽鏋滀负绌哄垯浣跨敤榛樿鍊?
        """

        # 璺敱鍣ㄥ搧鐗?
        self.router_type = router_info.split("_")[0]
        # 璺敱鍣ㄥ畬鏁翠俊鎭?
        self.router_info = router_info
        # 璺敱鍣?鍚勬帶浠?鍏冪礌 閰嶇疆鏂囦欢
        self.yaml_info = yamlTool(os.getcwd() + f'\\config\\router_xpath\\{self.router_type.split("_")[0]}_xpath.yaml')
        # self.yaml_info = yamlTool(
        #     fr'C:\Users\SH171300-1522\PycharmProjects\wifi_test\config\router_xpath\{self.router_type.split("_")[0]}_xpath.yaml')
        # 鍏冪礌閰嶇疆鏂囦欢 鏍硅妭鐐?
        self.xpath = self.yaml_info.get_note(self.router_type)
        # print(self.xpath)
        # 璺敱鍣ㄧ櫥褰曞湴鍧€锛屼紭鍏堜娇鐢ㄤ紶鍏ュ弬鏁帮紝鍏舵浣跨敤棰勮榛樿鍊?
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

        # 鍏ㄥ眬绛夊緟3绉?锛堝綋driver 鍘绘煡璇?鎺т欢鏃剁敓鏁堬級

        logging.info('*' * 80)
        logging.info(f'* Router {self.router_info}')
        logging.info('*' * 80)

    def scroll_to(self, target):
        self.driver.execute_script(self.SCROL_JS, target)

    def _init(self):
        self.option = webdriver.ChromeOptions()
        # if display == True:
        self.option.add_argument("--start-maximized")  # 绐楀彛鏈€澶у寲
        self.option.add_experimental_option("detach", True)  # 涓嶈嚜鍔ㄥ叧闂祻瑙堝櫒
        self.driver = webdriver.Chrome(options=self.option)
        # else:
        # self.option.add_argument(argument='headless')
        # self.driver = webdriver.Chrome(options=self.option)
        self.driver.implicitly_wait(3)

    def login(self):
        '''
        login in router
        @return:
        '''
        # 瀹炰緥 driver 鐢ㄤ簬瀵规祻瑙堝櫒杩涜鎿嶄綔
        self._init()
        self.driver.get(f"http://{self.address}")
        time.sleep(1)
        WebDriverWait(driver=self.driver, timeout=10, poll_frequency=0.5).until(
            EC.presence_of_element_located((By.ID, self.xpath['username_element'])))
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

    def change_setting(self, router):
        ...

    def reboot_router(self):
        '''
        reboot router
        @return:
        '''
        self.driver.execute_script('reboot()')
        self.driver.switch_to.alert.accept()

        element = {
            'asus_86u': self.xpath['wait_reboot_element']['asus_86u'],
            'asus_88u': self.xpath['wait_reboot_element']['asus_88u'],
            'asus_88u_pro': self.xpath['wait_reboot_element']['asus_88u_pro'],
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

    def handle_alert_or_popup(self, timeout=3):
        # 鍏堝鐞嗗師鐢?alert
        try:
            alert = self.driver.switch_to.alert
            alert.accept()
            return True
        except NoAlertPresentException:
            pass

        # 澶勭悊 HTML 寮圭獥 (OK/纭畾/纭)
        selectors = [
            "//button[text()='OK']",
            "//button[text()='确定']",
            "//button[contains(., '确认')]",
            "//input[@value='OK']",
            "//input[@value='确定']",
        ]
        for sel in selectors:
            try:
                btn = WebDriverWait(self.driver, timeout).until(
                    EC.element_to_be_clickable((By.XPATH, sel))
                )
                btn.click()
                return True
            except TimeoutException:
                continue

        # 濡傛灉閮芥病鏈夛紝鐩存帴杩斿洖 False锛屼笉鎶ラ敊
        return False

    # def __del__(self):
    #     self.driver.quit()
