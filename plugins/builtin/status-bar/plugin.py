#!/usr/bin/env python3
# plugins/builtin/status-bar/plugin.py
"""状态消息栏插件 — 状态消息行 + 自动清除"""

import time
import curses
from typing import List, Tuple, Any

from lib.plugins.core import Plugin, PluginInfo, PluginPriority
from lib.layout import Region, Slot


class StatusBarPlugin(Plugin):
    """状态消息栏插件 — 显示临时状态消息，支持自动清除"""

    def __init__(self):
        super().__init__()
        self._msg = ""
        self._clear_at = 0.0
        self._ctx = None

    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            id="builtin.status-bar",
            name="状态消息栏",
            version="1.0.0",
            author="system",
            description="状态消息行 + 自动清除",
            priority=PluginPriority.HIGH,
            provides=["status_bar"],
        )

    # ========== 生命周期 ==========

    def on_load(self):
        """加载时订阅事件"""
        super().on_load()
        # 在 on_enable 中通过 context 订阅事件

    def on_enable(self):
        """启用时订阅 set_status 事件"""
        super().on_enable()
        if self._context and self._context.events:
            self._context.events.on("set_status", self._on_set_status, priority=50)

    # ========== 事件处理 ==========

    def _on_set_status(self, data: dict):
        """处理 set_status 事件"""
        if data is None:
            data = {}
        self._msg = data.get("msg", "")
        duration = data.get("duration", 3.0)
        self._clear_at = time.time() + duration

    # ========== Region 渲染接口 ==========

    def declare_regions(self) -> List[Region]:
        """声明底部状态消息栏区域"""
        return [
            Region(
                id="status_bar",
                slot=Slot.BOTTOM,
                min_height=1,
                weight=50,
                priority=100,
            )
        ]

    def render_region(self, region_id: str, rect, data: dict) -> List[Tuple[int, int, str, Any]]:
        """渲染底部状态消息栏"""
        if region_id != "status_bar":
            return []

        cells = []

        # 检查是否需要清除消息
        if self._msg and time.time() > self._clear_at:
            self._msg = ""

        # 显示消息（如果有）
        if self._msg:
            # 使用主题颜色（如果没有 context，使用默认颜色对 2）
            if self._context and self._context.theme:
                color = self._context.theme.get_color("status")
            else:
                color = curses.color_pair(2)
            cells.append((0, 2, self._msg, color))

        return cells
