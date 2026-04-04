#!/usr/bin/env python3
# plugins/builtin/neural-grid/plugin.py - 神经网格插件
"""神经网格插件 - 右下神经网格会话状态卡片"""

import curses
import math
import random
import time
from typing import List, Tuple

from lib.plugins.core import Plugin, PluginInfo, PluginPriority
from lib.layout import Region, Slot


# 会话状态显示配置
STATUS_DISPLAY = {
    "start":       {"char": "◇", "color": 6, "pulse": True},    # 品红 - 启动
    "idle":        {"char": "○", "color": 5, "pulse": False},   # 白色(暗淡) - 闲置
    "working":     {"char": "◆", "color": 2, "pulse": True},    # 黄色 - 工作
    "hitl":        {"char": "⚠", "color": 4, "pulse": True},    # 红色 - 等待人工
    "complete":    {"char": "✦", "color": 3, "pulse": False},   # 绿色 - 完成
    "error":       {"char": "✖", "color": 4, "pulse": True},    # 红色 - 错误
    "api_error":   {"char": "⛔", "color": 4, "pulse": True},   # 红色 - API错误
    "offline":     {"char": "·", "color": 5, "pulse": False},   # 白色(暗淡) - 离线
}

# 网格排序优先级（越小越靠前）
GRID_PRIORITY = {
    "hitl": 0, "error": 1, "api_error": 2, "working": 3,
    "start": 4, "complete": 5, "idle": 6, "offline": 7,
}


class NeuralGridPlugin(Plugin):
    """神经网格插件 - 右下神经网格会话状态卡片"""

    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            id="builtin.neural-grid",
            name="神经网格",
            version="1.0.0",
            author="system",
            description="右下神经网格 — 会话状态卡片",
            priority=PluginPriority.HIGH,
            provides=["neural_grid"],
        )

    def declare_regions(self) -> list:
        """声明需要 RIGHT_BOT 区域"""
        return [
            Region(
                id="neural_grid",
                slot=Slot.RIGHT_BOT,
                min_height=4,
                weight=100,
                priority=80,
            )
        ]

    def on_load(self):
        """加载时订阅队列更新事件"""
        super().on_load()
        if self._context and self._context.events:
            self._context.events.on("queue_update", self._on_queue_update)

    def _on_queue_update(self, event):
        """队列更新时刷新 sessions 缓存"""
        # Session 数据通过 ctx.sessions.get_sessions() 实时获取
        # 这里只是触发重绘
        pass

    def render_region(self, region_id: str, rect, data: dict) -> list:
        """渲染神经网格

        Args:
            region_id: 区域 ID (neural_grid)
            rect: Region 对象 (包含 row, col, height, width)
            data: 数据字典

        Returns:
            [(row, col, text, attr), ...] - 坐标相对于 Rect 左上角
        """
        if rect.height < 4 or rect.width < 20:
            return []

        # 获取 sessions
        sessions = []
        if self._context and self._context.sessions:
            sessions = self._context.sessions.get_sessions()

        frame_phase = time.time() % 2.0

        # 无会话时显示等待状态
        if not sessions:
            mid_row = rect.height // 2
            return [
                (mid_row, 2, " awaiting connections... ", curses.color_pair(1) | curses.A_DIM)
            ]

        # 排序会话
        sorted_sessions = self._sort_sessions_for_grid(sessions)
        max_cards = max(1, rect.height // 2)
        visible = sorted_sessions[:max_cards]
        overflow = len(sorted_sessions) - max_cards

        cells = []
        row = 0

        # 渲染每张会话卡片
        for session in visible:
            rows_used = self._render_session_card(
                cells, row, 0, rect.width, session, frame_phase
            )
            row += rows_used

        # 溢出提示
        if overflow > 0:
            status_counts = {}
            for s in sorted_sessions[max_cards:]:
                status_counts[s.status] = status_counts.get(s.status, 0) + 1
            summary_parts = [f"{k}:{v}" for k, v in status_counts.items()]
            summary = f"... +{overflow} more  " + "  ".join(summary_parts)
            if row < rect.height:
                cells.append((row, 2, summary[:rect.width - 4], curses.A_DIM))

        return cells

    def _render_session_card(self, cells: list, row: int, col: int, width: int,
                             session, frame_phase: float) -> int:
        """渲染单张会话卡片（1-2 行）

        Args:
            cells: 输出单元格列表
            row: 起始行（相对坐标）
            col: 起始列（相对坐标）
            width: 可用宽度
            session: SessionState 对象
            frame_phase: 动画帧相位

        Returns:
            占用行数 (1-2)
        """
        display = STATUS_DISPLAY.get(session.status, STATUS_DISPLAY["idle"])
        icon = display["char"]
        icon_color = curses.color_pair(display["color"])

        # 脉冲动画
        if display["pulse"]:
            phase = math.sin(frame_phase * math.pi)
            if phase > 0.3:
                icon_color |= curses.A_BOLD
            elif phase < -0.3:
                icon_color |= curses.A_DIM

        # 第一行：[icon] name  [activity_bar]  STATUS  tool
        cells.append((row, col, icon, icon_color))

        name = (session.project or session.session)[:12]
        cells.append((row, col + 2, name, curses.color_pair(5)))

        bar_text, bar_attr = self._build_activity_bar(
            session.status, frame_phase, session.last_event_ts
        )
        cells.append((row, col + 15, bar_text, bar_attr))

        # 状态标签
        label_map = {
            "working": "WORK", "hitl": "HITL!", "idle": "IDLE",
            "error": "ERR!!", "api_error": "API!", "complete": "DONE",
            "start": "LOAD", "offline": "OFF",
        }
        label = label_map.get(session.status, "????")
        cells.append((row, col + 26, label, icon_color))

        # 工具名（仅 working 状态）
        remaining = width - 32
        if remaining > 3 and session.tool:
            cells.append((row, col + 32, session.tool[:remaining], curses.A_DIM))

        # 第二行：详情（条件渲染）
        detail, detail_attr = self._format_session_detail(session)
        if detail:
            detail_text = "  └─ " + detail
            cells.append((row + 1, col, detail_text[:width], detail_attr))
            return 2

        return 1

    def _build_activity_bar(self, status: str, frame_phase: float,
                            last_event_ts: float) -> Tuple[str, int]:
        """构建 10 字符动画活动条

        Args:
            status: 会话状态
            frame_phase: 动画帧相位
            last_event_ts: 最后事件时间戳

        Returns:
            (bar_text, attr) 元组
        """
        if status == "working":
            fill_pct = 0.5 + 0.2 * math.sin(frame_phase * math.pi)
            filled = int(10 * fill_pct)
            bar = "\u2593" * filled + "\u2591" * (10 - filled)
            return bar, curses.color_pair(2)

        elif status == "hitl":
            bar = "\u2593" * 10
            if int(frame_phase * 2) % 2 == 0:
                attr = curses.color_pair(4) | curses.A_BOLD
            else:
                attr = curses.color_pair(4) | curses.A_DIM
            return bar, attr

        elif status == "idle":
            return "\u2591" * 10, curses.A_DIM

        elif status == "error":
            base = [1, 1, 0, 1, 1, 0, 0, 0, 1, 0]
            rng = random.Random(int(frame_phase * 10))
            for _ in range(3):
                idx = rng.randint(0, 9)
                base[idx] = 1 - base[idx]
            bar = "".join("\u2593" if b else "\u2591" for b in base)
            return bar, curses.color_pair(4)

        elif status == "api_error":
            base = [1, 1, 0, 1, 0, 0, 1, 0, 0, 1]
            rng = random.Random(int(frame_phase * 10))
            for _ in range(3):
                idx = rng.randint(0, 9)
                base[idx] = 1 - base[idx]
            chars = []
            for b in base:
                if b and rng.random() < 0.3:
                    chars.append("\u2588")
                elif b:
                    chars.append("\u2593")
                else:
                    chars.append("\u2591")
            return "".join(chars), curses.color_pair(4) | curses.A_BOLD

        elif status == "complete":
            bar = "\u2593" * 10
            age = time.time() - last_event_ts if last_event_ts > 0 else 999
            if age < 30:
                attr = curses.color_pair(3) | curses.A_BOLD
            elif age < 120:
                attr = curses.color_pair(3)
            else:
                attr = curses.color_pair(3) | curses.A_DIM
            return bar, attr

        elif status == "start":
            sweep_pos = int((frame_phase / 2.0) * 10) % 10
            bar_list = ["\u2591"] * 10
            for i in range(min(3, sweep_pos + 1)):
                pos = (sweep_pos - i) % 10
                bar_list[pos] = "\u2593"
            return "".join(bar_list), curses.color_pair(6)

        else:  # offline
            return "\u00b7" * 10, curses.A_DIM

    def _format_session_detail(self, session) -> Tuple[str, int]:
        """格式化会话卡片第二行详情文本

        Args:
            session: SessionState 对象

        Returns:
            (detail_text, attr) 元组
        """
        detail = ""
        attr = curses.A_DIM
        sub_text = ""

        if session.subagents:
            names = ",".join(session.subagents[:3])
            if len(session.subagents) > 3:
                names += ",..."
            sub_text = f" +{session.subagent_count} sub:{names}"

        if session.status == "hitl":
            detail = session.hitl_info or "awaiting response"
            attr = curses.color_pair(4) | curses.A_BOLD
        elif session.status == "working":
            parts = []
            if session.tool:
                parts.append(session.tool)
            if session.info and session.info != session.tool:
                parts.append(session.info[:20])
            detail = " ".join(parts) if parts else "processing"
            attr = curses.color_pair(6) | curses.A_DIM
        elif session.status in ("error", "api_error"):
            detail = session.info or "unknown error"
            attr = curses.color_pair(4)
        elif session.status == "idle":
            if session.last_event_ts > 0:
                elapsed = int(time.time() - session.last_event_ts)
                mins, secs = divmod(elapsed, 60)
                detail = f"idle {mins}m{secs:02d}s"
            else:
                detail = "idle"
            attr = curses.A_DIM
        elif session.status == "complete":
            detail = f"done {session.last_event_time}"
            attr = curses.color_pair(3) | curses.A_DIM
        elif session.status == "start":
            detail = "initializing..."
            attr = curses.color_pair(6) | curses.A_DIM
        elif session.status == "offline":
            detail = "disconnected"
            attr = curses.A_DIM

        if sub_text:
            detail = detail + sub_text if detail else sub_text.lstrip()

        return detail, attr

    def _sort_sessions_for_grid(self, sessions) -> list:
        """按优先级排序会话：hitl > error > working > start > complete > idle > offline

        Args:
            sessions: SessionState 列表

        Returns:
            排序后的 SessionState 列表
        """
        return sorted(sessions, key=lambda s: (
            GRID_PRIORITY.get(s.status, 99),
            -s.last_event_ts,
        ))


plugin_class = NeuralGridPlugin
