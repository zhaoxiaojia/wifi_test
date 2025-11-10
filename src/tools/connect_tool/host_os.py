import logging
import os
import re
import subprocess
import time

from src.tools.config_loader import load_config
from src.util.constants import TOOL_SECTION_KEY


class host_os:
    """
    Host OS.

    -------------------------
    It runs shell commands on the target device using ADB helpers and captures the output.
    It executes external commands via Python's subprocess module.
    It logs information for debugging or monitoring purposes.
    It introduces delays to allow the device to process commands.

    -------------------------
    Returns
    -------------------------
    None
        This class does not return a value.
    """

    def __new__(cls, *args, **kwargs):
        """
        New.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        if not hasattr(host_os, "_instance"):
            host_os._instance = object.__new__(cls)
        return host_os._instance

    def __init__(self):
        """
        Init.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        self.config = load_config(refresh=True)
        tool_cfg = self.config.get(TOOL_SECTION_KEY, {})
        self.host = tool_cfg.get('host_os') or {}
        if not self.host:
            raise RuntimeError("Missing host_os configuration in config_tool.yaml")
        self.user = self.host.get('user')
        self.passwd = self.host.get('password')
        if not self.user or not self.passwd:
            raise RuntimeError("Incomplete host_os credentials in config_tool.yaml")
        self.ip = ''

    def checkoutput(self, cmd):
        """
        Checkoutput.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It executes external commands via Python's subprocess module.

        -------------------------
        Parameters
        -------------------------
        cmd : Any
            Command string to parse or execute.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        try:
            info = subprocess.check_output(cmd, shell=True, encoding='utf-8')
        except Exception as e:
            return None
        else:
            return info

    def checkoutput_root(self, cmd):
        """
        Checkoutput root.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.

        -------------------------
        Parameters
        -------------------------
        cmd : Any
            Command string to parse or execute.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        cmd = f'echo {self.passwd}|sudo -S {cmd}'
        return self.checkoutput(cmd)

    def get_ipaddress(self, net_card=''):
        """
        Retrieve ipaddress.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It logs information for debugging or monitoring purposes.

        -------------------------
        Parameters
        -------------------------
        net_card : Any
            The ``net_card`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        info = self.checkoutput(f'ifconfig {net_card}')
        logging.info(f' ifconfig :{info}')
        info = re.findall(r'inet\s+(\d+\.\d+\.\d+\.\d+)', info, re.S)
        if info:
            return info[0]

    def dynamic_flush_network_card(self, net_card=''):
        """
        Dynamic flush network card.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It logs information for debugging or monitoring purposes.
        It introduces delays to allow the device to process commands.

        -------------------------
        Parameters
        -------------------------
        net_card : Any
            The ``net_card`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        self.checkoutput_root(f'netplan apply')
        for i in range(30):
            time.sleep(15)
            if self.get_ipaddress(net_card):
                self.ip = self.get_ipaddress(net_card)
                logging.info(f'get pc ip {self.ip}')
                return self.ip

