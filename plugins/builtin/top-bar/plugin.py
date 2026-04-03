#!/usr/bin/env python3
# plugins/builtin/top-bar/plugin.py - 顶栏统计插件
"""顶栏统计插件 - 显示队列统计信息"""

import curses
from lib.plugins.core import Plugin, PluginInfo, PluginPriority
from lib.layout import Region, Slot


class TopBarPlugin(Plugin):
    """顶栏统计插件 - 显示队列统计信息"""

    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            id="builtin.top-bar",
            name="顶栏统计",
            version="1.0.0",
            author="system",
            description="显示队列统计 (CLAUDE CODE MONITOR ...)",
            priority=PluginPriority(100),
            provides=["top_bar"],
        )

    def declare_regions(self) -> list:
        """声明需要 TOP 区域，优先级 100"""
        return [
            Region(
                id="builtin.top-bar.main",
                slot=Slot.TOP,
                min_height=1,
                weight=100,
                priority=100,
            )
        ]

    def render_region(self, region_id: str, rect, data: dict) -> list:
        """渲染顶栏统计

        Args:
            region_id: 区域 ID (builtin.top-bar.main)
            rect: Region 对象
            data: 包含 entries 的数据字典

        Returns:
            [(row, col, text, attr), ...] - 坐标相对于 Rect 左上角
        """
        entries = data.get("entries", [])

        # 过滤可操作事件
        actionable = [e for e in entries if e.get("type") in ("hitl", "task_complete", "error")]
        total = len(actionable)
        hitl = sum(1 for e in actionable if e.get("type") == "hitl")
        done = sum(1 for e in actionable if e.get("type") == "task_complete")

        # 构建显示文本
        bar = f" CLAUDE CODE MONITOR  {total} in queue"
        if hitl:
            bar += f"  HITL:{hitl}"
        if done:
            bar += f"  DONE:{done}"

        # 右填充到宽度
        bar = bar.ljust(rect.width)

        # 返回单元格渲染 (cyan bold)
        return [(0, 0, bar, curses.color_pair(1) | curses.A_BOLD)]


plugin_class = TopBarPlugin
