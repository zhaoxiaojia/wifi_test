"""Sections covering router and serial port configuration."""

from __future__ import annotations

from typing import Any

from ..group_proxy import _build_network_group as proxy_build_network_group
from ..group_proxy import _build_traffic_group as proxy_build_traffic_group
from ..sections import register_case_sections, register_section
from ..sections.base import ConfigSection


@register_section("router", case_types=("default",))
class RouterSection(ConfigSection):
    """Render router selection and gateway configuration."""

    panel = "execution"

    def build(self, config: dict[str, Any]) -> None:  # type: ignore[override]
        value = config.get("router") if isinstance(config, dict) else {}
        proxy_build_network_group(self.page, value)
        group = self.page._dut_groups.get("router")
        if group is not None:
            self.groups["router"] = group
        for key in ("router.name", "router.address"):
            widget = self.page.field_widgets.get(key)
            if widget is not None:
                self.widgets[key] = widget


@register_section("serial_port", case_types=("default",))
class SerialPortSection(ConfigSection):
    """Render serial port enablement controls."""

    panel = "execution"

    def build(self, config: dict[str, Any]) -> None:  # type: ignore[override]
        value = config.get("serial_port") if isinstance(config, dict) else {}
        proxy_build_traffic_group(self.page, value)
        group = self.page._dut_groups.get("serial_port") or self.page._other_groups.get("serial_port")
        if group is not None:
            self.groups["serial_port"] = group
        for key in ("serial_port.status", "serial_port.port", "serial_port.baud"):
            widget = self.page.field_widgets.get(key)
            if widget is not None:
                self.widgets[key] = widget


__all__ = ["RouterSection", "SerialPortSection"]

register_case_sections("default", ["router", "serial_port"])
