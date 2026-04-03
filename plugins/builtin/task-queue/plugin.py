#!/usr/bin/env python3
# plugins/builtin/task-queue/plugin.py
"""任务队列插件 — 左侧面板可操作事件列表 + Enter/d/c 输入处理"""

import curses
import subprocess
from typing import Dict, List, Tuple, Any

from lib.plugins.core import Plugin, PluginInfo, PluginPriority
from lib.layout import Region, Slot


# 类型颜色映射：(颜色对, 图标)
TYPE_COLOR = {
    "hitl": (curses.color_pair(2), "⚡"),
    "task_complete": (curses.color_pair(3), "✓"),
    "error": (curses.color_pair(4), "✗"),
}


class TaskQueuePlugin(Plugin):
    """任务队列插件 — 左侧面板渲染 + 输入处理"""

    def __init__(self):
        super().__init__()
        self._status_msg = ""
        self._status_clear_at = 0.0

    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            id="builtin.task-queue",
            name="任务队列",
            version="1.0.0",
            author="system",
            description="左侧任务队列 — 可操作事件列表 + Enter/d/c 输入处理",
            priority=PluginPriority.HIGH,
            provides=["task_queue"],
        )

    # ========== Region 渲染接口 ==========

    def declare_regions(self) -> List[Region]:
        """声明左侧任务队列区域"""
        return [
            Region(
                id="task_queue",
                slot=Slot.LEFT,
                min_height=5,
                weight=70,
                priority=100,
            )
        ]

    def render_region(self, region_id: str, rect, data: dict) -> List[Tuple[int, int, str, Any]]:
        """渲染左侧任务队列"""
        if region_id != "task_queue":
            return []

        entries = data.get("entries", [])
        cells = []
        row = 0
        width = rect.width

        # 过滤可操作事件
        actionable = self._get_actionable(entries)
        count = len(actionable)

        if count == 0:
            cells.append((row, 1, "队列空闲，等待事件...", curses.color_pair(5) | curses.A_DIM))
            return cells

        # 标题
        cells.append((row, 1, f"待处理: {count} 条", curses.color_pair(2) | curses.A_BOLD))
        row += 1

        for idx, entry in enumerate(actionable):
            if row >= rect.height - 1:  # 留一行底部空间
                cells.append((row, 2, f"... 还有 {count - idx} 条", curses.A_DIM))
                break

            ts = entry.get("ts", "")
            etype = entry.get("type", "")
            session = entry.get("session", "")
            win_name = entry.get("win_name", "")
            info = entry.get("info", "")
            wdir = entry.get("dir", "")

            color, icon = TYPE_COLOR.get(etype, (curses.color_pair(5), "·"))
            target = f"{session}:{win_name}" if win_name else session

            if idx == 0:
                # 队首：完整信息
                cells.append((row, 0, "▶ ", curses.color_pair(2) | curses.A_BOLD))
                cells.append((row, 2, f"{icon} [{etype}]", color | curses.A_BOLD))

                pos = 2 + len(f"{icon} [{etype}]") + 1
                cells.append((row, pos, target, curses.A_BOLD))

                pos += len(target) + 1
                cells.append((row, pos, ts, curses.A_DIM))
                row += 1

                if wdir:
                    cells.append((row, 4, wdir[:width - 6], curses.A_DIM))
                    row += 1
                if info:
                    cells.append((row, 4, info[:width - 6], curses.color_pair(6)))
                    row += 1
            else:
                # 后续：紧凑显示
                line = f"  {icon} [{etype}]  {target}  {ts}"
                cells.append((row, 1, line[:width], curses.A_DIM))
                row += 1
                if info:
                    cells.append((row, 5, info[:width - 7], curses.A_DIM))
                    row += 1

        return cells

    # ========== 输入处理 ==========

    def handle_key(self, key: int, context: dict) -> bool:
        """处理按键。返回 True 表示已消费该按键。"""
        import time

        entries = context.get("entries", [])
        actionable = self._get_actionable(entries)

        # Enter: 跳转到队首任务
        if key in (curses.KEY_ENTER, 10, 13):
            if not actionable:
                return True

            entry = actionable[0]
            err = self._jump_to_task(entry)
            if err:
                self.ctx.events.emit("set_status", {"text": err, "duration": 3.0})
            else:
                self.ctx.queue.remove(entry)
                self.ctx.events.emit("task_complete", entry)
                self.ctx.events.emit("set_status", {"text": "已跳转并处理任务", "duration": 2.0})
            return True

        # d/D: 丢弃队首
        if key in (ord("d"), ord("D")):
            if not actionable:
                return True
            entry = actionable[0]
            self.ctx.queue.remove(entry)
            self.ctx.events.emit("task_discard", {"entry": entry})
            self.ctx.events.emit("set_status", {"text": "已丢弃队首条目", "duration": 2.0})
            return True

        # c/C: 清空队列
        if key in (ord("c"), ord("C")):
            self.ctx.queue.clear()
            self.ctx.events.emit("queue_clear", {})
            self.ctx.events.emit("set_status", {"text": "队列已清空", "duration": 2.0})
            return True

        return False

    # ========== 辅助方法 ==========

    def _get_actionable(self, entries: List[dict]) -> List[dict]:
        """过滤可操作事件：hitl, task_complete, error"""
        return [e for e in entries if e.get("type") in TYPE_COLOR]

    def _tmux(self, cmd: List[str]) -> bool:
        """执行 tmux 命令"""
        try:
            subprocess.run(["tmux"] + cmd, capture_output=True)
            return True
        except Exception:
            return False

    def _jump_to_task(self, entry: dict) -> str:
        """跳转到任务。返回错误消息或 None"""
        session = entry.get("session", "")
        win_idx = entry.get("win_idx", "0")

        r = subprocess.run(["tmux", "has-session", "-t", session], capture_output=True)
        if r.returncode != 0:
            return f"Session '{session}' 不存在"

        self._tmux(["select-window", "-t", f"{session}:{win_idx}"])
        self._tmux(["switch-client", "-t", session])
        return None


# 导出插件类
plugin_class = TaskQueuePlugin
