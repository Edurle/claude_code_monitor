#!/usr/bin/env python3
# plugins/builtin/stats-view/plugin.py
"""统计全屏视图插件 — 显示统计信息、周图表和活跃项目"""

import curses
from typing import Dict, List, Tuple, Any

from lib.plugins.core import Plugin, PluginInfo, PluginPriority


class StatsViewPlugin(Plugin):
    """统计全屏视图插件"""

    def __init__(self):
        super().__init__()
        self._active = False

    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            id="builtin.stats-view",
            name="统计全屏页",
            version="1.0.0",
            author="system",
            description="统计信息全屏视图",
            priority=PluginPriority.HIGH,
            provides=["stats_view"],
        )

    def on_load(self):
        """加载时订阅视图切换事件"""
        super().on_load()
        if self._context and self._context.events:
            self._context.events.on("view_switch", self._on_view_switch)

    def _on_view_switch(self, data: dict):
        """视图切换事件处理"""
        view = data.get("view", "")
        if view == "stats":
            self._active = True
        elif view == "queue":
            self._active = False

    def render_fullscreen(self, screen_h: int, screen_w: int, data: dict) -> List[Tuple[int, int, str, Any]]:
        """全屏渲染统计视图"""
        if not self._active:
            return []

        cells = []
        row = 0

        # 标题
        title = " 统计面板 "
        cells.append((row, 0, "=" * screen_w, curses.color_pair(6)))
        cells.append((row, max(0, (screen_w - len(title)) // 2), title, curses.color_pair(6) | curses.A_BOLD))
        row += 2

        # 获取统计数据
        stats_manager = self._get_stats_manager()

        if not stats_manager:
            cells.append((row, 2, "统计数据未加载", curses.A_DIM))
        else:
            # 总体统计
            cells.append((row, 2, "总体统计", curses.color_pair(3) | curses.A_BOLD))
            row += 1

            summary = stats_manager.get_summary()
            cells.append((row, 4, f"总任务数: {summary['total_tasks']}", curses.color_pair(5)))
            row += 1
            cells.append((row, 4, f"HITL 次数: {summary['total_hitl']}", curses.color_pair(5)))
            row += 1
            cells.append((row, 4, f"错误次数: {summary['total_errors']}", curses.color_pair(5)))
            row += 1
            cells.append((row, 4, f"活跃项目: {summary['total_projects']}", curses.color_pair(5)))
            row += 1
            cells.append((row, 4, f"日均任务: {summary['avg_tasks_per_day']:.1f}", curses.color_pair(5)))
            row += 2

            # 周图表
            cells.append((row, 2, "本周任务", curses.color_pair(3) | curses.A_BOLD))
            row += 1

            week_chart = stats_manager.get_week_chart(width=30)
            for line in week_chart.split("\n"):
                if row >= screen_h - 4:
                    break
                cells.append((row, 4, line, curses.color_pair(5)))
                row += 1

            row += 1

            # 活跃项目
            if row < screen_h - 4:
                cells.append((row, 2, "活跃项目 TOP 5", curses.color_pair(3) | curses.A_BOLD))
                row += 1

                for project, stats in stats_manager.get_top_projects(5):
                    if row >= screen_h - 4:
                        break
                    cells.append((row, 4, f"* {project}: {stats['total']} 个任务", curses.color_pair(5)))
                    row += 1

        # 底部提示
        cells.append((screen_h - 1, 2, "[S/ESC] 返回队列", curses.A_DIM))

        return cells

    def handle_key(self, key: int, context: dict) -> bool:
        """处理按键"""
        if not self._active:
            return False

        # ESC 或 S 返回（由 monitor 处理）
        if key == 27 or key in (ord("s"), ord("S")):
            return False  # 让 monitor 处理视图切换

        return False

    def _get_stats_manager(self):
        """获取统计管理器"""
        if not self._context:
            return None
        return self._context.stats


# 导出插件类
plugin_class = StatsViewPlugin
