#!/usr/bin/env python3
# lib/theme.py - 主题引擎
"""动态主题系统，支持多种预设主题和自定义主题"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Optional, List
import json

# 主题目录
THEMES_DIR = Path(__file__).parent.parent / "themes"


@dataclass
class ThemeColors:
    """主题颜色配置"""
    primary: str = "#00FFFF"
    secondary: str = "#FF00FF"
    accent: str = "#FFFF00"
    background: str = "#0D0D0D"
    text: str = "#FFFFFF"
    dim: str = "#666666"
    success: str = "#00FF00"
    warning: str = "#FFAA00"
    error: str = "#FF0000"


@dataclass
class TypeStyle:
    """事件类型样式"""
    icon: str = "•"
    glow: bool = False
    blink: bool = False


@dataclass
class ThemeEffects:
    """主题效果配置"""
    enable_glow: bool = True
    enable_blink: bool = True
    border_style: str = "single"  # single, double, rounded


@dataclass
class Theme:
    """主题定义"""
    name: str
    author: str = "Claude"
    colors: ThemeColors = field(default_factory=ThemeColors)
    styles: Dict[str, TypeStyle] = field(default_factory=dict)
    effects: ThemeEffects = field(default_factory=ThemeEffects)

    def __post_init__(self):
        # 默认事件类型样式
        if not self.styles:
            self.styles = {
                "hitl": TypeStyle(icon="⚡", glow=True, blink=True),
                "task_complete": TypeStyle(icon="✓", glow=True),
                "error": TypeStyle(icon="✗", blink=True),
            }


def hex_to_256(hex_color: str) -> int:
    """将十六进制颜色转换为 256 色代码"""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) != 6:
        return 255

    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)

    # 转换为 6x6x6 色立方
    if r == g == b:
        # 灰度
        if r < 8:
            return 16
        if r > 248:
            return 231
        return round(((r - 8) / 247) * 24) + 232

    return 16 + (36 * (r // 51)) + (6 * (g // 51)) + (b // 51)


class ThemeManager:
    """主题管理器"""

    # 预设主题（内嵌，无需外部文件）
    BUILTIN_THEMES = {
        "default": Theme(
            name="Default",
            author="Claude",
            colors=ThemeColors(
                primary="#00FFFF",
                secondary="#FF00FF",
                accent="#FFFF00",
                background="#1A1A1A",
                text="#FFFFFF",
                dim="#666666",
                success="#00FF00",
                warning="#FFAA00",
                error="#FF0000",
            ),
        ),
        "cyberpunk": Theme(
            name="Cyberpunk 2077",
            author="Claude",
            colors=ThemeColors(
                primary="#FF00FF",  # 霓虹粉
                secondary="#00FFFF",  # 电光蓝
                accent="#FFFF00",  # 警告黄
                background="#0D0D0D",
                text="#FFFFFF",
                dim="#666666",
                success="#00FF88",
                warning="#FFAA00",
                error="#FF0044",
            ),
            effects=ThemeEffects(enable_glow=True, enable_blink=True, border_style="double"),
        ),
        "matrix": Theme(
            name="Matrix",
            author="Claude",
            colors=ThemeColors(
                primary="#00FF00",  # 矩阵绿
                secondary="#00AA00",
                accent="#88FF88",
                background="#000000",
                text="#00FF00",
                dim="#004400",
                success="#00FF00",
                warning="#88FF00",
                error="#FF0000",
            ),
            styles={
                "hitl": TypeStyle(icon="⚡", glow=True),
                "task_complete": TypeStyle(icon="✓"),
                "error": TypeStyle(icon="✗", blink=True),
            },
        ),
        "dracula": Theme(
            name="Dracula",
            author="Claude",
            colors=ThemeColors(
                primary="#BD93F9",
                secondary="#FF79C6",
                accent="#F1FA8C",
                background="#282A36",
                text="#F8F8F2",
                dim="#6272A4",
                success="#50FA7B",
                warning="#FFB86C",
                error="#FF5555",
            ),
        ),
        "nord": Theme(
            name="Nord",
            author="Claude",
            colors=ThemeColors(
                primary="#88C0D0",
                secondary="#81A1C1",
                accent="#EBCB8B",
                background="#2E3440",
                text="#ECEFF4",
                dim="#4C566A",
                success="#A3BE8C",
                warning="#EBCB8B",
                error="#BF616A",
            ),
        ),
        "solarized": Theme(
            name="Solarized Dark",
            author="Claude",
            colors=ThemeColors(
                primary="#268BD2",
                secondary="#D33682",
                accent="#B58900",
                background="#002B36",
                text="#FDF6E3",
                dim="#657B83",
                success="#859900",
                warning="#B58900",
                error="#DC322F",
            ),
        ),
    }

    def __init__(self, initial_theme: str = "default"):
        self._themes = dict(self.BUILTIN_THEMES)
        self._current_theme_name = initial_theme
        self._curses_colors = {}  # 缓存 curses 颜色对

    @property
    def current(self) -> Theme:
        """获取当前主题"""
        return self._themes.get(self._current_theme_name, self._themes["default"])

    @property
    def current_name(self) -> str:
        """获取当前主题名称"""
        return self._current_theme_name

    @property
    def available_themes(self) -> List[str]:
        """获取所有可用主题名称"""
        return list(self._themes.keys())

    def switch(self, theme_name: Optional[str] = None) -> str:
        """切换主题，返回新主题名称"""
        if theme_name and theme_name in self._themes:
            self._current_theme_name = theme_name
        else:
            # 循环切换
            themes = self.available_themes
            idx = themes.index(self._current_theme_name)
            self._current_theme_name = themes[(idx + 1) % len(themes)]
        return self._current_theme_name

    def init_curses_colors(self, stdscr) -> Dict[str, int]:
        """初始化 curses 颜色对"""
        theme = self.current
        colors = theme.colors

        # 定义颜色对映射
        color_map = {
            "primary": colors.primary,
            "secondary": colors.secondary,
            "accent": colors.accent,
            "text": colors.text,
            "dim": colors.dim,
            "success": colors.success,
            "warning": colors.warning,
            "error": colors.error,
            "hitl": colors.warning,
            "task_complete": colors.success,
            "error_type": colors.error,
        }

        import curses

        # 初始化颜色（索引 16-255 可自定义）
        color_idx = 16
        pair_idx = 1

        for name, hex_color in color_map.items():
            # 初始化颜色
            curses.init_color(color_idx, *self._hex_to_curses_rgb(hex_color))
            # 创建颜色对（前景色，背景透明）
            curses.init_pair(pair_idx, color_idx, -1)
            self._curses_colors[name] = curses.color_pair(pair_idx)
            color_idx += 1
            pair_idx += 1

        return self._curses_colors

    def _hex_to_curses_rgb(self, hex_color: str) -> tuple:
        """将十六进制颜色转换为 curses RGB 值 (0-1000)"""
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return (r * 1000 // 255, g * 1000 // 255, b * 1000 // 255)

    def get_color(self, name: str) -> int:
        """获取 curses 颜色对"""
        return self._curses_colors.get(name, 0)

    def get_style(self, event_type: str) -> TypeStyle:
        """获取事件类型样式"""
        return self.current.styles.get(event_type, TypeStyle())

    def get_border_chars(self) -> tuple:
        """获取边框字符"""
        style = self.current.effects.border_style
        if style == "double":
            return ("╔", "═", "╗", "║", "╝", "═", "╚", "║")
        elif style == "rounded":
            return ("╭", "─", "╮", "│", "╯", "─", "╰", "│")
        else:  # single
            return ("┌", "─", "┐", "│", "┘", "─", "└", "│")
