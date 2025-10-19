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

from src.tools.router_tool.RouterControl import ConfigError
from src.tools.router_tool.Xiaomi.XiaomiBaseControl import XiaomiBaseControl


class Xiaomiax3600Control(XiaomiBaseControl):
    '''

    rvr
    1,2.4G, XiaomiAX3000_2.4G,11ac ,6,40MHz ,超强加密(WPA3个人版) , 12345678,rx,TCP,5 ,10 10
    '''

    def __init__(self, address: str | None = None):
        super().__init__('xiaomi_ax3600', display=True, address=address)

    def change_setting(self, router):
        super().change_setting(router)

        # 点击apply
        try:
            temp = 'apply_2g' if router.band == self.BAND_2 else 'apply_5g'
            wait_for = self.driver.find_element(
                By.XPATH, self.xpath['apply_element'][temp])
            self.scroll_to(wait_for)
            wait_for.click()
            self.driver.find_element(By.XPATH, '/html/body/div[1]/div/div[3]/div/a[1]/span').click()
        except Exception as e:
            logging.warning("Failed to click apply")
        try:
            if ('需要30秒请等待...' in self.driver.
                    find_element(By.XPATH, '/html/body/div[1]/div/div[2]/div/div/div[2]').text):
                logging.info('Need wait 30 seconds')
                time.sleep(30)
            else:
                logging.info('Need wait 75 seconds')
                time.sleep(75)
        except Exception as e:
            time.sleep(75)
            logging.warning("Fail to find hold on windows")
        time.sleep(3)
        # 修改wiremode
        if router.wireless_mode:
            logging.info(f'coco {router.wireless_mode}')
            wifi6_switch = self.driver.find_element(By.XPATH,
                                                    '//*[@id="WIFI6switch"]')
            self.scroll_to(wifi6_switch)
            logging.info(wifi6_switch.get_attribute("data-on"))
            if wifi6_switch.get_attribute("data-on") != ('0' if router.wireless_mode == '11ax' else '1'):
                logging.info('click')
                wifi6_switch.click()
                time.sleep(35)

        logging.info('Router setting done')
        self.driver.quit()
        return True

# fields = ['serial', 'band', 'ssid', 'wireless_mode', 'channel', 'bandwidth', 'security_mode', 'password',
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
