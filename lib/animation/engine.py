#!/usr/bin/env python3
# lib/animation/engine.py - 动画引擎核心
"""帧动画引擎 - 支持字符画动画（最高20帧/秒）"""

import time
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path
from enum import Enum
import copy


class AnimationState(Enum):
    """动画状态"""
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"
    LOOPING = "looping"
    COMPLETED = "completed"


@dataclass
class Frame:
    """动画帧"""
    lines: List[str]                    # ASCII 艺术行
    duration: float = 0.1              # 帧持续时间（秒）
    effects: Dict[str, Any] = field(default_factory=dict)  # 额外效果（颜色、缩放等）


@dataclass
class Animation:
    """动画定义"""
    id: str
    name: str
    frames: List[Frame]
    fps: int = 10                       # 帧率
    loop: bool = False                  # 是否循环
    loop_count: int = -1                # 循环次数 (-1 无限)

    # 运行时状态
    _current_frame: int = field(default=0, repr=False)
    _loop_counter: int = field(default=0, repr=False)
    _state: AnimationState = field(default=AnimationState.STOPPED, repr=False)
    _start_time: float = field(default=0.0, repr=False)
    _last_frame_time: float = field(default=0.0, repr=False)
    _paused_time: float = field(default=0.0, repr=False)

    @property
    def total_frames(self) -> int:
        return len(self.frames)

    @property
    def current_frame(self) -> Frame:
        if self.frames:
            return self.frames[self._current_frame]
        return Frame(lines=[""])

    @property
    def state(self) -> AnimationState:
        return self._state

    @property
    def frame_index(self) -> int:
        return self._current_frame

    def play(self):
        """开始播放"""
        self._state = AnimationState.LOOPING if self.loop else AnimationState.PLAYING
        self._start_time = time.time()
        self._last_frame_time = self._start_time

    def pause(self):
        """暂停"""
        if self._state in [AnimationState.PLAYING, AnimationState.LOOPING]:
            self._state = AnimationState.PAUSED
            self._paused_time = time.time()

    def resume(self):
        """恢复"""
        if self._state == AnimationState.PAUSED:
            # 调整时间以补偿暂停时间
            pause_duration = time.time() - self._paused_time
            self._start_time += pause_duration
            self._last_frame_time += pause_duration
            self._state = AnimationState.LOOPING if self.loop else AnimationState.PLAYING

    def stop(self):
        """停止并重置"""
        self._state = AnimationState.STOPPED
        self._current_frame = 0
        self._loop_counter = 0

    def reset(self):
        """重置到初始状态"""
        self._current_frame = 0
        self._loop_counter = 0
        self._state = AnimationState.STOPPED

    def update(self, delta_time: float) -> Optional[Frame]:
        """更新动画，返回当前帧（如果需要更新）"""
        if self._state not in [AnimationState.PLAYING, AnimationState.LOOPING]:
            return None

        now = time.time()
        elapsed = now - self._last_frame_time
        frame_duration = self.frames[self._current_frame].duration if self.frames else 0.1

        if elapsed >= frame_duration:
            # 切换到下一帧
            self._current_frame += 1
            self._last_frame_time = now

            # 检查是否结束
            if self._current_frame >= self.total_frames:
                if self.loop and (self.loop_count == -1 or self._loop_counter < self.loop_count):
                    self._current_frame = 0
                    self._loop_counter += 1
                else:
                    self._state = AnimationState.COMPLETED
                    return None

        return self.current_frame

    def get_render_data(self) -> Tuple[List[str], Dict[str, Any]]:
        """获取当前帧的渲染数据"""
        frame = self.current_frame
        return frame.lines, frame.effects

    def copy(self) -> 'Animation':
        """创建动画副本（用于独立播放实例）"""
        return Animation(
            id=self.id,
            name=self.name,
            frames=copy.deepcopy(self.frames),
            fps=self.fps,
            loop=self.loop,
            loop_count=self.loop_count
        )


class AnimationEngine:
    """动画引擎 - 管理所有动画的播放"""

    MAX_FPS = 20  # 最大帧率限制

    def __init__(self, animations_dir: Optional[Path] = None):
        self.animations: Dict[str, Animation] = {}
        self.active_animations: Dict[str, Animation] = {}
        self._animations_dir = animations_dir
        self._last_update = time.time()

        if self._animations_dir and self._animations_dir.exists():
            self.load_animations(self._animations_dir)

    def load_animations(self, directory: Path):
        """从目录加载所有动画"""
        for anim_file in directory.glob("**/*.json"):
            try:
                self.load_animation(anim_file)
            except Exception as e:
                print(f"Warning: Failed to load animation {anim_file}: {e}", file=__import__('sys').stderr)

    def load_animation(self, file_path: Path) -> Optional[Animation]:
        """加载单个动画文件"""
        with open(file_path, encoding='utf-8') as f:
            data = json.load(f)

        frames = []
        for frame_data in data.get("frames", []):
            # 支持 lines 作为数组或单个多行字符串
            lines = frame_data.get("lines", [])
            if isinstance(lines, str):
                lines = lines.split('\n')

            frame = Frame(
                lines=lines,
                duration=frame_data.get("duration", 0.1),
                effects=frame_data.get("effects", {})
            )
            frames.append(frame)

        # 限制最大帧率
        fps = min(data.get("fps", 10), self.MAX_FPS)

        animation = Animation(
            id=data.get("id", file_path.stem),
            name=data.get("name", file_path.stem),
            frames=frames,
            fps=fps,
            loop=data.get("loop", False),
            loop_count=data.get("loop_count", -1)
        )

        self.animations[animation.id] = animation
        return animation

    def register_animation(self, animation: Animation):
        """注册动画"""
        self.animations[animation.id] = animation

    def create_animation(
        self,
        animation_id: str,
        frames: List[List[str]],
        durations: Optional[List[float]] = None,
        loop: bool = False
    ) -> Animation:
        """快速创建动画"""
        frame_list = []
        default_duration = 1.0 / min(len(frames), self.MAX_FPS) if frames else 0.1

        for i, lines in enumerate(frames):
            duration = (durations[i] if durations and i < len(durations) else default_duration)
            frame_list.append(Frame(lines=lines, duration=duration))

        animation = Animation(
            id=animation_id,
            name=animation_id,
            frames=frame_list,
            fps=min(len(frames), self.MAX_FPS),
            loop=loop
        )
        self.animations[animation_id] = animation
        return animation

    def play(self, animation_id: str, instance_id: Optional[str] = None) -> bool:
        """播放动画"""
        if animation_id not in self.animations:
            return False

        # 复制动画实例
        anim = self.animations[animation_id]
        instance = anim.copy()
        instance.play()

        key = instance_id or animation_id
        self.active_animations[key] = instance
        return True

    def stop(self, animation_id: str):
        """停止动画"""
        if animation_id in self.active_animations:
            self.active_animations[animation_id].stop()
            del self.active_animations[animation_id]

    def pause(self, animation_id: str):
        """暂停动画"""
        if animation_id in self.active_animations:
            self.active_animations[animation_id].pause()

    def resume(self, animation_id: str):
        """恢复动画"""
        if animation_id in self.active_animations:
            self.active_animations[animation_id].resume()

    def stop_all(self):
        """停止所有动画"""
        for anim in self.active_animations.values():
            anim.stop()
        self.active_animations.clear()

    def update(self) -> Dict[str, Tuple[Frame, Animation]]:
        """更新所有活动动画，返回 {animation_id: (current_frame, animation)}"""
        now = time.time()
        delta_time = now - self._last_update
        self._last_update = now

        current_frames = {}
        to_remove = []

        for anim_id, animation in self.active_animations.items():
            frame = animation.update(delta_time)
            if frame:
                current_frames[anim_id] = (frame, animation)
            elif animation.state == AnimationState.COMPLETED:
                to_remove.append(anim_id)

        # 清理已完成的动画
        for anim_id in to_remove:
            del self.active_animations[anim_id]

        return current_frames

    def get_frame(self, animation_id: str) -> Optional[Frame]:
        """获取动画当前帧"""
        if animation_id in self.active_animations:
            return self.active_animations[animation_id].current_frame
        return None

    def get_animation(self, animation_id: str) -> Optional[Animation]:
        """获取动画实例"""
        return self.active_animations.get(animation_id)

    def is_playing(self, animation_id: str) -> bool:
        """检查动画是否正在播放"""
        if animation_id in self.active_animations:
            return self.active_animations[animation_id].state in [
                AnimationState.PLAYING, AnimationState.LOOPING
            ]
        return False

    def is_completed(self, animation_id: str) -> bool:
        """检查动画是否已完成"""
        if animation_id in self.active_animations:
            return self.active_animations[animation_id].state == AnimationState.COMPLETED
        return False

    def get_active_count(self) -> int:
        """获取活动动画数量"""
        return len(self.active_animations)


# ========== 预设动画 ==========

def get_builtin_animations() -> Dict[str, Animation]:
    """获取内置动画"""
    animations = {}

    # 宠物开心动画
    animations["pet_happy"] = Animation(
        id="pet_happy",
        name="宠物开心",
        frames=[
            Frame(lines=["   ∧_∧", "  ( ^ω^)", "  o_(\")(\")"], duration=0.2),
            Frame(lines=["   ∧_∧", "  ( ^ω^) ✨", "  o_(\")(\")"], duration=0.15),
            Frame(lines=["   ∧_∧", "  ( ★ω★)", "  o_(\")(\")"], duration=0.15),
            Frame(lines=["   ∧_∧", "  ( ^ω^)", "  o_(\")(\")"], duration=0.2),
        ],
        fps=10,
        loop=False
    )

    # 宠物庆祝动画
    animations["pet_celebrate"] = Animation(
        id="pet_celebrate",
        name="宠物庆祝",
        frames=[
            Frame(lines=["   ∧_∧", "  ( ★ω★)", "  ┗( )┛"], duration=0.15),
            Frame(lines=["   ∧_∧ ✨", "  ( ★ω★)", "  ╰( )╯"], duration=0.15),
            Frame(lines=[" ✿ ∧_∧ ✿", "  ( ★ω★)", "  ╰( )╯"], duration=0.2),
            Frame(lines=["   ∧_∧", "  ( ^ω^) ✨", "  o_(\")(\")"], duration=0.2),
        ],
        fps=12,
        loop=False
    )

    # 成就解锁动画
    animations["achievement_unlock"] = Animation(
        id="achievement_unlock",
        name="成就解锁",
        frames=[
            Frame(lines=["  ╭───────╮", "  │  🏆   │", "  │  ???  │", "  ╰───────╯"], duration=0.1, effects={"scale": 0.5, "alpha": 0.3}),
            Frame(lines=["  ╭───────╮", "  │  🏆   │", "  │  ...  │", "  ╰───────╯"], duration=0.1, effects={"scale": 0.8, "alpha": 0.6}),
            Frame(lines=["  ╭───────╮", "  │  🏆   │", "  │  ★★★  │", "  ╰───────╯"], duration=0.15, effects={"scale": 1.0, "alpha": 1.0}),
            Frame(lines=[" ╭─────────╮", " │  🎉🏆🎉  │", " │  UNLOCK! │", " ╰─────────╯"], duration=0.2, effects={"glow": True}),
        ],
        fps=15,
        loop=False
    )

    # 边框彩虹动画
    animations["border_rainbow"] = Animation(
        id="border_rainbow",
        name="彩虹边框",
        frames=[
            Frame(lines=[], duration=0.125, effects={"border_color": 1}),  # 红
            Frame(lines=[], duration=0.125, effects={"border_color": 3}),  # 黄
            Frame(lines=[], duration=0.125, effects={"border_color": 2}),  # 绿
            Frame(lines=[], duration=0.125, effects={"border_color": 6}),  # 青
            Frame(lines=[], duration=0.125, effects={"border_color": 4}),  # 蓝
            Frame(lines=[], duration=0.125, effects={"border_color": 5}),  # 紫
        ],
        fps=8,
        loop=True
    )

    # 脉冲效果
    animations["pulse"] = Animation(
        id="pulse",
        name="脉冲",
        frames=[
            Frame(lines=[], duration=0.1, effects={"intensity": 0.5}),
            Frame(lines=[], duration=0.1, effects={"intensity": 0.8}),
            Frame(lines=[], duration=0.1, effects={"intensity": 1.0}),
            Frame(lines=[], duration=0.1, effects={"intensity": 0.8}),
            Frame(lines=[], duration=0.1, effects={"intensity": 0.5}),
        ],
        fps=10,
        loop=True
    )

    return animations
