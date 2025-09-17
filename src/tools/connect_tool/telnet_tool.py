# -*- coding: utf-8 -*-
"""
同步 Telnet 客户端，实现最小接口以兼容旧的测试逻辑。
"""
import logging
import subprocess
import telnetlib
import threading
import time
from typing import Optional, Union

from src.tools.connect_tool.dut import dut


BytesLike = Union[str, bytes]


class TelnetTool(dut):
    """同步 Telnet 实现，供路由器、实验室设备等场景复用。"""

    DEFAULT_PORT = 23
    DEFAULT_TIMEOUT = 5.0
    READ_INTERVAL = 0.1

    def __init__(
        self,
        ip: str,
        default_wildcard: BytesLike | None = None,
        *,
        port: int = DEFAULT_PORT,
        timeout: float = DEFAULT_TIMEOUT,
        encoding: str = "utf-8",
    ) -> None:
        super().__init__()
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.encoding = encoding
        self._default_wildcard = self._ensure_bytes(default_wildcard) if default_wildcard else None
        self.tn: Optional[telnetlib.Telnet] = None
        self._lock = threading.RLock()
        logging.info("*" * 80)
        logging.info(f"* Telnet {self.ip}")
        logging.info("*" * 80)

    # ------------------------------------------------------------------
    # 基础能力
    # ------------------------------------------------------------------
    def _ensure_bytes(self, value: BytesLike | None) -> bytes:
        if value is None:
            return b""
        if isinstance(value, bytes):
            return value
        return value.encode(self.encoding, errors="ignore")

    def _decode(self, data: bytes) -> str:
        return data.decode(self.encoding, errors="ignore").strip()

    def is_connected(self) -> bool:
        return self.tn is not None and getattr(self.tn, "sock", None)

    def connect(self) -> None:
        with self._lock:
            if self.is_connected():
                return
            if self.tn:
                try:
                    self.tn.close()
                except Exception as exc:  # pragma: no cover - 关闭异常仅记录
                    logging.debug(f"Telnet close error before reconnect: {exc}")
            self.tn = None
            try:
                self.tn = telnetlib.Telnet(self.ip, self.port, self.timeout)
            except Exception as exc:  # pragma: no cover - 连接异常仅记录
                logging.error(f"Telnet connect failed: {exc}")
                self.tn = None

    def close(self) -> None:
        with self._lock:
            if self.tn:
                try:
                    self.tn.close()
                except Exception as exc:  # pragma: no cover - 关闭异常仅记录
                    logging.debug(f"Telnet close error: {exc}")
            self.tn = None

    def __del__(self) -> None:  # pragma: no cover - 析构兜底
        try:
            self.close()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Telnet 操作
    # ------------------------------------------------------------------
    def login(self, username: str, password: str, prompt: BytesLike) -> None:
        prompt_bytes = self._ensure_bytes(prompt)
        with self._lock:
            self.connect()
            if not self.is_connected():
                raise ConnectionError("Telnet login error: no connection")
            tn = self.tn
            assert tn is not None  # for type checker
            tn.read_until(b"login:", timeout=self.timeout)
            tn.write(self._ensure_bytes(username) + b"\n")
            tn.read_until(b"Password:", timeout=self.timeout)
            tn.write(self._ensure_bytes(password) + b"\n")
            if prompt_bytes:
                tn.read_until(prompt_bytes, timeout=self.timeout)

    def _clear_buffer_locked(self) -> None:
        tn = self.tn
        if not tn:
            return
        try:
            tn.read_very_eager()
        except EOFError:
            self._handle_disconnect_locked()

    def _handle_disconnect_locked(self) -> None:
        if self.tn:
            try:
                self.tn.close()
            except Exception:  # pragma: no cover - 关闭异常不影响流程
                pass
        self.tn = None

    def _read_until_quiet_locked(self) -> bytes:
        tn = self.tn
        if not tn:
            return b""
        output: list[bytes] = []
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                chunk = tn.read_very_eager()
            except EOFError:
                self._handle_disconnect_locked()
                break
            if chunk:
                output.append(chunk)
                deadline = time.monotonic() + self.READ_INTERVAL
            elif time.monotonic() >= deadline:
                break
            else:
                time.sleep(self.READ_INTERVAL)
        return b"".join(output)

    def checkoutput(self, cmd: str, wildcard: BytesLike | None = "") -> str:
        attempt = 0
        while attempt < 2:
            with self._lock:
                self.connect()
                if not self.is_connected():
                    return ""
                tn = self.tn
                assert tn is not None
                try:
                    self._clear_buffer_locked()
                    tn.write(self._ensure_bytes(cmd) + b"\n")
                    time.sleep(self.READ_INTERVAL)
                    wildcard_bytes = self._ensure_bytes(wildcard) if wildcard else self._default_wildcard
                    if wildcard_bytes:
                        data = tn.read_until(wildcard_bytes, timeout=self.timeout)
                    else:
                        data = self._read_until_quiet_locked()
                    return self._decode(data)
                except EOFError as exc:
                    logging.warning(f"Telnet command '{cmd}' lost connection: {exc}")
                    self._handle_disconnect_locked()
                except Exception as exc:  # pragma: no cover - 仅记录异常并重试
                    logging.warning(f"Telnet command '{cmd}' failed: {exc}")
                    self._handle_disconnect_locked()
            attempt += 1
        return ""

    # ------------------------------------------------------------------
    # 兼容旧接口
    # ------------------------------------------------------------------
    def execute_cmd(self, cmd: str) -> str:
        return self.checkoutput(cmd)

    def popen_term(self, command: str):
        return subprocess.Popen(command.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def subprocess_run(self, cmd: str) -> str:
        return self.checkoutput(cmd)

    def root(self):  # pragma: no cover - 旧接口保留占位
        ...

    def remount(self):  # pragma: no cover - 旧接口保留占位
        ...

    def getprop(self, key: str) -> str:
        return self.checkoutput(f"getprop {key}")

    def get_mcs_tx(self) -> str:
        return "mcs_tx"

    def get_mcs_rx(self) -> str:
        return "mcs_rx"


# 向下兼容旧的导入方式
class telnet_tool(TelnetTool):
    pass
