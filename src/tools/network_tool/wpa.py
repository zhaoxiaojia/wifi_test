"""
Wpa

This module is part of the reporting package.
"""
import logging
import re
import time


class cmd_wpa:
    """
    Cmd wpa

    Parameters
    ----------
    None
        This class is instantiated without additional parameters.

    Returns
    -------
    None
        Classes return instances implicitly when constructed.
    """
    def __init__(self, host=None, dut=None):
        """
        Init

        Parameters
        ----------
        host : object
            Description of parameter 'host'.
        dut : object
            Description of parameter 'dut'.

        Returns
        -------
        None
            This function does not return a value.
        """
        self.host_control = host


        self.dut_control = dut
        self.interface = 'wlp0s20f3'

    def send_cmd(self, cmd, target):
        """
        Send cmd

        Sends shell commands to the host or device and returns the output.
        Asserts conditions to verify the success of operations.
        Logs informational or warning messages for debugging and status reporting.

        Parameters
        ----------
        cmd : object
            Description of parameter 'cmd'.
        target : object
            Identifier indicating whether the command runs on the host or the device.

        Returns
        -------
        object
            Description of the returned value.
        """
        if target == 'host':
            assert self.host_control, "Can't find any host control"
            logging.info(cmd)
            return self.host_control.checkoutput_root(cmd)
        elif target == 'dut':
            assert self.dut_control, "Can't find any dut control"
            logging.info(cmd)
            return self.dut.checkoutput(cmd)

    def  flush_wlan(self, target):
        """
        Flush wlan

        Sends shell commands to the host or device and returns the output.
        Waits for a specified duration to allow asynchronous operations to complete.

        Parameters
        ----------
        target : object
            Identifier indicating whether the command runs on the host or the device.

        Returns
        -------
        None
            This function does not return a value.
        """
        if not self.send_cmd(f'ifconfig {self.interface} |egrep -o "inet [^ ]*"|cut -d " " -f 2', target):
            self.send_cmd(f'dhclient {self.interface}', target)
            time.sleep(5)

    def clear_wlan(self, target):
        """
        Clear wlan

        Sends shell commands to the host or device and returns the output.
        Waits for a specified duration to allow asynchronous operations to complete.

        Parameters
        ----------
        target : object
            Identifier indicating whether the command runs on the host or the device.

        Returns
        -------
        None
            This function does not return a value.
        """
        if self.send_cmd(f'ifconfig {self.interface} |egrep -o "inet [^ ]*"|cut -d " " -f 2', target):
            self.send_cmd(f'dhclient -r {self.interface}', target)
            time.sleep(5)

    def associate_wifi(self, target, **kwargs):
        """
        Associate Wi‑Fi

        Sends shell commands to the host or device and returns the output.
        Configures or controls the wpa_supplicant client for Wi‑Fi connectivity.
        Waits for a specified duration to allow asynchronous operations to complete.
        Logs informational or warning messages for debugging and status reporting.

        Parameters
        ----------
        target : object
            Identifier indicating whether the command runs on the host or the device.
        kwargs : object
            Description of parameter 'kwargs'.

        Returns
        -------
        object
            Description of the returned value.
        """
        timeout = kwargs.get('timeout', 60)
        retry = 3
        interface = kwargs.get('interface', self.interface)
        radio = kwargs.get('radio', '2.4G')
        ssid = kwargs.get('ssid', None)
        psk = kwargs.get('psk', None)
        key_mgmt = kwargs.get('key_mgmt', None)
        configs = kwargs.get('configs', None)
        wpa_conf = kwargs.get('wpa_conf', None)
        ap_scan = kwargs.get('ap_scan', 1)
        p2p_disabled = kwargs.get('p2p_disabled', 1)
        ctrl_interface = kwargs.get('ctrl_interface', '/var/run/wpa_supplicant')
        ctrl_interface_group = kwargs.get('ctrl_interface_group', 0)
        pairwise = kwargs.get('pairwise', None)
        security = kwargs.get('security', None)
        bssid = kwargs.get('bssid', None)
        eap = kwargs.get('eap', None)
        phase2 = kwargs.get('phase2', None)
        proto = kwargs.get('proto', None)
        scan_ssid = kwargs.get('scan_ssid', None)

        current_status = self.send_cmd('wpa_cli status', target)
        if current_status:
            if ssid in current_status:
                logging.info('already associate')
                return True
            if 'wpa_state=COMPLETED' in current_status:
                logging.info('forget first')
                self.forget_wifi(target, **kwargs)
        wpa_supplicant_conf = '/etc/wpa_supplicant.conf'
        if not configs:
            configs = f'ap_scan={ap_scan}\np2p_disabled={p2p_disabled}\nctrl_interface={ctrl_interface}\nctrl_interface_group={ctrl_interface_group}\n'
            if radio == '6G':
                configs += 'pmf=2\n'
                configs += 'sae_pwe=2\n'
            configs += 'network={\n'
            if isinstance(security, str) and key_mgmt is None:
                if security == 'None':
                    key_mgmt = 'NONE'
                elif re.search(f'Enterprise', security, re.I):
                    key_mgmt = 'WPA-EAP'
                elif re.search(f'WPA3-Personal', security, re.I):
                    key_mgmt = 'SAE'
                else:
                    key_mgmt = 'WPA-PSK'
            if isinstance(security, str) and proto is None and re.search(f'WPA', security, re.I):
                proto = 'WPA RSN'
            for var in ['ssid', 'psk', 'wep_key0', 'wep_key1', 'wep_key2', 'wep_key3', 'identity', 'password',
                        'phase1', 'phase2']:
                if var in locals().keys() and locals()[var] != None:
                    if key_mgmt == 'NONE' and var == 'psk':
                        continue
                    configs += f'{var}=\\"{locals()[var]}\\"\n'
            for var in ['proto', 'key_mgmt', 'wep_tx_keyidx', 'pairwise', 'group', 'priority', 'scan_freq',
                        'filter_ssids',
                        'scan_ssid', 'frequency', 'freq_list', 'mode', 'eap', 'ht40_intolerant', 'bssid', 'ieee80211w']:
                if var in locals().keys() and locals()[var] != None:
                    configs += f'{var}={locals()[var]}\n'
            if isinstance(pairwise, str) and radio == '6G':
                configs += 'pairwise=CCMP\n'
            if key_mgmt == 'SAE':
                configs += 'ieee80211w=2\n'
            configs += '}'
        if wpa_conf is None:
            self.host_control.checkoutput(f'echo "{configs}" > /etc/wpa_supplicant.conf')
        else:
            tmp_conf = '/tmp/wpa_supplicant.conf'
            wpa_supplicant_conf = tmp_conf
            with open(tmp_conf, 'w') as conf:
                conf.write(wpa_conf)
        rsp = self.send_cmd(f'cat {wpa_supplicant_conf}', target)
        for i in range(retry):
            self.send_cmd(f'killall wpa_supplicant', target)
            self.send_cmd(f'wpa_supplicant -B -i {interface} -c /etc/wpa_supplicant.conf', target)
            time.sleep(5)
            for j in range(3):

                rsp = self.send_cmd(f'wpa_cli status', target)
                if rsp and ('wpa_state=COMPLETED' in rsp):
                    return True
                else:
                    if isinstance(radio, str) and radio == '6G':
                        time.sleep(30)
                    else:
                        time.sleep(5)
            else:
                return False

    def disassociate_wifi(self, target, **kwargs):
        """
        Disassociate Wi‑Fi

        Sends shell commands to the host or device and returns the output.
        Configures or controls the wpa_supplicant client for Wi‑Fi connectivity.

        Parameters
        ----------
        target : object
            Identifier indicating whether the command runs on the host or the device.
        kwargs : object
            Description of parameter 'kwargs'.

        Returns
        -------
        None
            This function does not return a value.
        """
        timeout = kwargs.get('timeout', 20)
        self.send_cmd(f'wpa_cli disconnect', target)


    def connect_wifi(self, target, **kwargs):
        """
        Connect Wi‑Fi

        Parameters
        ----------
        target : object
            Identifier indicating whether the command runs on the host or the device.
        kwargs : object
            Description of parameter 'kwargs'.

        Returns
        -------
        None
            This function does not return a value.
        """
        self.associate_wifi(target, **kwargs)
        self.flush_wlan(target)

    def forget_wifi(self, target, **kwargs):
        """
        Forget Wi‑Fi

        Parameters
        ----------
        target : object
            Identifier indicating whether the command runs on the host or the device.
        kwargs : object
            Description of parameter 'kwargs'.

        Returns
        -------
        None
            This function does not return a value.
        """
        self.disassociate_wifi(target, **kwargs)
        self.clear_wlan(target)

    def get_wifi_conn_info(self, target, **kwargs):
        """
        Get Wi‑Fi conn info

        Sends shell commands to the host or device and returns the output.
        Configures or controls the wpa_supplicant client for Wi‑Fi connectivity.

        Parameters
        ----------
        target : object
            Identifier indicating whether the command runs on the host or the device.
        kwargs : object
            Description of parameter 'kwargs'.

        Returns
        -------
        object
            Description of the returned value.
        """
        conn_info = {}
        timeout = kwargs.get('timeout', 20)
        interface = kwargs.get('interface', self.interface)
        rsp = self.send_cmd(f'wpa_cli status', target)
        rsp_line = rsp.splitlines()
        for index, line in enumerate(rsp_line):
            reg_rsp = re.findall('([^=]*)=([^\n]*)', line, re.I | re.M)
            if reg_rsp:
                conn_info[reg_rsp[0][0]] = reg_rsp[0][1]
        rsp = self.send_cmd(f'iwconfig {interface}', target)
        reg_rsp = re.findall('Access Point: (([0-9A-F]{2}:){5}[0-9A-F]{2})', rsp, re.I | re.M)
        if reg_rsp:
            conn_info['access_point'] = reg_rsp[0][0]
        reg_rsp = re.findall('Bit Rate=([0-9]{1,3})', rsp, re.I | re.M)
        if reg_rsp:
            conn_info['bit_rate'] = reg_rsp[0]
        reg_rsp = re.findall('Bit Rate:(.*) [M|G]b/s', rsp, re.I)
        if reg_rsp:
            conn_info['bit_rate'] = reg_rsp[0]
        reg_rsp = re.findall('ESSID:\"(.*)\"', rsp, re.I)
        if reg_rsp:
            conn_info['ssid'] = reg_rsp[0]
        reg_rsp = re.findall('Frequency:([0-9]+.[0-9]+) GHz', rsp, re.I)
        if reg_rsp:
            conn_info['frequency'] = reg_rsp[0]

        return conn_info

    def scan_aps(self, target, **kwargs):
        """
        Scan aps

        Sends shell commands to the host or device and returns the output.
        Configures or controls the wpa_supplicant client for Wi‑Fi connectivity.
        Waits for a specified duration to allow asynchronous operations to complete.

        Parameters
        ----------
        target : object
            Identifier indicating whether the command runs on the host or the device.
        kwargs : object
            Description of parameter 'kwargs'.

        Returns
        -------
        object
            Description of the returned value.
        """
        timeout = kwargs.get('timeout', 20)
        interface = kwargs.get('interface', self.interface)
        retry = kwargs.get('retry', 5)
        ap = kwargs.get('ap', None)
        rsp = ""

        scan_result = False
        self.send_cmd(f'killall wpa_supplicant', target)
        for i in range(retry):
            try:
                rsp = self.send_cmd(f'iw dev {interface} scan', target)
            except Exception as error:
                scan_result = False
            if ap:
                re1 = re.compile(r"{}(\b|\(|\n)".format(ap), re.I)
                if re1.search(rsp, re.I):
                    scan_result = True
                    break
                else:
                    scan_result = False
                    time.sleep(2)
            else:
                if re.search('busy|unavailable|No scan result', rsp, re.I):

                    scan_result = False
                    time.sleep(2)
                else:
                    break
        return scan_result








