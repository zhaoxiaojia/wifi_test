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

        def _norm(name: str) -> str:
            return re.sub(r"[\s\-]", "", str(name)).lower()

        target_norm = _norm(net_card) if net_card else ""

        current_name = ""
        current_norm = ""
        disconnected = False
        found_fallback = None

        def _header_to_name(header: str) -> str:
            h = header.rstrip(":").strip()
            if "适配器" in h:
                parts = h.split("适配器", 1)
                return parts[1].strip() if len(parts) > 1 else h
            m = re.search(r"adapter\s+(.+)$", h, re.IGNORECASE)
            if m:
                return m.group(1).strip()
            return h

        for line in lines:
            raw = line.rstrip()
            stripped = raw.strip()

            if stripped.endswith(":") and not raw.startswith((" ", "\t")):
                current_name = _header_to_name(stripped)
                current_norm = _norm(current_name)
                disconnected = False
                continue

            if not current_name:
                continue

            if ("媒体已断开连接" in stripped) or re.search(r"media\s+disconnected", stripped, re.IGNORECASE):
                disconnected = True

            if re.search(r"IPv4", stripped, re.IGNORECASE):
                m = re.search(r"(\d+\.\d+\.\d+\.\d+)", stripped)
                if not m:
                    continue
                ip = m.group(1)
                if ip.startswith("169.254.") or ip == "0.0.0.0":
                    continue

                if target_norm:
                    if target_norm in current_norm:
                        return ip
                else:
                    if not disconnected:
                        return ip
                    if found_fallback is None:
                        found_fallback = ip

        return found_fallback

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
