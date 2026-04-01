#!/usr/bin/env python3
# tests/test_pet_plugin.py - 宠物插件单元测试
"""宠物插件的单元测试 - 需要 pytest"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from plugins.builtin.pet.plugin import (
    PetPlugin, PetState, PetEvolution, PetArt, PET_ARTS
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
    p = PetPlugin()
    ctx = PluginContext(
        stdscr=None, theme_manager=None, data_dir="/tmp/test_data",
        config={}, render_buffer=None,
    )
    p.set_context(ctx)
    p.on_load()
    p.on_start()
    return p


class TestPetState:
    """测试宠物状态枚举"""

    def test_all_states_exist(self):
        expected = {"SLEEPING", "ALERT", "HAPPY", "WORRIED", "CELEBRATING", "HUNGRY", "YAWNING"}
        actual = {s.name for s in PetState}
        assert expected == actual


class TestPetEvolution:
    """测试宠物进化枚举"""

    def test_all_evolutions_exist(self):
        expected = {"BUNNY", "FOX", "DRAGON", "UNICORN"}
        actual = {e.name for e in PetEvolution}
        assert expected == actual


class TestPetPlugin:
    """测试宠物插件类"""

    def test_initial_state(self, plugin):
        assert plugin.get_state() == PetState.SLEEPING
        assert plugin.get_evolution() == PetEvolution.BUNNY

    def test_on_new_task(self, plugin):
        plugin._on_new_task({"type": "hitl"})
        assert plugin.get_state() == PetState.ALERT

    def test_on_task_complete(self, plugin):
        plugin._on_task_complete({}, {})
        assert plugin.get_state() == PetState.HAPPY

    def test_evolution_progression(self, plugin):
        plugin.set_achievement_count(10)
        assert plugin.get_evolution() == PetEvolution.FOX

        plugin.set_achievement_count(25)
        assert plugin.get_evolution() == PetEvolution.DRAGON

    def test_render_output(self, plugin):
        results = plugin._render_pet_area(10, 40)
        assert isinstance(results, list)
        assert len(results) > 0
        for item in results:
            assert isinstance(item, tuple)
            assert len(item) >= 3


if __name__ == "__main__":
    if pytest:
        pytest.main([__file__, "-v"])
    else:
        print("请安装 pytest: pip install pytest")
