#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2022/10/31 16:59
# @Author  : chao.li
# @Site    :
# @File    : Asusax5400Control.py
# @Software: PyCharm


import logging
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from src.tools.router_tool.RouterControl import ConfigError, RouterTools


class Asusax5400Control:
    def __init__(self):
        self.router_control = RouterTools('asus_5400', display=True)
        # 暴露 RouterTools 中的常量供 UI 使用
        attrs = [
            'BAND_LIST', 'WIRELESS_2', 'WIRELESS_5', 'CHANNEL_2', 'CHANNEL_5',
            'BANDWIDTH_2', 'BANDWIDTH_5', 'AUTHENTICATION_METHOD',
            'AUTHENTICATION_METHOD_LEGCY', 'WEP_ENCRYPT', 'WPA_ENCRYPT',
            'PASSWD_INDEX_DICT', 'PROTECT_FRAME'
        ]
        for attr in attrs:
            setattr(self, attr, getattr(self.router_control, attr))

    def change_setting(self, router):
        '''
        set up wifi envrioment
        @param router: Router instance
        @return: status : boolean
        '''
        logging.info('Try to set router')
        try:
            self.router_control.login()
            self.router_control.driver.find_element(By.ID, 'Advanced_Wireless_Content_menu').click()
            # Wireless - General
            WebDriverWait(driver=self.router_control.driver, timeout=5, poll_frequency=0.5).until(
                EC.presence_of_element_located((By.ID, 'FormTitle')))

            # 修改 band
            if router.band:
                if router.band not in self.BAND_LIST:
                    raise ConfigError('band element error')
                self.router_control.change_band(router.band)

            # 修改 wireless_mode
            if router.wireless_mode:
                target_list = self.WIRELESS_2 if router.band == '2.4 GHz' else self.WIRELESS_5
                if router.wireless_mode not in target_list:
                    raise ConfigError('channel element error')
                self.router_control.change_wireless_mode(router.wireless_mode)
                if 'AX only' == router.wireless_mode:
                    self.router_control.driver.find_element(
                        By.XPATH, '//*[@id="he_mode_field"]/td/div/select/option[1]').click()
            # 修改 ssid
            if (router.ssid):
                self.router_control.change_ssid(router.ssid)

            # 修改 ssid 是否隐藏
            if (router.hide_ssid):
                if (router.hide_ssid) == '是':
                    self.router_control.driver.find_element(
                        By.XPATH, '//*[@id="WLgeneral"]/tbody/tr[5]/td/input[1]').click()
                elif (router.hide_ssid) == '否':
                    self.router_control.driver.find_element(
                        By.XPATH, '//*[@id="WLgeneral"]/tbody/tr[5]/td/input[2]').click()
            else:
                self.router_control.driver.find_element(By.XPATH, ".//input[@type='radio' and @value='0']").click()

            # 修改 channel
            if router.channel:
                channel = str(router.channel)
                self.router_control.change_channel(channel)

            # 修改 bandwidth
            if router.bandwidth:
                if router.bandwidth not in {
                    '2.4 GHz': self.BANDWIDTH_2,
                    '5 GHz': self.BANDWIDTH_5,
                }[router.band]:
                    raise ConfigError('bandwidth element error')
                self.router_control.change_bandwidth(router.bandwidth)

            # 修改 authentication
            if router.authentication:
                self.router_control.change_authentication(router.authentication)

            # 修改 wep_encrypt
            if router.wep_encrypt:
                if router.wep_encrypt not in self.WEP_ENCRYPT:
                    raise ConfigError('wep encrypt elemenr error')
                self.router_control.change_wep_encrypt(self.WEP_ENCRYPT[router.wep_encrypt])

            # 修改 wpa_encrypt
            if router.wpa_encrypt:
                if router.wpa_encrypt not in self.WPA_ENCRYPT:
                    raise ConfigError('wpa encrypt elemenr error')
                self.router_control.change_wpa_encrypt(self.WPA_ENCRYPT[router.wpa_encrypt])

            # 修改 passwd_index
            if router.passwd_index:
                if router.passwd_index not in self.PASSWD_INDEX_DICT:
                    raise ConfigError('passwd index element error')
                self.router_control.change_passwd_index(router.passwd_index)

            # 修改 wep_passwd
            if (router.wep_passwd):
                self.router_control.change_wep_passwd(router.wep_passwd)

            # 修改 wpa_passwd
            if router.wpa_passwd:
                self.router_control.change_wpa_passwd(router.wpa_passwd)

            # 修改 受保护的管理帧
            if router.protect_frame:
                if router.protect_frame not in self.PROTECT_FRAME:
                    raise ConfigError('protect frame element error')
                self.router_control.change_protect_frame(self.PROTECT_FRAME[router.protect_frame])

            time.sleep(5)
            # 点击apply
            self.router_control.apply_setting()
            try:
                self.router_control.driver.switch_to.alert.accept()
                self.router_control.driver.switch_to.alert.accept()
                self.router_control.driver.switch_to.alert.accept()
                self.router_control.driver.switch_to.alert.accept()

            except Exception as e:
                ...
            try:
                # deal with hide ssid warning
                if router.hide_ssid == '是':
                    self.router_control.driver.find_element(By.XPATH, '/html/body/div[4]/div/div[3]/div[1]').click()
            except Exception as  e:
                ...
            WebDriverWait(self.router_control.driver, 20).until_not(
                #     //*[@id="loadingBlock"]/tbody/tr/td[2]
                EC.visibility_of_element_located((By.XPATH, '//*[@id="loadingBlock"]/tbody/tr/td[2]'))
            )
            time.sleep(2)
            logging.info('Router setting done')
            return True
        except Exception as e:
            logging.info('Router change setting with error')
            logging.info(e)
            return False
        finally:
            self.router_control.driver.quit()

# fields = ['serial', 'band', 'ssid', 'wireless_mode', 'channel', 'bandwidth', 'authentication', 'wep_encrypt',
#           'passwd_index', 'wep_passwd', 'wpa_passwd', 'protect_frame', 'wpa_encrypt', 'hide_ssid', 'hide_type']
# Router = namedtuple('Router', fields, defaults=[None, ] * len(fields))
# router = Router(serial='1', band='5 GHz', ssid='ASUSAX5400_5G', wireless_mode='N/AC mixed',
#                 channel='40', bandwidth='20 MHz', authentication='Open System',hide_ssid='是')
# control = Asusax5400Control()
# control.change_setting(router)
# control.router_control.reboot_router()
