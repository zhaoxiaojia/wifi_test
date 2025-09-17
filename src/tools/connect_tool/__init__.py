"""Connect tool package exports."""

from .telnet_tool import TelnetTool
from .telnet3_tool import Telnet3Tool

__all__ = ["TelnetTool", "Telnet3Tool", "create_telnet_client"]


def create_telnet_client(kind: str = "telnet3", *args, **kwargs):
    """简单的 Telnet 客户端工厂方法."""

    normalized = (kind or "").lower()
    if normalized in {"telnet3", "async"}:
        return Telnet3Tool(*args, **kwargs)
    if normalized in {"telnet", "sync"}:
        return TelnetTool(*args, **kwargs)
    raise ValueError(f"Unsupported telnet client kind: {kind}")
