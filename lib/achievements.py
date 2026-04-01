#!/usr/bin/env python3
# lib/achievements.py - 成就系统
"""游戏化成就系统，追踪用户行为并解锁成就"""

import json
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta

# 数据存储路径
DATA_DIR = Path(__file__).parent.parent / "data"
ACHIEVEMENTS_FILE = DATA_DIR / "achievements.json"


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

    def to_dict(self) -> dict:
        return {
            "total_tasks": self.total_tasks,
            "hitl_count": self.hitl_count,
            "hitl_count_5min": self.hitl_count_5min,
            "error_count": self.error_count,
            "error_free_hours": self.error_free_hours,
            "active_projects": self.active_projects,
            "consecutive_days": self.consecutive_days,
            "last_task_time": self.last_task_time,
            "tasks_today": self.tasks_today,
            "current_hour": self.current_hour,
            "first_task_time_today": self.first_task_time_today,
            "last_session_date": self.last_session_date,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UserStats":
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})


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

    def __init__(self):
        self._unlocked: List[str] = []
        self._stats = UserStats()
        self._history: List[dict] = []
        self._recently_unlocked: List[str] = []  # 新解锁的成就（用于显示动画）
        self._load()

    def _load(self):
        """从文件加载数据"""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if ACHIEVEMENTS_FILE.exists():
            try:
                data = json.loads(ACHIEVEMENTS_FILE.read_text())
                self._unlocked = data.get("unlocked", [])
                self._stats = UserStats.from_dict(data.get("stats", {}))
                self._history = data.get("history", [])
            except (json.JSONDecodeError, Exception):
                pass

    def _save(self):
        """保存数据到文件"""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "unlocked": self._unlocked,
            "stats": self._stats.to_dict(),
            "history": self._history,
        }
        ACHIEVEMENTS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))

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
            if aid not in self._unlocked:
                try:
                    if achievement.condition(self._stats):
                        self._unlock(aid)
                        newly_unlocked.append(aid)
                except Exception:
                    pass

        self._recently_unlocked = newly_unlocked
        return newly_unlocked

    def _unlock(self, achievement_id: str):
        """解锁成就"""
        if achievement_id not in self._unlocked:
            self._unlocked.append(achievement_id)
            self._history.append({
                "id": achievement_id,
                "unlocked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })
            self._save()

    def get_unlocked(self) -> List[Achievement]:
        """获取已解锁的成就列表"""
        return [ACHIEVEMENTS[aid] for aid in self._unlocked if aid in ACHIEVEMENTS]

    def get_all(self) -> List[tuple]:
        """获取所有成就及其解锁状态"""
        return [
            (ACHIEVEMENTS[aid], aid in self._unlocked)
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
        return len(self._unlocked)

    @property
    def total_count(self) -> int:
        """获取总成就数量"""
        return len(ACHIEVEMENTS)
