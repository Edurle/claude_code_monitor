#!/usr/bin/env python3
# lib/database.py - SQLite 数据库管理
"""统一的 SQLite 数据库管理，支持 schema 版本管理和 JSON 旧数据自动导入"""

import json
import sqlite3
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 当前 schema 版本
SCHEMA_VERSION = 1

# v1 建表语句
_SCHEMA_V1 = [
    """CREATE TABLE IF NOT EXISTS daily_stats (
        date TEXT PRIMARY KEY,
        tasks INTEGER DEFAULT 0,
        hitl_count INTEGER DEFAULT 0,
        errors INTEGER DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS daily_projects (
        date TEXT NOT NULL,
        project TEXT NOT NULL,
        PRIMARY KEY (date, project)
    )""",
    """CREATE TABLE IF NOT EXISTS project_stats (
        project TEXT PRIMARY KEY,
        total INTEGER DEFAULT 0,
        hitl INTEGER DEFAULT 0,
        errors INTEGER DEFAULT 0,
        last_seen TEXT DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS hourly_stats (
        hour INTEGER PRIMARY KEY,
        count INTEGER DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS user_meta (
        key TEXT PRIMARY KEY,
        value TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS unlocked_achievements (
        achievement_id TEXT PRIMARY KEY,
        unlocked_at TEXT
    )""",
]

# 版本迁移函数 {版本号: 迁移函数}，未来 schema 变更在此添加
_MIGRATIONS: dict[int, callable] = {}


class Database:
    """SQLite 数据库单例"""

    _instance: Optional["Database"] = None

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            data_dir = Path(__file__).parent.parent / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "claude.db")

        self._db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")

        self._init_schema()
        self._run_migrations()
        self._import_json_if_exists()

    @classmethod
    def get_instance(cls, db_path: Optional[str] = None) -> "Database":
        if cls._instance is None:
            cls._instance = cls(db_path)
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """重置单例（仅用于测试）"""
        if cls._instance is not None:
            cls._instance._conn.close()
            cls._instance = None

    # ========== Schema 管理 ==========

    def _init_schema(self):
        """初始化基础 schema"""
        for sql in _SCHEMA_V1:
            self._conn.execute(sql)
        if self._get_version() == 0:
            self._set_version(SCHEMA_VERSION)
        self._conn.commit()

    def _get_version(self) -> int:
        cur = self._conn.execute("PRAGMA user_version")
        row = cur.fetchone()
        return row[0] if row else 0

    def _set_version(self, version: int):
        self._conn.execute(f"PRAGMA user_version={version}")
        self._conn.commit()

    def _run_migrations(self):
        current = self._get_version()
        if current >= SCHEMA_VERSION:
            return
        for v in range(current + 1, SCHEMA_VERSION + 1):
            migrator = _MIGRATIONS.get(v)
            if migrator:
                try:
                    migrator(self._conn)
                    logger.info("Migrated schema v%d -> v%d", v - 1, v)
                except Exception as e:
                    logger.error("Migration v%d failed: %s", v, e)
                    break
        self._set_version(SCHEMA_VERSION)

    # ========== JSON 自动导入 ==========

    def _import_json_if_exists(self):
        """检测旧 JSON 文件，自动导入到 SQLite"""
        data_dir = Path(self._db_path).parent
        self._import_stats_json(data_dir / "stats.json")
        self._import_achievements_json(data_dir / "achievements.json")

    def _import_stats_json(self, json_path: Path):
        if not json_path.exists():
            return
        # 检查是否已有数据（避免重复导入）
        row = self._conn.execute("SELECT COUNT(*) FROM daily_stats").fetchone()
        if row[0] > 0:
            return
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return
            # 导入 daily_stats
            for date_str, daily in data.get("daily", {}).items():
                self._conn.execute(
                    "INSERT OR IGNORE INTO daily_stats (date, tasks, hitl_count, errors) VALUES (?, ?, ?, ?)",
                    (date_str, daily.get("tasks", 0), daily.get("hitl_count", 0), daily.get("errors", 0))
                )
                for proj in daily.get("projects", []):
                    self._conn.execute(
                        "INSERT OR IGNORE INTO daily_projects (date, project) VALUES (?, ?)",
                        (date_str, proj)
                    )
            # 导入 project_stats
            for proj, stats in data.get("projects", {}).items():
                self._conn.execute(
                    "INSERT OR REPLACE INTO project_stats (project, total, hitl, errors, last_seen) VALUES (?, ?, ?, ?, ?)",
                    (proj, stats.get("total", 0), stats.get("hitl", 0), stats.get("errors", 0), stats.get("last_seen", ""))
                )
            # 导入 hourly_stats
            for hour, count in data.get("hourly", {}).items():
                self._conn.execute(
                    "INSERT OR REPLACE INTO hourly_stats (hour, count) VALUES (?, ?)",
                    (int(hour), count)
                )
            self._conn.commit()
            imported_path = json_path.with_suffix(".json.imported")
            json_path.rename(imported_path)
            logger.info("Imported %s -> SQLite, renamed to %s", json_path.name, imported_path.name)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("Failed to import %s: %s", json_path, e)

    def _import_achievements_json(self, json_path: Path):
        if not json_path.exists():
            return
        row = self._conn.execute("SELECT COUNT(*) FROM unlocked_achievements").fetchone()
        if row[0] > 0:
            return
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return
            # 导入 user_meta (stats)
            stats = data.get("stats", {})
            for key, value in stats.items():
                self._conn.execute(
                    "INSERT OR REPLACE INTO user_meta (key, value) VALUES (?, ?)",
                    (key, json.dumps(value) if not isinstance(value, str) else value)
                )
            # 导入 unlocked_achievements (来自 history，保留时间戳)
            history = data.get("history", [])
            for entry in history:
                self._conn.execute(
                    "INSERT OR IGNORE INTO unlocked_achievements (achievement_id, unlocked_at) VALUES (?, ?)",
                    (entry.get("id", ""), entry.get("unlocked_at", ""))
                )
            # 补充 unlocked 列表中有但 history 中没有的
            for aid in data.get("unlocked", []):
                self._conn.execute(
                    "INSERT OR IGNORE INTO unlocked_achievements (achievement_id, unlocked_at) VALUES (?, datetime('now'))",
                    (aid,)
                )
            self._conn.commit()
            imported_path = json_path.with_suffix(".json.imported")
            json_path.rename(imported_path)
            logger.info("Imported %s -> SQLite, renamed to %s", json_path.name, imported_path.name)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("Failed to import %s: %s", json_path, e)

    # ========== 便捷方法 ==========

    def execute(self, sql: str, params=()):
        return self._conn.execute(sql, params)

    def query_one(self, sql: str, params=()) -> Optional[dict]:
        row = self._conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def query_all(self, sql: str, params=()) -> list[dict]:
        rows = self._conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()
