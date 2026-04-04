#!/usr/bin/env python3
# plugins/builtin/matrix-rain/plugin.py - 矩阵雨插件
"""矩阵雨效果 + 扫描线分隔"""

import time
import curses
from typing import List, Tuple, Any, Optional

from lib.plugins.core import Plugin, PluginInfo, PluginContext, PluginPriority
from lib.layout import Region, Slot, Rect


class MatrixRainPlugin(Plugin):
    """矩阵雨插件 — 矩阵雨粒子效果 + 扫描线分隔"""

    def __init__(self):
        super().__init__()
        self._emitter_id: Optional[str] = None
        self._last_layout: Optional[Tuple[int, int, int, int]] = None

    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            id="builtin.matrix-rain",
            name="矩阵雨",
            version="1.0.0",
            author="system",
            description="矩阵雨效果 + 扫描线分隔",
            priority=PluginPriority.HIGH,
            dependencies=[],
            provides=["matrix_rain"],
            hooks=[]
        )

    def declare_regions(self) -> List[Region]:
        """声明矩阵雨区域"""
        return [
            Region(
                id="matrix_rain",
                slot=Slot.RIGHT_TOP,
                min_height=3,
                priority=80
            )
        ]

    def render_region(self, region_id: str, rect: Rect, data: dict) -> List[Tuple[int, int, str, Any]]:
        """渲染矩阵雨区域

        返回 [(row, col, text, attr), ...], 坐标相对于 Rect 左上角
        """
        if region_id != "matrix_rain":
            return []

        # 高度检查
        if rect.height < 3:
            return []

        cells = []

        # 获取粒子系统
        if not self._context or not self._context.particles:
            return []

        particles = self._context.particles

        # 布局元组
        layout = (rect.col, rect.row, rect.width, rect.height)

        # 首次创建或布局变化时重建发射器
        if self._emitter_id is None or self._last_layout != layout:
            if rect.width <= 0 or rect.height <= 0:
                return []

            # 移除旧发射器
            if self._emitter_id:
                particles.remove_emitter(self._emitter_id)

            # 创建新发射器
            self._emitter_id = particles.create_matrix_rain(
                x=0,
                y=0,
                width=rect.width,
                height=rect.height - 1  # 最后一行留给扫描线
            )
            self._last_layout = layout

        # 获取发射器并渲染粒子
        emitter = particles.get_emitter(self._emitter_id)
        if emitter:
            # 渲染矩阵雨（带边界裁剪）
            bounds = (0, 0, rect.height - 1, rect.width)
            elements = emitter.render(bounds)
            for (r, c, text, attr) in elements:
                cells.append((r, c, text, attr))

        # 渲染扫描线（最后一行）
        scan_line_row = rect.height - 1
        scan_cells = self._render_scan_line(scan_line_row, 0, rect.width, data)
        cells.extend(scan_cells)

        return cells

    def _render_scan_line(self, row: int, start_col: int, width: int, data: dict) -> List[Tuple[int, int, str, Any]]:
        """渲染扫描线分隔

        显示: ─── ▸ NEURAL GRID ── N active ───
        """
        # 获取活跃会话数
        sessions = data.get("sessions", [])
        active_count = len(sessions)

        title = f" ▸ NEURAL GRID ── {active_count} active "

        cells = []

        # 宽度太窄的情况
        if len(title) + 4 >= width:
            line = "─" * width
            cells.append((row, start_col, line, curses.color_pair(1) | curses.A_DIM))
            return cells

        # 计算左右两侧的横线长度
        side_len = (width - len(title)) // 2
        left_side = "─" * side_len
        right_side = "─" * (width - len(title) - side_len)

        # 左侧横线
        cells.append((row, start_col, left_side, curses.color_pair(1) | curses.A_DIM))

        # 中间标题
        cells.append((row, start_col + side_len, title, curses.color_pair(1) | curses.A_BOLD))

        # 右侧横线
        cells.append((row, start_col + side_len + len(title), right_side, curses.color_pair(1) | curses.A_DIM))

        # 扫描线闪烁效果：每 0.7s 随机位置高亮
        if int(time.time() * 10) % 7 == 0:
            flick_pos = start_col + (int(time.time() * 3) % max(1, width))
            cells.append((row, flick_pos, "─", curses.color_pair(1) | curses.A_REVERSE))

        return cells

    def on_stop(self):
        """停止时清理发射器"""
        if self._emitter_id and self._context and self._context.particles:
            self._context.particles.remove_emitter(self._emitter_id)
            self._emitter_id = None
            self._last_layout = None
        super().on_stop()


plugin_class = MatrixRainPlugin
