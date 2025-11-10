#!/usr/bin/env python
# encoding: utf-8
"""Utility for controlling Wi‑Fi connectivity on Roku devices via wpa_supplicant.

This module defines a :class:`roku_wpa` class that abstracts common tasks
when managing Wi‑Fi connections on a Roku device under test.  It wraps an
executor object (typically a serial or telnet session) that provides
``write`` and ``recv`` methods for sending commands and reading their
output.  The class supports scanning for running wpa_supplicant
processes, killing or restarting them by type, generating and writing
wpa_supplicant configuration files for various authentication schemes,
bringing network interfaces up or down, obtaining IP addresses via DHCP
or static assignment, and orchestrating full connection attempts with
automatic retries and status polling.  Methods return results where
appropriate, log progress to the :mod:`logging` subsystem and handle
timeouts gracefully.
"""

import time
import re
import logging


class roku_wpa:
    """Manager for wpa_supplicant processes on a Roku device.

    Instances of this class interact with a remote Roku device via an
    executor object that must implement a ``write`` method to send shell
    commands and a ``recv`` method to read command output.  The class
    keeps track of running wpa_supplicant processes, categorises them as
    ``ui``, ``script`` or ``unknown`` based on configurable path
    signatures, and provides helpers to kill, restart and query those
    processes.  It also encapsulates generating wpa_supplicant
    configuration files for various security modes (open, WPA, WPA2,
    WPA3, enterprise), manages network interfaces, assigns IP addresses
    via DHCP or static configuration, and implements a high‑level
    connection routine with automatic retries and status polling.
    """

    def __init__(self, executor, ui_signature: str | None = None, script_signature: str | None = None) -> None:
        """Create a new :class:`roku_wpa` controller.

        Parameters
        ----------
        executor:
            An object exposing at least two methods:

            * ``write(cmd: str) -> None`` – Sends a command string to the
              remote device.
            * ``recv() -> str`` – Retrieves the accumulated output from
              previously issued commands.

            For example, this could be a serial port wrapper such as
            ``pytest.dut.roku.ser`` or a custom class providing the same
            interface.
        ui_signature:
            Path fragment that identifies wpa_supplicant processes
            associated with the Roku UI.  Defaults to
            ``'/etc/wpa-supp.conf'``; if provided, any running process
            whose command line contains this string will be categorised
            as type ``ui``.
        script_signature:
            Path fragment that identifies wpa_supplicant processes
            launched via generated configuration scripts.  Defaults to
            ``'/tmp/wpa_supplicant.conf'``; if provided, any running
            process whose command line contains this string will be
            categorised as type ``script``.

        Side Effects
        ------------
        Sets instance attributes ``executor``, ``ui_signature``,
        ``script_signature`` and initialises an empty ``process_list`` to
        track discovered processes.

        Returns
        -------
        None
        """
        self.executor = executor
        # Default location of the UI configuration file; used to
        # categorise wpa_supplicant processes as 'ui'.
        self.ui_signature = ui_signature or '/etc/wpa-supp.conf'
        # Default location of the script‑generated configuration file;
        # used to categorise wpa_supplicant processes as 'script'.
        self.script_signature = script_signature or '/tmp/wpa_supplicant.conf'
        # List of dictionaries capturing PID, command line and type of
        # currently running wpa_supplicant processes.
        self.process_list: list[dict[str, str]] = []

    def refresh_process_list(self):
        """Populate the internal list of running wpa_supplicant processes.

        Issues a ``ps`` command via the executor to list all running
        processes and filters for those whose command line contains
        ``wpa_supplicant``.  Each matching process line is parsed into
        a dictionary containing its PID, full command line, and a type
        classification based on whether the command line includes
        :attr:`ui_signature` (labelled ``ui``), :attr:`script_signature`
        (labelled ``script``) or neither (labelled ``unknown``).  The
        resulting dictionaries are appended to :attr:`process_list`.

        Returns
        -------
        None
        """
        # Clear any previous state to avoid stale entries
        self.process_list.clear()
        # Use ps to list all processes and filter on wpa_supplicant
        self.executor.write("ps -A -o pid,cmd | grep 'wpa_supplicant'")
        ps_out = self.executor.recv()
        for line in ps_out.splitlines():
            line = line.strip()
            if not line or "grep" in line:
                continue
            parts = line.split(None, 1)
            if len(parts) == 2:
                pid, cmdline = parts
                # Determine type based on configured signatures
                if self.ui_signature and self.ui_signature in cmdline:
                    proc_type = "ui"
                elif self.script_signature and self.script_signature in cmdline:
                    proc_type = "script"
                else:
                    proc_type = "unknown"
                self.process_list.append({"pid": pid, "cmdline": cmdline, "type": proc_type})

    def kill_by_type(self, proc_type):
        """Terminate all wpa_supplicant processes of a given type.

        After refreshing the process list, iterates through each entry and
        issues a ``kill`` command for processes whose ``type`` field
        matches ``proc_type``.  Each terminated process is logged with
        its PID and command line.  If no processes of the requested
        type are found, a notice is logged.  A brief delay is inserted
        after each kill to allow the system to clean up.

        Parameters
        ----------
        proc_type:
            The category of process to terminate.  Supported values are
            ``'ui'``, ``'script'`` or ``'unknown'``.

        Returns
        -------
        None
        """
        self.refresh_process_list()
        killed = []
        for proc in self.process_list:
            if proc["type"] == proc_type:
                self.executor.write(f"kill {proc['pid']}")
                killed.append(proc)
                logging.info("[KILL] %s: PID=%s CMD=%s", proc_type, proc['pid'], proc['cmdline'])
                time.sleep(0.5)
        if not killed:
            logging.info("No %s wpa_supplicant to kill", proc_type)

    def restart_ui_wpa(self, proc_type):
        """Restart previously discovered wpa_supplicant processes of a given type.

        This method first kills all wpa_supplicant processes of type
        ``script`` to ensure no conflicting instances remain.  It then
        iterates over the cached :attr:`process_list` and re‑launches
        each process whose ``type`` matches ``proc_type`` by issuing its
        original command line in the background.  Each restart is
        logged, and a delay is inserted to allow the process to settle.

        Parameters
        ----------
        proc_type:
            The category of process to restart.  Typically ``'ui'`` to
            restart the UI's wpa_supplicant processes.

        Returns
        -------
        None
        """
        # Kill all script processes to avoid duplicates
        self.kill_by_type('script')
        # Relaunch each process of the specified type
        for proc in self.process_list:
            if proc["type"] == proc_type:
                cmd = proc["cmdline"]
                self.executor.write(cmd + " &")
                logging.info("[RESTART] %s: %s", proc_type, cmd)
                time.sleep(1)

    def restart_interface(self, iface='wlan0'):
        """Bounce a network interface down and up.

        Sends ``ip link set <iface> down`` followed by ``ip link set
        <iface> up`` to the remote device, with short delays between
        commands.  This can help reset the wireless interface before
        establishing a new connection.

        Parameters
        ----------
        iface:
            Name of the network interface to cycle.  Defaults to
            ``'wlan0'``.

        Returns
        -------
        None
        """
        self.executor.write(f"ip link set {iface} down")
        time.sleep(0.5)
        self.executor.write(f"ip link set {iface} up")
        time.sleep(1)

    def make_ctrl_dir(self, path='/tmp/wpa_supplicant'):
        """Create the control directory for wpa_supplicant if missing.

        Issues a ``mkdir -p`` command to ensure that the specified
        directory exists on the remote device.  The control directory is
        used by wpa_supplicant for its control sockets and status files.

        Parameters
        ----------
        path:
            Filesystem path to create.  Defaults to ``'/tmp/wpa_supplicant'``.

        Returns
        -------
        None
        """
        self.executor.write(f"mkdir -p {path}")

    def create_conf(self, ssid, auth_type="WPA2-PSK", psk=None, eap=None, identity=None, password=None,
                    key_mgmt=None, proto=None, ieee80211w=None, pairwise=None, group=None, pmf=None,
                    priority=None, conf_path='/tmp/wpa_supplicant.conf'):
        """Generate and write a wpa_supplicant configuration file.

        Constructs a ``network={...}`` block appropriate for the given
        authentication type and writes it to a configuration file on the
        remote device via a ``cat <<EOF`` heredoc.  The method supports
        open networks, WPA/WPA2 personal, WPA3 (SAE), and WPA enterprise
        authentication.  Optional parameters are inserted only if they
        are provided to avoid duplicating fields.  A ``priority`` can be
        assigned to influence wpa_supplicant's network selection order.

        Parameters
        ----------
        ssid:
            Name of the Wi‑Fi network to connect to.
        auth_type:
            Authentication type for the network.  Supported values
            include ``"OPEN"``, ``"NONE"``, ``"WPA-PSK"``, ``"WPA2-PSK"``,
            ``"WPA3-SAE"``, and ``"WPA-EAP"`` (enterprise).
        psk:
            Pre‑shared key for WPA/WPA2/WPA3 networks, if required.
        eap:
            EAP method for enterprise authentication, e.g., ``"PEAP"``.
        identity:
            User identity/username for enterprise authentication.
        password:
            Password associated with ``identity`` for enterprise auth.
        key_mgmt, proto, ieee80211w, pairwise, group, pmf:
            Advanced wpa_supplicant options for key management, protocol,
            management frame protection and cipher suites.  These are
            included only if provided.
        priority:
            Integer priority assigned to the network; higher values take
            precedence when multiple networks are defined.
        conf_path:
            Destination path on the remote device where the generated
            configuration file will be written.  Defaults to
            ``'/tmp/wpa_supplicant.conf'``.

        Returns
        -------
        None
        """
        network_lines = [f'    ssid="{ssid}"']

        # Open
        if auth_type.upper() in ["OPEN", "NONE"]:
            network_lines.append('    key_mgmt=NONE')

        # WPA-PSK/WPA2-PSK
        elif auth_type.upper() in ["WPA-PSK", "WPA2-PSK"]:
            network_lines.append(f'    psk="{psk}"')
            network_lines.append('    key_mgmt=WPA-PSK')
            if ieee80211w is not None:
                network_lines.append(f'    ieee80211w={ieee80211w}')
            if pmf:
                network_lines.append(f'    pmf={pmf}')

        # WPA3-SAE
        elif auth_type.upper() == "WPA3-SAE":
            network_lines.append(f'    psk="{psk}"')
            network_lines.append('    key_mgmt=SAE')
            network_lines.append('    ieee80211w=2')  # 强制开启管理帧保护
            if pmf:
                network_lines.append(f'    pmf={pmf}')

        # WPA-EAP
        elif auth_type.upper() == "WPA-EAP":
            network_lines.append('    key_mgmt=WPA-EAP')
            if eap:
                network_lines.append(f'    eap={eap}')
            if identity:
                network_lines.append(f'    identity="{identity}"')
            if password:
                network_lines.append(f'    password="{password}"')
            if ieee80211w is not None:
                network_lines.append(f'    ieee80211w={ieee80211w}')
            if pmf:
                network_lines.append(f'    pmf={pmf}')

        # 通用扩展字段（避免重复）
        if key_mgmt and f'key_mgmt={key_mgmt}' not in network_lines:
            network_lines.append(f'    key_mgmt={key_mgmt}')
        if proto:
            network_lines.append(f'    proto={proto}')
        if pairwise:
            network_lines.append(f'    pairwise={pairwise}')
        if group:
            network_lines.append(f'    group={group}')
        if priority is not None:
            network_lines.append(f'    priority={priority}')

        network_block = "network={\n" + "\n".join(network_lines) + "\n}"

        conf = f"""ctrl_interface=/tmp/wpa_supplicant
update_config=1

{network_block}
    """
        cmd = f"cat > {conf_path} <<EOF\n{conf}\nEOF"
        self.executor.write(cmd)

    def start_wpa_supplicant(self, iface='wlan0', conf='/tmp/wpa_supplicant.conf', debug=False):
        """Launch wpa_supplicant in the background on the remote device.

        Parameters
        ----------
        iface:
            Network interface to bind wpa_supplicant to.  Defaults to
            ``'wlan0'``.
        conf:
            Path to the wpa_supplicant configuration file on the remote
            device.  Defaults to ``'/tmp/wpa_supplicant.conf'``.
        debug:
            If ``True``, pass the ``-d`` option to enable verbose
            debugging output from wpa_supplicant.

        Returns
        -------
        None
        """
        log_opt = "-d" if debug else ""
        self.executor.write(f"wpa_supplicant -i {iface} -c {conf} -B {log_opt} ")

    def run_udhcpc(self, iface='wlan0'):
        """Invoke the BusyBox DHCP client to obtain an IP address.

        Parameters
        ----------
        iface:
            Network interface to run the DHCP client on.  Defaults to
            ``'wlan0'``.

        Returns
        -------
        None
        """
        self.executor.write(f"udhcpc -i {iface}")

    def set_static_ip(self, iface, ip, mask='255.255.255.0'):
        """Assign a static IP address to an interface.

        Parameters
        ----------
        iface:
            Name of the network interface to configure.
        ip:
            IP address to assign.
        mask:
            Netmask to use.  Defaults to ``'255.255.255.0'``.

        Returns
        -------
        None
        """
        self.executor.write(f"ifconfig {iface} {ip} netmask {mask} up")

    def status_check(self, iface='wlan0'):
        """Query the current status of wpa_supplicant.

        Returns the result of running ``wpa_cli status`` on the remote
        device for the specified interface.  The output contains key
        fields such as ``wpa_state``, ``ssid``, ``ip_address`` and
        ``bssid``.

        Parameters
        ----------
        iface:
            Interface name to query.  Defaults to ``'wlan0'``.

        Returns
        -------
        str
            The raw status text returned by the executor.
        """
        return self.executor.write(f"wpa_cli -i {iface} -p /tmp/wpa_supplicant status")

    def scan_network(self, iface='wlan0'):
        """Perform a Wi‑Fi scan and return the results.

        Initiates a scan via ``wpa_cli scan``, waits for a short
        interval to allow the scan to complete, and then retrieves the
        results using ``wpa_cli scan_results``.

        Parameters
        ----------
        iface:
            Interface on which to perform the scan.  Defaults to
            ``'wlan0'``.

        Returns
        -------
        str
            The raw scan results returned by the executor.
        """
        self.executor.write(f"wpa_cli -i {iface} -p /tmp/wpa_supplicant scan")
        time.sleep(3)
        return self.executor.write(f"wpa_cli -i {iface} -p /tmp/wpa_supplicant scan_results")

    def get_ip(self, iface='wlan0'):
        """Retrieve the current IP configuration for an interface.

        Parameters
        ----------
        iface:
            Name of the network interface.  Defaults to ``'wlan0'``.

        Returns
        -------
        str
            The output of the ``ifconfig`` command, containing IP
            address, netmask and other details.
        """
        return self.executor.write(f"ifconfig {iface}")

    def ping_test(self, target='8.8.8.8', count=4):
        """Perform an ICMP ping test to a target host.

        Parameters
        ----------
        target:
            Destination host or IP address to ping.  Defaults to
            ``'8.8.8.8'`` (Google Public DNS).
        count:
            Number of echo requests to send.  Defaults to ``4``.

        Returns
        -------
        str
            The ping command output.
        """
        return self.executor.write(f"ping -c {count} {target}")

    def cleanup(self):
        """Terminate all wpa_supplicant instances and remove temporary files.

        Invokes :meth:`kill_wifi_process` to terminate running
        wpa_supplicant processes (not implemented in this snippet but
        assumed to exist in the executor's environment), deletes the
        generated configuration file and removes the control directory.

        Returns
        -------
        None
        """
        self.kill_wifi_process()
        self.executor.write("rm -f /tmp/wpa_supplicant.conf")
        self.executor.write("rm -rf /tmp/wpa_supplicant")

    def disconnect(self, iface='wlan0'):
        """Disconnect from the current Wi‑Fi network.

        Parameters
        ----------
        iface:
            Interface name.  Defaults to ``'wlan0'``.

        Returns
        -------
        None
        """
        self.executor.write(f"wpa_cli -i {iface} -p /tmp/wpa_supplicant disconnect")

    def reconnect(self, iface='wlan0'):
        """Reconnect to the previously configured Wi‑Fi network.

        Parameters
        ----------
        iface:
            Interface name.  Defaults to ``'wlan0'``.

        Returns
        -------
        None
        """
        self.executor.write(f"wpa_cli -i {iface} -p /tmp/wpa_supplicant reconnect")

    def list_networks(self, iface='wlan0'):
        """List all networks currently configured in wpa_supplicant.

        Parameters
        ----------
        iface:
            Interface name.  Defaults to ``'wlan0'``.

        Returns
        -------
        str
            The raw output from ``wpa_cli list_networks``.
        """
        return self.executor.write(f"wpa_cli -i {iface} -p /tmp/wpa_supplicant list_networks")

    def forget(self, iface='wlan0', net_id=None):
        """Remove one or all configured networks from wpa_supplicant.

        Parameters
        ----------
        iface:
            Interface on which to operate.  Defaults to ``'wlan0'``.
        net_id:
            Identifier of the network to remove.  If ``None``, all
            configured networks are removed.

        Returns
        -------
        None
        """
        if net_id is None:
            self.executor.write(f"wpa_cli -i {iface} -p /tmp/wpa_supplicant remove_network all")
        else:
            self.executor.write(f"wpa_cli -i {iface} -p /tmp/wpa_supplicant remove_network {net_id}")
        self.executor.write(f"wpa_cli -i {iface} -p /tmp/wpa_supplicant save_config")

    def select_network(self, iface='wlan0', net_id=0):
        """Select a configured network for connection.

        Parameters
        ----------
        iface:
            Interface name.  Defaults to ``'wlan0'``.
        net_id:
            Numeric identifier returned by ``list_networks``.  Defaults
            to ``0``.

        Returns
        -------
        None
        """
        self.executor.write(f"wpa_cli -i {iface} -p /tmp/wpa_supplicant select_network {net_id}")

    def set_default_route(self, gw='192.168.1.1', iface='wlan0'):
        """Configure the default gateway for an interface.

        Removes any existing default route associated with the specified
        interface and adds a new default route via the provided gateway.

        Parameters
        ----------
        gw:
            IP address of the default gateway.  Defaults to
            ``'192.168.1.1'``.
        iface:
            Interface name.  Defaults to ``'wlan0'``.

        Returns
        -------
        None
        """
        # Delete existing default route to avoid conflicts
        self.executor.write(f"ip route del default dev {iface}")
        # Add new default route
        self.executor.write(f"ip route add default via {gw} dev {iface}")

    def wait_for_state(self, iface='wlan0', target_state='COMPLETED', timeout=75, interval=5):
        """Poll wpa_supplicant until a target state is reached or timeout expires.

        Repeatedly queries ``wpa_cli status`` at ``interval`` seconds
        until the ``wpa_state`` field equals ``target_state`` or the
        ``timeout`` (in seconds) is reached.  Logs intermediate states
        and returns ``True`` on success.  If the timeout is exceeded
        without reaching the target state, logs an error and returns
        ``False``.

        Parameters
        ----------
        iface:
            Interface to query.  Defaults to ``'wlan0'``.
        target_state:
            Desired ``wpa_state`` value to wait for.  Defaults to
            ``'COMPLETED'``.
        timeout:
            Maximum time to wait in seconds.  Defaults to ``75``.
        interval:
            Delay between polls in seconds.  Defaults to ``5``.

        Returns
        -------
        bool
            ``True`` if the target state is reached before timeout,
            ``False`` otherwise.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            self.executor.write(f"wpa_cli -i {iface} -p /tmp/wpa_supplicant status")
            status = self.executor.recv()
            m = re.search(r'wpa_state=(\w+)', status)
            if m:
                curr = m.group(1)
                if curr == target_state:
                    logging.info("State reached %s", target_state)
                    return True
                else:
                    logging.info("Current state: %s, waiting...", curr)
            else:
                logging.warning("State field not detected, waiting...")
            time.sleep(interval)
        logging.error("Timeout waiting for state %s", target_state)
        return False

    def is_ip_in_use(self, ip, iface='wlan0'):
        """Check whether an IP address is currently in use on the network.

        Sends a single ICMP echo request to the specified IP via the
        given interface.  If a response is received the function
        returns ``True`` indicating that the IP is occupied; otherwise
        ``False``.

        Parameters
        ----------
        ip:
            The IP address to test.
        iface:
            Interface from which to send the ping.  Defaults to
            ``'wlan0'``.

        Returns
        -------
        bool
            ``True`` if the IP responds to a ping; ``False`` otherwise.
        """
        # Send a single ping via the specified interface
        self.executor.write(f"ping -c 1 -w 2 -I {iface} {ip}")
        result = self.executor.recv()
        return "1 received" in result or "bytes from" in result

    def set_available_static_ip(self, iface='wlan0', ip_pool=None, mask='255.255.255.0', gw='192.168.1.1'):
        """Assign the first available static IP from a candidate pool.

        Iterates through a list of candidate IP addresses and returns
        the first one that is not in use on the network.  Once a free
        address is found, it calls :meth:`set_static_ip` and
        :meth:`set_default_route` to configure the interface and logs
        the assignment.  If all addresses are in use, logs an error and
        returns ``None``.

        Parameters
        ----------
        iface:
            Interface to configure.  Defaults to ``'wlan0'``.
        ip_pool:
            Iterable of candidate IP addresses.  If ``None``, a default
            pool of ``192.168.1.200`` through ``192.168.1.250`` is used.
        mask:
            Netmask to apply to the selected IP.  Defaults to
            ``'255.255.255.0'``.
        gw:
            Default gateway to set once the IP is configured.  Defaults
            to ``'192.168.1.1'``.

        Returns
        -------
        str | None
            The IP address that was assigned, or ``None`` if none were
            available.
        """
        ip_pool = ip_pool or [f"192.168.1.{i}" for i in range(200, 251)]
        for ip in ip_pool:
            if not self.is_ip_in_use(ip, iface=iface):
                self.set_static_ip(iface, ip, mask)
                self.set_default_route(gw=gw, iface=iface)
                logging.info("Static IP set successfully: %s", ip)
                return ip
            else:
                logging.warning("IP %s is in use, trying next...", ip)
        logging.error("No available static IP, please check router allocation")
        return None

    def connect(self, ssid, auth_type="WPA2-PSK", psk=None, eap=None, identity=None, password=None,
                key_mgmt=None, proto=None, ieee80211w=None, pairwise=None, group=None, pmf=None,
                gw=None, mask='255.255.255.0', dhcp=False, iface='wlan0', priority=None,
                max_retry=3, wait_connect=5, state_timeout=75, retry_interval=2):
        """Attempt to connect to a Wi‑Fi network with retries and status checks.

        This high‑level convenience method encapsulates the full workflow
        for connecting to a network: killing existing UI processes,
        creating a wpa_supplicant configuration, starting
        wpa_supplicant, waiting for the desired state, obtaining an IP
        address (via DHCP or static assignment), and restarting UI
        processes.  It retries the entire sequence up to ``max_retry``
        times, waiting ``retry_interval`` seconds between attempts.

        Parameters
        ----------
        ssid:
            The SSID of the network to join.
        auth_type, psk, eap, identity, password, key_mgmt, proto,
        ieee80211w, pairwise, group, pmf, priority:
            Passed through to :meth:`create_conf` to build the
            configuration file.
        gw:
            Default gateway to configure when using static IP.  If
            ``None``, no default route is set explicitly.  Defaults
            to ``None``.
        mask:
            Netmask to use for static IP assignment.  Defaults to
            ``'255.255.255.0'``.
        dhcp:
            If ``True``, run DHCP after connecting; otherwise assign
            a static IP via :meth:`set_available_static_ip`.
        iface:
            Interface on which to perform the connection.  Defaults
            to ``'wlan0'``.
        priority:
            Priority assigned to the network; forwarded to
            :meth:`create_conf`.
        max_retry:
            Maximum number of connection attempts.  Defaults to ``3``.
        wait_connect:
            Seconds to wait after starting wpa_supplicant before
            checking connection state.  Defaults to ``5``.
        state_timeout:
            Maximum time in seconds to wait for the ``COMPLETED`` state
            in each attempt.  Defaults to ``75``.
        retry_interval:
            Delay between retries in seconds.  Defaults to ``2``.

        Returns
        -------
        str | None
            The output of :meth:`status_check` on success; ``None`` if
            all connection attempts failed.
        """
        for attempt in range(1, max_retry + 1):
            logging.info("Attempt %d to connect %s", attempt, ssid)
            self.kill_by_type("ui")
            self.make_ctrl_dir()
            self.create_conf(ssid, auth_type, psk, eap, identity, password,
                             key_mgmt, proto, ieee80211w, pairwise, group, pmf, priority)
            self.start_wpa_supplicant(iface=iface, debug=False)
            time.sleep(wait_connect)
            ok = self.wait_for_state(iface=iface, target_state='COMPLETED', timeout=state_timeout)
            if ok:
                if dhcp:
                    self.run_udhcpc(iface=iface)
                else:
                    self.set_available_static_ip()
                    self.set_default_route(gw=gw)
                logging.info("Attempt %d connection succeeded", attempt)
                time.sleep(3)
                self.restart_ui_wpa('ui')
                return self.status_check(iface=iface)
            else:
                logging.warning(
                    "Attempt %d connection failed, retrying in %d seconds...",
                    attempt,
                    retry_interval,
                )
                time.sleep(retry_interval)
                self.kill_by_type("script")
        logging.error("Connection to %s failed after multiple attempts", ssid)
        time.sleep(3)
        self.restart_ui_wpa('ui')
        return None


if __name__ == '__main__':
    from src.tools import serial_tool

    ser = serial_tool("COM4", 115200)
    wpa = roku_wpa(ser)
    wpa.connect("_coco", psk='12345678', priority=1, gw='192.168.1.1')
