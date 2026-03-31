#!/usr/bin/env python3
# lib/pet.py - 电子宠物助手
"""可爱的 ASCII 艺术宠物，根据队列状态和用户行为做出反应"""

import time
import random
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from enum import Enum


class PetState(Enum):
    """宠物状态"""
    SLEEPING = "sleeping"      # 等待任务中
    ALERT = "alert"            # 新任务来了
    HAPPY = "happy"            # 开心（被摸头/任务完成）
    WORRIED = "worried"        # 任务堆积中
    CELEBRATING = "celebrating"  # 庆祝（成就解锁）
    HUNGRY = "hungry"          # 饥饿（长时间未互动）
    YAWNING = "yawning"        # 打哈欠（空闲）


class PetEvolution(Enum):
    """宠物进化形态"""
    BUNNY = "bunny"      # 初始形态 - 小兔子
    FOX = "fox"          # 10个成就 - 狐狸
    DRAGON = "dragon"    # 25个成就 - 小龙
    UNICORN = "unicorn"  # 50个成就 - 独角兽


@dataclass
class PetArt:
    """宠物 ASCII 艺术"""
    lines: List[str]
    mood_text: str


# 不同形态的宠物艺术
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


class Pet:
    """电子宠物"""

    # 根据成就数量确定进化形态
    EVOLUTION_THRESHOLDS = [
        (50, PetEvolution.UNICORN),
        (25, PetEvolution.DRAGON),
        (10, PetEvolution.FOX),
        (0, PetEvolution.BUNNY),
    ]

    def __init__(self, achievement_count: int = 0):
        self._state = PetState.SLEEPING
        self._evolution = self._get_evolution(achievement_count)
        self._last_interaction = time.time()
        self._last_state_change = time.time()
        self._yawn_cooldown = 0

    def _get_evolution(self, achievement_count: int) -> PetEvolution:
        """根据成就数量获取进化形态"""
        for threshold, evolution in self.EVOLUTION_THRESHOLDS:
            if achievement_count >= threshold:
                return evolution
        return PetEvolution.BUNNY

    def update_evolution(self, achievement_count: int) -> bool:
        """更新进化形态，返回是否发生进化"""
        new_evolution = self._get_evolution(achievement_count)
        if new_evolution != self._evolution:
            self._evolution = new_evolution
            self._state = PetState.CELEBRATING
            self._last_state_change = time.time()
            return True
        return False

    def set_state(self, state: PetState):
        """设置宠物状态"""
        if state != self._state:
            self._state = state
            self._last_state_change = time.time()

    def on_new_task(self):
        """新任务到达"""
        self._last_interaction = time.time()
        self.set_state(PetState.ALERT)

    def on_task_complete(self):
        """任务完成"""
        self._last_interaction = time.time()
        self.set_state(PetState.HAPPY)

    def on_task_discard(self):
        """任务被丢弃"""
        self._last_interaction = time.time()

    def on_queue_clear(self):
        """队列被清空"""
        self._last_interaction = time.time()
        self.set_state(PetState.HAPPY)

    def on_achievement_unlock(self):
        """成就解锁"""
        self.set_state(PetState.CELEBRATING)

    def on_pet(self):
        """被摸头"""
        self._last_interaction = time.time()
        self.set_state(PetState.HAPPY)
        return random.choice([
            "喵~", "开心！", "喜欢~", "再摸摸！", "(*^▽^*)",
        ])

    def on_feed(self):
        """被喂食"""
        self._last_interaction = time.time()
        self.set_state(PetState.CELEBRATING)
        return random.choice([
            "好吃！", "谢谢~", " yummy!", "还想吃！", "(★ω★)",
        ])

    def update(self, queue_length: int = 0) -> str:
        """更新宠物状态，返回当前心情文字"""
        now = time.time()

        # 自动状态转换
        idle_time = now - self._last_interaction
        state_duration = now - self._last_state_change

        # 庆祝状态持续一段时间后恢复
        if self._state == PetState.CELEBRATING and state_duration > 3:
            self._state = PetState.HAPPY if queue_length == 0 else PetState.ALERT
            self._last_state_change = now

        # 开心状态持续一段时间后恢复
        elif self._state == PetState.HAPPY and state_duration > 5:
            self._state = PetState.SLEEPING if queue_length == 0 else PetState.ALERT
            self._last_state_change = now

        # 警报状态持续一段时间后
        elif self._state == PetState.ALERT and state_duration > 10:
            if queue_length > 3:
                self._state = PetState.WORRIED
            else:
                self._state = PetState.SLEEPING if queue_length == 0 else PetState.ALERT
            self._last_state_change = now

        # 空闲时的行为
        elif queue_length == 0 and self._state == PetState.SLEEPING:
            # 长时间无互动
            if idle_time > 300:  # 5分钟
                self._state = PetState.HUNGRY
            # 随机打哈欠
            elif idle_time > 60 and now > self._yawn_cooldown:
                if random.random() < 0.1:  # 10%概率
                    self._state = PetState.YAWNING
                    self._yawn_cooldown = now + 30  # 30秒冷却
                    self._last_state_change = now

        # 哈欠状态恢复
        elif self._state == PetState.YAWNING and state_duration > 3:
            self._state = PetState.SLEEPING
            self._last_state_change = now

        # 根据队列长度更新状态
        if queue_length > 5 and self._state not in [PetState.CELEBRATING, PetState.WORRIED]:
            self._state = PetState.WORRIED

        return self.current_art.mood_text

    @property
    def current_state(self) -> PetState:
        """获取当前状态"""
        return self._state

    @property
    def current_evolution(self) -> PetEvolution:
        """获取当前进化形态"""
        return self._evolution

    @property
    def current_art(self) -> PetArt:
        """获取当前状态的 ASCII 艺术"""
        return PET_ARTS[self._evolution][self._state]

    def get_art_lines(self) -> List[str]:
        """获取当前艺术的行列表"""
        return self.current_art.lines

    def get_evolution_name(self) -> str:
        """获取进化形态名称"""
        names = {
            PetEvolution.BUNNY: "小兔子",
            PetEvolution.FOX: "小狐狸",
            PetEvolution.DRAGON: "小龙",
            PetEvolution.UNICORN: "独角兽",
        }
        return names[self._evolution]

    def get_next_evolution_progress(self, achievement_count: int) -> Tuple[str, int, int]:
        """获取下一个进化进度 (名称, 当前进度, 需要数量)"""
        for i, (threshold, evolution) in enumerate(self.EVOLUTION_THRESHOLDS):
            if achievement_count < threshold:
                continue
            if i > 0:
                next_threshold, next_evolution = self.EVOLUTION_THRESHOLDS[i - 1]
                names = {
                    PetEvolution.BUNNY: "小兔子",
                    PetEvolution.FOX: "小狐狸",
                    PetEvolution.DRAGON: "小龙",
                    PetEvolution.UNICORN: "独角兽",
                }
                return names[next_evolution], achievement_count, next_threshold
            break
        return "已满级", achievement_count, achievement_count
