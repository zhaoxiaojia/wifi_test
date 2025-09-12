#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2022/12/14 10:00
# @Author  : chao.li
# @Site    :
# @File    : TplinkWr842Control.py
# @Software: PyCharm



import logging
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from src.tools.router_tool.RouterControl import RouterTools,ConfigError
from src.tools.router_tool.Tplink.TplinkConfig import TplinkWr842Config


class TplinkWr842Control:
    BAND_2 = '2.4G'
    BAND_5 = '5G'

    def __init__(self):
        self.router_control = RouterTools('tplink_wr842', display=True)
        self.type = 'wr842'
        # self.router_control.driver.maximize_window()

    def login(self):
        # click login
        # try:
        self.router_control.driver.get(f"http://{self.router_control.address}")
        self.router_control.driver.find_element(
            By.ID, self.router_control.xpath['password_element'][self.type]).click()
        self.router_control.driver.find_element(
            By.ID, self.router_control.xpath['password_element'][self.type]).send_keys(
            self.router_control.xpath['passwd'])
        # click login
        self.router_control.driver.find_element(
            By.ID, self.router_control.xpath['signin_element'][self.type]).click()
        # wait for login in done
        WebDriverWait(driver=self.router_control.driver, timeout=10, poll_frequency=0.5).until(
            EC.presence_of_element_located((By.XPATH, '/html/frameset')))
        # except NoSuchElementException as e:
        #     ...
        time.sleep(1)


    def change_setting(self, router):
        '''
        set up wifi envrioment
        @param router: Router instance
        @return: status : boolean
        '''

        if router.band == self.BAND_5:
            self.router_control.driver.quit()
            raise ValueError("Not support 5g")

        if router.band not in TplinkWr842Config.BAND_LIST:
            raise ConfigError('band key error')

        logging.info('Try to set router')

        try:
            self.login()
            frame_sidebar = self.router_control.driver.find_element(
                By.CSS_SELECTOR, "html > frameset > frameset:nth-child(2) > frame:nth-child(1)")
            self.router_control.driver.switch_to.frame(frame_sidebar)
            self.router_control.driver.find_element(By.ID, 'a8').click()

            self.router_control.driver.switch_to.parent_frame()
            frame_content = self.router_control.driver.find_element(
                By.CSS_SELECTOR, "html > frameset > frameset:nth-child(2) > frame:nth-child(3)")
            self.router_control.driver.switch_to.frame(frame_content)

            # 修改 ssid
            if (router.ssid):
                ssid_input = self.router_control.driver.find_element(
                    By.CSS_SELECTOR, self.router_control.xpath['ssid_element_2g'][self.type])
                ssid_input.click()
                ssid_input.clear()
                ssid_input.send_keys(router.ssid)

            # 修改 channel
            if (router.channel):
                channel = str(router.channel)
                if router.channel not in TplinkWr842Config.CHANNEL_2_DICT:
                    raise ConfigError('channel key error')
                index = TplinkWr842Config.CHANNEL_2_DICT[router.channel]
                # /html/body/center/form/table/tbody/tr[2]/td/table/tbody/tr[1]/td[2]/table[2]/tbody/tr[1]/td/table/tbody/tr[3]/td[2]/select/option[1]
                self.router_control.driver.find_element(
                    By.XPATH, self.router_control.xpath['channel_select_element'][self.type].format(index)).click()

            # 修改 wireless_mode
            if (router.wireless_mode):

                if router.wireless_mode not in TplinkWr842Config.WIRELESS_MODE_2G_DICT: raise ConfigError(
                    'wireless mode key error')
                index = TplinkWr842Config.WIRELESS_MODE_2G_DICT[router.wireless_mode]
                self.router_control.driver.find_element(
                    By.XPATH, self.router_control.xpath['wireless_mode_element'][self.type].format(index)).click()

            # 修改 bandwidth
            try:
                if (router.bandwidth):
                    if router.bandwidth not in TplinkWr842Config.BANDWIDTH_2_DICT:
                        raise ConfigError('bandwidth element error')
                    select_xpath = self.router_control.xpath['bandwidth_element'][self.type]

                    select_list = self.router_control.driver.find_element(
                        By.XPATH,
                        '/html/body/center/form/table/tbody/tr[2]/td/table/tbody/tr[1]/td[2]/table[2]/tbody/tr[1]/td/table/tbody/tr[5]/td[2]/select')
                    if select_list.text:
                        lis = select_list.find_elements(By.TAG_NAME, 'option')
                        index = [i.text for i in lis].index(router.bandwidth) + 1
                        logging.debug("%s", router.bandwidth)
                        logging.debug("%s", index)
                        self.router_control.driver.find_element(
                            By.XPATH, select_xpath.format(index)).click()
            except NotImplementedError:
                logging.info('Select element is disabled !!')

            # 修改 ssid 是否隐藏
            select = self.router_control.driver.find_element(
                By.XPATH,
                '/html/body/center/form/table/tbody/tr[2]/td/table/tbody/tr[1]/td[2]/table[2]/tbody/tr[1]/td/table/tbody/tr[7]/td[2]/input')

            if (router.hide_ssid):
                if (router.hide_ssid == '是') and select.is_selected():
                    select.click()
                if (router.hide_ssid == '否') and not select.is_selected():
                    select.click()
            else:
                if not select.is_selected():
                    select.click()

            # 点击apply

            apply = self.router_control.driver.find_element(
                By.ID, self.router_control.xpath['apply_element'][self.type])
            apply.click()
            if router.wireless_mode == '11n only':
                try:
                    self.router_control.driver.switch_to.alert.accept()
                except Exception as e:
                    ...
            time.sleep(1)

            self.router_control.driver.switch_to.parent_frame()
            time.sleep(1)
            self.router_control.driver.switch_to.frame(frame_sidebar)
            time.sleep(1)
            self.router_control.driver.find_element(By.ID, 'a10').click()
            self.router_control.driver.switch_to.parent_frame()
            time.sleep(1)
            self.router_control.driver.switch_to.frame(frame_content)
            time.sleep(1)
            wait_for = self.router_control.driver.find_element(By.ID, "help")
            target_element = ''
            if (router.security_mode):
                if router.security_mode not in TplinkWr842Config.AUTHENTICATION_METHOD_LIST:
                    raise ConfigError('security protocol method key error')

                if router.security_mode in 'WPA/WPA2':
                    target_element = 'WPA/WPA2'
                elif router.security_mode in 'WPA-PSK/WPA2-PSK':
                    target_element = 'WPA-PSK/WPA2-PSK'
                elif router.security_mode == 'OPEN':
                    target_element = 'NONE'
                else:
                    target_element = 'WEP'
                    self.router_control.scroll_to(wait_for)

                self.router_control.driver.find_element(
                    By.XPATH, self.router_control.xpath['wr842_authentication_element'][target_element]).click()
                if target_element != 'NONE':
                    if router.security_mode == 'WPA/WPA2' or router.security_mode == 'WPA-PSK/WPA2-PSK':
                        security_mode = '自动'
                    else:
                        security_mode = router.security_mode
                    target_dict = {
                        'WPA/WPA2': TplinkWr842Config.WPA_DICT,
                        'WPA-PSK/WPA2-PSK': TplinkWr842Config.PSK_DICT,
                        'WEP': TplinkWr842Config.WEP_DICT
                    }
                    index = target_dict[target_element][security_mode]
                    # /html/body/center/form/table/tbody/tr[2]/td/table/tbody/tr[1]/td[2]/table[8]/tbody/tr[2]/td[2]/select/option[1]
                    self.router_control.driver.find_element(
                        By.XPATH,
                        self.router_control.xpath['wr842_authentication_select_element'][target_element].format(
                            index)).click()
                    # self.router_control.driver.find_element(
                    #     By.XPATH, self.router_control.xpath['authentication_regu_element'][
                    #         target_element].format(index)).click()

            # 修改wpa加密方式
            if router.wpa_encrypt:
                index = TplinkWr842Config.WPA_ENCRYPT[router.wpa_encrypt]
                logging.debug(
                    self.router_control.xpath['wr842_authentication_encrypt_element'][target_element].format(
                        index
                    )
                )
                self.router_control.driver.find_element(
                    By.XPATH,
                    self.router_control.xpath['wr842_authentication_encrypt_element'][target_element].format(
                        index
                    )
                ).click()

            # 修改wpa密码
            if (router.wpa_passwd):
                self.router_control.driver.find_element(
                    By.ID, self.router_control.xpath['wr842_passwd_element'][target_element]).clear()
                self.router_control.driver.find_element(
                    By.ID, self.router_control.xpath['wr842_passwd_element'][target_element]).send_keys(
                    router.wpa_passwd)

            if router.wep_encrypt:
                index = TplinkWr842Config.WEP_ENCRUPT[router.wep_encrypt]
                self.router_control.driver.find_element(
                    By.XPATH,
                    self.router_control.xpath['wr842_authentication_encrypt_element']['WEP'].format(index)).click()

            if router.wep_passwd:
                if router.wep_passwd not in ['12345678901234567890123456', '12345', '1234567890', '1234567890123']:
                    raise ConfigError("passwd should be 12345|1234567890|12345678901234567890123456")
                # /html/body/center/form/table/tbody/tr[2]/td/table/tbody/tr[1]/td[2]/table[8]/tbody/tr[5]/td[3]/select/option[2]
                # /html/body/center/form/table/tbody/tr[2]/td/table/tbody/tr[1]/td[2]/table[8]/tbody/tr[5]/td[3]/select/option[3]
                if router.wep_passwd in ['12345', '1234567890']:
                    index = '2'
                if router.wep_passwd in ['1234567890123', '12345678901234567890123456']:
                    index = '3'
                self.router_control.driver.find_element(
                    By.XPATH,
                    '/html/body/center/form/table/tbody/tr[2]/td/table/tbody/tr[1]/td[2]/table[8]/tbody/tr[5]/td[3]/select/option[{}]'.format(
                        index)
                ).click()
                self.router_control.driver.find_element(
                    By.ID, self.router_control.xpath['wr842_passwd_element']['WEP']).click()
                self.router_control.driver.find_element(
                    By.ID, self.router_control.xpath['wr842_passwd_element']['WEP']).clear()
                self.router_control.driver.find_element(
                    By.ID, self.router_control.xpath['wr842_passwd_element']['WEP']).send_keys(router.wep_passwd)

            time.sleep(1)

            self.router_control.scroll_to(wait_for)
            self.router_control.driver.find_element(By.ID,
                                                    self.router_control.xpath['apply_element'][self.type]).click()
            try:
                WebDriverWait(self.router_control.driver, 30).until(
                    EC.visibility_of_element_located(
                        (By.ID, self.router_control.xpath['apply_element'][self.type])))
            except Exception:
                ...

            time.sleep(2)
            logging.info('Router setting done')
            return True
        except Exception as e:
            logging.info('Router change setting with error')
            logging.info(e)
            return False
        finally:
            self.router_control.driver.quit()


# fields = ['band', 'ssid', 'wireless_mode', 'channel', 'bandwidth', 'security_mode',
#           'wpa_passwd', 'test_type', 'wep_encrypt', 'passwd_index', 'wep_passwd', 'protect_frame',
#           'wpa_encrypt', 'hide_ssid']
# Router = namedtuple('Router', fields, defaults=[None, ] * len(fields))
# router = Router(band='2.4G', ssid='Tplinkwr842_2.4G#$', wireless_mode='11bgn mixed', channel='12',
#                 bandwidth='40MHz', authentication='共享秘钥', wep_encrypt='ASCII码', wep_passwd='1234567890123')
# control = TplinkWr842Control()
# control.change_setting(router)
# control.reboot_router()
