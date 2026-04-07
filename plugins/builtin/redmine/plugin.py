#!/usr/bin/env python3
# plugins/builtin/redmine/plugin.py - Redmine 任务查看插件
"""Redmine 任务查看插件 — 显示当前用户的待办任务"""

import json
import curses
import threading
import time
import urllib.request
import urllib.error
from typing import List, Tuple, Any, Optional, Dict

from lib.plugins.core import Plugin, PluginInfo, PluginContext, PluginPriority
from lib.layout import Region, Slot
from lib.utils import display_width, truncate_to_width


class RedminePlugin(Plugin):
    """Redmine 任务查看插件"""

    def __init__(self):
        super().__init__()
        self._redmine_url: str = ""
        self._api_key: str = ""
        self._refresh_interval: int = 60
        self._issues: List[dict] = []
        self._error: Optional[str] = None
        self._page: int = 0
        self._per_page: int = 10
        self._total_count: int = 0
        self._fetching: bool = False
        self._last_fetch: float = 0

    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            id="builtin.redmine",
            name="Redmine",
            version="1.0.0",
            author="system",
            description="显示 Redmine 待办任务列表",
            priority=PluginPriority.HIGH,
            dependencies=[],
            provides=["redmine_tasks"],
            hooks=[]
        )

    def declare_regions(self) -> List[Region]:
        return [
            Region(
                id="redmine",
                slot=Slot.RIGHT_TOP,
                min_height=3,
                priority=80
            )
        ]

    def on_load(self):
        super().on_load()
        self._redmine_url = self.get_config("redmine_url", "").rstrip("/")
        self._api_key = self.get_config("api_key", "")
        self._refresh_interval = int(self.get_config("refresh_interval", 60))

    def on_start(self):
        super().on_start()
        self._fetch_issues()

    # ========== 数据获取 ==========

    def _fetch_issues(self):
        """在后台线程获取 Redmine 任务"""
        if self._fetching:
            return
        if not self._redmine_url or not self._api_key:
            self._error = "请在 plugins.yaml 配置 redmine_url 和 api_key"
            return

        self._fetching = True
        t = threading.Thread(target=self._do_fetch, daemon=True)
        t.start()

    def _do_fetch(self):
        """实际 HTTP 请求（在子线程中执行）"""
        try:
            url = (
                f"{self._redmine_url}/issues.json"
                f"?assigned_to_id=me&status_id=open"
                f"&sort=updated_on:desc&limit=100"
            )
            req = urllib.request.Request(url)
            req.add_header("X-Redmine-API-Key", self._api_key)
            req.add_header("Content-Type", "application/json")

            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            self._issues = data.get("issues", [])
            self._total_count = data.get("total_count", len(self._issues))
            self._error = None
            self._last_fetch = time.time()
        except urllib.error.URLError as e:
            self._error = f"连接失败: {e.reason}"
        except Exception as e:
            self._error = f"错误: {e}"
        finally:
            self._fetching = False

    # ========== 渲染 ==========

    def render_region(self, region_id: str, rect, data: dict) -> List[Tuple[int, int, str, Any]]:
        if region_id != "redmine":
            return []

        # 自动刷新
        if not self._fetching and self._last_fetch > 0:
            if time.time() - self._last_fetch >= self._refresh_interval:
                self._fetch_issues()

        width = rect.width
        cells = []
        row = 0

        # 标题行
        if self._error:
            cells.append((row, 1, f"Redmine: {self._error}", curses.color_pair(1)))
        elif self._fetching and not self._issues:
            cells.append((row, 1, "Redmine: 加载中...", curses.A_DIM))
        else:
            count = self._total_count
            cells.append((row, 1, f"Redmine: 我的待办 ({count})", curses.color_pair(2) | curses.A_BOLD))
        row += 1

        # 分隔线
        cells.append((row, 0, "─" * width, curses.color_pair(1) | curses.A_DIM))
        row += 1

        # 错误/无数据时提前返回
        if self._error and not self._issues:
            cells.append((row, 1, "无数据", curses.A_DIM))
            row += 1
        elif not self._issues:
            cells.append((row, 1, "没有待办任务", curses.color_pair(2)))
            row += 1
        else:
            # 任务列表
            per_page = max(1, rect.height - 3)  # 减去标题、分隔线、底栏
            self._per_page = per_page
            total_pages = max(1, (len(self._issues) + per_page - 1) // per_page)
            if self._page >= total_pages:
                self._page = total_pages - 1
            if self._page < 0:
                self._page = 0

            start = self._page * per_page
            end = min(start + per_page, len(self._issues))
            max_rows = rect.height - 1  # 留一行给底栏

            for i in range(start, min(end, start + max_rows)):
                issue = self._issues[i]
                cells.extend(self._render_issue(row, issue, width))
                row += 1

            # 底栏
            row = rect.height - 1
            footer = f" {self._page + 1}/{total_pages}  <:上页 >:下页 R:刷新"
            cells.append((row, 0, footer[:width], curses.A_DIM))

        return cells

    def _render_issue(self, row: int, issue: dict, width: int) -> List[Tuple[int, int, str, Any]]:
        """渲染单行任务"""
        cells = []

        # 优先级标记
        priority = issue.get("priority", {})
        priority_name = priority.get("name", "普通")
        if "高" in priority_name or "紧急" in priority_name or "Urgent" in priority_name or "High" in priority_name:
            marker, color = "●", curses.color_pair(1)
        elif "低" in priority_name or "Low" in priority_name:
            marker, color = "○", curses.A_DIM
        else:
            marker, color = "◆", curses.color_pair(3)

        issue_id = issue.get("id", "?")
        subject = issue.get("subject", "")
        status = issue.get("status", {}).get("name", "")

        # 布局: "[#61084] ● 主题                    状态"
        left = f"[#{issue_id}] {marker} "
        right_part = f" {status}"
        left_w = display_width(left)
        right_w = display_width(right_part)
        max_subject = width - left_w - right_w - 1
        if max_subject < 4:
            max_subject = 4

        truncated = truncate_to_width(subject, max_subject)

        cells.append((row, 0, left, color))
        cells.append((row, left_w, truncated, curses.A_NORMAL))

        # 状态靠右
        status_col = width - right_w
        if status_col > left_w + display_width(truncated):
            cells.append((row, status_col, right_part, curses.color_pair(5) | curses.A_DIM))

        return cells

    # ========== 输入处理 ==========

    def handle_key(self, key: int, context: dict) -> bool:
        """处理翻页和刷新按键"""
        if key in (ord("<"), ord(",")):
            if self._page > 0:
                self._page -= 1
            return True

        if key in (ord(">"), ord(".")):
            per_page = self._per_page
            total_pages = max(1, (len(self._issues) + per_page - 1) // per_page)
            if self._page < total_pages - 1:
                self._page += 1
            return True

        if key in (ord("R"), ord("r")):
            self._fetch_issues()
            return True

        return False


# 插件入口
plugin_class = RedminePlugin
