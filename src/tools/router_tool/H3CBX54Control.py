#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2022/10/26 08:12
# @Author  : chao.li
# @Site    :
# @File    : H3CBX54Control.py
# @Software: PyCharm


import logging
import time

from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from src.tools.router_tool.H3CBX54Config import H3CRouterConfig
from src.tools.router_tool.RouterControl import ConfigError,RouterTools


class H3CBX54Control():
    '''
    H3c bx54 router

    Attributes:
    '''

    def __init__(self):
        self.router_control = RouterTools('h3c_bx54',display=True)

    def login(self):
        # click login
        try:
            self.router_control.driver.get(f"http://{self.router_control.address}")
            self.router_control.driver.find_element(By.ID, self.router_control.xpath['signin_element']).click()
            # input passwd
            self.router_control.driver.find_element(By.ID, self.router_control.xpath['password_element']).click()
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
            self.router_control.driver.find_element(By.ID, 'wanzheng_img').click()
            # Wireless - Profession
            self.router_control.driver.switch_to.frame('contents')
            WebDriverWait(driver=self.router_control.driver, timeout=5, poll_frequency=0.5).until(
                EC.presence_of_element_located((By.ID, 'gotomobile')))

            self.router_control.driver.find_element(By.ID, 'wlan_menu2').click()
            self.router_control.driver.switch_to.default_content()

            # 修改 band
            if (router.band):
                if router.band not in H3CRouterConfig.BAND_LIST: raise ConfigError('band element error')
                self.router_control.driver.switch_to.frame('banner')
                time.sleep(1)
                if '2' in router.band:
                    self.router_control.driver.find_element(By.XPATH,
                                                            '//*[@id="tabctrl"]/table/tbody/tr/td[1]/a').click()
                else:
                    self.router_control.driver.find_element(By.XPATH,
                                                            '//*[@id="tabctrl"]/table/tbody/tr/td[2]/a').click()

            self.router_control.driver.switch_to.default_content()
            self.router_control.driver.switch_to.frame('main_screen')

            if (router.channel):
                channel = str(router.channel)
                # try:
                #     if router.band == '2.4G':
                #         channel_index = H3CRouterConfig.CHANNEL_2_DICT[channel]
                #     else:
                #         channel_index = H3CRouterConfig.CHANNEL_5_DICT[channel]
                # except KeyError:
                #     raise ConfigError('channel element error')
                # //*[@id="WLgeneral"]/tbody/tr[11]/td/select/option[22]
                self.router_control.change_channel(channel)
                self.router_control.driver.find_element(By.ID, 'op_confirm').click()
                try:
                    self.router_control.click_alert()
                except Exception:
                    ...
            # 修改 wireless_mode
            if (router.wireless_mode):
                target_dict = H3CRouterConfig.WIRELESS_MODE_2G_DICT if '2' in router.band else H3CRouterConfig.WIRELESS_MODE_5G_DICT
                if router.wireless_mode not in target_dict: raise ConfigError(
                    'wireless mode element error')
                self.router_control.change_wireless_mode(router.wireless_mode)
                self.router_control.driver.find_element(By.ID, 'op_confirm_two').click()

            # 修改 bandwidth
            try:
                if (router.bandwidth):
                    if router.bandwidth not in \
                            {'2.4G': H3CRouterConfig.BANDWIDTH_2_LIST, '5G': H3CRouterConfig.BANDWIDTH_5_LIST}[
                                router.band]: raise ConfigError('bandwidth element error')
                    self.router_control.change_bandwidth(router.bandwidth)
            except NotImplementedError:
                logging.info('Select element is disabled !!')

            # /html/body/form/table/tbody/tr/td/div/div/table/tbody/tr[2]/td[1]/img
            # //*[@id="edit"]
            self.router_control.driver.switch_to.default_content()
            self.router_control.driver.switch_to.frame('main_screen')
            self.router_control.driver.switch_to.frame('wlan_ap_list')
            self.router_control.driver.find_element(By.XPATH, '//*[@id="edit"]').click()

            # 修改 ssid
            if (router.ssid):
                self.router_control.driver.switch_to.default_content()
                self.router_control.driver.switch_to.frame('main_screen')
                if '2' in router.band:
                    self.router_control.driver.find_element(
                        By.XPATH, '//*[@id="SSID_NAME_LINE"]/td[3]/input').clear()
                    self.router_control.driver.find_element(
                        By.XPATH, '//*[@id="SSID_NAME_LINE"]/td[3]/input').send_keys(
                        router.ssid)
                else:
                    self.router_control.driver.find_element(By.XPATH, '//*[@id="ssid_name"] ').clear()
                    self.router_control.driver.find_element(By.XPATH, '//*[@id="ssid_name"] ').send_keys(router.ssid)
            # 修改 ssid 是否隐藏
            if '2' in router.band:
                target_element = '//*[@id="SSID_BROAD_LINE"]/td[3]/select'
            else:
                target_element = '//*[@id="ssid_broad"]'
            if (router.hide_ssid):
                if (router.hide_ssid) == '是':
                    self.router_control.driver.find_element(
                        By.XPATH, target_element + '/option[1]').click()
                elif (router.hide_ssid) == '否':
                    self.router_control.driver.find_element(
                        By.XPATH, target_element + '/option[2]').click()
            else:
                self.router_control.driver.find_element(
                    By.XPATH, target_element + '/option[1]').click()

            # 修改 authentication
            # //*[@id="WLgeneral"]/tbody/tr[13]/td/div[1]/select/option[1]
            # //*[@id="WLgeneral"]/tbody/tr[13]/td/div[1]/select/option[5]
            #
            if (router.authentication):
                try:
                    index = H3CRouterConfig.AUTHENTICATION_METHOD_DICT[router.authentication]
                except ConfigError:
                    raise ConfigError('authentication method element error')
                # //*[@id="ssid_enc"]/option[1]
                self.router_control.change_authentication(index)

            # 修改密码
            if (router.wpa_passwd):
                self.router_control.driver.find_element(By.ID, self.router_control.xpath['wep_passwd_element']).clear()
                self.router_control.driver.find_element(By.ID, self.router_control.xpath['wep_passwd_element']). \
                    send_keys(router.wpa_passwd)

            self.router_control.driver.find_element(By.ID, 'amend').click()

            time.sleep(5)
            # 点击apply
            # self.router_control.driver.find_element(By.ID, 'amend').click()
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
            return False
        finally:
            self.router_control.driver.quit()


# fields = ['serial', 'band', 'ssid', 'wireless_mode', 'channel', 'bandwidth',
#           'authentication', 'wpa_passwd', 'test_type', 'wep_encrypt',
#           'passwd_index', 'wep_passwd', 'protect_frame', 'wpa_encrypt', 'hide_ssid']
# Router = namedtuple('Router', fields, defaults=[None, ] * len(fields))
# router = Router(serial='1', band='2.4G', ssid='H3CBX54_2.4G', wireless_mode='b+g+n', channel='8', bandwidth='20M',
#                 authentication='不加密', hide_ssid="否")
# control = H3CBX54Control()
# control.change_setting(router)
# control.reboot_router()
