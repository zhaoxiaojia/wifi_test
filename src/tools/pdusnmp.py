"""High-level control interfaces for SNMP-based power distribution units.

This module provides a simple wrapper around SNMP commands to control power
relays. It exposes a :class:`power_ctrl` class that reads configuration
information, constructs SNMP command strings and executes them using
``subprocess``.  All function and method arguments are documented in a
``Parameters`` section.
"""
import logging
import subprocess

from src.tools.config_loader import load_config


class power_ctrl:
    """Encapsulate control of power relays using SNMP via shell commands.

    Instances of this class read relay configuration from a configuration
    loader and provide methods to switch individual ports on or off as well
    as to change the state of all configured relays at once.  Commands are
    executed via :func:`subprocess.check_output` and log their output.

    The command templates stored in :attr:`SWITCH_CMD` and :attr:`SET_CMD`
    include placeholders for the target IP, port number and desired state.
    """

    SWITCH_CMD = 'snmpset -v1 -c private {} .1.3.6.1.4.1.23280.9.1.2.{} i {}'
    SET_CMD = 'snmpset -v1 -c private {} 1.3.6.1.4.1.23273.4.4{}.0 i 255'

    def __init__(self) -> None:
        """Initialize the power control object from configuration.

        The constructor loads power relay configuration using
        :func:`load_config` and precomputes a list of (IP, port) tuples from
        that configuration.
        """
        self.config = load_config(refresh=True)
        self.power_ctrl = self.config.get('power_relay')
        self.ip_list = list(self.power_ctrl.keys())
        self.ctrl = self._handle_env_data()

    def _handle_env_data(self) -> list[tuple[str, int]]:
        """Flatten the configuration into a list of (IP, port) tuples.

        Returns:
            list[tuple[str, int]]: A list of tuples where each tuple contains
            an IP address and an integer port number defined in the configuration.
        """
        temp: list[tuple[str, int]] = []
        for k, v in self.power_ctrl.items():
            if v:
                for i in v:
                    temp.append((k, i))
        return temp

    @staticmethod
    def check_output(cmd: str) -> bytes | None:
        """Run a shell command and log its output.

        Parameters:
            cmd (str): The command string to execute via the shell.

        Returns:
            bytes | None: The raw command output if execution succeeded,
            otherwise ``None``.
        """
        try:
            info = subprocess.check_output(cmd, shell=True)
            logging.info(info)
            return info
        except subprocess.CalledProcessError as e:
            logging.error(f"Command failed: {e}")
            return None

    def switch(self, ip: str, port: int, status: int) -> None:
        """Toggle an individual relay on or off.

        Parameters:
            ip (str): The IP address of the relay device.
            port (int): The port number on the relay device to control.
            status (int): ``1`` to turn the port on, ``0`` or ``2`` to turn
                it off depending on the underlying SNMP semantics.

        Returns:
            None
        """
        logging.info(
            f'Setting power relay: {ip} port {port} {"on" if status == 1 else "off"}'
        )
        cmd = self.SWITCH_CMD.format(ip, port, status)
        self.check_output(cmd)

    def set_all(self, status: bool) -> None:
        """Set all configured relays to the given state.

        Parameters:
            status (bool): ``True`` to power on all relays or ``False`` to shut
                them down.  The SNMP command is constructed accordingly.

        Returns:
            None
        """
        for k in ['192.168.200.3', '192.168.200.4', '192.168.200.5', '192.168.200.6']:
            cmd = self.SET_CMD.format(k, 0 if status else 1)
            self.check_output(cmd)

    def shutdown(self) -> None:
        """Shut down all relays via SNMP.

        Returns:
            None
        """
        logging.info('Shutting down all relays')
        self.set_all(False)

# s = PowerCtrl("192.168.50.230")
# s.switch(2, True)
# s.dark()
# s.survival(1)
# print(s.get_status(1))
# time.sleep(1)
# print("start on")
# s.switch(1, True)
# print(s.get_status(2))

# s = power_ctrl()
# s.switch('192.168.200.4',4,1)
