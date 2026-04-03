#!/usr/bin/env python3
# plugins/builtin/hints-bar/plugin.py
"""快捷键提示栏插件 — 快捷键提示行 + 视图切换"""

import curses
from typing import List, Tuple, Any

from lib.plugins.core import Plugin, PluginInfo, PluginPriority
from lib.layout import Region, Slot


class HintsBarPlugin(Plugin):
    """快捷键提示栏插件 — 显示快捷键提示，处理视图切换按键"""

    def __init__(self):
        super().__init__()
        self._ctx = None

    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            id="builtin.hints-bar",
            name="快捷键提示栏",
            version="1.0.0",
            author="system",
            description="快捷键提示行 + 视图切换",
            priority=PluginPriority.NORMAL,
            provides=["hints_bar"],
        )

    # ========== 生命周期 ==========

    def on_load(self):
        """加载时存储 context 引用"""
        super().on_load()
        # context 会在 set_context 时设置

    def set_context(self, context):
        """设置插件上下文"""
        super().set_context(context)
        self._ctx = context

    # ========== Region 渲染接口 ==========

    def declare_regions(self) -> List[Region]:
        """声明底部快捷键提示栏区域"""
        return [
            Region(
                id="hints_bar",
                slot=Slot.BOTTOM,
                min_height=1,
                weight=50,
                priority=90,
            )
        ]

    def render_region(self, region_id: str, rect, data: dict) -> List[Tuple[int, int, str, Any]]:
        """渲染底部快捷键提示栏"""
        if region_id != "hints_bar":
            return []

        cells = []
        hints = "[Enter]jump [d]drop [c]clear [T]theme [A]achieve [S]stats [P]pet [q]quit"

        # 使用暗色显示提示
        cells.append((0, 0, hints, curses.A_DIM))

        return cells

    # ========== 输入处理 ==========

    def handle_key(self, key: int, context: dict) -> bool:
        """处理快捷键：t/T 切换主题、a/A 切换成就视图、s/S 切换统计视图、ESC 返回队列视图"""
        if not self._ctx:
            return False

        # 主题切换 (t/T)
        if key in (ord("t"), ord("T")):
            new_theme = self._ctx.theme.switch()
            self._ctx.events.emit("theme_change", {"theme": new_theme})
            self._ctx.events.emit("set_status", {"msg": f"主题切换: {new_theme}", "duration": 2.0})
            return True

        # 成就视图 (a/A)
        if key in (ord("a"), ord("A")):
            self._ctx.events.emit("view_switch", {"view": "achievements"})
            return True

        # 统计视图 (s/S)
        if key in (ord("s"), ord("S")):
            self._ctx.events.emit("view_switch", {"view": "stats"})
            return True

        # ESC 返回队列视图
        if key == 27:  # ESC key
            self._ctx.events.emit("view_switch", {"view": "queue"})
            return True

        return False
