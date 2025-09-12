#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2022/11/4 09:28
# @Author  : chao.li
# @Site    :
# @File    : Linksys1200acControl.py
# @Software: PyCharm


import logging
import time

from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from src.tools.router_tool.Linksys1200acConfig import Linksys1200acConfig
from src.tools.router_tool.RouterControl import RouterTools,ConfigError


class Linksys1200acControl():
    '''
    H3c bx54 router

    Attributes:
    '''

    def __init__(self):
        self.router_control = RouterTools('linksys_1200ac', display=True)
        self.router_control.driver.maximize_window()

    def login(self):
        WebDriverWait(driver=self.router_control.driver, timeout=10, poll_frequency=0.5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#adminPass")))
        # click login
        try:
            # input passwd
            self.router_control.driver.find_element(By.ID, self.router_control.xpath['password_element']).click()
            self.router_control.driver.find_element(By.XPATH, '//*[@id="language-select"]/option[23]').click()
            time.sleep(2)
            self.router_control.driver.find_element(By.ID, self.router_control.xpath['password_element']).send_keys(
                self.router_control.xpath['passwd'])
            # click login
            self.router_control.driver.find_element(By.ID, self.router_control.xpath['signin_element']).click()
            # wait for login in done
            WebDriverWait(driver=self.router_control.driver, timeout=10, poll_frequency=0.5).until(
                EC.presence_of_element_located((By.ID, self.router_control.xpath['signin_done_element'])))
        except NoSuchElementException as e:
            ...
        time.sleep(1)

    def change_setting(self, router):
        '''
        set up wifi envrioment
        @param router: Router instance
        @return: status : boolean
        '''
        logging.info('Try to set router')
        try:
            self.login()
            self.router_control.driver.find_element(
                By.XPATH, '//*[@id="68980747-C5AA-4C8B-AF53-FC1023DE2567"]/ul/li[3]').click()
            # Wireless - Profession
            WebDriverWait(driver=self.router_control.driver, timeout=5, poll_frequency=0.5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '#RADIO_2\.4GHz > h2:nth-child(1)')))

            # 修改 channel
            if (router.channel):
                channel = str(router.channel)
                try:
                    if router.band == '2.4G':
                        channel_index = Linksys1200acConfig.CHANNEL_2_DICT[channel]
                        self.router_control.driver.find_element(
                            By.XPATH,
                            self.router_control.xpath['channel_regu_element']['channel_2g'].format(
                                channel_index)).click()
                    else:
                        channel_index = Linksys1200acConfig.CHANNEL_5_DICT[channel]
                        self.router_control.driver.find_element(
                            By.XPATH,
                            self.router_control.xpath['channel_regu_element']['channel_5g'].format(
                                channel_index)).click()
                except KeyError:
                    raise ConfigError('channel element error')

            # 修改 wireless_mode
            if (router.wireless_mode):
                if '2' in router.band:
                    target_dict = Linksys1200acConfig.WIRELESS_MODE_2G_DICT
                    target_element = 'mode_2g'
                else:
                    target_dict = Linksys1200acConfig.WIRELESS_MODE_5G_DICT
                    target_element = 'mode_5g'
                if router.wireless_mode not in target_dict: raise ConfigError(
                    'wireless mode element error')
                index = target_dict[router.wireless_mode]
                self.router_control.driver.find_element(
                    By.XPATH, self.router_control.xpath['wireless_mode_element'][target_element].format(index)).click()

            # 修改 bandwidth
            try:
                if (router.bandwidth):
                    if '2' in router.band:
                        target_dict = Linksys1200acConfig.BANDWIDTH_2_DICT
                        target_element = 'bandwidth_2g'
                    else:
                        target_dict = Linksys1200acConfig.BANDWIDTH_5_DICT
                        target_element = 'bandwidth_5g'
                    if router.bandwidth not in target_dict: raise ConfigError('bandwidth element error')
                    index = target_dict[router.bandwidth]
                    self.router_control.driver.find_element(
                        By.XPATH, self.router_control.xpath['bandwidth_element'][target_element].format(index)).click()
            except NotImplementedError:
                logging.info('Select element is disabled !!')

            # 修改 ssid
            if (router.ssid):
                if '2' in router.band:
                    self.router_control.driver.find_element(By.XPATH,
                                                            self.router_control.xpath['ssid_element_2g']).clear()
                    self.router_control.driver.find_element(
                        By.XPATH, self.router_control.xpath['ssid_element_2g']).send_keys(router.ssid)
                else:
                    self.router_control.driver.find_element(By.XPATH,
                                                            self.router_control.xpath['ssid_element_5g']).clear()
                    self.router_control.driver.find_element(
                        By.XPATH, self.router_control.xpath['ssid_element_5g']).send_keys(router.ssid)

            #
            if (router.security_mode):
                try:
                    index = Linksys1200acConfig.AUTHENTICATION_METHOD_DICT[router.security_mode]
                except ConfigError:
                    raise ConfigError('security protocol method element error')
                # //*[@id="ssid_enc"]/option[1]
                if '2' in router.band:
                    target_element = 'authtication_2g'
                else:
                    target_element = 'authtication_5g'
                self.router_control.driver.find_element(
                    By.XPATH,
                    self.router_control.xpath['authentication_regu_element'][target_element].format(
                        index)).click()
                try:
                    self.router_control.driver.find_element(By.ID, "error-dialog-wrapper") \
                        .find_element(By.ID, "generic-warning-dialog") \
                        .find_element(By.CSS_SELECTOR, '#generic-warning-dialog > div.dialog-buttons.text-orphan') \
                        .find_element(By.CSS_SELECTOR,
                                      '#generic-warning-dialog > div.dialog-buttons.text-orphan > button.submit').click()
                except Exception:
                    ...
            if '2' in router.band:
                element = '//*[@id="RADIO_2.4GHz"]/div/select[1]/option[{}]'
            else:
                element = '//*[@id="RADIO_5GHz"]/div/select[1]/option[{}]'

            # 修改 ssid 是否隐藏
            if (router.hide_ssid):
                if (router.hide_ssid) == '是':
                    self.router_control.driver.find_element(By.XPATH, element.format('2')).click()
                elif (router.hide_ssid) == '否':
                    self.router_control.driver.find_element(By.XPATH, element.format('1')).click()
            else:
                self.router_control.driver.find_element(By.XPATH, element.format('1')).click()

            # 修改 wep_encrypt
            if (router.wep_encrypt):
                if router.wep_encrypt not in Linksys1200acConfig.WEP_ENCRYPT: raise ConfigError(
                    'wep encrypt elemenr error')
                if '2' in router.band:
                    target = 'wep_2g'
                else:
                    target = 'wep_5g'
                index = Linksys1200acConfig.WEP_ENCRYPT[router.wep_encrypt]
                self.router_control.driver.find_element(
                    By.XPATH, self.router_control.xpath['wep_encrypt_regu_element'][target].format(index)).click()

            if '2' in router.band:
                target_element = 'passwd_2g'
                target_wep = 'wep_2g'
            else:
                target_element = 'passwd_5g'
                target_wep = 'wep_5g'
            # 修改密码
            if (router.wpa_passwd):
                self.router_control.driver.find_element(
                    By.XPATH, self.router_control.xpath['wpa_passwd'][target_element]).clear()
                self.router_control.driver.find_element(
                    By.XPATH, self.router_control.xpath['wpa_passwd'][target_element]).send_keys(router.wpa_passwd)

            if (router.wep_passwd):
                self.router_control.driver.find_element(
                    By.XPATH, self.router_control.xpath['wep_passwd'][target_wep]).clear()
                self.router_control.driver.find_element(
                    By.XPATH, self.router_control.xpath['wep_passwd'][target_wep]).send_keys(router.wep_passwd)

                # self.router_control.driver.find_element(
                #     By.XPATH, self.router_control.xpath['wep_index'][target_wep]).clear()
                # self.router_control.driver.find_element(
                #     By.XPATH, self.router_control.xpath['wep_index'][target_wep]).send_keys(router.wep_passwd)

            time.sleep(5)
            # 点击apply
            wait_for = self.router_control.driver.find_element(By.XPATH, '//*[@id="wireless-applet"]/footer/button[1]')
            self.router_control.scroll_to(wait_for)
            wait_for.click()

            # 点击弹窗 您的一个或多个无线网络禁用了安全模式。 您的网络可能会对未授权用户开放。 您是否确定要继续？
            try:
                self.router_control.driver.find_element(By.XPATH,
                                                        '/html/body/div[2]/div[5]/div[23]/div/div[2]/button[2]').click()
            # self.router_control.driver.find_element(By.ID, "error-dialog-wrapper") \
            #     .find_element(By.ID, "generic-warning-dialog") \
            #     .find_element(
            #     By.XPATH, '//*[@id="generic-warning-dialog"]/div[2]/button[2]').click()
            except Exception:
                ...

            # 点击确认wifi设置弹窗
            try:
                self.router_control.driver.find_element(By.ID, "generic-dialog-wrapper") \
                    .find_element(By.ID, "radio-disconnect-warning") \
                    .find_element(By.XPATH, '//*[@id="radio-disconnect-warning"]/div[3]/button[2]').click()
            except Exception:
                ...

            # 点击应用更改弹窗
            try:
                self.router_control.driver.find_element(By.ID, "error-dialog-wrapper") \
                    .find_element(By.ID, "router-interruption") \
                    .find_element(By.CSS_SELECTOR, '#confirm').click()
            except Exception:
                ...
            WebDriverWait(self.router_control.driver, 30).until_not(
                EC.visibility_of_element_located((By.ID, 'waiting')))
            time.sleep(2)
            logging.info('Router setting done')
            return True
        except Exception as e:
            logging.info('Router change setting with error')
            logging.info(e)
            return False
        finally:
            self.router_control.driver.quit()

# fields = ['serial', 'band', 'ssid', 'wireless_mode', 'channel', 'bandwidth', 'security_mode',
#           'wpa_passwd', 'test_type', 'wep_encrypt', 'passwd_index', 'wep_passwd',
#           'protect_frame', 'wpa_encrypt', 'hide_ssid']
# Router = namedtuple('Router', fields, defaults=[None, ] * len(fields))
# router = Router(serial='1', band='2.4G', ssid='Linksys1200ac_2.4G', wireless_mode='混合模式',
#                 channel='1', bandwidth='仅使用20 MHz', authentication='无',)
#                 # wep_encrypt='104/128位（26个十六进制数字）',
#                 # wep_passwd='01234567890123456789012345')
# control = Linksys1200acControl()
# control.change_setting(router)
# control.reboot_router()
