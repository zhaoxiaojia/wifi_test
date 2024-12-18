#!/usr/bin/env python 
# -*- coding: utf-8 -*-
# @Time    : 2022/9/22 10:25
# @Author  : chao.li
# @Site    :
# @File    : Asusax86uControl.py
# @Software: PyCharm


import logging
import time
from collections import namedtuple

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from tools.router_tool.RouterControl import ConfigError, RouterTools


class Asusax86uControl(RouterTools):
    '''
    Asus ax86u router

    Attributes:
    '''

    CHANNEL_2_DICT = {
        'auto': '1',
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

    def __init__(self):
        super().__init__('asus_86u', display=True)

    def change_setting(self, router):
        '''
        set up wifi envrioment
        @param router: Router instance
        @return: status : boolean
        '''
        logging.info('Try to set router')
        # try:
        self.login()
        # self.driver.find_element(By.ID, 'Advanced_Wireless_Content_menu').click()
        self.driver.find_element(By.CSS_SELECTOR, '#Advanced_Wireless_Content_menu').click()
        # Wireless - General
        WebDriverWait(driver=self.driver, timeout=5, poll_frequency=0.5).until(
            EC.presence_of_element_located((By.ID, 'FormTitle')))

        # 修改 band
        if (router.band):
            if router.band not in self.BAND_LIST: raise ConfigError('band element error')
            self.change_band(router.band)

        # 修改 wireless_mode
        if (router.wireless_mode):
            self.change_wireless_mode(router.wireless_mode)

        if router.wifi6:
            if router.wifi6 == 'on':
                index = '1'
            else:
                index = '2'
            try:
                self.driver.find_element(By.XPATH,
                                         self.xpath['wireless_ax_element'][self.router_info].format(index)).click()
            except Exception as e:
                ...
        # 修改 ssid
        if (router.ssid):
            self.change_ssid(router.ssid)

        # 修改 ssid 是否隐藏
        if (router.hide_ssid):
            if (router.hide_ssid) == '是':
                self.driver.find_element(By.XPATH, ".//input[@type='radio' and @value='1']").click()
            elif (router.hide_ssid) == '否':
                self.driver.find_element(By.XPATH, ".//input[@type='radio' and @value='0']").click()
        else:
            self.driver.find_element(By.XPATH, ".//input[@type='radio' and @value='0']").click()

        # 修改 bandwidth
        if (router.bandwidth):
            if router.bandwidth not in \
                    {'2.4 GHz': self.BANDWIDTH_2, '5 GHz': self.BANDWIDTH_5}[
                        router.band]: raise ConfigError('bandwidth element error')
            self.change_bandwidth(router.bandwidth)

        # 修改 channel //*[@id="WLgeneral"]/tbody/tr[11]/td/select
        # //*[@id="WLgeneral"]/tbody/tr[11]/td/select/option[1] 2.4G Auto
        # //*[@id="WLgeneral"]/tbody/tr[11]/td/select/option[14] 2.4G 13
        # //*[@id="WLgeneral"]/tbody/tr[11]/td/select/option[1] 5G Auto
        # //*[@id="WLgeneral"]/tbody/tr[11]/td/select/option[6] 5G 165
        if (router.channel):
            channel = str(router.channel)
            # try:
            #     channel_index = (
            #         Asus86uConfig.CHANNEL_2_DICT[channel] if router.band == '2.4 GHz' else
            #         Asus86uConfig.CHANNEL_5_DICT[
            #             channel])
            # except ConfigError:
            #     raise ConfigError('channel element error')
            # //*[@id="WLgeneral"]/tbody/tr[11]/td/select/option[22]
            self.change_channel(channel)

        # 修改 authentication_method
        # //*[@id="WLgeneral"]/tbody/tr[13]/td/div[1]/select/option[1]
        # //*[@id="WLgeneral"]/tbody/tr[13]/td/div[1]/select/option[5]
        if (router.authentication_method):
            self.change_authentication_method(router.authentication_method)

        # 修改 wep_encrypt
        if (router.wep_encrypt):
            self.change_wep_encrypt(router.wep_encrypt)

        # 修改 wpa_encrypt
        if (router.wpa_encrypt):
            self.change_wpa_encrypt(router.wpa_encrypt)

        # 修改 passwd_index
        # //*[@id="WLgeneral"]/tbody/tr[17]/td/select/option[1]
        if (router.passwd_index):
            self.change_passwd_index(router.passwd_index)

        # 修改 wep_passwd
        if (router.wep_passwd):
            self.change_wep_passwd(router.wep_passwd)

        # 修改 wpa_passwd
        if (router.wpa_passwd):
            self.change_wpa_passwd(router.wpa_passwd)

        # 修改 受保护的管理帧
        # //*[@id="WLgeneral"]/tbody/tr[26]/td/select/option[1]
        if (router.protect_frame):
            if router.protect_frame not in self.PROTECT_FRAME: raise ConfigError(
                'protect frame element error')
            self.change_protect_frame(self.PROTECT_FRAME[router.protect_frame])

        time.sleep(5)
        # 点击apply
        self.driver.find_element(By.ID, 'applyButton').click()
        try:
            self.driver.switch_to.alert.accept()
            self.driver.switch_to.alert.accept()
        except Exception as e:
            ...
        WebDriverWait(self.driver, 20).until_not(
            #     //*[@id="loadingBlock"]/tbody/tr/td[2]
            EC.visibility_of_element_located((By.XPATH, '//*[@id="loadingBlock"]/tbody/tr/td[2]'))
        )
        time.sleep(2)
        logging.info('Router setting done')
        return True
        # except Exception as e:
        #     logging.info('Router change setting with error')
        #     logging.info(e)
        #     return False
        # finally:
        #     self.driver.quit()


fields = ['band', 'ssid', 'wireless_mode', 'channel', 'bandwidth', 'authentication_method', 'wpa_passwd', 'test_type',
          'wep_encrypt', 'passwd_index', 'wep_passwd', 'protect_frame', 'wpa_encrypt', 'hide_ssid', 'wifi6']
Router = namedtuple('Router', fields, defaults=[None, ] * len(fields))
router = Router(band='5 GHz', ssid='ATC_ASUS_AX88U_5G', wireless_mode='AX only', channel='100', bandwidth='20 MHz',
                authentication_method='Open System', wifi6='on')
control = Asusax86uControl()
control.change_setting(router)
# control.reboot_router()
