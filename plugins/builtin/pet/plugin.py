#!/usr/bin/env python3
# plugins/builtin/pet/plugin.py - 宠物插件
"""电子宠物插件 - 支持动画和状态变化"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

from lib.plugins.core import Plugin, PluginInfo, PluginContext, PluginPriority


class PetState(Enum):
    """宠物状态"""
    IDLE = "idle"           # 闲置
    HAPPY = "happy"         # 开心
    ALERT = "alert"         # 警觉（新任务）
    WORKING = "working"     # 工作
    WORRIED = "worried"     # 担心（任务太多）
    HUNGRY = "hungry"       # 饥饿（长时间无互动）
    SLEEPING = "sleeping"   # 睡眠


class PetEvolution(Enum):
    """宠物进化阶段"""
    BABY = "baby"           # 幼年期
    CHILD = "child"         # 成长期
    TEEN = "teen"           # 青春期
    ADULT = "adult"         # 成年期


# 不同状态的 ASCII 艺术
PET_ARTS: Dict[str, Dict[PetState, List[str]]] = {
    "bunny": {
        PetState.IDLE: [
            "   ∧_∧",
            "  ( ^ω^)",
            "  o_(\")(\")"
        ],
        PetState.HAPPY: [
            "   ∧_∧",
            "  ( ★ω★)",
            "  o_(\")(\")"
        ],
        PetState.ALERT: [
            "   ∧_∧",
            "  ( OωO)",
            "  o_(\")(\")"
        ],
        PetState.WORKING: [
            "   ∧_∧",
            "  ( ·ω·)",
            "  o_(\")(\")"
        ],
        PetState.WORRIED: [
            "   ∧_∧",
            "  ( ;ω;)",
            "  o_(\")(\")"
        ],
        PetState.HUNGRY: [
            "   ∧_∧",
            "  ( -ω-)",
            "  o_(\")(\")  zzz"
        ],
        PetState.SLEEPING: [
            "   ∧_∧",
            "  ( -ω-)",
            "  o_(\")(\")  💤"
        ],
    },
    "fox": {
        PetState.IDLE: [
            "   / \\__",
            "  (    @@___",
            "  /         \\",
            " /     .  .  \\",
            "/    .      . \\"
        ],
        PetState.HAPPY: [
            "   / \\__",
            "  ( ★  @@___",
            "  /         \\",
            " /     ^  ^  \\",
            "/    .      . \\"
        ],
        PetState.ALERT: [
            "   / \\__",
            "  ( O  @@___",
            "  /         \\",
            " /     .  .  \\",
            "/    .      . \\"
        ],
        PetState.WORKING: [
            "   / \\__",
            "  ( ·  @@___",
            "  /         \\",
            " /     .  .  \\",
            "/    .      . \\"
        ],
        PetState.WORRIED: [
            "   / \\__",
            "  ( ;  @@___",
            "  /         \\",
            " /     ;  ;  \\",
            "/    .      . \\"
        ],
        PetState.HUNGRY: [
            "   / \\__",
            "  ( -  @@___",
            "  /         \\",
            " /     -  -  \\",
            "/    .      . \\"
        ],
        PetState.SLEEPING: [
            "   / \\__",
            "  ( -  @@___ 💤",
            "  /         \\",
            " /     -  -  \\",
            "/    .      . \\"
        ],
    },
    "dragon": {
        PetState.IDLE: [
            "    /\\___/\\",
            "   (  ^ω^  )",
            "  /|       |\\",
            "  \\|  ___  |/",
            "   | |   | |"
        ],
        PetState.HAPPY: [
            "    /\\___/\\",
            "   (  ★ω★  ) ✨",
            "  /|       |\\",
            "  \\|  ___  |/",
            "   | |   | |"
        ],
        PetState.ALERT: [
            "    /\\___/\\",
            "   (  OωO  )",
            "  /|       |\\",
            "  \\|  ___  |/",
            "   | |   | |"
        ],
        PetState.WORKING: [
            "    /\\___/\\",
            "   (  ·ω·  )",
            "  /|       |\\",
            "  \\|  ___  |/",
            "   | |   | |"
        ],
        PetState.WORRIED: [
            "    /\\___/\\",
            "   (  ;ω;  )",
            "  /|       |\\",
            "  \\|  ___  |/",
            "   | |   | |"
        ],
        PetState.HUNGRY: [
            "    /\\___/\\",
            "   (  -ω-  )",
            "  /|       |\\",
            "  \\|  ___  |/",
            "   | |   | | 💤"
        ],
        PetState.SLEEPING: [
            "    /\\___/\\",
            "   (  -ω-  )",
            "  /|       |\\",
            "  \\|  ___  |/",
            "   | |   | | 💤💤"
        ],
    }
}


@dataclass
class PetData:
    """宠物数据"""
    evolution: PetEvolution = PetEvolution.BABY
    total_interactions: int = 0
    consecutive_days: int = 0
    last_interaction: float = 0.0
    current_state: PetState = PetState.IDLE
    mood_text: str = ""
    mood_text_time: float = 0.0


class PetPlugin(Plugin):
    """宠物插件"""

    def __init__(self):
        super().__init__()
        self._data = PetData()
        self._pet_type = "bunny"
        self._frame = 0
        self._animation_id: Optional[str] = None
        self._mood_messages: Dict[PetState, List[str]] = {
            PetState.HAPPY: ["开心~", "好棒!", "太好了!", "耶!"],
            PetState.ALERT: ["有新任务!", "注意!", "来了来了!"],
            PetState.WORKING: ["努力中...", "工作中...", "加油!"],
            PetState.WORRIED: ["任务好多...", "有点担心", "加油..."],
            PetState.HUNGRY: ["好饿...", "想休息...", "zzz..."],
            PetState.SLEEPING: ["Zzz...", "梦中...", "..."],
        }

    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            id="builtin.pet",
            name="电子宠物",
            version="2.0.0",
            author="Claude",
            description="可爱的 ASCII 艺术宠物，根据状态变化",
            priority=PluginPriority.NORMAL,
            provides=["pet_system", "pet_art"],
            hooks=["render_pet_area", "on_new_task", "on_task_complete", "on_achievement_unlock"]
        )

    def on_load(self):
        super().on_load()
        self._pet_type = self.get_config("pet_type", "bunny")

        # 注册钩子
        self.register_hook("render_pet_area", self._render_pet_area)
        self.register_hook("on_new_task", self._on_new_task)
        self.register_hook("on_task_complete", self._on_task_complete)
        self.register_hook("on_achievement_unlock", self._on_achievement_unlock)

    def on_start(self):
        super().on_start()
        self._data.last_interaction = time.time()

    # ========== 钩子实现 ==========

    def _render_pet_area(self, start_row: int, width: int) -> List[Tuple[int, int, str, int]]:
        """渲染宠物区域"""
        self._update_state()
        self._frame += 1

        results = []
        art = self._get_current_art()

        for i, line in enumerate(art):
            row = start_row + i
            # 居中显示
            col = max(0, (width - len(line)) // 2)
            results.append((row, col, line, 0))  # 0 = 默认颜色

        # 显示心情文字
        if self._data.mood_text and time.time() - self._data.mood_text_time < 3.0:
            mood_row = start_row + len(art)
            mood_col = max(0, (width - len(self._data.mood_text)) // 2)
            results.append((mood_row, mood_col, self._data.mood_text, 0))

        return results

    def _on_new_task(self, entry: dict):
        """新任务入队"""
        self._data.total_interactions += 1
        self._data.last_interaction = time.time()
        self.set_state(PetState.ALERT)
        self._set_mood("新任务!")

    def _on_task_complete(self, entry: dict, stats: dict):
        """任务完成"""
        self._data.last_interaction = time.time()
        self.set_state(PetState.HAPPY)
        self._set_random_mood(PetState.HAPPY)

        # 触发庆祝动画
        if self._context and self._context.animation_engine:
            self._context.animation_engine.play("pet_celebrate", "pet_animation")

        # 触发粒子效果
        if self._context and self._context.particle_system:
            # 获取宠物位置（大约在屏幕底部）
            self._context.particle_system.create_sparkle(20, 5, 8)

    def _on_achievement_unlock(self, achievement_id: str, achievement_data: dict):
        """成就解锁"""
        self._data.last_interaction = time.time()
        self.set_state(PetState.HAPPY)
        self._set_mood("解锁成就!")

        # 触发庆祝粒子
        if self._context and self._context.particle_system:
            self._context.particle_system.create_celebration(20, 8, 6)

    # ========== 状态管理 ==========

    def set_state(self, state: PetState):
        """设置宠物状态"""
        self._data.current_state = state

    def _update_state(self):
        """根据时间和互动更新状态"""
        now = time.time()
        idle_time = now - self._data.last_interaction

        # 长时间无互动
        if idle_time > 300:  # 5分钟
            self.set_state(PetState.SLEEPING)
        elif idle_time > 180:  # 3分钟
            self.set_state(PetState.HUNGRY)
        elif idle_time > 60:  # 1分钟
            self.set_state(PetState.IDLE)

    def _set_mood(self, text: str):
        """设置心情文字"""
        self._data.mood_text = text
        self._data.mood_text_time = time.time()

    def _set_random_mood(self, state: PetState):
        """随机设置心情"""
        import random
        messages = self._mood_messages.get(state, [""])
        if messages:
            self._set_mood(random.choice(messages))

    def _get_current_art(self) -> List[str]:
        """获取当前状态的 ASCII 艺术"""
        pet_arts = PET_ARTS.get(self._pet_type, PET_ARTS["bunny"])
        return pet_arts.get(self._data.current_state, pet_arts[PetState.IDLE])

    # ========== 公共 API ==========

    def get_state(self) -> PetState:
        """获取当前状态"""
        return self._data.current_state

    def interact(self):
        """与宠物互动"""
        self._data.total_interactions += 1
        self._data.last_interaction = time.time()
        self.set_state(PetState.HAPPY)
        self._set_random_mood(PetState.HAPPY)

    def set_pet_type(self, pet_type: str):
        """设置宠物类型"""
        if pet_type in PET_ARTS:
            self._pet_type = pet_type


# 插件入口
plugin_class = PetPlugin
