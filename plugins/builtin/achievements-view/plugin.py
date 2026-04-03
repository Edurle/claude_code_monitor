#!/usr/bin/env python3
# plugins/builtin/achievements-view/plugin.py
"""成就全屏视图插件 — 显示成就列表和统计"""

import curses
from typing import Dict, List, Tuple, Any

from lib.plugins.core import Plugin, PluginInfo, PluginPriority


class AchievementsViewPlugin(Plugin):
    """成就全屏视图插件"""

    def __init__(self):
        super().__init__()
        self._active = False
        self._scroll = 0

    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            id="builtin.achievements-view",
            name="成就全屏页",
            version="1.0.0",
            author="system",
            description="成就系统全屏视图",
            priority=PluginPriority.HIGH,
            provides=["achievements_view"],
        )

    def on_load(self):
        """加载时订阅视图切换事件"""
        super().on_load()
        if self._context and self._context.events:
            self._context.events.on("view_switch", self._on_view_switch)

    def _on_view_switch(self, data: dict):
        """视图切换事件处理"""
        view = data.get("view", "")
        if view == "achievements":
            self._active = True
            self._scroll = 0
        elif view == "queue":
            self._active = False

    def render_fullscreen(self, screen_h: int, screen_w: int, data: dict) -> List[Tuple[int, int, str, Any]]:
        """全屏渲染成就视图"""
        if not self._active:
            return []

        cells = []
        row = 0

        # 标题
        title = " 成就系统 "
        cells.append((row, 0, "=" * screen_w, curses.color_pair(3)))
        cells.append((row, max(0, (screen_w - len(title)) // 2), title, curses.color_pair(3) | curses.A_BOLD))
        row += 2

        # 获取成就数据
        achievements_data = self._get_achievements_data()

        if not achievements_data:
            cells.append((row, 2, "成就系统未加载", curses.A_DIM))
        else:
            all_achievements = achievements_data.get("all", [])
            stats = achievements_data.get("stats")

            visible_count = screen_h - 6  # 留出标题和底部空间
            start = self._scroll
            end = min(start + visible_count, len(all_achievements))

            for i in range(start, end):
                if row >= screen_h - 4:
                    break

                achievement, unlocked = all_achievements[i]
                prefix = "* " if unlocked else "o "
                color = curses.color_pair(3) if unlocked else curses.A_DIM

                # 成就名称行
                name_line = f"{prefix}{achievement.icon} {achievement.name}"
                cells.append((row, 2, name_line, color | (curses.A_BOLD if unlocked else 0)))
                row += 1

                # 描述行
                cells.append((row, 6, achievement.desc, curses.A_DIM))
                row += 2

            # 滚动提示
            if len(all_achievements) > visible_count:
                scroll_info = f"[{start + 1}-{end}/{len(all_achievements)}]"
                cells.append((2, screen_w - len(scroll_info) - 2, scroll_info, curses.A_DIM))

            # 统计信息
            if stats:
                stats_row = screen_h - 5
                cells.append((stats_row, 2, "-" * 40, curses.A_DIM))
                cells.append((stats_row + 1, 2, f"统计: 总任务 {stats.total_tasks} | HITL {stats.hitl_count} | 错误 {stats.error_count}", curses.color_pair(5)))
                cells.append((stats_row + 2, 2, f"连续 {stats.consecutive_days} 天 | 今日 {stats.tasks_today} 个任务", curses.color_pair(5)))

        # 底部提示
        cells.append((screen_h - 1, 2, "[A/ESC] 返回队列", curses.A_DIM))

        return cells

    def handle_key(self, key: int, context: dict) -> bool:
        """处理按键"""
        if not self._active:
            return False

        # 上滚
        if key == curses.KEY_UP:
            if self._scroll > 0:
                self._scroll -= 1
            return True

        # 下滚
        if key == curses.KEY_DOWN:
            achievements_data = self._get_achievements_data()
            if achievements_data:
                all_achievements = achievements_data.get("all", [])
                max_scroll = max(0, len(all_achievements) - 5)
                if self._scroll < max_scroll:
                    self._scroll += 1
            return True

        # ESC 或 A 返回（由 monitor 处理）
        if key == 27 or key in (ord("a"), ord("A")):
            return False  # 让 monitor 处理视图切换

        return False

    def _get_achievements_data(self) -> dict:
        """获取成就数据"""
        if not self._context:
            return {}

        # 尝试从成就插件获取
        if self._context.stats:
            # 通过 stats 获取成就管理器
            pass

        # 回退：通过 monitor 获取
        if hasattr(self._context, "monitor") and self._context.monitor:
            monitor = self._context.monitor

            # 优先使用成就插件
            achievement_plugin = getattr(monitor, "_get_achievement_plugin", lambda: None)()
            if achievement_plugin:
                return {
                    "all": achievement_plugin.get_all(),
                    "stats": achievement_plugin.stats,
                }

            # 回退到旧版
            achievement_manager = getattr(monitor, "achievement_manager", None)
            if achievement_manager:
                return {
                    "all": achievement_manager.get_all(),
                    "stats": achievement_manager.stats,
                }

        return {}


# 导出插件类
plugin_class = AchievementsViewPlugin
