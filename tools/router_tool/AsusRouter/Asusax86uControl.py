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

from tools.router_tool.AsusRouter.AsusRouterConfig import Asusax86uConfig
from tools.router_tool.RouterConfig import ConfigError
from tools.router_tool.RouterControl import RouterTools


class Asusax86uControl():
    '''
    Asus ax86u router

    Attributes:
    '''

    def __init__(self):
        self.router_control = RouterTools('asus_86u')

    def change_setting(self, router):
        '''
        set up wifi envrioment
        @param router: Router instance
        @return: status : boolean
        '''
        logging.info('Try to set router')
        try:
            self.router_control.login()
            # self.router_control.driver.find_element(By.ID, 'Advanced_Wireless_Content_menu').click()
            self.router_control.driver.find_element(By.CSS_SELECTOR, '#Advanced_Wireless_Content_menu').click()
            # Wireless - General
            WebDriverWait(driver=self.router_control.driver, timeout=5, poll_frequency=0.5).until(
                EC.presence_of_element_located((By.ID, 'FormTitle')))

            # 修改 band
            if (router.band):
                if router.band not in Asusax86uConfig.BAND_LIST: raise ConfigError('band element error')
                self.router_control.change_band(router.band)

            # 修改 wireless_mode
            if (router.wireless_mode):
                try:
                    if router.band == '2.4 GHz':
                        assert router.wireless_mode in Asusax86uConfig.WIRELESS_2_MODE
                        if router.wireless_mode == 'AX only':
                            if router.wireless_mode == 'AX only':
                                index = '1'
                                router = router._replace(wireless_mode='自动')
                            else:
                                index = '2'
                            self.router_control.driver.find_element(
                                By.XPATH,
                                self.router_control.xpath['wireless_ax_element'][
                                    self.router_control.router_info].format(
                                    index),
                            ).click()
                    else:
                        assert router.wireless_mode in Asusax86uConfig.WIRELESS_5_MODE
                except ConfigError:
                    raise ConfigError('channel element error')
                self.router_control.change_wireless_mode(router.wireless_mode)

            # 修改 ssid
            if (router.ssid):
                self.router_control.change_ssid(router.ssid)

            # 修改 ssid 是否隐藏
            if (router.hide_ssid):
                if (router.hide_ssid) == '是':
                    self.router_control.driver.find_element(By.XPATH, ".//input[@type='radio' and @value='1']").click()
                elif (router.hide_ssid) == '否':
                    self.router_control.driver.find_element(By.XPATH, ".//input[@type='radio' and @value='0']").click()
            else:
                self.router_control.driver.find_element(By.XPATH, ".//input[@type='radio' and @value='0']").click()

            # 修改 bandwidth
            if (router.bandwidth):
                if router.bandwidth not in \
                        {'2.4 GHz': Asusax86uConfig.BANDWIDTH_2, '5 GHz': Asusax86uConfig.BANDWIDTH_5}[
                            router.band]: raise ConfigError('bandwidth element error')
                self.router_control.change_bandwidth(router.bandwidth)

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
                self.router_control.change_channel(channel)

            # 修改 authentication_method
            # //*[@id="WLgeneral"]/tbody/tr[13]/td/div[1]/select/option[1]
            # //*[@id="WLgeneral"]/tbody/tr[13]/td/div[1]/select/option[5]
            if (router.authentication_method):
                try:
                    index = (Asusax86uConfig.AUTHENTICATION_METHOD[router.authentication_method]
                             if router.wireless_mode != 'Legacy' else
                             Asusax86uConfig.AUTHENTICATION_METHOD_LEGCY[router.authentication_method])
                except ConfigError:
                    raise ConfigError('authentication method element error')
                self.router_control.change_authentication_method(index)

            # 修改 wep_encrypt
            if (router.wep_encrypt):
                if router.wep_encrypt not in Asusax86uConfig.WEP_ENCRYPT: raise ConfigError('wep encrypt elemenr error')
                self.router_control.change_wep_encrypt(Asusax86uConfig.WEP_ENCRYPT[router.wep_encrypt])

            # 修改 wpa_encrypt
            if (router.wpa_encrypt):
                if router.wpa_encrypt not in Asusax86uConfig.WPA_ENCRYPT: raise ConfigError('wpa encrypt elemenr error')
                self.router_control.change_wpa_encrypt(Asusax86uConfig.WPA_ENCRYPT[router.wpa_encrypt])

            # 修改 passwd_index
            # //*[@id="WLgeneral"]/tbody/tr[17]/td/select/option[1]
            if (router.passwd_index):
                if router.passwd_index not in Asusax86uConfig.PASSWD_INDEX_DICT: raise ConfigError(
                    'passwd index element error')
                self.router_control.change_passwd_index(router.passwd_index)

            # 修改 wep_passwd
            if (router.wep_passwd):
                self.router_control.change_wep_passwd(router.wep_passwd)

            # 修改 wpa_passwd
            if (router.wpa_passwd):
                self.router_control.change_wpa_passwd(router.wpa_passwd)

            # 修改 受保护的管理帧
            # //*[@id="WLgeneral"]/tbody/tr[26]/td/select/option[1]
            if (router.protect_frame):
                if router.protect_frame not in Asusax86uConfig.PROTECT_FRAME: raise ConfigError(
                    'protect frame element error')
                self.router_control.change_protect_frame(self.PROTECT_FRAME[router.protect_frame])

            time.sleep(5)
            # 点击apply
            self.router_control.driver.find_element(By.ID, 'applyButton').click()
            try:
                self.router_control.driver.switch_to.alert.accept()
                self.router_control.driver.switch_to.alert.accept()
            except Exception as e:
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
        #     return False
        # finally:
        #     self.router_control.driver.quit()

# fields = ['band', 'ssid', 'wireless_mode', 'channel', 'bandwidth', 'authentication_method', 'wpa_passwd', 'test_type',
#           'wep_encrypt', 'passwd_index', 'wep_passwd', 'protect_frame', 'wpa_encrypt', 'hide_ssid']
# Router = namedtuple('Router', fields, defaults=[None, ] * len(fields))
# router = Router(band='5 GHz', ssid='ATC_ASUS_AX88U_5G', wireless_mode='Legacy', channel='100', bandwidth='20 MHz',
#                 authentication_method='Shared Key', hide_ssid='否', wep_encrypt='WEP-64bits', wep_passwd='12345')
# control = Asusax86uControl()
# control.change_setting(router)
# control.reboot_router()
