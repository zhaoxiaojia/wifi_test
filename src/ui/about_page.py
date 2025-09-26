#!/usr/bin/env python
# encoding: utf-8

from PyQt5.QtWidgets import QVBoxLayout
from qfluentwidgets import CardWidget, StrongBodyLabel, BodyLabel

from .theme import apply_theme


class AboutPage(CardWidget):
    """Simple about page describing the tool and team."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("aboutPage")
        apply_theme(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        title_label = StrongBodyLabel("关于 FAE-QA Wi-Fi Test Tool")
        apply_theme(title_label)
        layout.addWidget(title_label)

        sections = [
            (
                "工具简介",
                "FAE-QA Wi-Fi Test Tool 用于整合 Wi-Fi 相关测试流程，"
                "提供用例配置、场景参数和结果展示的全流程体验。"
                "借助一体化界面帮助工程师快速完成测试执行与数据回顾。",
            ),
            (
                "作者/鸣谢",
                "工具由 FAE-QA 团队持续维护，感谢 Wi-Fi 研发、验证及自动化平台团队"
                "在需求梳理、功能验证与体验优化方面提供的大力支持。",
            ),
            (
                "晶晨文化",
                "秉持“协同、务实、创新”的晶晨文化，我们致力于为客户与伙伴"
                "提供可靠的无线连接体验，共同打造开放、共赢的生态体系。",
            ),
        ]

        for heading, content in sections:
            header_label = StrongBodyLabel(heading)
            apply_theme(header_label)
            layout.addWidget(header_label)

            body_label = BodyLabel(content)
            body_label.setWordWrap(True)
            apply_theme(body_label)
            layout.addWidget(body_label)

        layout.addStretch(1)
