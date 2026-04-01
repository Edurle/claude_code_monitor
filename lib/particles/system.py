#!/usr/bin/env python3
# lib/particles/system.py - 粒子系统核心
"""粒子系统 - 支持火焰、星星、雪花、烟花等效果"""

import time
import random
import math
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any, Callable
from enum import Enum


class BlendMode(Enum):
    """粒子混合模式"""
    NORMAL = "normal"
    ADDITIVE = "additive"    # 叠加（发光效果）
    MULTIPLY = "multiply"    # 正片叠底


@dataclass
class Particle:
    """单个粒子"""
    x: float
    y: float
    vx: float = 0              # x 速度
    vy: float = 0              # y 速度
    char: str = "*"            # 显示字符
    life: float = 1.0          # 生命值 (0-1)
    max_life: float = 1.0      # 最大生命
    color: int = 0             # curses 颜色对
    size: float = 1.0          # 大小

    # 物理属性
    gravity: float = 0         # 重力
    friction: float = 0        # 摩擦力
    bounce: float = 0          # 弹性系数
    rotation: float = 0        # 旋转角度
    rotation_speed: float = 0  # 旋转速度

    def update(self, delta_time: float) -> bool:
        """更新粒子状态，返回是否存活"""
        # 应用物理
        self.vy += self.gravity * delta_time
        self.vx *= (1 - self.friction * delta_time)
        self.vy *= (1 - self.friction * delta_time)

        # 更新位置
        self.x += self.vx * delta_time
        self.y += self.vy * delta_time

        # 更新旋转
        self.rotation += self.rotation_speed * delta_time

        # 更新生命
        self.life -= delta_time / self.max_life

        return self.life > 0

    @property
    def alpha(self) -> float:
        """透明度（基于生命值）"""
        return max(0, min(1, self.life))

    @property
    def is_alive(self) -> bool:
        """是否存活"""
        return self.life > 0


@dataclass
class ParticleConfig:
    """粒子发射器配置"""
    # 发射参数
    emit_rate: float = 10              # 每秒发射数量
    burst_count: int = 0               # 爆发数量（0 为持续发射）
    max_particles: int = 100           # 最大粒子数

    # 外观
    chars: List[str] = field(default_factory=lambda: ["*"])
    colors: List[int] = field(default_factory=lambda: [0])
    size_range: Tuple[float, float] = (1.0, 1.0)

    # 位置和速度
    x_range: Tuple[float, float] = (0, 0)
    y_range: Tuple[float, float] = (0, 0)
    vx_range: Tuple[float, float] = (-1, 1)
    vy_range: Tuple[float, float] = (-1, 1)

    # 生命周期
    life_range: Tuple[float, float] = (0.5, 1.5)

    # 物理属性
    gravity: float = 0
    friction: float = 0.1
    bounce: float = 0
    rotation_speed: float = 0

    # 混合模式
    blend_mode: BlendMode = BlendMode.NORMAL


class ParticleEmitter:
    """粒子发射器"""

    _id_counter = 0

    def __init__(self, config: ParticleConfig, x: float = 0, y: float = 0):
        ParticleEmitter._id_counter += 1
        self.id = f"emitter_{ParticleEmitter._id_counter}"

        self.config = config
        self.x = x
        self.y = y
        self.particles: List[Particle] = []
        self._emit_accumulator = 0.0
        self._active = True
        self._auto_remove = False  # 自动移除（当无粒子时）

    def emit(self, count: int = 1):
        """发射粒子"""
        for _ in range(count):
            if len(self.particles) >= self.config.max_particles:
                # 移除最老的粒子
                self.particles.pop(0)

            size = random.uniform(*self.config.size_range)
            particle = Particle(
                x=self.x + random.uniform(*self.config.x_range),
                y=self.y + random.uniform(*self.config.y_range),
                vx=random.uniform(*self.config.vx_range),
                vy=random.uniform(*self.config.vy_range),
                char=random.choice(self.config.chars),
                color=random.choice(self.config.colors),
                size=size,
                max_life=random.uniform(*self.config.life_range),
                life=1.0,
                gravity=self.config.gravity,
                friction=self.config.friction,
                bounce=self.config.bounce,
                rotation_speed=self.config.rotation_speed,
            )
            self.particles.append(particle)

    def burst(self, count: Optional[int] = None):
        """爆发发射"""
        count = count or self.config.burst_count or 20
        self.emit(count)

    def update(self, delta_time: float):
        """更新发射器和所有粒子"""
        if not self._active:
            # 仍然更新现有粒子
            self.particles = [p for p in self.particles if p.update(delta_time)]
            return

        # 持续发射
        if self.config.emit_rate > 0:
            self._emit_accumulator += delta_time * self.config.emit_rate
            while self._emit_accumulator >= 1:
                self.emit(1)
                self._emit_accumulator -= 1

        # 更新粒子
        self.particles = [p for p in self.particles if p.update(delta_time)]

    def render(self, bounds: Optional[Tuple[int, int, int, int]] = None) -> List[Tuple[int, int, str, int]]:
        """渲染粒子，返回 [(row, col, char, color)] 列表"""
        results = []

        for particle in self.particles:
            # 转换为整数坐标
            px, py = int(round(particle.x)), int(round(particle.y))

            # 边界检查
            if bounds:
                min_y, min_x, max_y, max_x = bounds
                if not (min_y <= py < max_y and min_x <= px < max_x):
                    continue

            # 根据透明度选择字符
            if particle.alpha > 0.7:
                char = particle.char
            elif particle.alpha > 0.4:
                char = self._get_faded_char(particle.char)
            else:
                char = "·"

            results.append((py, px, char, particle.color))

        return results

    def _get_faded_char(self, char: str) -> str:
        """获取淡化后的字符"""
        fade_map = {
            "✦": "·", "★": "·", "♦": "·", "●": "·",
            "❄": "·", "❅": "·", "❆": "·",
            "^": "·", "~": "·",
            "█": "▓", "▓": "▒", "▒": "░", "░": "·",
        }
        return fade_map.get(char, char)

    def start(self):
        """开始发射"""
        self._active = True

    def stop(self):
        """停止发射"""
        self._active = False

    def clear(self):
        """清除所有粒子"""
        self.particles.clear()

    @property
    def particle_count(self) -> int:
        return len(self.particles)

    @property
    def is_empty(self) -> bool:
        return len(self.particles) == 0


class ParticleSystem:
    """粒子系统管理器"""

    def __init__(self):
        self.emitters: Dict[str, ParticleEmitter] = {}
        self._last_update = time.time()

    def create_emitter(
        self,
        emitter_id: str,
        config: ParticleConfig,
        x: float = 0,
        y: float = 0
    ) -> ParticleEmitter:
        """创建粒子发射器"""
        emitter = ParticleEmitter(config, x, y)
        self.emitters[emitter_id] = emitter
        return emitter

    def remove_emitter(self, emitter_id: str):
        """移除发射器"""
        if emitter_id in self.emitters:
            del self.emitters[emitter_id]

    def get_emitter(self, emitter_id: str) -> Optional[ParticleEmitter]:
        """获取发射器"""
        return self.emitters.get(emitter_id)

    def update(self):
        """更新所有发射器"""
        now = time.time()
        delta_time = min(now - self._last_update, 0.1)  # 限制最大 delta
        self._last_update = now

        to_remove = []
        for emitter_id, emitter in self.emitters.items():
            emitter.update(delta_time)
            # 自动清理已完成且无粒子的发射器
            if emitter._auto_remove and emitter.is_empty and not emitter._active:
                to_remove.append(emitter_id)

        for emitter_id in to_remove:
            del self.emitters[emitter_id]

    def render(self, bounds: Optional[Tuple[int, int, int, int]] = None) -> List[Tuple[int, int, str, int]]:
        """渲染所有粒子"""
        all_particles = []
        for emitter in self.emitters.values():
            all_particles.extend(emitter.render(bounds))
        return all_particles

    def clear_all(self):
        """清除所有粒子"""
        for emitter in self.emitters.values():
            emitter.clear()

    def remove_all(self):
        """移除所有发射器"""
        self.emitters.clear()

    @property
    def total_particles(self) -> int:
        """获取总粒子数"""
        return sum(e.particle_count for e in self.emitters.values())

    # ========== 预设效果工厂方法 ==========

    def create_fire(self, x: float, y: float, width: float = 5) -> str:
        """创建火焰效果"""
        config = ParticleConfig(
            emit_rate=25,
            max_particles=40,
            chars=["^", "·", "°", "~", "▲"],
            colors=[3, 3, 4, 4, 5],  # 黄、橙、红
            x_range=(-width/2, width/2),
            y_range=(0, 0),
            vx_range=(-0.3, 0.3),
            vy_range=(-2.5, -1.0),
            life_range=(0.3, 0.7),
            gravity=-0.3,  # 上升
            friction=0.3,
        )
        emitter_id = f"fire_{int(time.time()*1000)}"
        self.create_emitter(emitter_id, config, x, y)
        return emitter_id

    def create_stars(self, x: float, y: float, width: float, height: float) -> str:
        """创建星星效果"""
        config = ParticleConfig(
            emit_rate=3,
            max_particles=25,
            chars=["✦", "✧", "·", "★"],
            colors=[3, 5, 6, 2],  # 多彩
            x_range=(0, width),
            y_range=(0, height),
            vx_range=(-0.1, 0.1),
            vy_range=(0, 0.3),
            life_range=(1.5, 4.0),
            gravity=0.05,
            friction=0.05,
        )
        emitter_id = f"stars_{int(time.time()*1000)}"
        self.create_emitter(emitter_id, config, x, y)
        return emitter_id

    def create_snow(self, x: float, y: float, width: float, height: float) -> str:
        """创建雪花效果"""
        config = ParticleConfig(
            emit_rate=12,
            max_particles=50,
            chars=["❄", "❅", "❆", "·", "*"],
            colors=[5, 5, 5, 5, 5],  # 白色
            x_range=(0, width),
            y_range=(0, 0),
            vx_range=(-0.4, 0.4),
            vy_range=(0.4, 1.2),
            life_range=(2.0, 5.0),
            gravity=0.08,
            friction=0.2,
        )
        emitter_id = f"snow_{int(time.time()*1000)}"
        self.create_emitter(emitter_id, config, x, y)
        return emitter_id

    def create_celebration(self, x: float, y: float, spread: float = 8) -> str:
        """创建庆祝效果（烟花爆发）"""
        config = ParticleConfig(
            emit_rate=0,  # 不持续发射
            burst_count=35,
            max_particles=50,
            chars=["✦", "★", "♦", "●", "✿", "❀"],
            colors=[2, 3, 4, 5, 6, 1],  # 多彩
            x_range=(-1, 1),
            y_range=(-1, 1),
            vx_range=(-spread, spread),
            vy_range=(-spread, spread),
            life_range=(0.6, 1.4),
            gravity=0.8,
            friction=0.15,
        )
        emitter_id = f"celebration_{int(time.time()*1000)}"
        emitter = self.create_emitter(emitter_id, config, x, y)
        emitter.burst(35)
        emitter._auto_remove = True
        return emitter_id

    def create_confetti(self, x: float, y: float, width: float = 20) -> str:
        """创建彩带效果"""
        config = ParticleConfig(
            emit_rate=15,
            max_particles=60,
            chars=["▀", "▄", "█", "▌", "▐"],
            colors=[1, 2, 3, 4, 5, 6],
            x_range=(-width/2, width/2),
            y_range=(0, 0),
            vx_range=(-0.5, 0.5),
            vy_range=(1.0, 2.0),
            life_range=(1.5, 3.0),
            gravity=0.3,
            friction=0.1,
            rotation_speed=5.0,
        )
        emitter_id = f"confetti_{int(time.time()*1000)}"
        self.create_emitter(emitter_id, config, x, y)
        return emitter_id

    def create_sparkle(self, x: float, y: float, count: int = 10) -> str:
        """创建闪烁效果"""
        config = ParticleConfig(
            emit_rate=0,
            burst_count=count,
            max_particles=count,
            chars=["✨", "★", "·"],
            colors=[3, 5, 6],
            x_range=(-2, 2),
            y_range=(-2, 2),
            vx_range=(-1.5, 1.5),
            vy_range=(-1.5, 1.5),
            life_range=(0.3, 0.6),
            gravity=0,
            friction=0.5,
        )
        emitter_id = f"sparkle_{int(time.time()*1000)}"
        emitter = self.create_emitter(emitter_id, config, x, y)
        emitter.burst(count)
        emitter._auto_remove = True
        return emitter_id

    def create_matrix_rain(self, x: float, y: float, width: float, height: float) -> str:
        """创建矩阵雨效果"""
        chars = [chr(c) for c in range(0x30A0, 0x30FF)]  # 片假名
        config = ParticleConfig(
            emit_rate=20,
            max_particles=80,
            chars=chars,
            colors=[2, 2, 2, 6],  # 绿色为主
            x_range=(0, width),
            y_range=(0, 0),
            vx_range=(0, 0),
            vy_range=(2, 4),
            life_range=(1.0, 2.5),
            gravity=0,
            friction=0,
        )
        emitter_id = f"matrix_{int(time.time()*1000)}"
        self.create_emitter(emitter_id, config, x, y)
        return emitter_id
