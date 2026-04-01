#!/usr/bin/env python3
# tests/test_achievement_plugin.py - 成就插件单元测试
"""成就插件的单元测试 - 需要 pytest"""

import json
import tempfile
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from plugins.builtin.achievements.plugin import (
    AchievementsPlugin, Achievement, UserStats, ACHIEVEMENTS
)
from lib.plugins.core import PluginContext

try:
    import pytest
except ImportError:
    print("pytest 未安装，跳过 pytest 测试")
    pytest = None


@pytest.fixture
def plugin():
    """创建插件实例"""
    with tempfile.TemporaryDirectory() as tmpdir:
        p = AchievementsPlugin()
        ctx = PluginContext(
            stdscr=None, theme_manager=None, data_dir=tmpdir,
            config={}, render_buffer=None,
        )
        p.set_context(ctx)
        p.on_load()
        p.on_start()
        yield p


class TestUserStats:
    """测试用户统计数据"""

    def test_defaults(self):
        stats = UserStats()
        assert stats.total_tasks == 0

    def test_serialization(self):
        stats = UserStats(total_tasks=10, hitl_count=5)
        data = stats.to_dict()
        restored = UserStats.from_dict(data)
        assert restored.total_tasks == 10


class TestAchievements:
    """测试成就定义"""

    def test_all_defined(self):
        expected = {
            "first_step", "lightning", "zen_master", "night_owl",
            "early_bird", "multitasker", "streak_3", "streak_7",
            "streak_30", "centurion", "millennium", "perfectionist"
        }
        assert set(ACHIEVEMENTS.keys()) == expected


class TestAchievementsPlugin:
    """测试成就插件"""

    def test_initial_state(self, plugin):
        assert plugin.unlocked_count == 0

    def test_record_task(self, plugin):
        plugin._record_task("hitl", "test")
        assert plugin.stats.total_tasks == 1

    def test_first_step_unlock(self, plugin):
        plugin._record_task("hitl", "")
        unlocked = plugin._check_achievements()
        assert "first_step" in unlocked


if __name__ == "__main__":
    if pytest:
        pytest.main([__file__, "-v"])
    else:
        print("请安装 pytest: pip install pytest")
