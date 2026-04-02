#!/usr/bin/env python3
# plugins/builtin/border_particles/plugin.py - 边框粒子效果插件
"""边框粒子效果插件 - 沿窗口四条边持续发射粒子，形成动态发光边框"""

import time
from typing import Dict, List, Tuple, Optional

from lib.plugins.core import Plugin, PluginInfo, PluginContext, PluginPriority
from lib.particles.system import ParticleConfig, ParticleSystem


class BorderParticlesPlugin(Plugin):
    """边框粒子效果插件"""

    def __init__(self):
        super().__init__()
        self._emitter_ids: Dict[str, str] = {}
        self._style: str = "sparkle"
        self._last_size: Tuple[int, int] = (0, 0)
        self._emit_rate_multiplier: float = 1.0
        self._particle_density: float = 1.0
        self._last_render_time: float = 0

    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            id="builtin.border_particles",
            name="边框粒子",
            version="1.0.0",
            author="Claude",
            description="沿窗口边缘发射粒子，形成动态发光边框",
            priority=PluginPriority.LOW,
            provides=["border_particle_effects"],
            hooks=["render_particles"]
        )

    def on_load(self):
        super().on_load()
        self._style = self.get_config("style", "sparkle")
        self._emit_rate_multiplier = float(self.get_config("emit_rate_multiplier", 1.0))
        self._particle_density = float(self.get_config("particle_density", 1.0))

        self.register_hook("render_particles", self._render_particles)

    def on_start(self):
        super().on_start()
        self._create_border_emitters()

    def on_stop(self):
        self._remove_border_emitters()
        super().on_stop()

    def on_reload(self):
        self._remove_border_emitters()
        self._style = self.get_config("style", "sparkle")
        self._emit_rate_multiplier = float(self.get_config("emit_rate_multiplier", 1.0))
        self._particle_density = float(self.get_config("particle_density", 1.0))
        self._create_border_emitters()

    # ========== 发射器管理 ==========

    def _create_border_emitters(self):
        """创建四条边的粒子发射器"""
        if not self._context or not self._context.particle_system:
            return

        ps: ParticleSystem = self._context.particle_system
        h, w = self._context.monitor.get_effective_size()
        self._last_size = (h, w)

        configs = self._get_style_configs(self._style, h, w)

        for edge, (config, x, y) in configs.items():
            emitter_id = f"border_{edge}"
            ps.create_emitter(emitter_id, config, x, y)
            self._emitter_ids[edge] = emitter_id

    def _remove_border_emitters(self):
        """移除所有边框发射器"""
        if not self._context or not self._context.particle_system:
            return
        ps = self._context.particle_system
        for emitter_id in self._emitter_ids.values():
            ps.remove_emitter(emitter_id)
        self._emitter_ids.clear()

    def _check_resize(self):
        """检测终端尺寸变化，重建发射器"""
        if not self._context or not self._context.monitor:
            return
        h, w = self._context.monitor.get_effective_size()
        if (h, w) != self._last_size:
            self._remove_border_emitters()
            self._create_border_emitters()

    # ========== 钩子实现 ==========

    def _render_particles(self) -> List[Tuple[int, int, str, int]]:
        """渲染边框粒子"""
        if not self._context or not self._context.particle_system:
            return []

        # 检测 resize
        self._check_resize()

        ps = self._context.particle_system

        # 更新粒子系统（与 particle_fx 共享，短时间内重复调用 delta≈0）
        now = time.time()
        if now - self._last_render_time > 0.05:
            ps.update()
            self._last_render_time = now

        # 仅渲染自己的发射器，避免重复渲染其他插件的粒子
        results = []
        for edge, emitter_id in self._emitter_ids.items():
            emitter = ps.get_emitter(emitter_id)
            if emitter:
                results.extend(emitter.render())

        return results

    # ========== 样式配置 ==========

    def _get_style_configs(self, style: str, h: int, w: int) -> Dict[str, Tuple[ParticleConfig, float, float]]:
        """获取指定样式的四边发射器配置

        返回: {edge_name: (ParticleConfig, x, y)}
        """
        m_rate = self._emit_rate_multiplier
        m_density = self._particle_density

        if style == "flame_trail":
            return self._flame_trail_configs(h, w, m_rate, m_density)
        elif style == "matrix":
            return self._matrix_configs(h, w, m_rate, m_density)
        elif style == "neon_glow":
            return self._neon_glow_configs(h, w, m_rate, m_density)
        else:
            return self._sparkle_configs(h, w, m_rate, m_density)

    @staticmethod
    def _sparkle_configs(h: int, w: int, m_rate: float, m_density: float) -> Dict[str, Tuple[ParticleConfig, float, float]]:
        """闪烁样式 - 短寿命闪烁粒子，轻微向内漂移"""
        common_chars = ["*", ".", "+", "~"]
        common_colors = [3, 6, 2, 5]  # 绿、青、黄、白
        common_life = (0.4, 1.0)
        common_gravity = 0
        common_friction = 0.3

        return {
            "top": (
                ParticleConfig(
                    emit_rate=max(1, int(8 * m_rate)),
                    max_particles=max(5, int(30 * m_density)),
                    chars=common_chars, colors=common_colors,
                    x_range=(0, max(1, w - 1)), y_range=(0, 0),
                    vx_range=(-0.2, 0.2), vy_range=(0.2, 0.8),
                    life_range=common_life, gravity=common_gravity, friction=common_friction,
                ), 0, 0
            ),
            "bottom": (
                ParticleConfig(
                    emit_rate=max(1, int(8 * m_rate)),
                    max_particles=max(5, int(30 * m_density)),
                    chars=common_chars, colors=common_colors,
                    x_range=(0, max(1, w - 1)), y_range=(0, 0),
                    vx_range=(-0.2, 0.2), vy_range=(-0.8, -0.2),
                    life_range=common_life, gravity=common_gravity, friction=common_friction,
                ), 0, h - 1
            ),
            "left": (
                ParticleConfig(
                    emit_rate=max(1, int(6 * m_rate)),
                    max_particles=max(5, int(25 * m_density)),
                    chars=common_chars, colors=common_colors,
                    x_range=(0, 0), y_range=(0, max(1, h - 1)),
                    vx_range=(0.2, 0.8), vy_range=(-0.2, 0.2),
                    life_range=common_life, gravity=common_gravity, friction=common_friction,
                ), 0, 0
            ),
            "right": (
                ParticleConfig(
                    emit_rate=max(1, int(6 * m_rate)),
                    max_particles=max(5, int(25 * m_density)),
                    chars=common_chars, colors=common_colors,
                    x_range=(0, 0), y_range=(0, max(1, h - 1)),
                    vx_range=(-0.8, -0.2), vy_range=(-0.2, 0.2),
                    life_range=common_life, gravity=common_gravity, friction=common_friction,
                ), w - 1, 0
            ),
        }

    @staticmethod
    def _flame_trail_configs(h: int, w: int, m_rate: float, m_density: float) -> Dict[str, Tuple[ParticleConfig, float, float]]:
        """火焰余烬样式 - 暖色快速粒子"""
        chars = ["^", "~", ".", ":"]
        colors = [4, 3, 2, 1]  # 红、黄、青变体

        return {
            "top": (
                ParticleConfig(
                    emit_rate=max(1, int(12 * m_rate)),
                    max_particles=max(5, int(35 * m_density)),
                    chars=chars, colors=colors,
                    x_range=(0, max(1, w - 1)), y_range=(0, 0),
                    vx_range=(-0.3, 0.3), vy_range=(0.5, 1.5),
                    life_range=(0.3, 0.8), gravity=0.1, friction=0.4,
                ), 0, 0
            ),
            "bottom": (
                ParticleConfig(
                    emit_rate=max(1, int(12 * m_rate)),
                    max_particles=max(5, int(35 * m_density)),
                    chars=chars, colors=colors,
                    x_range=(0, max(1, w - 1)), y_range=(0, 0),
                    vx_range=(-0.3, 0.3), vy_range=(-1.5, -0.5),
                    life_range=(0.3, 0.8), gravity=-0.1, friction=0.4,
                ), 0, h - 1
            ),
            "left": (
                ParticleConfig(
                    emit_rate=max(1, int(10 * m_rate)),
                    max_particles=max(5, int(30 * m_density)),
                    chars=chars, colors=colors,
                    x_range=(0, 0), y_range=(0, max(1, h - 1)),
                    vx_range=(0.5, 1.5), vy_range=(-0.3, 0.3),
                    life_range=(0.3, 0.8), gravity=0, friction=0.4,
                ), 0, 0
            ),
            "right": (
                ParticleConfig(
                    emit_rate=max(1, int(10 * m_rate)),
                    max_particles=max(5, int(30 * m_density)),
                    chars=chars, colors=colors,
                    x_range=(0, 0), y_range=(0, max(1, h - 1)),
                    vx_range=(-1.5, -0.5), vy_range=(-0.3, 0.3),
                    life_range=(0.3, 0.8), gravity=0, friction=0.4,
                ), w - 1, 0
            ),
        }

    @staticmethod
    def _matrix_configs(h: int, w: int, m_rate: float, m_density: float) -> Dict[str, Tuple[ParticleConfig, float, float]]:
        """矩阵样式 - 片假名字符，绿色为主"""
        chars = list("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!@#$%^&*") + \
                list("天地玄黄宇宙洪荒日月星辰寒来暑往云腾致雨金生丽水")
        colors = [2, 6, 2, 2]  # 绿色为主

        return {
            "top": (
                ParticleConfig(
                    emit_rate=max(1, int(10 * m_rate)),
                    max_particles=max(5, int(40 * m_density)),
                    chars=chars, colors=colors,
                    x_range=(0, max(1, w - 1)), y_range=(0, 0),
                    vx_range=(0, 0), vy_range=(1.5, 3.5),
                    life_range=(0.8, 2.0), gravity=0, friction=0,
                ), 0, 0
            ),
            "bottom": (
                ParticleConfig(
                    emit_rate=max(1, int(10 * m_rate)),
                    max_particles=max(5, int(40 * m_density)),
                    chars=chars, colors=colors,
                    x_range=(0, max(1, w - 1)), y_range=(0, 0),
                    vx_range=(0, 0), vy_range=(-3.5, -1.5),
                    life_range=(0.8, 2.0), gravity=0, friction=0,
                ), 0, h - 1
            ),
            "left": (
                ParticleConfig(
                    emit_rate=max(1, int(6 * m_rate)),
                    max_particles=max(5, int(25 * m_density)),
                    chars=chars, colors=colors,
                    x_range=(0, 0), y_range=(0, max(1, h - 1)),
                    vx_range=(1.5, 3.5), vy_range=(0, 0),
                    life_range=(0.8, 2.0), gravity=0, friction=0,
                ), 0, 0
            ),
            "right": (
                ParticleConfig(
                    emit_rate=max(1, int(6 * m_rate)),
                    max_particles=max(5, int(25 * m_density)),
                    chars=chars, colors=colors,
                    x_range=(0, 0), y_range=(0, max(1, h - 1)),
                    vx_range=(-3.5, -1.5), vy_range=(0, 0),
                    life_range=(0.8, 2.0), gravity=0, friction=0,
                ), w - 1, 0
            ),
        }

    @staticmethod
    def _neon_glow_configs(h: int, w: int, m_rate: float, m_density: float) -> Dict[str, Tuple[ParticleConfig, float, float]]:
        """霓虹样式 - 慢速长寿命，明亮色彩"""
        chars = ["=", "-", "|", "+", "#"]
        colors = [6, 2, 3, 1, 5]  # 品红、黄、绿、青、白

        return {
            "top": (
                ParticleConfig(
                    emit_rate=max(1, int(4 * m_rate)),
                    max_particles=max(5, int(40 * m_density)),
                    chars=chars, colors=colors,
                    x_range=(0, max(1, w - 1)), y_range=(0, 0),
                    vx_range=(-0.1, 0.1), vy_range=(0.1, 0.3),
                    life_range=(1.0, 2.5), gravity=0, friction=0.05,
                ), 0, 0
            ),
            "bottom": (
                ParticleConfig(
                    emit_rate=max(1, int(4 * m_rate)),
                    max_particles=max(5, int(40 * m_density)),
                    chars=chars, colors=colors,
                    x_range=(0, max(1, w - 1)), y_range=(0, 0),
                    vx_range=(-0.1, 0.1), vy_range=(-0.3, -0.1),
                    life_range=(1.0, 2.5), gravity=0, friction=0.05,
                ), 0, h - 1
            ),
            "left": (
                ParticleConfig(
                    emit_rate=max(1, int(3 * m_rate)),
                    max_particles=max(5, int(35 * m_density)),
                    chars=chars, colors=colors,
                    x_range=(0, 0), y_range=(0, max(1, h - 1)),
                    vx_range=(0.1, 0.3), vy_range=(-0.1, 0.1),
                    life_range=(1.0, 2.5), gravity=0, friction=0.05,
                ), 0, 0
            ),
            "right": (
                ParticleConfig(
                    emit_rate=max(1, int(3 * m_rate)),
                    max_particles=max(5, int(35 * m_density)),
                    chars=chars, colors=colors,
                    x_range=(0, 0), y_range=(0, max(1, h - 1)),
                    vx_range=(-0.3, -0.1), vy_range=(-0.1, 0.1),
                    life_range=(1.0, 2.5), gravity=0, friction=0.05,
                ), w - 1, 0
            ),
        }

    # ========== 公共 API ==========

    def set_style(self, style: str):
        """切换粒子样式"""
        if style != self._style:
            self._style = style
            self._remove_border_emitters()
            self._create_border_emitters()


# 插件入口
plugin_class = BorderParticlesPlugin
