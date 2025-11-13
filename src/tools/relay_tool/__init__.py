#!/usr/bin/env python 
# encoding: utf-8 
'''
@author: chao.li
@contact: chao.li@amlogic.com
@software: pycharm
@file: __init__.py.py 
@time: 11/13/2025 10:57 AM 
@desc: 
'''

from abc import ABC, abstractmethod
from typing import Any

__all__ = ["Relay"]


class Relay(ABC):
    """Common ABC for relay controllers."""

    def __init__(self, port: Any | None = None) -> None:
        """Store optional default port metadata."""
        self.port = port

    @abstractmethod
    def pulse(self, direction: str = "power_off", *, port: Any | None = None, **kwargs) -> None:
        """Toggle a single relay contact."""
        raise NotImplementedError
