#!/usr/bin/env python 
# encoding: utf-8 
'''
@author: chao.li
@contact: chao.li@amlogic.com
@software: pycharm
@file: theme.py 
@time: 8/17/2025 2:27 PM 
@desc: 
'''

FONT_SIZE = 16
FONT_FAMILY = "Verdana"
TEXT_COLOR = "#fafafa"
BACKGROUND_COLOR = "#2b2b2b"
STYLE_BASE = f"font-size:{FONT_SIZE}px; font-family:{FONT_FAMILY};"
HTML_STYLE = f"{STYLE_BASE} color:{TEXT_COLOR};"


def apply_theme(widget):
    """Apply the global theme to a widget."""
    widget.setStyleSheet(
        f"""
        {STYLE_BASE} color:{TEXT_COLOR}; background:{BACKGROUND_COLOR};
        QTreeView, QTreeView::item {{
            {STYLE_BASE} color:{TEXT_COLOR};
            background:{BACKGROUND_COLOR};
        }}
        """
    )


def format_log_html(message: str) -> str:
    """根据消息内容返回带统一主题的 HTML 字符串"""
    base_style = "font-family: Consolas, 'Courier New', monospace;"
    upper_msg = message.upper()
    colors = {
        "ERROR": "red",
        "WARNING": "orange",
        "INFO": "blue",
    }
    for level, color in colors.items():
        if level in upper_msg:
            return f"<span style='{base_style} color:{color};'>{message}</span>"
    return f"<span style='{base_style}'>{message}</span>"
