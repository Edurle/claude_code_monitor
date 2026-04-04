#!/usr/bin/env python3
# plugins/builtin/pet/plugin.py - 宠物插件
"""电子宠物插件 - 支持动画和状态变化"""

import time
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

from lib.plugins.core import Plugin, PluginInfo, PluginContext, PluginPriority
from lib.layout import Region, Slot, Rect


class PetState(Enum):
    """宠物状态 - 与 lib/pet.py 保持一致"""
    SLEEPING = "sleeping"      # 等待任务中
    ALERT = "alert"            # 新任务来了
    HAPPY = "happy"            # 开心（被摸头/任务完成）
    WORRIED = "worried"        # 任务堆积中
    CELEBRATING = "celebrating"  # 庆祝（成就解锁）
    HUNGRY = "hungry"          # 饥饿（长时间未互动）
    YAWNING = "yawning"        # 打哈欠（空闲）


class PetEvolution(Enum):
    """宠物进化形态 - 与 lib/pet.py 保持一致"""
    BUNNY = "bunny"      # 初始形态 - 小兔子
    FOX = "fox"          # 10个成就 - 狐狸
    DRAGON = "dragon"    # 25个成就 - 小龙
    UNICORN = "unicorn"  # 50个成就 - 独角兽


@dataclass
class PetArt:
    """宠物 ASCII 艺术"""
    lines: List[str]
    mood_text: str


# 不同形态的宠物艺术 - 与 lib/pet.py 保持一致
PET_ARTS: Dict[PetEvolution, Dict[PetState, PetArt]] = {
    PetEvolution.BUNNY: {
        PetState.SLEEPING: PetArt([
            "   ∧_∧",
            "  ( -.-) zZ",
            "  o_(\")(\")",
        ], "等待任务中..."),
        PetState.ALERT: PetArt([
            "   ∧_∧",
            "  ( •ω•)",
            "  o_(\")(\")",
        ], "新任务来了！按 Enter 处理~"),
        PetState.HAPPY: PetArt([
            "   ∧_∧",
            "  ( ^ω^)",
            "  o_(\")(\")",
        ], "干得好！继续保持~"),
        PetState.WORRIED: PetArt([
            "   ∧_∧",
            "  ( ;ω;)",
            "  o_(\")(\")",
        ], "任务堆积中...快处理一下！"),
        PetState.CELEBRATING: PetArt([
            "   ∧_∧",
            "  ( ★ω★)",
            "  ┗( )┛",
        ], "太棒了！🎉"),
        PetState.HUNGRY: PetArt([
            "   ∧_∧",
            "  ( <_<)",
            "  o_(\")(\")",
        ], "好饿...喂我一点零食吧~"),
        PetState.YAWNING: PetArt([
            "   ∧_∧",
            "  ( O.O) *yawn*",
            "  o_(\")(\")",
        ], "有点无聊呢..."),
    },
    PetEvolution.FOX: {
        PetState.SLEEPING: PetArt([
            "  / \\__",
            " (    @@)",
            " /     \\",
            "/  _  _ \\",
            "\\  \\\\//  /",
        ], "狐狸正在休息..."),
        PetState.ALERT: PetArt([
            "  / \\__",
            " (    @@)  !",
            " /     \\",
            "/  ▲  ▲ \\",
            "\\  ω    /",
        ], "狐狸发现新任务！"),
        PetState.HAPPY: PetArt([
            "  / \\__",
            " (    ^^)",
            " /     \\",
            "/  ▲  ▲ \\",
            "\\  ~ω~  /",
        ], "狐狸很开心！"),
        PetState.WORRIED: PetArt([
            "  / \\__",
            " (    ;;)",
            " /     \\",
            "/  ×  × \\",
            "\\  ;ω;  /",
        ], "狐狸有点担心..."),
        PetState.CELEBRATING: PetArt([
            "  / \\__",
            " (    ★★)",
            " /     \\",
            "/  ★  ★ \\",
            "╰(  ω  )╯",
        ], "狐狸在庆祝！🦊"),
        PetState.HUNGRY: PetArt([
            "  / \\__",
            " (    ..)",
            " /     \\",
            "/  -  - \\",
            "\\  ._.  /",
        ], "狐狸饿了..."),
        PetState.YAWNING: PetArt([
            "  / \\__",
            " (    oo)",
            " /     \\",
            "/  -  - \\",
            "\\  ω    /",
        ], "狐狸打了个哈欠~"),
    },
    PetEvolution.DRAGON: {
        PetState.SLEEPING: PetArt([
            "   /\\___/\\",
            "  (  -.-  )",
            " /|       |\\",
            "( |  zZ   | )",
            " \\|_______|/",
        ], "小龙在睡觉..."),
        PetState.ALERT: PetArt([
            "   /\\___/\\",
            "  (  •ω•  )",
            " /|       |\\",
            "( | FIRE! | )",
            " \\|_______|/",
        ], "小龙发现任务！"),
        PetState.HAPPY: PetArt([
            "   /\\___/\\",
            "  (  ^ω^  )",
            " /|       |\\",
            "( | <3    | )",
            " \\|_______|/",
        ], "小龙很开心！"),
        PetState.WORRIED: PetArt([
            "   /\\___/\\",
            "  (  ;ω;  )",
            " /|       |\\",
            "( | ???   | )",
            " \\|_______|/",
        ], "小龙有点担心..."),
        PetState.CELEBRATING: PetArt([
            "   /\\___/\\",
            "  (  ★ω★  )",
            " /|       |\\",
            "( | ***** | )",
            " ╰(     )╯",
        ], "小龙喷火庆祝！🐲"),
        PetState.HUNGRY: PetArt([
            "   /\\___/\\",
            "  (  <_<  )",
            " /|       |\\",
            "( | meat? | )",
            " \\|_______|/",
        ], "小龙想吃东西..."),
        PetState.YAWNING: PetArt([
            "   /\\___/\\",
            "  (  O.O  )",
            " /|       |\\",
            "( | *yawn*| )",
            " \\|_______|/",
        ], "小龙打哈欠~"),
    },
    PetEvolution.UNICORN: {
        PetState.SLEEPING: PetArt([
            "   \\|/",
            "   (o_o)",
            "  /(   )\\",
            " / |   | \\",
            "/  |   |  \\",
        ], "独角兽在休息..."),
        PetState.ALERT: PetArt([
            "   \\|/",
            "   (•ω•)",
            "  /(   )\\",
            " / | ✨ | \\",
            "/  |   |  \\",
        ], "独角兽发现魔法任务！"),
        PetState.HAPPY: PetArt([
            "   \\|/",
            "   (^ω^)",
            "  /(   )\\",
            " / | ❤️ | \\",
            "/  |   |  \\",
        ], "独角兽很开心！"),
        PetState.WORRIED: PetArt([
            "   \\|/",
            "   (;ω;)",
            "  /(   )\\",
            " / | ?!? | \\",
            "/  |   |  \\",
        ], "独角兽有点担心..."),
        PetState.CELEBRATING: PetArt([
            "   \\|/",
            "   (★ω★)",
            "  /(   )\\",
            " / | ✨✨ | \\",
            "╰(     )╯",
        ], "独角兽施展魔法！🦄"),
        PetState.HUNGRY: PetArt([
            "   \\|/",
            "   (<_<)",
            "  /(   )\\",
            " / | ... | \\",
            "/  |   |  \\",
        ], "独角兽需要魔法能量..."),
        PetState.YAWNING: PetArt([
            "   \\|/",
            "   (O.O)",
            "  /(   )\\",
            " / | zzz | \\",
            "/  |   |  \\",
        ], "独角兽打哈欠~"),
    },
}


@dataclass
class PetData:
    """宠物数据"""
    evolution: PetEvolution = PetEvolution.BUNNY
    total_interactions: int = 0
    consecutive_days: int = 0
    last_interaction: float = 0.0
    current_state: PetState = PetState.SLEEPING
    last_state_change: float = 0.0
    mood_text: str = ""
    mood_text_time: float = 0.0
    yawn_cooldown: float = 0.0
    achievement_count: int = 0


class PetPlugin(Plugin):
    """宠物插件"""

    # 根据成就数量确定进化形态
    EVOLUTION_THRESHOLDS = [
        (50, PetEvolution.UNICORN),
        (25, PetEvolution.DRAGON),
        (10, PetEvolution.FOX),
        (0, PetEvolution.BUNNY),
    ]

    def __init__(self):
        super().__init__()
        self._data = PetData()
        self._pet_type = "bunny"
        self._frame = 0
        self._animation_id: Optional[str] = None
        self._mood_messages: Dict[PetState, List[str]] = {
            PetState.HAPPY: ["开心~", "好棒!", "太好了!", "耶!"],
            PetState.ALERT: ["有新任务!", "注意!", "来了来了!"],
            PetState.WORRIED: ["任务好多...", "有点担心", "加油..."],
            PetState.HUNGRY: ["好饿...", "想休息...", "zzz..."],
            PetState.CELEBRATING: ["太棒了!", "庆祝!", "🎉"],
            PetState.YAWNING: ["啊~", "有点困", "..."],
            PetState.SLEEPING: ["Zzz...", "梦中...", "..."],
        }

    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            id="builtin.pet",
            name="电子宠物",
            version="2.1.0",
            author="Claude",
            description="可爱的 ASCII 艺术宠物，根据状态变化",
            priority=PluginPriority.NORMAL,
            provides=["pet_system", "pet_art"],
            hooks=["render_pet_area", "on_new_task", "on_task_complete", "on_achievement_unlock"]
        )

    def on_load(self):
        super().on_load()
        self._pet_type = self.get_config("pet_type", "bunny")
        self._data.last_interaction = time.time()
        self._data.last_state_change = time.time()

        # 通过 EventBus 订阅事件
        if self._context and self._context.events:
            self._context.events.on("task_complete", self._on_task_complete_event)
            self._context.events.on("queue_changed", self._on_queue_changed)

    def declare_regions(self) -> List[Region]:
        """声明宠物区域"""
        return [Region(id="pet", slot=Slot.LEFT, min_height=4, weight=30, priority=50)]

    def render_region(self, region_id: str, rect: Rect, data: dict) -> List[Tuple[int, int, str, int]]:
        """渲染指定区域。返回 [(row, col, text, attr), ...], 坐标相对于 Rect 左上角。"""
        if region_id != "pet":
            return []

        self._update_state(queue_length=len(data.get("entries", [])))
        self._frame += 1

        results = []
        art = self._get_current_art()

        for i, line in enumerate(art.lines):
            row = i  # 相对坐标
            # 居中显示
            col = max(0, (rect.width - len(line)) // 2)
            results.append((row, col, line, 0))  # 0 = 默认颜色

        # 显示心情文字
        mood = self._get_mood_text()
        if mood:
            mood_row = len(art.lines)
            mood_col = max(0, (rect.width - len(mood)) // 2)
            results.append((mood_row, mood_col, mood, 0))

        return results

    def handle_key(self, key: int, context: dict) -> bool:
        """处理按键。P=互动，F=喂食"""
        if key == ord('p') or key == ord('P'):
            self.interact()
            if self._context and self._context.events:
                self._context.events.emit("set_status", {"msg": "摸了摸宠物~"})
            return True
        elif key == ord('f') or key == ord('F'):
            self.feed()
            if self._context and self._context.events:
                self._context.events.emit("set_status", {"msg": "喂食成功~"})
            return True
        return False

    def feed(self):
        """喂食宠物"""
        self._data.total_interactions += 1
        self._data.last_interaction = time.time()
        self.set_state(PetState.HAPPY)
        self._set_mood("好吃!")

    def _on_task_complete_event(self, data: dict):
        """任务完成事件 (EventBus)"""
        self._data.last_interaction = time.time()
        self.set_state(PetState.HAPPY)
        self._set_random_mood(PetState.HAPPY)

        # 触发庆祝动画
        if self._context and self._context.animation_engine:
            self._context.animation_engine.play("pet_celebrate", "pet_animation")

        # 触发粒子效果
        if self._context and self._context.particle_system:
            self._context.particle_system.create_sparkle(20, 5, 8)

    def _on_queue_changed(self, data: dict):
        """队列变化事件 (EventBus)"""
        queue_length = data.get("queue_length", 0) if data else 0
        if queue_length > 0:
            self._data.total_interactions += 1
            self._data.last_interaction = time.time()
            self.set_state(PetState.ALERT)
            self._set_mood("新任务!")

    def on_start(self):
        super().on_start()
        self._data.last_interaction = time.time()
        self._data.last_state_change = time.time()

    # ========== 钩子实现 ==========

    def _render_pet_area(self, start_row: int, width: int) -> List[Tuple[int, int, str, int]]:
        """渲染宠物区域"""
        self._update_state()
        self._frame += 1

        results = []
        art = self._get_current_art()

        for i, line in enumerate(art.lines):
            row = start_row + i
            # 居中显示
            col = max(0, (width - len(line)) // 2)
            results.append((row, col, line, 0))  # 0 = 默认颜色

        # 显示心情文字
        mood = self._get_mood_text()
        if mood:
            mood_row = start_row + len(art.lines)
            mood_col = max(0, (width - len(mood)) // 2)
            results.append((mood_row, mood_col, mood, 0))

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
        self._data.achievement_count += 1
        self._update_evolution()
        self.set_state(PetState.CELEBRATING)
        self._set_mood("解锁成就!")

        # 触发庆祝粒子
        if self._context and self._context.particle_system:
            self._context.particle_system.create_celebration(20, 8, 6)

    # ========== 状态管理 ==========

    def set_state(self, state: PetState):
        """设置宠物状态"""
        if state != self._data.current_state:
            self._data.current_state = state
            self._data.last_state_change = time.time()

    def _update_state(self, queue_length: int = 0):
        """根据时间和互动更新状态"""
        now = time.time()
        idle_time = now - self._data.last_interaction
        state_duration = now - self._data.last_state_change

        # 庆祝状态持续一段时间后恢复
        if self._data.current_state == PetState.CELEBRATING and state_duration > 3:
            self.set_state(PetState.HAPPY)
            return

        # 开心状态持续一段时间后恢复
        if self._data.current_state == PetState.HAPPY and state_duration > 5:
            self.set_state(PetState.SLEEPING if queue_length == 0 else PetState.ALERT)
            return

        # 警报状态持续一段时间后
        if self._data.current_state == PetState.ALERT and state_duration > 10:
            if queue_length > 3:
                self.set_state(PetState.WORRIED)
            else:
                self.set_state(PetState.SLEEPING if queue_length == 0 else PetState.ALERT)
            return

        # 空闲时的行为
        if queue_length == 0 and self._data.current_state == PetState.SLEEPING:
            # 长时间无互动
            if idle_time > 300:  # 5分钟
                self.set_state(PetState.HUNGRY)
            # 随机打哈欠
            elif idle_time > 60 and now > self._data.yawn_cooldown:
                if random.random() < 0.1:  # 10%概率
                    self.set_state(PetState.YAWNING)
                    self._data.yawn_cooldown = now + 30  # 30秒冷却

        # 哈欠状态恢复
        if self._data.current_state == PetState.YAWNING and state_duration > 3:
            self.set_state(PetState.SLEEPING)

        # 根据队列长度更新状态
        if queue_length > 5 and self._data.current_state not in [PetState.CELEBRATING, PetState.WORRIED]:
            self.set_state(PetState.WORRIED)

    def _set_mood(self, text: str):
        """设置心情文字"""
        self._data.mood_text = text
        self._data.mood_text_time = time.time()

    def _set_random_mood(self, state: PetState):
        """随机设置心情"""
        messages = self._mood_messages.get(state, [""])
        if messages:
            self._set_mood(random.choice(messages))

    def _get_mood_text(self) -> str:
        """获取当前心情文字"""
        # 优先显示手动设置的心情
        if self._data.mood_text and time.time() - self._data.mood_text_time < 3.0:
            return self._data.mood_text
        # 否则返回当前状态的默认心情
        art = self._get_current_art()
        return art.mood_text

    def _get_current_art(self) -> PetArt:
        """获取当前状态的 ASCII 艺术"""
        pet_arts = PET_ARTS.get(self._data.evolution, PET_ARTS[PetEvolution.BUNNY])
        return pet_arts.get(self._data.current_state, pet_arts[PetState.SLEEPING])

    def _get_evolution(self, achievement_count: int) -> PetEvolution:
        """根据成就数量获取进化形态"""
        for threshold, evolution in self.EVOLUTION_THRESHOLDS:
            if achievement_count >= threshold:
                return evolution
        return PetEvolution.BUNNY

    def _update_evolution(self) -> bool:
        """更新进化形态，返回是否发生进化"""
        new_evolution = self._get_evolution(self._data.achievement_count)
        if new_evolution != self._data.evolution:
            self._data.evolution = new_evolution
            self.set_state(PetState.CELEBRATING)
            return True
        return False

    # ========== 公共 API ==========

    def get_state(self) -> PetState:
        """获取当前状态"""
        return self._data.current_state

    def get_evolution(self) -> PetEvolution:
        """获取当前进化形态"""
        return self._data.evolution

    def interact(self):
        """与宠物互动"""
        self._data.total_interactions += 1
        self._data.last_interaction = time.time()
        self.set_state(PetState.HAPPY)
        self._set_random_mood(PetState.HAPPY)

    def set_pet_type(self, pet_type: str):
        """设置宠物类型"""
        if pet_type in ["bunny", "fox", "dragon", "unicorn"]:
            self._pet_type = pet_type

    def get_evolution_name(self) -> str:
        """获取进化形态名称"""
        names = {
            PetEvolution.BUNNY: "小兔子",
            PetEvolution.FOX: "小狐狸",
            PetEvolution.DRAGON: "小龙",
            PetEvolution.UNICORN: "独角兽",
        }
        return names.get(self._data.evolution, "小兔子")

    def get_next_evolution_progress(self) -> Tuple[str, int, int]:
        """获取下一个进化进度 (名称, 当前进度, 需要数量)"""
        count = self._data.achievement_count
        for i, (threshold, evolution) in enumerate(self.EVOLUTION_THRESHOLDS):
            if count < threshold:
                continue
            if i > 0:
                next_threshold, next_evolution = self.EVOLUTION_THRESHOLDS[i - 1]
                names = {
                    PetEvolution.BUNNY: "小兔子",
                    PetEvolution.FOX: "小狐狸",
                    PetEvolution.DRAGON: "小龙",
                    PetEvolution.UNICORN: "独角兽",
                }
                return names[next_evolution], count, next_threshold
            break
        return "已满级", count, count

    def set_achievement_count(self, count: int):
        """设置成就数量（用于初始化）"""
        self._data.achievement_count = count
        self._data.evolution = self._get_evolution(count)


# 插件入口
plugin_class = PetPlugin
