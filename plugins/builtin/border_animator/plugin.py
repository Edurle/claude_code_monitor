#!/usr/bin/env python3
# plugins/builtin/border_animator/plugin.py - 边框动画插件
"""边框动画插件 - 为窗口边框添加动态效果"""

import time
from typing import Dict, List, Tuple, Optional, Any

from lib.plugins.core import Plugin, PluginInfo, PluginContext, PluginPriority


class BorderAnimatorPlugin(Plugin):
    """边框动画插件"""

    # 彩虹颜色序列
    RAINBOW_COLORS = [1, 3, 2, 6, 4, 5]  # 红、黄、绿、青、蓝、紫

    # 边框字符样式
    BORDER_STYLES = {
        "single": ("┌", "─", "┐", "│", "┘", "─", "└", "│"),
        "double": ("╔", "═", "╗", "║", "╝", "═", "╚", "║"),
        "round": ("╭", "─", "╮", "│", "╯", "─", "╰", "│"),
        "ascii": ("+", "-", "+", "|", "+", "-", "+", "|"),
        "stars": ("*", "*", "*", "*", "*", "*", "*", "*"),
        "dots": ("·", "·", "·", "·", "·", "·", "·", "·"),
    }

    def __init__(self):
        super().__init__()
        self._frame = 0
        self._last_update = 0
        self._animation_speed = 0.5
        self._style = "rainbow"  # rainbow / pulse / glitch / neon

    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            id="builtin.border_animator",
            name="边框动画",
            version="1.0.0",
            author="Claude",
            description="为窗口边框添加动态效果",
            priority=PluginPriority.LOW,
            provides=["border_animation"],
            hooks=["render_border", "render_border_char"]
        )

    def on_load(self):
        super().on_load()
        self._style = self.get_config("style", "rainbow")
        self._animation_speed = self.get_config("animation_speed", 0.5)

        # 注册钩子
        self.register_hook("render_border_char", self._render_border_char)

    def _render_border_char(self, position: str, char: str, frame: int) -> Tuple[str, int]:
        """渲染单个边框字符"""
        now = time.time()
        if now - self._last_update > self._animation_speed:
            self._frame = (self._frame + 1) % 60
            self._last_update = now

        if self._style == "rainbow":
            return self._rainbow_char(char)
        elif self._style == "pulse":
            return self._pulse_char(char)
        elif self._style == "glitch":
            return self._glitch_char(char)
        elif self._style == "neon":
            return self._neon_char(char)
        else:
            return (char, 0)

    def _rainbow_char(self, char: str) -> Tuple[str, int]:
        """彩虹效果"""
        import curses
        color_idx = self._frame % len(self.RAINBOW_COLORS)
        return (char, curses.color_pair(self.RAINBOW_COLORS[color_idx]))

    def _pulse_char(self, char: str) -> Tuple[str, int]:
        """脉冲效果"""
        import curses
        # 亮度变化
        intensity = (1 + (self._frame % 10) / 10.0)
        if intensity > 1.5:
            return (char, curses.A_BOLD)
        else:
            return (char, curses.A_DIM)

    def _glitch_char(self, char: str) -> Tuple[str, int]:
        """故障效果"""
        import random
        glitch_chars = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
        if random.random() < 0.05:  # 5% 几率故障
            return (random.choice(glitch_chars), 0)
        return (char, 0)

    def _neon_char(self, char: str) -> Tuple[str, int]:
        """霓虹效果"""
        import curses
        # 交替亮暗
        if self._frame % 4 < 2:
            return (char, curses.color_pair(6) | curses.A_BOLD)  # 亮青色
        else:
            return (char, curses.color_pair(6))  # 暗青色

    def set_style(self, style: str):
        """设置动画样式"""
        self._style = style

    def set_speed(self, speed: float):
        """设置动画速度"""
        self._animation_speed = max(0.1, min(2.0, speed))


# 插件入口
plugin_class = BorderAnimatorPlugin
