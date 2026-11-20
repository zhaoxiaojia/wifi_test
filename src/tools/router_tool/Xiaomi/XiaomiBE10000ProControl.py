"""Independent radio settings for MiWiFi BE 10000 Pro (RP04)."""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.selenium_manager import SeleniumManager
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from src.tools.router_tool.RouterControl import ConfigError
from src.tools.router_tool.Xiaomi.XiaomiBaseControl import XiaomiBaseControl


class XiaomiBE10000ProControl(XiaomiBaseControl):
    RADIOS = {"2.4G": "wifiset24", "5G": "wifiset50", "5G Game": "wifiset5g2"}
    BAND_LIST = list(RADIOS)
    WIRELESS_2 = ["auto", "11n", "11ax"]
    WIRELESS_5 = ["auto", "11ac", "11ax"]
    CHANNEL_5 = ("auto", "149", "153", "157", "161", "165")
    CHANNEL_5_GAME = ("auto", "36", "40", "44", "48", "52", "56", "60", "64")
    SECURITY = {
        "Open System": "none", "WPA2-Personal": "psk2", "WPA3-Personal": "ccmp",
        "超强加密(WPA3个人版)": "ccmp", "强混合加密(WPA3/WPA2个人版)": "psk2+ccmp",
        "强加密(WPA2个人版)": "psk2", "混合加密(WPA/WPA2个人版)": "mixed-psk",
        "无加密(允许所有人连接)": "none",
    }

    def __init__(self, address=None):
        super().__init__("xiaomi_be10000pro", address=address)

    def _init(self):
        # The QA workstation also has an older ChromeDriver on PATH.
        paths = SeleniumManager().binary_paths(
            ["--browser", "chrome", "--skip-driver-in-path"]
        )
        options = webdriver.ChromeOptions()
        options.ignore_local_proxy_environment_variables()
        self.driver = webdriver.Chrome(service=Service(paths["driver_path"]), options=options)
        self.driver.implicitly_wait(3)

    def _settings(self):
        # Keep credentials in memory only. Use the firmware's own password decoder.
        return self.driver.execute_script("""
            const ids = arguments[0];
            if (document.querySelector('#bsdswitch')?.dataset.on !== '0')
                return null;
            const result = {};
            for (const [offset,id] of ids.entries()) {
                const f = document.getElementById(id)?.elements;
                if (!f || f.wifiIndex.value !== String(offset + 1)) return null;
                const fields = {on:f.on.value, ssid:f.ssid.value,
                    pwd:$.pwddecode(f.pwd.value), encryption:f.encryption.value,
                    hidden:f.hidden.checked ? '1' : '0', channel:f.channel.value,
                    bandwidth:f.bandwidth.value, txpwr:f.txpwr.value};
                const choices = {};
                for (const name of ['encryption','channel','bandwidth'])
                    choices[name] = Array.from(f[name].options, o => o.value);
                result[id] = {fields, choices};
            }
            return result;
        """, list(self.RADIOS.values()))

    def _changes(self, router, choices):
        changes = {}
        modes = self.WIRELESS_2 if router.band == self.BAND_2 else self.WIRELESS_5
        if router.wireless_mode not in (None, "", *modes):
            raise ConfigError("Unsupported wireless mode")
        if router.ssid:
            if len(router.ssid.encode("utf-8")) > 32:
                raise ConfigError("SSID exceeds 32 bytes")
            changes["ssid"] = router.ssid
        if router.password:
            changes["pwd"] = router.password
        if router.hide_ssid:
            changes["hidden"] = {"是": "1", "否": "0"}[router.hide_ssid]
        if router.security_mode:
            if router.security_mode not in self.SECURITY:
                raise ConfigError("Unsupported security mode")
            changes["encryption"] = self.SECURITY[router.security_mode]
        if router.channel is not None and router.channel != "":
            changes["channel"] = "0" if router.channel == "auto" else str(router.channel)
        if router.bandwidth:
            widths = self.BANDWIDTH_2 if router.band == self.BAND_2 else self.BANDWIDTH_5
            if router.bandwidth not in widths:
                raise ConfigError("Unsupported bandwidth")
            changes["bandwidth"] = ("0" if "/" in router.bandwidth
                                    else router.bandwidth.split(" ")[0])
        for name in changes.keys() & choices.keys():
            if changes[name] not in choices[name]:
                raise ConfigError(f"Unsupported {name} for {router.band}")
        return changes

    def change_setting(self, router):
        if router.band not in self.RADIOS:
            raise ConfigError("Unsupported radio")
        target = self.RADIOS[router.band]
        try:
            self.login()
            link = self.driver.find_element(By.CSS_SELECTOR, "a.btn_wifi")
            self.driver.get(link.get_attribute("href"))
            wait = WebDriverWait(self.driver, 12)
            state = wait.until(lambda _: self._settings())
            expected = {key: value["fields"].copy() for key, value in state.items()}
            expected[target].update(self._changes(router, state[target]["choices"]))
            if router.wireless_mode not in (None, "", "auto"):
                compatibility = "0" if router.wireless_mode == "11ax" else "1"
                if self.driver.execute_script(
                    "return document.getElementById('WIFI6switch').dataset.on"
                ) != compatibility:
                    game = state[self.RADIOS["5G Game"]]["fields"]
                    self.driver.set_script_timeout(45)
                    code = self.driver.execute_async_script("""
                        const done = arguments[arguments.length - 1];
                        $.ajax({url:'../../api/xqnetwork/set_wifi_ax', type:'POST',
                            dataType:'json', timeout:40000, data:arguments[0]})
                            .done(r => done(r.code)).fail(() => done(null));
                    """, {"ax": "1" if compatibility == "0" else "0",
                          "isDFS": int(52 <= int(game["channel"]) <= 64
                                       or game["bandwidth"] == "0")})
                    if code != 0:
                        raise ConfigError(f"Wi-Fi compatibility save failed (status {code})")

                    def mode_applied(_):
                        self.driver.refresh()
                        current = wait.until(lambda _: self._settings())
                        return (current == state and self.driver.execute_script(
                            "return document.getElementById('WIFI6switch').dataset.on"
                        ) == compatibility)

                    WebDriverWait(self.driver, 120, poll_frequency=3,
                                  ignored_exceptions=(TimeoutException,)).until(mode_applied)
            if expected[target] == state[target]["fields"]:
                return True
            fields = expected[target]
            if fields["encryption"] != "none" and not 8 <= len(fields["pwd"].encode()) <= 63:
                raise ConfigError("Secured Wi-Fi requires an 8–63 byte passphrase")
            if fields["encryption"] == "none" and router.password:
                raise ConfigError("An open network cannot use a passphrase")
            payload = {"bsd": "0"}
            for index, form_id in enumerate(self.RADIOS.values(), 1):
                values = expected[form_id]
                payload.update({f"{key}{index}": value for key, value in values.items()})
            payload["isDFS"] = int(payload["on2"] != "0" and (
                52 <= int(payload["channel2"]) <= 64 or payload["bandwidth2"] == "0"))
            self.driver.set_script_timeout(45)
            code = self.driver.execute_async_script("""
                const done = arguments[arguments.length - 1];
                $.ajax({url:'../../api/xqnetwork/set_all_wifi', type:'POST',
                    dataType:'json', timeout:40000, data:arguments[0]})
                    .done(r => done(r.code)).fail(() => done(null));
            """, payload)
            if code != 0:
                raise ConfigError(f"Router save failed (status {code})")

            def applied(_):
                self.driver.refresh()
                current = wait.until(lambda _: self._settings())
                return all(current[key]["fields"] == fields for key, fields in expected.items())

            WebDriverWait(self.driver, 120, poll_frequency=3,
                          ignored_exceptions=(TimeoutException,)).until(applied)
            return True
        except WebDriverException:
            raise ConfigError("Router login, settings load or configuration readback failed") from None
        finally:
            if getattr(self, "driver", None):
                self.driver.quit()
