import logging
import os
import re
import subprocess
import time
import locale
from subprocess import check_output

from src.tools.yamlTool import yamlTool


class LocalOS:
    def __new__(cls, *args, **kwargs):
        if not hasattr(LocalOS, "_instance"):
            LocalOS._instance = object.__new__(cls)
        return LocalOS._instance

    def __init__(self):
        self.ip = ''

    def checkoutput(self, cmd):
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            encoding=locale.getpreferredencoding(False),
            errors='ignore',
        )
        logging.info("Local os cmd: %s", cmd)
        logging.info("Local os stdout: %s", result.stdout)
        logging.info("Local os stderr: %s", result.stderr)
        if result.returncode != 0:
            logging.error("Local os exit code: %s", result.returncode)
            return None
        return result.stdout

    def get_ipaddress(self, net_card=''):
        output = self.checkoutput('ipconfig')
        if not output:
            return None

        lines = output.splitlines()

        if net_card:
            in_block = False
            for line in lines:
                stripped = line.strip()
                if stripped.endswith(':') and not line.startswith(' '):
                    in_block = net_card in stripped
                    continue
                if in_block and 'IPv4' in line:
                    match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                    if match:
                        return match.group(1)
            return None

        for line in lines:
            if 'IPv4' in line:
                match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                if match:
                    return match.group(1)

        match = re.search(r'(\d+\.\d+\.\d+\.\d+)', output)
        if match:
            return match.group(1)

        return None

    def dynamic_flush_network_card(self, net_card=''):
        disable_cmd = f'netsh interface set interface "{net_card}" disable'
        enable_cmd = f'netsh interface set interface "{net_card}" enable'
        self.checkoutput(disable_cmd)
        self.checkoutput(enable_cmd)

        for _ in range(30):
            time.sleep(5)
            ip = self.get_ipaddress(net_card)
            if ip:
                self.ip = ip
                return self.ip
