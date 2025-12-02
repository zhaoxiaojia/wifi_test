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
        info = self.checkoutput('ipconfig')
        if not info:
            return None
        lines = info.splitlines()
        blocks = []
        current_header = None
        current_lines = []

        for line in lines:
            if line.strip() == '':
                if current_header is not None:
                    blocks.append((current_header, current_lines))
                    current_header = None
                    current_lines = []
                continue

            if not line.startswith(' ') and line.strip().endswith(':'):
                if current_header is not None:
                    blocks.append((current_header, current_lines))
                current_header = line.strip()
                current_lines = [line]
            else:
                if current_header is not None:
                    current_lines.append(line)

        if current_header is not None:
            blocks.append((current_header, current_lines))

        if net_card:
            target_block = None
            key = net_card.lower()
            for header, content in blocks:
                if key in header.lower():
                    target_block = '\n'.join(content)
                    break

            if target_block:
                ipv4_list = re.findall(r'IPv4[^\n:]*:\s*([\d\.]+)', target_block, re.S)
                for ip in ipv4_list:
                    if not ip.startswith('127.'):
                        return ip

                generic_list = re.findall(r'(\d+\.\d+\.\d+\.\d+)', target_block, re.S)
                for ip in generic_list:
                    if not ip.startswith('127.'):
                        return ip

        ipv4_list = re.findall(r'IPv4[^\n:]*:\s*([\d\.]+)', info, re.S)
        for ip in ipv4_list:
            if not ip.startswith('127.'):
                return ip

        generic_list = re.findall(r'(\d+\.\d+\.\d+\.\d+)', info, re.S)
        for ip in generic_list:
            if not ip.startswith('127.'):
                return ip

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
