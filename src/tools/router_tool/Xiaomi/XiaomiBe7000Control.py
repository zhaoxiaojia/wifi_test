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

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from src.tools.router_tool.RouterControl import ConfigError
from src.tools.router_tool.Xiaomi.XiaomiBaseControl import XiaomiBaseControl


class XiaomiBe7000Control(XiaomiBaseControl):

    def __init__(self, address: str | None = None):
        super().__init__('xiaomi_be7000', display=True, address=address)

    def change_setting(self, router):
        super().change_setting(router)
        try:
            wait_for = self.driver.find_element(
                By.XPATH, self.xpath['apply_element']['apply_5g'])
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
        except Exception:
            logging.warning("Fail to find hold on windows")
        # 修改wiremode
        if router.wireless_mode:
            # //*[@id="WIFI6switch"]
            wifi6_switch = self.driver.find_element(By.XPATH, '//*[@id="WIFI6switch"]')
            self.scroll_to(wifi6_switch)
            if wifi6_switch.get_attribute("data-on") != '0' if router.wireless_mode == '11ax' else '1':
                wifi6_switch.click()
                time.sleep(15)
        logging.info('Router setting done')
        self.driver.quit()
        return True
        # except Exception as e:
        #     logging.info('Router change setting with error')
        #     logging.info(e)
        #     return False
