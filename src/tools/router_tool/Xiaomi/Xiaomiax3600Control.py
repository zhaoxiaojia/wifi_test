#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2022/11/3 09:42
# @Author  : chao.li
# @Site    :
# @File    : Xiaomiax3600Control.py
# @Software: PyCharm


import logging
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from src.tools.router_tool.RouterControl import ConfigError, RouterTools


class Xiaomiax3600Control(RouterTools):
    '''

    rvr
    1,2.4G, XiaomiAX3000_2.4G,11ac ,6,40MHz ,超强加密(WPA3个人版) , 12345678,rx,TCP,5 ,10 10
    '''
    BAND_2 = '2.4G'
    BAND_5 = '5G'
    CHANNEL_2 = {
        '自动': '1',
        '1': '2',
        '2': '3',
        '3': '4',
        '4': '5',
        '5': '6',
        '6': '7',
        '7': '8',
        '8': '9',
        '9': '10',
        '10': '11',
        '11': '12',
        '12': '13',
        '13': '14',
    }

    CHANNEL_5 = {
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
        '165': '14'
    }

    AUTHENTICATION_METHOD = {
        '超强加密(WPA3个人版)': '1',
        '强混合加密(WPA3/WPA2个人版)': '2',
        '强加密(WPA2个人版)': '3',
        '混合加密(WPA/WPA2个人版)': '4',
        '无加密(允许所有人连接)': '5'
    }

    BANDWIDTH_5 = {
        '160/80/40/20MHz': '1',
        '20MHz': '2',
        '40MHz': '3',
        '80MHz': '4'
    }

    BANDWIDTH_2 = {
        '40/20MHz': '1',
        '20MHz': '2',
        '40MHz': '3'
    }

    WIRELESS_2 = ['11n', '11ax']
    WIRELESS_5 = ['11ac', '11ax']

    def __init__(self, address: str | None = None):
        super().__init__('xiaomi_ax3600', display=True, address=address)

    def login(self):
        '''

        Returns:

        '''
        # try:
        super().login()
        self.driver.get(f"http://{self.address}")
        # input passwd
        self.driver.find_element(By.ID, self.xpath['password_element']).click()
        time.sleep(0.5)
        self.driver.find_element(By.ID, self.xpath['password_element']).send_keys(
            self.xpath['passwd'])
        # click login
        self.driver.find_element(By.ID, self.xpath['signin_element']).click()
        # wait for login in done
        WebDriverWait(driver=self.driver, timeout=10, poll_frequency=0.5).until(
            EC.presence_of_element_located((By.ID, self.xpath['signin_done_element'])))
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
        self.login()
        WebDriverWait(driver=self.driver, timeout=10, poll_frequency=0.5).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, "div.mask-menu")))
        element = self.driver.find_element(By.CSS_SELECTOR, "a.btn_wifi")
        self.driver.execute_script("arguments[0].click();", element)
        # Wireless - Profession
        wait = WebDriverWait(driver=self.driver, timeout=5, poll_frequency=0.5)
        wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="wifiset24"]/div[1]')))

        if router.band == self.BAND_5:
            wait_for = self.driver.find_element(By.XPATH, '//*[@id="wifiset50"]')
            self.scroll_to(wait_for)

        # 修改 ssid
        if router.ssid:
            if self.BAND_2 == router.band:
                target = 'ssid_2g'
            else:
                target = 'ssid_5g'
            self.driver.find_element(
                By.XPATH, self.xpath['ssid_element'][target]).clear()
            self.driver.find_element(
                By.XPATH, self.xpath['ssid_element'][target]).send_keys(router.ssid)
            self.driver.find_element(By.XPATH, self.xpath['ssid_element'][target]).click()

        hide_2g = self.driver.find_element(
            By.ID, self.xpath['hide_ssid']['hide_2g'])
        hide_5g = self.driver.find_element(
            By.ID, self.xpath['hide_ssid']['hide_5g'])

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
        # 修改 security_protocol
        if router.security_protocol:
            try:
                index = self.AUTHENTICATION_METHOD[router.security_protocol]
            except ConfigError:
                raise ConfigError('security protocol method element error')
            target = 'authentication_2g' if self.BAND_2 == router.band else 'authentication_5g'
            self.driver.find_element(
                By.XPATH, self.xpath['authentication_select_element'][target]).click()
            # //*[@id="dummydata"]/a[3]/span
            self.driver.find_element(
                By.XPATH, self.xpath['authentication_regu_element'].format(index)).click()

        # 修改密码
        if router.password:
            if self.BAND_2 == router.band:
                target = 'passwd_2g'
            else:
                target = 'passwd_5g'
            self.driver.find_element(
                By.XPATH, self.xpath['passwd_element'][target]).clear()
            self.driver.find_element(
                By.XPATH, self.xpath['passwd_element'][target]).send_keys(router.password)

        if router.channel:
            channel = str(router.channel)
            try:
                if router.band == '2.4G':
                    index = self.CHANNEL_2[channel]
                    target = 'channel_2g'
                else:
                    index = self.CHANNEL_5[channel]
                    target = 'channel_5g'
            except KeyError:
                raise ConfigError('channel element error')

            self.driver.find_element(
                By.XPATH, self.xpath['channel_select_element'][target]).click()
            wait_for = self.driver.find_element(
                By.XPATH, self.xpath['channel_regu_element'].format(index))
            self.scroll_to(wait_for)
            time.sleep(1)
            wait_for.click()

            try:
                self.driver.find_element(By.XPATH, "/html/body/div[1]/div/div[3]/div/a").click()
            except Exception:
                ...

        # 修改 bandwidth
        if router.bandwidth:
            if router.band == self.BAND_2:
                target_dict = self.BANDWIDTH_2
                target = 'bandwidth_2g'
            else:
                target_dict = self.BANDWIDTH_5
                target = 'bandwidth_5g'
            if router.bandwidth not in target_dict: raise ConfigError('bandwidth element error')
            self.driver.find_element(
                By.XPATH, self.xpath['bandwidth_select_element'][target]).click()
            time.sleep(1)
            select_list = self.driver.find_element(By.ID, 'dummydata')
            lis = select_list.find_elements(By.TAG_NAME, 'span')
            if len(lis) > 1:
                index = [i.text for i in lis].index(router.bandwidth) + 1
                self.driver.find_element(
                    By.XPATH, self.xpath['bandwidth_element'].format(index)).click()

        time.sleep(5)
        # 点击apply
        temp = 'apply_2g' if router.band == self.BAND_2 else 'apply_5g'
        wait_for = self.driver.find_element(
            By.XPATH, self.xpath['apply_element'][temp])
        self.scroll_to(wait_for)
        wait_for.click()
        self.driver.find_element(By.XPATH, '/html/body/div[1]/div/div[3]/div/a[1]/span').click()
        # try:
        if ('需要30秒请等待...' in self.driver.
                find_element(By.XPATH, '/html/body/div[1]/div/div[2]/div/p').text):
            logging.info('Need wait 30 seconds')
            time.sleep(30)
        else:
            logging.info('Need wait 75 seconds')
            time.sleep(75)

        # except Exception as e:
        #     logging.info(e)
        time.sleep(3)
        # 修改wiremode
        if router.wireless_mode:
            wifi6_switch = self.driver.find_element(By.XPATH,
                                                    '//*[@id="WIFI6switch"]')
            self.scroll_to(wifi6_switch)
            if wifi6_switch.get_attribute("data-on") != {'11ax': '0', '11ac': '1', '11n': '1'}[
                router.wireless_mode]:
                wifi6_switch.click()
                time.sleep(35)

        logging.info('Router setting done')
        self.driver.quit()
        return True

# fields = ['serial', 'band', 'ssid', 'wireless_mode', 'channel', 'bandwidth', 'security_protocol', 'password',
#           'test_type',
#           'wep_encrypt', 'passwd_index', 'wep_passwd', 'protect_frame', 'wpa_encrypt', 'hide_ssid']
# Router = namedtuple('Router', fields, defaults=[None, ] * len(fields))
# router5 = Router(serial='1', band='5G', ssid='XiaomiAX3000_2.4G', channel='36', wireless_mode='11ax',
#                  bandwidth='80MHz', authentication='超强加密(WPA3个人版)', password='12345678',
#                  hide_ssid='否')
# router2 = Router(serial='1', band='2.4G', ssid='XiaomiAX3000_2.4G', channel='1', wireless_mode='11ac',
#                  bandwidth='40MHz', authentication='超强加密(WPA3个人版)', password='12345678',
#                  hide_ssid='否')
# control = Xiaomiax3000Control()
# control.change_setting(router2)
# control.reboot_router()
