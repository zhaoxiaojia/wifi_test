"""
Asusax86u control

This module is part of the AsusRouter package.
"""

import logging
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from src.tools.router_tool.RouterControl import ConfigError
from src.tools.router_tool.AsusRouter.AsusBaseControl import AsusBaseControl


class Asusax86uControl(AsusBaseControl):
    """
        Asusax86u control
            Parameters
            ----------
            None
                This class is instantiated without additional parameters.
            Returns
            -------
            None
                Classes return instances implicitly when constructed.
    """

    def __init__(self, address: str | None = None):
        """
            Init
                Parameters
                ----------
                address : object
                    The router's login address or IP address; if None, a default is used.
                Returns
                -------
                None
                    This function does not return a value.
        """
        super().__init__('asus_86u', display=True, address=address)

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
        logging.info(f'Try to set router {router}')
        self.login()
        self.driver.find_element(By.ID, 'Advanced_Wireless_Content_menu').click()

        WebDriverWait(driver=self.driver, timeout=5, poll_frequency=0.5).until(
            EC.presence_of_element_located((By.ID, 'FormTitle')))

        if router.band:
            band = self.BAND_MAP[router.band]
            self.change_band(band)

        if router.wireless_mode:
            self.change_wireless_mode(router.wireless_mode)

        if (router.ssid):
            self.change_ssid(router.ssid)

        if (router.hide_ssid):
            if (router.hide_ssid) == '是':
                self.driver.find_element(By.XPATH, ".//input[@type='radio' and @value='1']").click()
            elif (router.hide_ssid) == '否':
                self.driver.find_element(By.XPATH, ".//input[@type='radio' and @value='0']").click()
        else:
            self.driver.find_element(By.XPATH, ".//input[@type='radio' and @value='0']").click()

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

        if router.security_mode:
            self.change_authentication(router.security_mode)

        if (router.wep_encrypt):
            self.change_wep_encrypt(router.wep_encrypt)

        if (router.wpa_encrypt):
            self.change_wpa_encrypt(router.wpa_encrypt)

        if (router.passwd_index):
            self.change_passwd_index(router.passwd_index)

        if router.password:
            self.change_passwd(router.password)

        if (router.protect_frame):
            if router.protect_frame not in self.PROTECT_FRAME: raise ConfigError(
                'protect frame element error')
            self.change_protect_frame(self.PROTECT_FRAME[router.protect_frame])

        time.sleep(5)

        self.driver.find_element(By.ID, 'applyButton').click()
        self.handle_alert_or_popup()
        self.handle_alert_or_popup()
        self.handle_alert_or_popup()
        try:
            WebDriverWait(self.driver, 20).until(

                EC.visibility_of_element_located((By.ID, 'applyButton'))
            )
        except Exception as e:
            ...
        time.sleep(2)
        logging.info('Router setting done')
        self.driver.quit()
        return True
















