#!/usr/bin/env python3
# lib/stats.py - 统计模块
"""用户行为统计和分析"""

import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List
from datetime import datetime, timedelta
from collections import defaultdict

# 数据存储路径
DATA_DIR = Path(__file__).parent.parent / "data"
STATS_FILE = DATA_DIR / "stats.json"


@dataclass
class DailyStats:
    """每日统计"""
    date: str
    tasks: int = 0
    hitl_count: int = 0
    errors: int = 0
    projects: set = field(default_factory=set)

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "tasks": self.tasks,
            "hitl_count": self.hitl_count,
            "errors": self.errors,
            "projects": list(self.projects),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DailyStats":
        return cls(
            date=data["date"],
            tasks=data.get("tasks", 0),
            hitl_count=data.get("hitl_count", 0),
            errors=data.get("errors", 0),
            projects=set(data.get("projects", [])),
        )


class StatsManager:
    """统计管理器"""

    def __init__(self):
        self._daily_stats: Dict[str, DailyStats] = {}
        self._project_stats: Dict[str, Dict] = defaultdict(lambda: {
            "total": 0, "hitl": 0, "errors": 0, "last_seen": ""
        })
        self._hourly_distribution: Dict[int, int] = defaultdict(int)
        self._load()

    def _load(self):
        """从文件加载"""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if STATS_FILE.exists():
            try:
                data = json.loads(STATS_FILE.read_text())
                self._daily_stats = {
                    k: DailyStats.from_dict(v)
                    for k, v in data.get("daily", {}).items()
                }
                self._project_stats = defaultdict(
                    lambda: {"total": 0, "hitl": 0, "errors": 0, "last_seen": ""},
                    data.get("projects", {})
                )
                self._hourly_distribution = defaultdict(
                    int, data.get("hourly", {})
                )
            except (json.JSONDecodeError, Exception):
                pass

    def _save(self):
        """保存到文件"""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "daily": {k: v.to_dict() for k, v in self._daily_stats.items()},
            "projects": dict(self._project_stats),
            "hourly": {str(k): v for k, v in self._hourly_distribution.items()},
        }
        STATS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def record_event(self, event_type: str, project: str = ""):
        """记录事件"""
        today = datetime.now().strftime("%Y-%m-%d")
        hour = datetime.now().hour

        # 更新每日统计
        if today not in self._daily_stats:
            self._daily_stats[today] = DailyStats(date=today)

        daily = self._daily_stats[today]
        daily.tasks += 1
        if event_type == "hitl":
            daily.hitl_count += 1
        elif event_type == "error":
            daily.errors += 1
        if project:
            daily.projects.add(project)

        # 更新项目统计
        if project:
            self._project_stats[project]["total"] += 1
            self._project_stats[project]["last_seen"] = today
            if event_type == "hitl":
                self._project_stats[project]["hitl"] += 1
            elif event_type == "error":
                self._project_stats[project]["errors"] += 1

        # 更新小时分布
        self._hourly_distribution[hour] += 1

        self._save()

    def get_today_stats(self) -> DailyStats:
        """获取今日统计"""
        today = datetime.now().strftime("%Y-%m-%d")
        return self._daily_stats.get(today, DailyStats(date=today))

    def get_week_stats(self) -> List[DailyStats]:
        """获取本周统计"""
        today = datetime.now()
        week_start = today - timedelta(days=today.weekday())
        stats = []
        for i in range(7):
            date = (week_start + timedelta(days=i)).strftime("%Y-%m-%d")
            stats.append(self._daily_stats.get(date, DailyStats(date=date)))
        return stats

    def get_top_projects(self, limit: int = 5) -> List[tuple]:
        """获取最活跃的项目"""
        sorted_projects = sorted(
            self._project_stats.items(),
            key=lambda x: x[1]["total"],
            reverse=True
        )
        return sorted_projects[:limit]

    def get_peak_hours(self, limit: int = 5) -> List[tuple]:
        """获取高峰时段"""
        sorted_hours = sorted(
            self._hourly_distribution.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_hours[:limit]

    def get_summary(self) -> dict:
        """获取统计摘要"""
        total_tasks = sum(d.tasks for d in self._daily_stats.values())
        total_hitl = sum(d.hitl_count for d in self._daily_stats.values())
        total_errors = sum(d.errors for d in self._daily_stats.values())
        total_projects = len(self._project_stats)

        return {
            "total_tasks": total_tasks,
            "total_hitl": total_hitl,
            "total_errors": total_errors,
            "total_projects": total_projects,
            "days_active": len(self._daily_stats),
            "avg_tasks_per_day": total_tasks / max(len(self._daily_stats), 1),
        }

    def get_week_chart(self, width: int = 20) -> str:
        """生成周任务图表（ASCII）"""
        week_stats = self.get_week_stats()
        max_tasks = max(d.tasks for d in week_stats) or 1

        lines = []
        day_names = ["一", "二", "三", "四", "五", "六", "日"]

        for i, stat in enumerate(week_stats):
            bar_len = int(stat.tasks / max_tasks * width)
            bar = "█" * bar_len + "░" * (width - bar_len)
            lines.append(f"周{day_names[i]} │{bar} {stat.tasks}")

        return "\n".join(lines)
