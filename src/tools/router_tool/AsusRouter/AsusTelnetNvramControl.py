#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""华硕路由器基于 Telnet/NVRAM 的通用控制实现."""

from __future__ import annotations

import logging
import telnetlib
import time
from typing import Union

from src.tools.router_tool.RouterControl import ConfigError
from src.tools.router_tool.AsusRouter.AsusBaseControl import AsusBaseControl


class AsusTelnetNvramControl(AsusBaseControl):
    """封装通过 Telnet 修改 NVRAM 的常见操作."""

    MODE_PARAM = {
        'Open System': 'openowe',
        'Shared Key': 'shared',
        'WPA2-Personal': 'psk2',
        'WPA3-Personal': 'sae',
        'WPA/WPA2-Personal': 'pskpsk2',
        'WPA2/WPA3-Personal': 'psk2sae',
    }

    TELNET_PORT = 23
    TELNET_USER = 'admin'

    def __init__(self, router_key: str, *, display: bool = True, address: str | None = None,
                 prompt: bytes = b':/tmp/home/root#') -> None:
        super().__init__(router_key, display=display, address=address)
        self.host = self.address
        self.port = self.TELNET_PORT
        self.prompt = prompt
        self.telnet: telnetlib.Telnet | None = None
        self._is_logged_in = False

    # ------------------------------------------------------------------
    # Telnet helpers
    # ------------------------------------------------------------------
    def _login(self) -> None:
        """初始化 Telnet 连接并完成登录."""
        self.telnet = telnetlib.Telnet(self.host, self.port)
        self._is_logged_in = False
        try:
            if self.telnet is not None:
                try:
                    self.telnet.close()
                except Exception:
                    pass
            self.telnet = telnetlib.Telnet(self.host, self.port, timeout=10)
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
        if not self._is_logged_in or self.telnet is None or getattr(self.telnet, 'sock', None) is None:
            self._login()

    def telnet_write(self, cmd: Union[str, bytes], *, wait_prompt: bool = False, timeout: int = 30) -> None:
        """发送 Telnet 命令，可选等待提示符返回."""
        self._ensure_connection()
        if isinstance(cmd, str):
            data = (cmd + '\n').encode('ascii', errors='ignore')
        else:
            data = cmd + (b'' if cmd.endswith(b'\n') else b'\n')

        logging.info("Executing: %r", cmd)
        try:
            assert self.telnet is not None  # 为类型检查器消除告警
            self.telnet.write(data)
            if wait_prompt:
                self.telnet.read_until(self.prompt, timeout=timeout)
        except Exception as exc:
            self._is_logged_in = False
            logging.error("Telnet command %r failed: %s", cmd, exc, exc_info=True)
            raise RuntimeError(f"Telnet command failed: {exc}") from exc

    def quit(self) -> None:
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

    # ------------------------------------------------------------------
    # NVRAM setters
    # ------------------------------------------------------------------
    def set_2g_ssid(self, ssid: str) -> None:
        self.telnet_write(f'nvram set wl0_ssid={ssid};')

    def set_5g_ssid(self, ssid: str) -> None:
        self.telnet_write(f'nvram set wl1_ssid={ssid};')

    def set_2g_wireless(self, mode: str) -> None:
        cmd = {
            'auto': 'nvram set wl0_11ax=0;nvram set wl0_nmode_x=0;',
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
        cmd = {
            'auto': 'nvram set wl1_11ax=0;nvram set wl1_nmode_x=0;',
            '11a': 'nvram set wl1_11ax=0;nvram set wl1_nmode_x=7;',
            '11ac': 'nvram set wl1_11ax=0;nvram set wl1_nmode_x=3;',
            '11ax': 'nvram set wl1_11ax=1;nvram set wl1_nmode_x=0;',
            'Legacy': 'nvram set wl1_he_features=0;nvram set wl1_nmode_x=2;',
        }
        if mode not in self.WIRELESS_5:
            raise ConfigError('wireless element error')
        self.telnet_write(cmd[mode])

    def set_2g_password(self, passwd: str) -> None:
        self.telnet_write(f'nvram set wl0_wpa_psk={passwd};')

    def set_5g_password(self, passwd: str) -> None:
        self.telnet_write(f'nvram set wl1_wpa_psk={passwd};')

    def set_2g_authentication(self, method: str) -> None:
        cmd = 'nvram set wl0_auth_mode_x={};'
        mode_list = self.AUTHENTICATION_METHOD if method != 'Legacy' else self.AUTHENTICATION_METHOD_LEGCY
        if method not in mode_list:
            raise ConfigError('security protocol method element error')
        self.telnet_write(cmd.format(self.MODE_PARAM[method]))
        if method == 'Open System':
            self.set_2g_wep_encrypt('None')

    def set_5g_authentication(self, method: str) -> None:
        cmd = 'nvram set wl1_auth_mode_x={};'
        mode_list = self.AUTHENTICATION_METHOD if method != 'Legacy' else self.AUTHENTICATION_METHOD_LEGCY
        if method not in mode_list:
            raise ConfigError('security protocol method element error')
        self.telnet_write(cmd.format(self.MODE_PARAM[method]))
        if method == 'Open System':
            self.set_5g_wep_encrypt('None')

    def set_2g_channel(self, channel: Union[str, int]) -> None:
        channel = str(channel)
        if channel not in self.CHANNEL_2:
            raise ConfigError('channel element error')
        self.telnet_write(f'nvram set wl0_chanspec={0 if channel == "auto" else channel};')

    def set_5g_channel(self, channel: Union[str, int]) -> None:
        channel = str(channel)
        if channel not in self.CHANNEL_5:
            raise ConfigError('channel element error')
        self.telnet_write(f'nvram set wl1_chanspec={0 if channel == "auto" else channel}/80;')

    def set_2g_bandwidth(self, width: str) -> None:
        if width not in self.BANDWIDTH_2:
            raise ConfigError('bandwidth element error')
        self.telnet_write(f'nvram set wl0_bw={self.BANDWIDTH_2.index(width)};')

    def set_5g_bandwidth(self, width: str) -> None:
        if width not in self.BANDWIDTH_5:
            raise ConfigError('bandwidth element error')
        self.telnet_write(f'nvram set wl1_bw={self.BANDWIDTH_5.index(width)};')

    def set_2g_wep_encrypt(self, encrypt: str) -> None:
        if encrypt not in self.WEP_ENCRYPT:
            raise ConfigError('wep encrypt element error')
        index = '1' if '64' in encrypt else '2'
        index = '0' if encrypt == 'None' else index
        self.telnet_write(f'nvram set wl0_wep_x={index};nvram set w1_wep_x={index};')

    def set_5g_wep_encrypt(self, encrypt: str) -> None:
        if encrypt not in self.WEP_ENCRYPT:
            raise ConfigError('wep encrypt element error')
        index = '1' if '64' in encrypt else '2'
        index = '0' if encrypt == 'None' else index
        self.telnet_write(f'nvram set wl1_wep_x={index};nvram set w1_wep_x={index};')

    def set_2g_wep_passwd(self, passwd: str) -> None:
        self.telnet_write(f'nvram set wl0_key1={passwd};')

    def set_5g_wep_passwd(self, passwd: str) -> None:
        self.telnet_write(f'nvram set wl1_key1={passwd};')

    def commit(self) -> None:
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

    # ------------------------------------------------------------------
    # High level API
    # ------------------------------------------------------------------
    def _reconnect_after_restart(self, max_wait: int = 120) -> None:
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

        if router.channel:
            if '2' in router.band:
                self.set_2g_channel(router.channel)
            else:
                self.set_5g_channel(router.channel)

        if router.bandwidth:
            if '2' in router.band:
                self.set_2g_bandwidth(router.bandwidth)
            else:
                self.set_5g_bandwidth(router.bandwidth)

        self.commit()
        time.sleep(3)
        logging.info('Router setting done')
        return True
