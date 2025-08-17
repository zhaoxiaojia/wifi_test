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

from PyQt5.QtGui import QFont

FONT_SIZE = 16
FONT_FAMILY = "Verdana"
TEXT_COLOR = "#fafafa"
BACKGROUND_COLOR = "#2b2b2b"
STYLE_BASE = f"font-size:{FONT_SIZE}px; font-family:{FONT_FAMILY};"
HTML_STYLE = f"{STYLE_BASE} color:{TEXT_COLOR};"
# --- 追加 import ---
from PyQt5.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem
from PyQt5.QtCore import QSize
from PyQt5.QtGui import QFontMetrics


class FixedFontDelegate(QStyledItemDelegate):
    def __init__(self, family="Verdana", size_px=16, parent=None):
        super().__init__(parent)
        self._font = QFont(family)
        # 用像素尺寸更直观，且和 QFluentWidgets 默认保持一致
        self._font.setPixelSize(size_px)

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        # 关键：放在最后，覆盖模型的 Qt.FontRole 和库内部的改动
        option.font = self._font

    def sizeHint(self, option, index):
        # 根据字体重新计算行高，避免文字被裁切
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        fm = QFontMetrics(opt.font)
        h = fm.height() + 6  # 适度留白
        # 宽度让视图自己管，这里只保证行高
        return QSize(opt.rect.width(), h)


def apply_tree_font(tree, family="Verdana", size_px=20):
    # 安装固定字体 delegate（整表或按列都行，这里整表）
    tree.setItemDelegate(FixedFontDelegate(family, size_px, tree))
    tree.setUniformRowHeights(False)  # 行高随字体变化
    # 轻微增加 item padding，避免紧绷
    tree.setStyleSheet(tree.styleSheet() + "\nQTreeView::item { padding: 2px 6px; }")
    tree.viewport().update()


def apply_theme(widget):
    widget.setStyleSheet(
        f"""
        {STYLE_BASE} color:{TEXT_COLOR}; background:{BACKGROUND_COLOR};
        QTreeView, QTreeView::item {{
            {STYLE_BASE}
            color:{TEXT_COLOR};
            background:{BACKGROUND_COLOR};
            font-family:  {FONT_FAMILY};
            font-size: {FONT_SIZE}pt;
        }}
        """
    )
    # 不必再 setFont，但如果你想保底也可以留着
    widget.setFont(QFont(FONT_FAMILY, FONT_SIZE))

    # 关键：viewport 也加上字体，防止只改颜色不改字体导致覆盖
    if hasattr(widget, "viewport"):
        widget.viewport().setStyleSheet(
            f"""
            {STYLE_BASE}
            color:{TEXT_COLOR}; background:{BACKGROUND_COLOR};
            font-family: {FONT_FAMILY};
            font-size: {FONT_SIZE}pt;
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
