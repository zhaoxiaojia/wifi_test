"""
Tplink ax6000 control

This module is part of the AsusRouter package.
"""

import logging
import re
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from src.tools.router_tool.RouterControl import RouterTools, ConfigError
from src.tools.router_tool.Tplink.TplinkConfig import TplinkAx6000Config


class TplinkAx6000Control:
    """
        Tplink ax6000 control
            Parameters
            ----------
            None
                This class is instantiated without additional parameters.
            Returns
            -------
            None
                Classes return instances implicitly when constructed.
    """
    BAND_2 = '2.4G'
    BAND_5 = '5G'

    def __init__(self):
        """
            Init
                Parameters
                ----------
                None
                    This function does not accept any parameters beyond the implicit context.
                Returns
                -------
                None
                    This function does not return a value.
        """
        self.router_control = RouterTools('tplink_ax6000', display=True)

        self.type = 'ax6000'

    def login(self):

        """
            Login
                Interacts with the router's web interface using Selenium WebDriver.
                Waits for specific web elements to satisfy conditions using WebDriverWait.
                Pauses execution for a specified duration to allow operations to complete.
                Parameters
                ----------
                None
                    This function does not accept any parameters beyond the implicit context.
                Returns
                -------
                None
                    This function does not return a value.
        """
        self.router_control.driver.get(f"http://{self.router_control.address}")

        self.router_control.driver.find_element(By.ID, self.router_control.xpath['password_element'][self.type]).click()
        self.router_control.driver.find_element(By.ID,
                                                self.router_control.xpath['password_element'][self.type]).send_keys(
            self.router_control.xpath['passwd'])

        self.router_control.driver.find_element(By.XPATH,
                                                self.router_control.xpath['signin_element'][self.type]).click()

        WebDriverWait(driver=self.router_control.driver, timeout=10, poll_frequency=0.5).until(
            EC.presence_of_element_located((By.ID, self.router_control.xpath['signin_done_element'])))

        time.sleep(1)

    def change_setting(self, router):

        """
            Change setting
                Interacts with the router's web interface using Selenium WebDriver.
                Waits for specific web elements to satisfy conditions using WebDriverWait.
                Performs router login or authentication before executing actions.
                Pauses execution for a specified duration to allow operations to complete.
                Logs informational or debugging messages for tracing execution.
                Parameters
                ----------
                router : object
                    Router control object or router information required to perform operations.
                Returns
                -------
                object
                    Description of the returned value.
        """

        def confirm():
            """
                Confirm
                    Interacts with the router's web interface using Selenium WebDriver.
                    Parameters
                    ----------
                    None
                        This function does not accept any parameters beyond the implicit context.
                    Returns
                    -------
                    None
                        This function does not return a value.
            """
            try:
                self.router_control.driver.find_element(By.ID, 'Confirm').find_element(By.ID, "hsConf") \
                    .find_element(By.CSS_SELECTOR, '#hsConf > input.subBtn.ok').click()
            except Exception as e:
                ...

        logging.info('Try to set router')
        try:
            self.login()
            WebDriverWait(driver=self.router_control.driver, timeout=5, poll_frequency=0.5).until(
                EC.presence_of_element_located((By.ID, 'netStateLCon')))

            if router.band not in TplinkAx6000Config.BAND_LIST:
                raise ConfigError('band key error')

            self.router_control.driver.find_element(By.ID, 'routerSetMbtn').click()
            self.router_control.driver.find_element(By.ID, 'wireless2G_rsMenu').click()

            if '5' in router.band:
                select_element = self.router_control.driver.find_element(
                    By.XPATH, '//*[@id="hcCo"]/div[6]/label')
                self.router_control.scroll_to(select_element)

            if (router.ssid):

                if '2' in router.band:
                    ssid_input = self.router_control.driver.find_element(
                        By.ID, self.router_control.xpath['ssid_element_2g'][self.type])
                    ssid_input.click()
                    time.sleep(1)
                    ssid_input.clear()
                    ssid_input.clear()
                    ssid_input.send_keys(router.ssid)
                else:
                    ssid_input = self.router_control.driver.find_element(
                        By.ID, self.router_control.xpath['ssid_element_5g'])
                    ssid_input.click()
                    time.sleep(1)
                    ssid_input.clear()
                    ssid_input.clear()
                    ssid_input.send_keys(router.ssid)

            if '2' in router.band:
                select = self.router_control.driver.find_element(By.ID, 'ssidBrd')
            else:
                select = self.router_control.driver.find_element(By.ID, 'ssidBrd5g')

            if (router.hide_ssid):
                if (router.hide_ssid == '是') and select.is_selected():
                    select.click()
                if (router.hide_ssid == '否') and not select.is_selected():
                    select.click()
            else:
                if not select.is_selected():
                    select.click()

            if (router.wpa_passwd):
                if '2' in router.band:
                    target_element = 'passwd_2g'
                else:
                    target_element = 'passwd_5g'
                self.router_control.driver.find_element(
                    By.ID, self.router_control.xpath['wpa_passwd'][target_element]).click()
                self.router_control.driver.find_element(
                    By.ID, self.router_control.xpath['wpa_passwd'][target_element]).clear()
                self.router_control.driver.find_element(
                    By.ID, self.router_control.xpath['wpa_passwd'][target_element]).send_keys(router.wpa_passwd)

            time.sleep(2)
            if (router.security_mode):
                try:
                    index = TplinkAx6000Config.AUTHENTICATION_METHOD_DICT[router.security_mode]
                except ConfigError:
                    raise ConfigError('security protocol method key error')

                if '2' in router.band:
                    target_element = 'authtication_2g'
                else:
                    target_element = 'authtication_5g'
                wait_for = self.router_control.driver.find_element(
                    By.XPATH, self.router_control.xpath['authentication_select_element'][target_element])
                self.router_control.scroll_to(wait_for)
                wait_for.click()
                self.router_control.driver.find_element(
                    By.XPATH, self.router_control.xpath['authentication_regu_element'][
                        target_element].format(index)).click()

            if (router.channel):
                channel = str(router.channel)
                try:
                    channel_index = {self.BAND_2: TplinkAx6000Config.CHANNEL_2_DICT,
                                     self.BAND_5: TplinkAx6000Config.CHANNEL_5_DICT}[router.band][channel]
                except Exception:
                    raise ConfigError('channel key error')
                if router.band == self.BAND_2:
                    select_list = self.router_control.driver.find_element(
                        By.XPATH, self.router_control.xpath['channel_select_element'][self.type]['channel_2g'])
                    self.router_control.scroll_to(select_list)
                    select_list.click()
                    select_element = self.router_control.driver.find_element(
                        By.XPATH, self.router_control.xpath['channel_regu_element']['channel_2g'].format(
                            channel_index))
                    self.router_control.scroll_to(select_element)
                    select_element.click()
                else:
                    select_list = self.router_control.driver.find_element(
                        By.XPATH, self.router_control.xpath['channel_select_element'][self.type]['channel_5g'])
                    self.router_control.scroll_to(select_list)
                    select_list.click()
                    select_element = self.router_control.driver.find_element(
                        By.XPATH, self.router_control.xpath['channel_regu_element']['channel_5g'].format(
                            channel_index))
                    self.router_control.scroll_to(select_element)
                    select_element.click()

            if (router.wireless_mode):
                if '2' in router.band:
                    target_dict = TplinkAx6000Config.WIRELESS_MODE_2G_DICT
                    target_element = 'mode_2g'
                else:
                    target_dict = TplinkAx6000Config.WIRELESS_MODE_5G_DICT
                    target_element = 'mode_5g'
                if router.wireless_mode not in target_dict: raise ConfigError(
                    'wireless mode key error')
                index = target_dict[router.wireless_mode]
                wait_for = self.router_control.driver.find_element(
                    By.XPATH, self.router_control.xpath['wireless_mode_select_element'][self.type][target_element])
                self.router_control.scroll_to(wait_for)
                wait_for.click()
                self.router_control.driver.find_element(
                    By.XPATH,
                    self.router_control.xpath['wireless_mode_element'][self.type][target_element].format(index)).click()

            try:
                if (router.bandwidth):
                    if '2' in router.band:
                        target_dict = TplinkAx6000Config.BANDWIDTH_2_DICT
                        target_element = 'bandwidth_2g'
                    else:
                        target_dict = TplinkAx6000Config.BANDWIDTH_5_DICT
                        target_element = 'bandwidth_5g'
                    if router.bandwidth not in target_dict: raise ConfigError('bandwidth element error')
                    index = target_dict[router.bandwidth]
                    self.router_control.driver.find_element(
                        By.XPATH, self.router_control.xpath['bandwidth_select_element'][target_element]).click()
                    select_xpath = self.router_control.xpath['bandwidth_element'][self.type][target_element]

                    select_list = self.router_control.driver.find_element(By.XPATH, select_xpath[:-7])
                    if select_list.text:
                        lis = select_list.find_elements(By.TAG_NAME, 'li')
                        index = [i.get_attribute('title') for i in lis].index(router.bandwidth) + 1
                        logging.debug("%s", router.bandwidth)
                        logging.debug("%s", index)
                        wair_for = self.router_control.driver.find_element(
                            By.XPATH, select_xpath.format(index))
                        self.router_control.scroll_to(wait_for)
                        wair_for.click()
            except NotImplementedError:
                logging.info('Select element is disabled !!')

            time.sleep(5)

            if '2' in router.band:
                apply_element = 'apply_2g'
            else:
                apply_element = 'apply_5g'

            wait_for = self.router_control.driver.find_element(
                By.ID, self.router_control.xpath['apply_element'][self.type][apply_element])
            self.router_control.scroll_to(wait_for)
            wait_for.click()

            if re.findall(r'52|56|64|60', router.channel):
                confirm()
            if '5' in router.band and '20MHz' == router.bandwidth:
                confirm()
            try:
                WebDriverWait(self.router_control.driver, 30).until_not(
                    EC.visibility_of_element_located(
                        (By.ID, self.router_control.xpath['apply_element'][apply_element])))
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











