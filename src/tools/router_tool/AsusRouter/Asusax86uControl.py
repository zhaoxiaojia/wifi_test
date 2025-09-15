#!/usr/bin/env python 
# -*- coding: utf-8 -*-
# @Time    : 2022/9/22 10:25
# @Author  : chao.li
# @Site    :
# @File    : Asusax86uControl.py
# @Software: PyCharm


import logging
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from src.tools.router_tool.RouterControl import ConfigError
from src.tools.router_tool.AsusRouter.AsusBaseControl import AsusBaseControl


class Asusax86uControl(AsusBaseControl):
    '''
    Asus ax86u router

    Attributes:
    '''

    def __init__(self, address: str | None = None):
        super().__init__('asus_86u', display=True, address=address)

    def change_setting(self, router):
        '''
        set up wifi envrioment
        @param router: Router instance
        @return: status : boolean
        '''
        logging.info(f'Try to set router {router}')
        self.login()
        self.driver.find_element(By.ID, 'Advanced_Wireless_Content_menu').click()
        # self.driver.find_element(By.CSS_SELECTOR, '#Advanced_Wireless_Content_menu').click()
        # Wireless - General
        WebDriverWait(driver=self.driver, timeout=5, poll_frequency=0.5).until(
            EC.presence_of_element_located((By.ID, 'FormTitle')))

        # 修改 band
        if router.band:
            band = self.BAND_MAP[router.band]
            self.change_band(band)

        # 修改 wireless_mode
        if router.wireless_mode:
            self.change_wireless_mode(router.wireless_mode)
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
                    {'2.4G': self.BANDWIDTH_2, '5G': self.BANDWIDTH_5}[
                        router.band]: raise ConfigError('bandwidth element error')
            self.change_bandwidth(router.bandwidth)

        if (router.channel):
            channel = str(router.channel)
            if channel == 'auto':
                channel = '自动'
            self.change_channel(channel)

        # 修改 security_mode
        # //*[@id="WLgeneral"]/tbody/tr[13]/td/div[1]/select/option[1]
        # //*[@id="WLgeneral"]/tbody/tr[13]/td/div[1]/select/option[5]
        if router.security_mode:
            self.change_authentication(router.security_mode)

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

        # 修改 password
        if router.password:
            self.change_passwd(router.password)

        # 修改 受保护的管理帧
        # //*[@id="WLgeneral"]/tbody/tr[26]/td/select/option[1]
        if (router.protect_frame):
            if router.protect_frame not in self.PROTECT_FRAME: raise ConfigError(
                'protect frame element error')
            self.change_protect_frame(self.PROTECT_FRAME[router.protect_frame])

        time.sleep(5)
        # 点击apply
        self.driver.find_element(By.ID, 'applyButton').click()
        self.handle_alert_or_popup()
        self.handle_alert_or_popup()
        self.handle_alert_or_popup()
        try:
            WebDriverWait(self.driver, 20).until(
                #     //*[@id="loadingBlock"]/tbody/tr/td[2]
                EC.visibility_of_element_located((By.ID, 'applyButton'))
            )
        except Exception as e:
            ...
        time.sleep(2)
        logging.info('Router setting done')
        self.driver.quit()
        return True
        # except Exception as e:
        #     logging.info('Router change setting with error')
        #     logging.info(e)
        #     return False
        # finally:
        #     self.driver.quit()

# from collections import  namedtuple
# fields = ['band', 'ssid', 'wireless_mode', 'channel', 'bandwidth', 'security_mode', 'password', 'test_type',
#           'wep_encrypt', 'passwd_index', 'wep_passwd', 'protect_frame', 'wpa_encrypt', 'hide_ssid', 'wifi6']
# Router = namedtuple('Router', fields, defaults=[None, ] * len(fields))
# router = Router(band='5G', ssid='ATC_ASUS_AX88U_5G', wireless_mode='11ax', channel='100', bandwidth='20 MHz',
#                 security_mode='Open System')
# control = Asusax86uControl()
# control.change_setting(router)
# control.reboot_router()
