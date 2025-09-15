from src.tools.router_tool.RouterControl import RouterTools, ConfigError
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait


class AsusBaseControl(RouterTools):
    """华硕路由器通用控制基类

    提供标准字段到设备实际取值的映射，以减少各型号间的重复代码。
    """
    CHANNEL_2_DICT = {
        'auto': '1',
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
        'auto': '1',
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
    }
    BAND_MAP = {"2.4G": "2.4 GHz", "5G": "5 GHz"}
    WIRELESS_MAP = {
        "auto": "自动",
        "11n": "N only",
        "11ax": '自动',
        "11ac": "自动",
        "11a": "自动"
    }

    def change_wireless_mode(self, mode):
        '''
        select mode
        @param mode:
        @return:
        '''
        ui_mode = self.WIRELESS_MAP[mode]
        wireless_mode_select = Select(
            self.driver.find_element(By.XPATH, self.xpath['wireless_mode_element'][self.router_info]))
        wireless_mode_select.select_by_visible_text(ui_mode)
        assert wireless_mode_select.first_selected_option.text == ui_mode, "Wireless mode not selected"
        if mode == '11ax':
            index = '1'
        else:
            index = '2'
        self.driver.find_element(By.XPATH,
                                 self.xpath['wireless_ax_element'][self.router_info].format(index)).click()

    def change_country(self, router_or_code):
        self.login()
        self.driver.find_element(By.ID, 'Advanced_Wireless_Content_menu').click()
        # Wireless - General
        WebDriverWait(driver=self.driver, timeout=5, poll_frequency=0.5).until(
            EC.presence_of_element_located((By.ID, 'FormTitle'))
        )

        # 判断参数类型，提取 country_code
        if isinstance(router_or_code, str):
            country_code = router_or_code
        else:
            country_code = getattr(router_or_code, "country_code", None)

        # 修改 国家码
        if country_code:
            if country_code not in self.COUNTRY_CODE:
                raise ConfigError('country code error')

            self.driver.find_element(
                By.XPATH, '//*[@id="Advanced_WAdvanced_Content_tab"]/div'
            ).click()

            WebDriverWait(driver=self.driver, timeout=5, poll_frequency=0.5).until(
                EC.presence_of_element_located((By.ID, 'titl_desc'))
            )

            index = self.COUNTRY_CODE[country_code]
            self.driver.find_element(
                By.XPATH,
                self.xpath['country_code_element'][self.router_info].format(index)
            ).click()

            self.driver.find_element(
                By.XPATH, '//*[@id="apply_btn"]/input'
            ).click()

            # 处理弹窗
            for _ in range(2):
                try:
                    self.driver.switch_to.alert.accept()
                except Exception:
                    ...

            WebDriverWait(driver=self.driver, timeout=120, poll_frequency=0.5).until_not(
                EC.visibility_of_element_located((By.XPATH, '//*[@id="loadingBlock"]/tbody'))
            )
