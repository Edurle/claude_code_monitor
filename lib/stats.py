#!/usr/bin/env python3
# lib/stats.py - 统计模块
"""用户行为统计和分析"""

from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime, timedelta

from lib.database import Database


@dataclass
class DailyStats:
    """每日统计"""
    date: str
    tasks: int = 0
    hitl_count: int = 0
    errors: int = 0
    projects: set = field(default_factory=set)


class StatsManager:
    """统计管理器"""

    def __init__(self, db: Optional[Database] = None):
        self._db = db or Database.get_instance()

    def record_event(self, event_type: str, project: str = ""):
        """记录事件"""
        today = datetime.now().strftime("%Y-%m-%d")
        hour = datetime.now().hour

        # 确保当日记录存在
        self._db.execute(
            "INSERT OR IGNORE INTO daily_stats (date, tasks, hitl_count, errors) VALUES (?, 0, 0, 0)",
            (today,)
        )

        # 更新每日统计
        if event_type == "hitl":
            self._db.execute(
                "UPDATE daily_stats SET tasks = tasks + 1, hitl_count = hitl_count + 1 WHERE date = ?",
                (today,)
            )
        elif event_type == "error":
            self._db.execute(
                "UPDATE daily_stats SET tasks = tasks + 1, errors = errors + 1 WHERE date = ?",
                (today,)
            )
        else:
            self._db.execute(
                "UPDATE daily_stats SET tasks = tasks + 1 WHERE date = ?",
                (today,)
            )

        # 关联项目
        if project:
            self._db.execute(
                "INSERT OR IGNORE INTO daily_projects (date, project) VALUES (?, ?)",
                (today, project)
            )
            # 更新项目统计
            self._db.execute(
                "INSERT INTO project_stats (project, total, hitl, errors, last_seen) VALUES (?, 0, 0, 0, '') "
                "ON CONFLICT(project) DO UPDATE SET "
                "total = total + 1, "
                "hitl = hitl + CASE WHEN ? = 'hitl' THEN 1 ELSE 0 END, "
                "errors = errors + CASE WHEN ? = 'error' THEN 1 ELSE 0 END, "
                "last_seen = ?",
                (project, event_type, event_type, today)
            )

        # 更新小时分布
        self._db.execute(
            "INSERT INTO hourly_stats (hour, count) VALUES (?, 1) "
            "ON CONFLICT(hour) DO UPDATE SET count = count + 1",
            (hour,)
        )

        self._db.commit()

    def get_today_stats(self) -> DailyStats:
        """获取今日统计"""
        today = datetime.now().strftime("%Y-%m-%d")
        row = self._db.query_one("SELECT * FROM daily_stats WHERE date = ?", (today,))
        if not row:
            return DailyStats(date=today)
        projects = {
            r["project"] for r in self._db.query_all(
                "SELECT project FROM daily_projects WHERE date = ?", (today,)
            )
        }
        return DailyStats(
            date=today,
            tasks=row["tasks"],
            hitl_count=row["hitl_count"],
            errors=row["errors"],
            projects=projects,
        )

    def get_week_stats(self) -> List[DailyStats]:
        """获取本周统计"""
        today = datetime.now()
        week_start = today - timedelta(days=today.weekday())
        start_str = week_start.strftime("%Y-%m-%d")
        end_str = (week_start + timedelta(days=6)).strftime("%Y-%m-%d")

        daily_rows = self._db.query_all(
            "SELECT * FROM daily_stats WHERE date BETWEEN ? AND ?",
            (start_str, end_str)
        )
        daily_map = {r["date"]: r for r in daily_rows}

        project_rows = self._db.query_all(
            "SELECT date, project FROM daily_projects WHERE date BETWEEN ? AND ?",
            (start_str, end_str)
        )
        proj_map: dict[str, set] = {}
        for r in project_rows:
            proj_map.setdefault(r["date"], set()).add(r["project"])

        stats = []
        for i in range(7):
            d = (week_start + timedelta(days=i)).strftime("%Y-%m-%d")
            if d in daily_map:
                row = daily_map[d]
                stats.append(DailyStats(
                    date=d, tasks=row["tasks"],
                    hitl_count=row["hitl_count"], errors=row["errors"],
                    projects=proj_map.get(d, set()),
                ))
            else:
                stats.append(DailyStats(date=d))
        return stats

    def get_top_projects(self, limit: int = 5) -> List[tuple]:
        """获取最活跃的项目"""
        rows = self._db.query_all(
            "SELECT project, total, hitl, errors, last_seen FROM project_stats "
            "ORDER BY total DESC LIMIT ?", (limit,)
        )
        return [(r["project"], {
            "total": r["total"], "hitl": r["hitl"],
            "errors": r["errors"], "last_seen": r["last_seen"]
        }) for r in rows]

    def get_peak_hours(self, limit: int = 5) -> List[tuple]:
        """获取高峰时段"""
        rows = self._db.query_all(
            "SELECT hour, count FROM hourly_stats ORDER BY count DESC LIMIT ?", (limit,)
        )
        return [(r["hour"], r["count"]) for r in rows]

    def get_summary(self) -> dict:
        """获取统计摘要"""
        row = self._db.query_one(
            "SELECT COALESCE(SUM(tasks), 0) as total_tasks, "
            "COALESCE(SUM(hitl_count), 0) as total_hitl, "
            "COALESCE(SUM(errors), 0) as total_errors, "
            "COUNT(*) as days_active "
            "FROM daily_stats"
        ) or {"total_tasks": 0, "total_hitl": 0, "total_errors": 0, "days_active": 0}
        proj_row = self._db.query_one("SELECT COUNT(*) as cnt FROM project_stats")
        total_tasks = row["total_tasks"]
        days_active = row["days_active"]
        return {
            "total_tasks": total_tasks,
            "total_hitl": row["total_hitl"],
            "total_errors": row["total_errors"],
            "total_projects": proj_row["cnt"] if proj_row else 0,
            "days_active": days_active,
            "avg_tasks_per_day": total_tasks / max(days_active, 1),
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
