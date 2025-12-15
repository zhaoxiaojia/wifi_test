"""
Asus telnet nvram control

This module is part of the AsusRouter package.
"""

from __future__ import annotations

import logging
import time
from typing import Union

from src.tools.router_tool.RouterControl import ConfigError
from src.tools.router_tool.AsusRouter.AsusBaseControl import AsusBaseControl
from src.tools.connect_tool.telnet_common import TelnetSession


class AsusTelnetNvramControl(AsusBaseControl):
    """
        Asus telnet nvram control
            Parameters
            ----------
            None
                This class is instantiated without additional parameters.
            Returns
            -------
            None
                Classes return instances implicitly when constructed.
    """
    CHANNEL_2 = ['auto', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14']
    CHANNEL_2_CHANSPEC_MAP = {
        'auto': '0',
        '1': '1l',
        '2': '2l',
        '3': '3l',
        '4': '4l',
        '5': '5l',
        '6': '6l',
        '7': '7l',
        '8': '8l',
        '9': '9l',
        '10': '10u',
        '11': '11u',
        '12': '12u',
        '13': '13u',
        '14': '14',
    }

    MODE_PARAM = {
        'Open System': 'openowe',
        'Shared Key': 'shared',
        'WPA2-Personal': 'psk2',
        'WPA3-Personal': 'sae',
        'WPA/WPA2-Personal': 'pskpsk2',
        'WPA2/WPA3-Personal': 'psk2sae',
    }

    WL1_BANDWIDTH_MAP = {
        '20MHZ': ('0', '20'),
        '40MHZ': ('1', '40'),
        '80MHZ': ('2', '80'),
        '160MHZ': ('3', '160'),
        '20/40/80MHZ': ('2', '80'),
        '20/40MHZ': ('1', '40'),
        '20/40/80/160MHZ': ('3', '160'),
    }

    TELNET_PORT = 23
    TELNET_USER = 'admin'

    def __init__(self, router_key: str, *, display: bool = True, address: str | None = None,
                 prompt: bytes = b':/tmp/home/root#') -> None:
        """
            Init
                Parameters
                ----------
                router_key : object
                    Description of parameter 'router_key'.
                display : object
                    Flag indicating whether the browser should run in visible mode.
                address : object
                    The router's login address or IP address; if None, a default is used.
                prompt : object
                    Description of parameter 'prompt'.
                Returns
                -------
                None
                    This function does not return a value.
        """
        super().__init__(router_key, display=display, address=address)
        self.host = self.address
        self.port = self.TELNET_PORT
        self.prompt = prompt
        self.telnet: TelnetSession | None = None
        self._is_logged_in = False
        self._wl0_channel: str = 'auto'
        self._wl0_bandwidth: str | None = None
        self._last_wl0_chanspec: str | None = None
        self._wl1_channel: str | None = 'auto'
        self._wl1_chanspec_suffix: str | None = '80'
        self._last_wl1_chanspec: str | None = None
        self._wl1_bandwidth_map = dict(self.WL1_BANDWIDTH_MAP)
        if self.router_info in {'asus_88u', 'asus_88u_pro'}:
            self._wl1_bandwidth_map.update({
                '20MHZ': ('1', '20'),
                '40MHZ': ('2', '40'),
                '80MHZ': ('3', '80'),
                '160MHZ': ('5', '160'),
                '20/40/80MHZ': ('0', '80'),
                '20/40/80/160MHZ': ('0', '160'),
            })

    def _login(self) -> None:
        """
            Login
                Logs informational or debugging messages for tracing execution.
                Parameters
                ----------
                None
                    This function does not accept any parameters beyond the implicit context.
                Returns
                -------
                None
                    This function does not return a value.
        """
        self._is_logged_in = False
        try:
            if self.telnet is not None:
                try:
                    self.telnet.close()
                except Exception:
                    pass
            self.telnet = TelnetSession(self.host, self.port, timeout=10)
            self.telnet.open()
            self.telnet.read_until(b'login:', timeout=10)
            self.telnet.write(self.TELNET_USER.encode('ascii') + b'\n')
            self.telnet.read_until(b'Password:', timeout=10)
            self.telnet.write(str(self.xpath['passwd']).encode('ascii') + b'\n')
            self.telnet.read_until(self.prompt, timeout=10)
        except Exception as exc:
            if self.telnet is not None:
                try:
                    self.telnet.close()
                except Exception:
                    pass
            self.telnet = None
            logging.error("Telnet login failed: %s", exc, exc_info=True)
            raise RuntimeError(f"Telnet login failed: {exc}") from exc
        else:
            self._is_logged_in = True

    def _ensure_connection(self) -> None:
        """
            Ensure connection
                Parameters
                ----------
                None
                    This function does not accept any parameters beyond the implicit context.
                Returns
                -------
                None
                    This function does not return a value.
        """
        if not self._is_logged_in or self.telnet is None or getattr(self.telnet, 'sock', None) is None:
            self._login()

    def telnet_write(self, cmd: Union[str, bytes], *, wait_prompt: bool = False, timeout: int = 30) -> None:
        """
            Telnet write
                Logs informational or debugging messages for tracing execution.
                Asserts conditions to validate the success of operations.
                Parameters
                ----------
                cmd : object
                    Description of parameter 'cmd'.
                wait_prompt : object
                    Description of parameter 'wait_prompt'.
                timeout : object
                    Maximum time in seconds to wait for a condition to be satisfied.
                Returns
                -------
                None
                    This function does not return a value.
        """
        self._ensure_connection()
        if isinstance(cmd, str):
            data = (cmd + '\n').encode('ascii', errors='ignore')
        else:
            data = cmd + (b'' if cmd.endswith(b'\n') else b'\n')

        logging.info("Executing: %r", cmd)
        try:
            assert self.telnet is not None
            self.telnet.write(data)
            if wait_prompt:
                self.telnet.read_until(self.prompt, timeout=timeout)
        except Exception as exc:
            self._is_logged_in = False
            logging.error("Telnet command %r failed: %s", cmd, exc, exc_info=True)
            raise RuntimeError(f"Telnet command failed: {exc}") from exc

    @staticmethod
    def _normalize_bandwidth(width: str) -> str:
        """
            Normalize bandwidth
                Parameters
                ----------
                width : object
                    Description of parameter 'width'.
                Returns
                -------
                str
                    Description of the returned value.
        """
        return width.replace(' ', '').upper()

    def _get_wl0_chanspec(self) -> str:
        """
            Get wl0 chanspec
                Parameters
                ----------
                None
                    This function does not accept any parameters beyond the implicit context.
                Returns
                -------
                str
                    Description of the returned value.
        """
        channel = self._wl0_channel or 'auto'
        if channel not in self.CHANNEL_2:
            raise ConfigError('channel element error')
        if self._wl0_bandwidth == '40MHZ':
            return self.CHANNEL_2_CHANSPEC_MAP[channel]
        return '0' if channel == 'auto' else channel

    def _update_wl0_chanspec(self, *, force: bool = False) -> None:
        """
            Update wl0 chanspec
                Parameters
                ----------
                force : object
                    Description of parameter 'force'.
                Returns
                -------
                None
                    This function does not return a value.
        """
        chanspec = self._get_wl0_chanspec()
        if not force and chanspec == self._last_wl0_chanspec:
            return
        self.telnet_write(f'nvram set wl0_chanspec={chanspec};')
        self._last_wl0_chanspec = chanspec

    def _get_wl1_40mhz_chanspec(self, channel: str) -> str:
        """
            Get wl1 40mhz chanspec
                Parameters
                ----------
                channel : object
                    Specific wireless channel to select during configuration.
                Returns
                -------
                str
                    Description of the returned value.
        """
        if channel == 'auto':
            return '0'
        try:
            index = self.CHANNEL_5.index(channel)
        except ValueError as exc:
            raise ConfigError('channel element error') from exc
        suffix = 'l' if (index - 1) % 2 == 0 else 'u'
        return f'{channel}{suffix}'

    def _update_wl1_chanspec(self, *, force: bool = False) -> None:
        """
            Update wl1 chanspec
                Parameters
                ----------
                force : object
                    Description of parameter 'force'.
                Returns
                -------
                None
                    This function does not return a value.
        """
        suffix = self._wl1_chanspec_suffix
        if not suffix:
            return
        channel = self._wl1_channel or 'auto'
        if suffix == '40':
            chanspec = self._get_wl1_40mhz_chanspec(channel)
        else:
            channel_value = '0' if channel == 'auto' else channel
            chanspec = f'{channel_value}/{suffix}'
        if not force and chanspec == self._last_wl1_chanspec:
            return
        self.telnet_write(f'nvram set wl1_chanspec={chanspec};')
        self._last_wl1_chanspec = chanspec

    def quit(self) -> None:
        """
            Quit
                Logs informational or debugging messages for tracing execution.
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
            if self.telnet is not None:
                if self._is_logged_in:
                    try:
                        self.telnet_write('exit')
                    except Exception:
                        logging.exception('Telnet exit command failed')
                self.telnet.close()
        except Exception as exc:
            logging.error("Telnet quit failed: %s", exc)
        finally:
            self.telnet = None
            self._is_logged_in = False

    def set_2g_ssid(self, ssid: str) -> None:
        """
            Set 2g SSID
                Parameters
                ----------
                ssid : object
                    Wi‑Fi network SSID used for association.
                Returns
                -------
                None
                    This function does not return a value.
        """
        self.telnet_write(f'nvram set wl0_ssid={ssid};')

    def set_5g_ssid(self, ssid: str) -> None:
        """
            Set 5g SSID
                Parameters
                ----------
                ssid : object
                    Wi‑Fi network SSID used for association.
                Returns
                -------
                None
                    This function does not return a value.
        """
        self.telnet_write(f'nvram set wl1_ssid={ssid};')

    def set_2g_wireless(self, mode: str) -> None:
        """
            Set 2g wireless
                Parameters
                ----------
                mode : object
                    Wireless mode to configure on the router (e.g. 11n, 11ax).
                Returns
                -------
                None
                    This function does not return a value.
        """
        cmd = {
            'auto': 'nvram set wl0_11ax=1;nvram set wl0_nmode_x=0;',
            '11n': 'nvram set wl0_11ax=0;nvram set wl0_nmode_x=1;',
            '11g': 'nvram set wl0_11ax=0;nvram set wl0_nmode_x=5;',
            '11b': 'nvram set wl0_11ax=0;nvram set wl0_nmode_x=6;',
            '11ax': 'nvram set wl0_11ax=1;nvram set wl0_nmode_x=0',
            'Legacy': 'nvram set wl0_he_features=0;nvram set wl0_nmode_x=2;',
        }
        if mode not in self.WIRELESS_2:
            raise ConfigError('wireless element error')
        self.telnet_write(cmd[mode])

    def set_5g_wireless(self, mode: str) -> None:
        """
            Set 5g wireless
                Parameters
                ----------
                mode : object
                    Wireless mode to configure on the router (e.g. 11n, 11ax).
                Returns
                -------
                None
                    This function does not return a value.
        """
        cmd = {
            'auto': 'nvram set wl1_11ax=1;nvram set wl1_nmode_x=0;',
            '11a': 'nvram set wl1_11ax=0;nvram set wl1_nmode_x=7;',
            '11n': 'nvram set wl1_11ax=0;nvram set wl1_nmode_x=1;',
            '11ac': 'nvram set wl1_11ax=0;nvram set wl1_nmode_x=3;',
            '11ax': 'nvram set wl1_11ax=1;nvram set wl1_nmode_x=0;',
            'Legacy': 'nvram set wl1_he_features=0;nvram set wl1_nmode_x=2;',
        }
        if mode not in self.WIRELESS_5:
            raise ConfigError('wireless element error')
        self.telnet_write(cmd[mode])

    def set_2g_password(self, passwd: str) -> None:
        """
            Set 2g password
                Parameters
                ----------
                passwd : object
                    Description of parameter 'passwd'.
                Returns
                -------
                None
                    This function does not return a value.
        """
        self.telnet_write(f'nvram set wl0_wpa_psk={passwd};')

    def set_5g_password(self, passwd: str) -> None:
        """
            Set 5g password
                Parameters
                ----------
                passwd : object
                    Description of parameter 'passwd'.
                Returns
                -------
                None
                    This function does not return a value.
        """
        self.telnet_write(f'nvram set wl1_wpa_psk={passwd};')

    def set_2g_authentication(self, method: str) -> None:
        """
            Set 2g authentication
                Parameters
                ----------
                method : object
                    Description of parameter 'method'.
                Returns
                -------
                None
                    This function does not return a value.
        """
        cmd = 'nvram set wl0_auth_mode_x={};'
        mode_list = self.AUTHENTICATION_METHOD if method != 'Legacy' else self.AUTHENTICATION_METHOD_LEGCY
        if method not in mode_list:
            raise ConfigError('security protocol method element error')
        self.telnet_write(cmd.format(self.MODE_PARAM[method]))
        if method == 'Open System':
            self.set_2g_wep_encrypt('None')

    def set_5g_authentication(self, method: str) -> None:
        """
            Set 5g authentication
                Parameters
                ----------
                method : object
                    Description of parameter 'method'.
                Returns
                -------
                None
                    This function does not return a value.
        """
        cmd = 'nvram set wl1_auth_mode_x={};'
        mode_list = self.AUTHENTICATION_METHOD if method != 'Legacy' else self.AUTHENTICATION_METHOD_LEGCY
        if method not in mode_list:
            raise ConfigError('security protocol method element error')
        self.telnet_write(cmd.format(self.MODE_PARAM[method]))
        if method == 'Open System':
            self.set_5g_wep_encrypt('None')

    def set_2g_channel(self, channel: Union[str, int]) -> None:
        """
            Set 2g channel
                Parameters
                ----------
                channel : object
                    Specific wireless channel to select during configuration.
                Returns
                -------
                None
                    This function does not return a value.
        """
        channel = str(channel)
        if channel not in self.CHANNEL_2:
            raise ConfigError('channel element error')
        self._wl0_channel = channel
        self._update_wl0_chanspec(force=True)

    def set_2g_bandwidth(self, width: str) -> None:
        """
            Set 2g bandwidth
                Parameters
                ----------
                width : object
                    Description of parameter 'width'.
                Returns
                -------
                None
                    This function does not return a value.
        """
        if width not in self.BANDWIDTH_2:
            raise ConfigError('bandwidth element error')
        normalized_width = self._normalize_bandwidth(width)
        if normalized_width != self._wl0_bandwidth:
            self._wl0_bandwidth = normalized_width
            self._update_wl0_chanspec(force=True)
        self.telnet_write(f'nvram set wl0_bw={self.BANDWIDTH_2.index(width)};')

    def set_5g_channel_bandwidth(
            self,
            *,
            bandwidth: str | None = None,
            channel: Union[str, int, None] = None,
    ) -> None:
        """
            Set 5g channel bandwidth
                Parameters
                ----------
                bandwidth : object
                    Channel bandwidth (e.g. 20 MHz, 40 MHz, 80 MHz) when configuring wireless settings.
                channel : object
                    Specific wireless channel to select during configuration.
                Returns
                -------
                None
                    This function does not return a value.
        """
        needs_update = False
        if channel is not None:
            channel = str(channel)
            if channel not in self.CHANNEL_5:
                raise ConfigError('channel element error')
            if channel != self._wl1_channel:
                self._wl1_channel = channel
                needs_update = True
        if bandwidth is not None:
            normalized_width = self._normalize_bandwidth(bandwidth)
            mapping = self._wl1_bandwidth_map.get(normalized_width)
            if mapping is None:
                raise ConfigError('bandwidth element error')
            bw_value, suffix = mapping
            if suffix != self._wl1_chanspec_suffix:
                self._wl1_chanspec_suffix = suffix
                needs_update = True
            if needs_update:
                self._update_wl1_chanspec(force=True)
                needs_update = False
            self.telnet_write(f'nvram set wl1_bw={bw_value};')
        elif needs_update:
            self._update_wl1_chanspec(force=True)

    def set_2g_wep_encrypt(self, encrypt: str) -> None:
        """
            Set 2g wep encrypt
                Parameters
                ----------
                encrypt : object
                    Description of parameter 'encrypt'.
                Returns
                -------
                None
                    This function does not return a value.
        """
        if encrypt not in self.WEP_ENCRYPT:
            raise ConfigError('wep encrypt element error')
        index = '1' if '64' in encrypt else '2'
        index = '0' if encrypt == 'None' else index
        self.telnet_write(f'nvram set wl0_wep_x={index};nvram set w1_wep_x={index};')

    def set_5g_wep_encrypt(self, encrypt: str) -> None:
        """
            Set 5g wep encrypt
                Parameters
                ----------
                encrypt : object
                    Description of parameter 'encrypt'.
                Returns
                -------
                None
                    This function does not return a value.
        """
        if encrypt not in self.WEP_ENCRYPT:
            raise ConfigError('wep encrypt element error')
        index = '1' if '64' in encrypt else '2'
        index = '0' if encrypt == 'None' else index
        self.telnet_write(f'nvram set wl1_wep_x={index};nvram set w1_wep_x={index};')

    def set_2g_wep_passwd(self, passwd: str) -> None:
        """
            Set 2g wep passwd
                Parameters
                ----------
                passwd : object
                    Description of parameter 'passwd'.
                Returns
                -------
                None
                    This function does not return a value.
        """
        self.telnet_write(f'nvram set wl0_key1={passwd};')

    def set_5g_wep_passwd(self, passwd: str) -> None:
        """
            Set 5g wep passwd
                Parameters
                ----------
                passwd : object
                    Description of parameter 'passwd'.
                Returns
                -------
                None
                    This function does not return a value.
        """
        self.telnet_write(f'nvram set wl1_key1={passwd};')

    def commit(self) -> None:
        """
            Commit
                Pauses execution for a specified duration to allow operations to complete.
                Asserts conditions to validate the success of operations.
                Parameters
                ----------
                None
                    This function does not accept any parameters beyond the implicit context.
                Returns
                -------
                None
                    This function does not return a value.
        """
        self._update_wl1_chanspec()
        self.telnet_write('nvram set wl0_radio=1', wait_prompt=False)
        self.telnet_write('nvram set wl1_radio=1', wait_prompt=False)
        self.telnet_write('nvram commit', wait_prompt=True, timeout=60)
        self.telnet_write('restart_wireless &', wait_prompt=False)
        time.sleep(2)
        try:
            assert self.telnet is not None
            self.telnet.read_until(self.prompt, timeout=60)
        except EOFError:
            self._reconnect_after_restart()

    def _reconnect_after_restart(self, max_wait: int = 120) -> None:
        """
            Reconnect after restart
                Pauses execution for a specified duration to allow operations to complete.
                Parameters
                ----------
                max_wait : object
                    Description of parameter 'max_wait'.
                Returns
                -------
                None
                    This function does not return a value.
        """
        self._is_logged_in = False
        if self.telnet is not None:
            try:
                self.telnet.close()
            except Exception:
                pass
        self.telnet = None
        t0 = time.time()
        while time.time() - t0 < max_wait:
            try:
                self._login()
                return
            except Exception:
                time.sleep(2)
        raise RuntimeError('Telnet reconnect after restart failed')

    def change_setting(self, router) -> bool:
        """
            Change setting
                Pauses execution for a specified duration to allow operations to complete.
                Logs informational or debugging messages for tracing execution.
                Parameters
                ----------
                router : object
                    Router control object or router information required to perform operations.
                Returns
                -------
                bool
                    Description of the returned value.
        """
        if router.ssid:
            if '2' in router.band:
                self.set_2g_ssid(router.ssid)
            else:
                self.set_5g_ssid(router.ssid)

        if router.wireless_mode:
            if '2' in router.band:
                self.set_2g_wireless(router.wireless_mode)
            else:
                self.set_5g_wireless(router.wireless_mode)

        if router.password:
            if '2' in router.band:
                self.set_2g_password(router.password)
            else:
                self.set_5g_password(router.password)

        if router.security_mode:
            if '2' in router.band:
                self.set_2g_authentication(router.security_mode)
            else:
                self.set_5g_authentication(router.security_mode)

        channel_5g: Union[str, int, None] = None
        if router.channel:
            if '2' in router.band:
                self.set_2g_channel(router.channel)
            else:
                channel_5g = router.channel

        if router.bandwidth:
            if '2' in router.band:
                self.set_2g_bandwidth(router.bandwidth)
            else:
                self.set_5g_channel_bandwidth(bandwidth=router.bandwidth, channel=channel_5g)
        elif channel_5g is not None:
            self.set_5g_channel_bandwidth(channel=channel_5g)

        self.commit()
        time.sleep(3)
        logging.info('Router setting done')
        return True
