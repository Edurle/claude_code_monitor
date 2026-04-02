#!/usr/bin/env python3
# lib/achievements.py - 成就系统
"""游戏化成就系统，追踪用户行为并解锁成就"""

import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta

from lib.database import Database


@dataclass
class Achievement:
    """成就定义"""
    id: str
    name: str
    desc: str
    icon: str
    condition: Callable  # 检查是否解锁的条件函数
    hidden: bool = False  # 是否为隐藏成就


@dataclass
class UserStats:
    """用户统计数据"""
    total_tasks: int = 0
    hitl_count: int = 0
    hitl_count_5min: int = 0
    error_count: int = 0
    error_free_hours: float = 0.0
    active_projects: int = 0
    consecutive_days: int = 0
    last_task_time: float = 0.0
    tasks_today: int = 0
    current_hour: int = 0
    first_task_time_today: float = 0.0
    last_session_date: str = ""

    # 字段名列表，用于 user_meta 键值读写
    _fields = [
        "total_tasks", "hitl_count", "hitl_count_5min", "error_count",
        "error_free_hours", "active_projects", "consecutive_days",
        "last_task_time", "tasks_today", "current_hour",
        "first_task_time_today", "last_session_date",
    ]

    def _type_defaults(self) -> dict:
        return {
            "total_tasks": 0, "hitl_count": 0, "hitl_count_5min": 0,
            "error_count": 0, "error_free_hours": 0.0, "active_projects": 0,
            "consecutive_days": 0, "last_task_time": 0.0, "tasks_today": 0,
            "current_hour": 0, "first_task_time_today": 0.0, "last_session_date": "",
        }


# 成就定义
ACHIEVEMENTS: Dict[str, Achievement] = {
    "first_step": Achievement(
        id="first_step",
        name="初来乍到",
        desc="处理第一个任务",
        icon="🎯",
        condition=lambda s: s.total_tasks >= 1,
    ),
    "lightning": Achievement(
        id="lightning",
        name="闪电侠",
        desc="5分钟内处理10个HITL",
        icon="⚡",
        condition=lambda s: s.hitl_count_5min >= 10,
    ),
    "zen_master": Achievement(
        id="zen_master",
        name="禅宗大师",
        desc="连续2小时无错误",
        icon="🧘",
        condition=lambda s: s.error_free_hours >= 2,
    ),
    "night_owl": Achievement(
        id="night_owl",
        name="夜猫子",
        desc="凌晨(0-5点)处理任务",
        icon="🌙",
        condition=lambda s: 0 <= s.current_hour < 5 and s.tasks_today > 0,
    ),
    "early_bird": Achievement(
        id="early_bird",
        name="早起鸟",
        desc="早上(5-7点)处理任务",
        icon="🌅",
        condition=lambda s: 5 <= s.current_hour < 7 and s.tasks_today > 0,
    ),
    "multitasker": Achievement(
        id="multitasker",
        name="多面手",
        desc="同时处理3个以上项目",
        icon="🔄",
        condition=lambda s: s.active_projects >= 3,
    ),
    "streak_3": Achievement(
        id="streak_3",
        name="三天连胜",
        desc="连续3天使用",
        icon="🔥",
        condition=lambda s: s.consecutive_days >= 3,
    ),
    "streak_7": Achievement(
        id="streak_7",
        name="周冠军",
        desc="连续7天使用",
        icon="🏆",
        condition=lambda s: s.consecutive_days >= 7,
    ),
    "streak_30": Achievement(
        id="streak_30",
        name="月度之星",
        desc="连续30天使用",
        icon="⭐",
        condition=lambda s: s.consecutive_days >= 30,
    ),
    "centurion": Achievement(
        id="centurion",
        name="百夫长",
        desc="累计处理100个任务",
        icon="🎖️",
        condition=lambda s: s.total_tasks >= 100,
    ),
    "millennium": Achievement(
        id="millennium",
        name="千禧年",
        desc="累计处理1000个任务",
        icon="🏅",
        condition=lambda s: s.total_tasks >= 1000,
    ),
    "perfectionist": Achievement(
        id="perfectionist",
        name="完美主义者",
        desc="处理50个任务且无任何错误",
        icon="💎",
        condition=lambda s: s.total_tasks >= 50 and s.error_count == 0,
    ),
}


class AchievementManager:
    """成就管理器"""

    def __init__(self, db: Optional[Database] = None):
        self._db = db or Database.get_instance()
        self._stats = UserStats()
        self._recently_unlocked: List[str] = []
        self._load()

    def _load(self):
        """从数据库加载"""
        rows = self._db.query_all("SELECT key, value FROM user_meta")
        meta = {r["key"]: r["value"] for r in rows}

        for fname in UserStats._fields:
            raw = meta.get(fname)
            if raw is not None:
                default_val = self._stats._type_defaults()[fname]
                try:
                    if isinstance(default_val, int):
                        setattr(self._stats, fname, int(raw))
                    elif isinstance(default_val, float):
                        setattr(self._stats, fname, float(raw))
                    else:
                        setattr(self._stats, fname, raw)
                except (ValueError, TypeError):
                    pass

    def _save(self):
        """保存统计数据到数据库"""
        for fname in UserStats._fields:
            value = getattr(self._stats, fname)
            # 保持与 JSON 导入一致：数字直接存为字符串
            val_str = str(value)
            self._db.execute(
                "INSERT OR REPLACE INTO user_meta (key, value) VALUES (?, ?)",
                (fname, val_str)
            )
        self._db.commit()

    def record_task(self, event_type: str, project: str = ""):
        """记录任务事件"""
        now = time.time()
        today = datetime.now().strftime("%Y-%m-%d")
        current_hour = datetime.now().hour

        # 更新基础统计
        self._stats.total_tasks += 1
        self._stats.current_hour = current_hour

        if event_type == "hitl":
            self._stats.hitl_count += 1
            # 计算5分钟内的HITL数量
            if now - self._stats.last_task_time < 300:  # 5分钟
                self._stats.hitl_count_5min += 1
            else:
                self._stats.hitl_count_5min = 1
        elif event_type == "error":
            self._stats.error_count += 1
            self._stats.error_free_hours = 0

        # 更新连续天数
        if self._stats.last_session_date != today:
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            if self._stats.last_session_date == yesterday:
                self._stats.consecutive_days += 1
            else:
                self._stats.consecutive_days = 1
            self._stats.last_session_date = today

        # 更新今日任务数
        if self._stats.last_session_date == today:
            self._stats.tasks_today += 1
        else:
            self._stats.tasks_today = 1

        self._stats.last_task_time = now
        self._save()

        # 检查成就
        return self.check_achievements()

    def update_error_free_time(self):
        """更新无错误时间"""
        if self._stats.last_task_time > 0:
            hours = (time.time() - self._stats.last_task_time) / 3600
            if self._stats.error_count == 0:
                self._stats.error_free_hours = max(self._stats.error_free_hours, hours)

    def set_active_projects(self, count: int):
        """设置活跃项目数"""
        self._stats.active_projects = count
        self._save()

    def check_achievements(self) -> List[str]:
        """检查并解锁成就，返回新解锁的成就ID列表"""
        newly_unlocked = []

        for aid, achievement in ACHIEVEMENTS.items():
            if aid not in self._get_unlocked_set():
                try:
                    if achievement.condition(self._stats):
                        self._unlock(aid)
                        newly_unlocked.append(aid)
                except Exception:
                    pass

        self._recently_unlocked = newly_unlocked
        return newly_unlocked

    def _get_unlocked_set(self) -> set:
        rows = self._db.query_all("SELECT achievement_id FROM unlocked_achievements")
        return {r["achievement_id"] for r in rows}

    def _unlock(self, achievement_id: str):
        """解锁成就"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._db.execute(
            "INSERT OR IGNORE INTO unlocked_achievements (achievement_id, unlocked_at) VALUES (?, ?)",
            (achievement_id, now_str)
        )
        self._db.commit()

    def get_unlocked(self) -> List[Achievement]:
        """获取已解锁的成就列表"""
        unlocked_ids = self._get_unlocked_set()
        return [ACHIEVEMENTS[aid] for aid in unlocked_ids if aid in ACHIEVEMENTS]

    def get_all(self) -> List[tuple]:
        """获取所有成就及其解锁状态"""
        unlocked_ids = self._get_unlocked_set()
        return [
            (ACHIEVEMENTS[aid], aid in unlocked_ids)
            for aid in ACHIEVEMENTS
        ]

    def get_recently_unlocked(self) -> List[Achievement]:
        """获取最近解锁的成就"""
        return [
            ACHIEVEMENTS[aid]
            for aid in self._recently_unlocked
            if aid in ACHIEVEMENTS
        ]

    def clear_recently_unlocked(self):
        """清除最近解锁记录"""
        self._recently_unlocked = []

    @property
    def stats(self) -> UserStats:
        """获取统计数据"""
        return self._stats

    @property
    def unlocked_count(self) -> int:
        """获取已解锁成就数量"""
        row = self._db.query_one("SELECT COUNT(*) as cnt FROM unlocked_achievements")
        return row["cnt"] if row else 0

    @property
    def total_count(self) -> int:
        """获取总成就数量"""
        return len(ACHIEVEMENTS)
