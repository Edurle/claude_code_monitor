#!/usr/bin/env python3
# tests/run_tests.py - 简单的测试运行器（不依赖 pytest）
"""运行宠物和成就插件的单元测试"""

import sys
import time
import tempfile
import json
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 测试结果
passed = 0
failed = 0
errors = []

def test(name):
    """测试装饰器"""
    def decorator(func):
        def wrapper():
            global passed, failed, errors
            try:
                func()
                passed += 1
                print(f"  ✓ {name}")
            except AssertionError as e:
                failed += 1
                errors.append((name, str(e)))
                print(f"  ✗ {name}: {e}")
            except Exception as e:
                failed += 1
                errors.append((name, str(e)))
                print(f"  ✗ {name}: {type(e).__name__}: {e}")
        return wrapper
    return decorator


# ============ 宠物插件测试 ============
print("\n=== 宠物插件测试 ===\n")

from plugins.builtin.pet.plugin import (
    PetPlugin, PetState, PetEvolution, PetArt, PET_ARTS
)
from lib.plugins.core import PluginContext


@test("PetState - 所有状态存在")
def test_pet_states():
    expected = {"SLEEPING", "ALERT", "HAPPY", "WORRIED", "CELEBRATING", "HUNGRY", "YAWNING"}
    actual = {s.name for s in PetState}
    assert expected == actual, f"缺少: {expected - actual}"


@test("PetEvolution - 所有进化形态存在")
def test_pet_evolutions():
    expected = {"BUNNY", "FOX", "DRAGON", "UNICORN"}
    actual = {e.name for e in PetEvolution}
    assert expected == actual, f"缺少: {expected - actual}"


@test("PET_ARTS - 每个进化形态都有所有状态的艺术")
def test_pet_arts_complete():
    for evolution in PetEvolution:
        assert evolution in PET_ARTS, f"缺少 {evolution}"
        for state in PetState:
            assert state in PET_ARTS[evolution], f"{evolution} 缺少 {state}"
            art = PET_ARTS[evolution][state]
            assert isinstance(art, PetArt), f"{evolution}/{state} 类型错误"
            assert len(art.lines) > 0, f"{evolution}/{state} 行数为空"


@test("PetPlugin - 初始状态正确")
def test_pet_plugin_initial():
    plugin = PetPlugin()
    assert plugin.get_state() == PetState.SLEEPING
    assert plugin.get_evolution() == PetEvolution.BUNNY


@test("PetPlugin - 新任务状态转换")
def test_pet_plugin_new_task():
    plugin = PetPlugin()
    plugin._on_new_task({"type": "hitl"})
    assert plugin.get_state() == PetState.ALERT


@test("PetPlugin - 任务完成状态转换")
def test_pet_plugin_task_complete():
    plugin = PetPlugin()
    plugin._on_task_complete({}, {})
    assert plugin.get_state() == PetState.HAPPY


@test("PetPlugin - 成就解锁状态转换")
def test_pet_plugin_achievement():
    plugin = PetPlugin()
    plugin._on_achievement_unlock("test", {})
    assert plugin.get_state() == PetState.CELEBRATING
    assert plugin._data.achievement_count == 1


@test("PetPlugin - 进化系统")
def test_pet_plugin_evolution():
    plugin = PetPlugin()
    assert plugin.get_evolution() == PetEvolution.BUNNY

    plugin.set_achievement_count(10)
    assert plugin.get_evolution() == PetEvolution.FOX

    plugin.set_achievement_count(25)
    assert plugin.get_evolution() == PetEvolution.DRAGON

    plugin.set_achievement_count(50)
    assert plugin.get_evolution() == PetEvolution.UNICORN


@test("PetPlugin - 渲染输出格式正确")
def test_pet_plugin_render():
    plugin = PetPlugin()
    results = plugin._render_pet_area(10, 40)

    assert isinstance(results, list)
    assert len(results) > 0

    for item in results:
        assert isinstance(item, tuple), f"渲染项应该是元组: {type(item)}"
        assert len(item) >= 3, f"渲染项应该至少有3个元素: {len(item)}"
        row, col, text = item[0], item[1], item[2]
        assert isinstance(row, int), f"row 应该是 int: {type(row)}"
        assert isinstance(col, int), f"col 应该是 int: {type(col)}"
        assert isinstance(text, str), f"text 应该是 str: {type(text)}"


@test("PetPlugin - 渲染包含宠物艺术")
def test_pet_plugin_render_art():
    plugin = PetPlugin()
    results = plugin._render_pet_area(10, 40)

    art_text = "\n".join(item[2] for item in results if len(item) >= 3)
    # 小兔子应该有这些特征
    assert "∧_∧" in art_text or "•ω•" in art_text or "-.-" in art_text, \
        f"未找到宠物艺术特征: {art_text[:100]}"


@test("PetPlugin - 进化名称")
def test_pet_plugin_evolution_names():
    plugin = PetPlugin()
    assert plugin.get_evolution_name() == "小兔子"

    plugin.set_achievement_count(10)
    assert plugin.get_evolution_name() == "小狐狸"

    plugin.set_achievement_count(25)
    assert plugin.get_evolution_name() == "小龙"

    plugin.set_achievement_count(50)
    assert plugin.get_evolution_name() == "独角兽"


@test("PetPlugin - 进度显示")
def test_pet_plugin_progress():
    plugin = PetPlugin()
    name, current, needed = plugin.get_next_evolution_progress()
    assert name == "小狐狸"
    assert current == 0
    assert needed == 10


# ============ 成就插件测试 ============
print("\n=== 成就插件测试 ===\n")

from plugins.builtin.achievements.plugin import (
    AchievementsPlugin, Achievement, UserStats, ACHIEVEMENTS
)


@test("UserStats - 默认值")
def test_user_stats_defaults():
    stats = UserStats()
    assert stats.total_tasks == 0
    assert stats.hitl_count == 0
    assert stats.consecutive_days == 0


@test("UserStats - to_dict/from_dict")
def test_user_stats_serialization():
    stats = UserStats(total_tasks=10, hitl_count=5)
    data = stats.to_dict()
    assert data["total_tasks"] == 10

    restored = UserStats.from_dict(data)
    assert restored.total_tasks == 10
    assert restored.hitl_count == 5


@test("ACHIEVEMENTS - 所有成就已定义")
def test_achievements_defined():
    expected = {
        "first_step", "lightning", "zen_master", "night_owl",
        "early_bird", "multitasker", "streak_3", "streak_7",
        "streak_30", "centurion", "millennium", "perfectionist"
    }
    actual = set(ACHIEVEMENTS.keys())
    assert expected == actual, f"缺少: {expected - actual}"


@test("AchievementsPlugin - 初始状态")
def test_achievement_plugin_initial():
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin = AchievementsPlugin()
        context = PluginContext(
            stdscr=None, theme_manager=None, data_dir=tmpdir,
            config={}, render_buffer=None,
        )
        plugin.set_context(context)
        plugin.on_load()

        assert plugin.unlocked_count == 0
        assert plugin.total_count == len(ACHIEVEMENTS)


@test("AchievementsPlugin - 记录任务")
def test_achievement_plugin_record():
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin = AchievementsPlugin()
        context = PluginContext(
            stdscr=None, theme_manager=None, data_dir=tmpdir,
            config={}, render_buffer=None,
        )
        plugin.set_context(context)
        plugin.on_load()

        plugin._record_task("hitl", "project1")
        assert plugin.stats.total_tasks == 1
        assert plugin.stats.hitl_count == 1


@test("AchievementsPlugin - 解锁 first_step")
def test_achievement_plugin_first_step():
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin = AchievementsPlugin()
        context = PluginContext(
            stdscr=None, theme_manager=None, data_dir=tmpdir,
            config={}, render_buffer=None,
        )
        plugin.set_context(context)
        plugin.on_load()

        plugin._record_task("hitl", "")
        newly_unlocked = plugin._check_achievements()

        assert "first_step" in newly_unlocked
        assert plugin.unlocked_count == 1


@test("AchievementsPlugin - 数据持久化")
def test_achievement_plugin_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建并记录
        plugin = AchievementsPlugin()
        context = PluginContext(
            stdscr=None, theme_manager=None, data_dir=tmpdir,
            config={}, render_buffer=None,
        )
        plugin.set_context(context)
        plugin.on_load()
        plugin.on_start()  # 需要调用 on_start 来初始化 _load()

        plugin._record_task("hitl", "project1")
        plugin._check_achievements()
        plugin._save()

        # 验证文件
        data_file = Path(tmpdir) / "achievements.json"
        assert data_file.exists(), f"数据文件不存在: {data_file}"

        data = json.loads(data_file.read_text())
        assert data["stats"]["total_tasks"] == 1
        assert "first_step" in data["unlocked"]


@test("AchievementsPlugin - get_all()")
def test_achievement_plugin_get_all():
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin = AchievementsPlugin()
        context = PluginContext(
            stdscr=None, theme_manager=None, data_dir=tmpdir,
            config={}, render_buffer=None,
        )
        plugin.set_context(context)
        plugin.on_load()

        all_achievements = plugin.get_all()
        assert len(all_achievements) == len(ACHIEVEMENTS)

        for achievement, unlocked in all_achievements:
            assert isinstance(achievement, Achievement)
            assert isinstance(unlocked, bool)


@test("Achievement - night_owl 条件")
def test_achievement_night_owl():
    stats = UserStats(current_hour=2, tasks_today=1)
    assert ACHIEVEMENTS["night_owl"].condition(stats) == True

    stats = UserStats(current_hour=10, tasks_today=1)
    assert ACHIEVEMENTS["night_owl"].condition(stats) == False


@test("Achievement - streak 条件")
def test_achievement_streak():
    stats = UserStats(consecutive_days=3)
    assert ACHIEVEMENTS["streak_3"].condition(stats) == True

    stats = UserStats(consecutive_days=7)
    assert ACHIEVEMENTS["streak_7"].condition(stats) == True


@test("Achievement - perfectionist 条件")
def test_achievement_perfectionist():
    stats = UserStats(total_tasks=50, error_count=0)
    assert ACHIEVEMENTS["perfectionist"].condition(stats) == True

    stats = UserStats(total_tasks=50, error_count=1)
    assert ACHIEVEMENTS["perfectionist"].condition(stats) == False


# 运行所有测试
if __name__ == "__main__":
    # 收集所有测试函数
    test_funcs = []
    for name, obj in list(globals().items()):
        if name.startswith('test_') and callable(obj):
            test_funcs.append(obj)

    # 运行测试
    for func in test_funcs:
        func()

    # 打印结果
    print(f"\n{'='*50}")
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print(f"{'='*50}")

    if errors:
        print("\n失败的测试:")
        for name, error in errors:
            print(f"  - {name}: {error}")

    sys.exit(0 if failed == 0 else 1)
