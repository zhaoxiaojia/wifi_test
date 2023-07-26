

import logging
import time
from collections import namedtuple

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from tools.RouterControl import ConfigError,RouterTools
from tools.RouterConfig import RouterConfig


class ZTEax5400Config(RouterConfig):
    def __init__(self):
        super(ZTEax5400Config, self).__init__()

    CHANNEL_2_DICT = {
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

    CHANNEL_5_DICT = {
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
        '165': '14',
    }

    WIRELESS_MODE_2G_DICT = {
        '802.11 b/g/n': '1',
        '802.11 b/g/n/ax.11b/g/n': '2'
    }

    WIRELESS_MODE_5G_DICT = {
        '802.11 a/n/ac': '1',
        '802.11 a/n/ac/ax.11ac': '2'
    }

    BANDWIDTH_2_DICT = {'20MHz': '1', '40MHz': '2', '20MHz/40MHz': '3'}

    BANDWIDTH_5_DICT = {'20MHz': '1', '20MHz/40MHz': '2', '20MHz/40MHz/80MHz': '3', '20MHz/40MHz/80MHz/160MHz': '4'}

    AUTHENTICATION_METHOD_DICT = {
        'OPEN': '1',
        'WPA2(AES)-PSK': '2',
        'WPA-PSK/WPA2-PSK': '3',
        'WPA2-PSK/WPA3-PSK': '4',
    }


class ZTEax5400Control():
    '''
    H3c bx54 router

    Attributes:
    '''

    def __init__(self):
        self.router_control = RouterTools('zte_ax5400',display=True)

    def login(self):

        # click login
        try:
            self.router_control.driver.get(self.router_control.address)
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
            self.router_control.driver.find_element(By.ID, "h_wifi_setting_btn").click()
            # Wireless - Profession
            WebDriverWait(driver=self.router_control.driver, timeout=5, poll_frequency=0.5).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="innerContainer"]/div[2]/div[2]/div/div[1]/a/img')))

            # 修改 ssid
            if (router.ssid):
                if '2' in router.band:
                    self.router_control.driver.find_element(
                        By.ID, self.router_control.xpath['ssid_element_2g']).clear()
                    self.router_control.driver.find_element(
                        By.ID, self.router_control.xpath['ssid_element_2g']).send_keys(router.ssid)
                else:
                    self.router_control.driver.find_element(
                        By.ID, self.router_control.xpath['ssid_element_5g']).clear()
                    self.router_control.driver.find_element(
                        By.ID, self.router_control.xpath['ssid_element_5g']).send_keys(router.ssid)
            # 修改 ssid 是否隐藏
            if '2' in router.band:
                select = self.router_control.driver.find_element(By.CSS_SELECTOR, '#broadcastCheckbox')
                element = self.router_control.driver.find_element(
                    By.CSS_SELECTOR, '#frmSSID1_24G5G > div.content > div > div:nth-child(2) > div > p')
            else:
                select = self.router_control.driver.find_element(By.ID, 'broadcastCheckbox_5G')
                element = self.router_control.driver.find_element(
                    By.CSS_SELECTOR, '#ssid1_5G_div > div > div:nth-child(2) > div > p')

            if (router.hide_ssid):
                if (router.hide_ssid == '是') and select.get_attribute('checked')=='true':
                    element.click()
                if (router.hide_ssid == '否') and not select.get_attribute('checked'):
                    element.click()
            else:
                if not select.get_attribute('checked'):
                    element.click()

            # 修改 authentication_method
            if (router.authentication_method):
                try:
                    index = ZTEax5400Config.AUTHENTICATION_METHOD_DICT[router.authentication_method]
                except ConfigError:
                    raise ConfigError('authentication method element error')
                # //*[@id="ssid_enc"]/option[1]
                if '2' in router.band:
                    target_element = 'authtication_2g'
                else:
                    target_element = 'authtication_5g'
                self.router_control.driver.find_element(
                    By.XPATH,
                    self.router_control.xpath['authentication_method_regu_element'][target_element].format(
                        index)).click()

            # 修改密码
            if (router.wpa_passwd):
                if '2' in router.band:
                    target_element = 'passwd_2g'
                else:
                    target_element = 'passwd_5g'
                self.router_control.driver.find_element(
                    By.XPATH, self.router_control.xpath['wep_passwd'][target_element]).clear()
                self.router_control.driver.find_element(
                    By.XPATH, self.router_control.xpath['wep_passwd'][target_element]).send_keys(router.wpa_passwd)

            self.router_control.driver.find_element(By.ID, "ssid1_apply_5G").click()
            self.router_control.driver.find_element(By.ID, "yesbtn").click()

            WebDriverWait(self.router_control.driver, 30).until_not(
                EC.visibility_of_element_located((By.ID, 'loadingImg')))
            time.sleep(3)

            self.router_control.driver.find_element(By.XPATH, '//*[@id="wifiNav"]/li[5]/a').click()

            # 修改 channel
            if (router.channel):
                channel = str(router.channel)
                try:
                    if router.band == '2.4 GHz':
                        channel_index = ZTEax5400Config.CHANNEL_2_DICT[channel]
                        self.router_control.driver.find_element(
                            By.XPATH,
                            self.router_control.xpath['channel_regu_element']['channel_2g'].format(
                                channel_index)).click()
                    else:
                        channel_index = ZTEax5400Config.CHANNEL_5_DICT[channel]
                        self.router_control.driver.find_element(
                            By.XPATH,
                            self.router_control.xpath['channel_regu_element']['channel_5g'].format(
                                channel_index)).click()
                except KeyError:
                    raise ConfigError('channel element error')
                try:
                    self.router_control.driver.find_element(By.ID,'okbtn').click()
                except Exception:
                    ...

            # 修改 wireless_mode
            if (router.wireless_mode):
                if '2' in router.band:
                    target_dict = ZTEax5400Config.WIRELESS_MODE_2G_DICT
                    target_element = 'mode_2g'
                else:
                    target_dict = ZTEax5400Config.WIRELESS_MODE_5G_DICT
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
                        target_dict = ZTEax5400Config.BANDWIDTH_2_DICT
                        target_element = 'bandwidth_2g'
                    else:
                        target_dict = ZTEax5400Config.BANDWIDTH_5_DICT
                        target_element = 'bandwidth_5g'
                    if router.bandwidth not in target_dict: raise ConfigError('bandwidth element error')
                    index = target_dict[router.bandwidth]
                    self.router_control.driver.find_element(
                        By.XPATH, self.router_control.xpath['bandwidth_element'][target_element].format(index)).click()
            except NotImplementedError:
                logging.info('Select element is disabled !!')

            time.sleep(5)
            # 点击apply
            self.router_control.driver.find_element(By.XPATH,
                                                    '//*[@id="wifi_advance_form_24g_5g"]/div[9]/div[8]/input').click()
            self.router_control.driver.find_element(By.ID, "yesbtn").click()

            WebDriverWait(self.router_control.driver, 30).until_not(
                EC.visibility_of_element_located((By.ID, 'loadingImg')))
            time.sleep(3)

            logging.info('Router setting done')
            return True
        except Exception as e:
            logging.info('Router change setting with error')
            logging.info(e)
            return False
        finally:
            self.router_control.driver.quit()

# fields = ['band', 'ssid', 'wireless_mode', 'channel', 'bandwidth', 'authentication_method',
#           'wpa_passwd', 'test_type', 'wep_encrypt', 'passwd_index', 'wep_passwd',
#           'protect_frame', 'wpa_encrypt', 'hide_ssid']
# Router = namedtuple('Router', fields, defaults=[None, ] * len(fields))
# router_zte = Router(band='5 GHz', ssid='ZTEax5400_5G', wireless_mode='802.11 a/n/ac', channel='161', bandwidth='20MHz/40MHz/80MHz',
#                    authentication_method='WPA-PSK/WPA2-PSK', wpa_passwd='12345678')
# control = ZTEax5400Control()
# control.change_setting(router_zte)
# control.reboot_router()
