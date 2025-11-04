from __future__ import annotations

import logging
import re
import time
from typing import Iterable

try:
    import serial  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    serial = None  # type: ignore

_RELAY_RELEASE = bytes([0xA0, 0x01, 0x00, 0xA1])  # A1: release
_RELAY_ENGAGE = bytes([0xA0, 0x01, 0x01, 0xA2])    # A2: engage
_DEFAULT_BAUDRATE = 9600
_DEFAULT_TIMEOUT = 1.0
_SEND_INTERVAL = 0.1
_WINDOWS_COM_PORT_PATTERN = re.compile(r"^(COM\d+)", flags=re.IGNORECASE)
_SUPPORTED_WIRING = {"NO", "NC"}


def _normalize_port_name(port: str) -> str:
    """Trim human-friendly suffixes (e.g. 'COM4 (USB-SERIAL ...)') from port names."""
    candidate = (port or "").strip()
    if not candidate:
        return candidate

    match = _WINDOWS_COM_PORT_PATTERN.match(candidate)
    if match:
        return match.group(1).upper()

    if "(" in candidate:
        candidate = candidate.split("(", 1)[0].strip()
    if " " in candidate:
        candidate = candidate.split(" ", 1)[0]
    return candidate


class UsbRelayDevice:
    def __init__(self, port: str, *, baudrate: int = _DEFAULT_BAUDRATE, timeout: float = _DEFAULT_TIMEOUT) -> None:
        self.raw_port = (port or "").strip()
        self.port = _normalize_port_name(self.raw_port)
        self.baudrate = baudrate
        self.timeout = timeout
        self._serial = None
        if self.raw_port and self.port and self.raw_port != self.port:
            logging.debug("Normalized USB relay port from %s to %s", self.raw_port, self.port)

    def open(self) -> None:
        if self._serial is not None or serial is None:
            return
        try:
            self._serial = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
        except Exception as exc:  # pragma: no cover - depends on environment
            port_label = self.port
            if self.raw_port and self.raw_port != self.port:
                port_label = f"{self.port} (from {self.raw_port})"
            logging.error("Failed to open USB relay port %s: %s", port_label, exc)
            raise

    def close(self) -> None:
        if self._serial is not None:
            try:
                self._serial.close()
            finally:
                self._serial = None

    def __enter__(self) -> "UsbRelayDevice":
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def send(self, command: bytes) -> None:
        if serial is None:
            raise RuntimeError("pyserial is required for USB relay control")
        if self._serial is None:
            self.open()
        assert self._serial is not None
        self._serial.write(command)
        self._serial.flush()

    def send_sequence(self, commands: Iterable[bytes], *, interval: float = _SEND_INTERVAL) -> None:
        for command in commands:
            self.send(command)
            time.sleep(max(0.0, interval))


def _normalize_wiring(mode: str) -> str:
    wiring = (mode or "NO").strip().upper()
    if wiring not in _SUPPORTED_WIRING:
        logging.warning("Unknown wiring mode %s, defaulting to NO", mode)
        return "NO"
    return wiring


def _command_for_coil_state(desired_state: str) -> bytes:
    desired = desired_state.lower()
    if desired == "on":
        return _RELAY_ENGAGE
    if desired == "off":
        return _RELAY_RELEASE
    raise ValueError(f"Unsupported relay state: {desired_state}")


def _describe_contact_state(wiring: str, coil_engaged: bool) -> str:
    if wiring == "NO":
        return "closed" if coil_engaged else "open"
    # wiring == "NC"
    return "open" if coil_engaged else "closed"


def apply_state(device: UsbRelayDevice, mode: str, desired_state: str) -> None:
    """Set the relay coil explicitly to on (engaged) or off (released).

    For `mode="NO"` a coil engagement closes the contact; for `mode="NC"` it opens it.
    The command bytes match the USB protocol directly (01 -> engage, 00 -> release).
    """
    wiring = _normalize_wiring(mode)
    command = _command_for_coil_state(desired_state)
    coil_engaged = command == _RELAY_ENGAGE
    logging.debug(
        "Relay wiring=%s -> coil %s (contact %s)",
        wiring,
        "engaged" if coil_engaged else "released",
        _describe_contact_state(wiring, coil_engaged),
    )
    device.send_sequence((command,), interval=0.0)


def pulse(device: UsbRelayDevice, mode: str, press_seconds: float | None = None) -> None:
    """Simulate a short button tap by energising the coil then releasing it."""
    wiring = _normalize_wiring(mode)
    hold = _SEND_INTERVAL if press_seconds is None else max(0.0, press_seconds)
    logging.debug(
        "Relay pulse wiring=%s hold=%ss (contact presses %s)",
        wiring,
        hold,
        _describe_contact_state(wiring, True),
    )
    device.send_sequence((_RELAY_ENGAGE,), interval=0.0)
    if hold > 0.0:
        time.sleep(hold)
    device.send_sequence((_RELAY_RELEASE,), interval=0.0)


def long_press(device: UsbRelayDevice, mode: str, hold_seconds: float) -> None:
    """Hold the button for the requested duration before releasing the relay."""
    wiring = _normalize_wiring(mode)
    hold = max(0.0, hold_seconds)
    logging.debug(
        "Relay long-press wiring=%s hold=%ss (contact presses %s)",
        wiring,
        hold,
        _describe_contact_state(wiring, True),
    )
    device.send_sequence((_RELAY_ENGAGE,), interval=0.0)
    time.sleep(hold)
    device.send_sequence((_RELAY_RELEASE,), interval=0.0)
