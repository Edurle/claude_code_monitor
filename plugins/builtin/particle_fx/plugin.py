#!/usr/bin/env python3
# plugins/builtin/particle_fx/plugin.py - 粒子效果插件
"""粒子效果插件 - 在特定事件触发粒子动画"""

import time
from typing import Dict, List, Tuple, Optional

from lib.plugins.core import Plugin, PluginInfo, PluginContext, PluginPriority
from lib.eventbus import EventType


class ParticleFXPlugin(Plugin):
    """粒子效果插件"""

    def __init__(self):
        super().__init__()
        self._effects_config: Dict[str, dict] = {}
        self._active_effects: Dict[str, str] = {}  # {effect_name: emitter_id}

    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            id="builtin.particle_fx",
            name="粒子效果",
            version="1.0.0",
            author="Claude",
            description="在特定事件触发粒子动画效果",
            priority=PluginPriority.LOW,
            provides=["particle_effects"],
            hooks=["render_particles", "on_achievement_unlock", "on_task_complete"]
        )

    def on_load(self):
        super().on_load()

        # 加载配置
        self._effects_config = self.get_config("effects", {
            "celebration": {
                "enabled": True,
                "trigger_on_achievement": True,
            },
            "sparkle": {
                "enabled": True,
                "trigger_on_task": True,
            },
            "ambient": {
                "enabled": False,
                "type": "stars",
            }
        })

        # 注册钩子
        self.register_hook("render_particles", self._render_particles)
        self.register_hook("on_achievement_unlock", self._on_achievement_unlock)
        self.register_hook("on_task_complete", self._on_task_complete)

        # 通过 EventBus 订阅事件
        if self._context and self._context.events:
            self._context.events.subscribe(EventType.TASK_COMPLETE, self._on_task_complete_event)
            self._context.events.subscribe(EventType.ACHIEVEMENT_UNLOCK, self._on_achievement_unlock_event)

    def on_start(self):
        super().on_start()

        # 启动环境效果
        ambient = self._effects_config.get("ambient", {})
        if ambient.get("enabled") and self._context and self._context.particle_system:
            ps = self._context.particle_system
            effect_type = ambient.get("type", "stars")
            # 在屏幕顶部创建环境效果
            if effect_type == "stars":
                self._active_effects["ambient"] = ps.create_stars(0, 0, 60, 15)
            elif effect_type == "snow":
                self._active_effects["ambient"] = ps.create_snow(0, 0, 60, 15)

    # ========== 钩子实现 ==========

    def _render_particles(self) -> List[Tuple[int, int, str, int]]:
        """渲染粒子效果"""
        if not self._context or not self._context.particle_system:
            return []

        # 更新粒子系统
        self._context.particle_system.update()

        # 渲染所有粒子（不受 bounds 裁剪）
        return self._context.particle_system.render()

    def _on_achievement_unlock(self, achievement_id: str, achievement_data: dict):
        """成就解锁时触发庆祝效果"""
        config = self._effects_config.get("celebration", {})
        if not config.get("enabled"):
            return

        if not config.get("trigger_on_achievement", True):
            return

        if self._context and self._context.particle_system:
            # 使用实际屏幕尺寸计算中心位置
            ps = self._context.particle_system
            h, w = 20, 60  # 默认值
            if self._context.monitor:
                h, w = self._context.monitor.get_effective_size()
            center_y = h // 2
            center_x = w // 2

            ps.create_celebration(center_y, center_x, 6)
            ps.create_sparkle(center_y, center_x, 15)

    def _on_task_complete(self, entry: dict, stats: dict):
        """任务完成时触发闪烁效果"""
        config = self._effects_config.get("sparkle", {})
        if not config.get("enabled"):
            return

        if not config.get("trigger_on_task", True):
            return

        if self._context and self._context.particle_system:
            # 使用实际屏幕尺寸计算中心位置
            h, w = 20, 60  # 默认值
            if self._context.monitor:
                h, w = self._context.monitor.get_effective_size()
            center_y = h // 2
            center_x = w // 2

            self._context.particle_system.create_sparkle(center_x, center_y, 5)

    def render_overlay(self, screen_h: int, screen_w: int, data: dict) -> List[Tuple[int, int, str, int]]:
        """叠加层渲染。 返回 [(row, col, text, attr), ...], 绝对屏幕坐标。"""
        if not self._context or not self._context.particle_system:
            return []

        # 更新粒子系统
        self._context.particle_system.update()

        # 渲染所有粒子（不受 bounds 裁剪）
        return self._context.particle_system.render()

    # ========== EventBus 事件处理 ==========

    def _on_task_complete_event(self, data: dict):
        """任务完成事件 (EventBus)"""
        self._on_task_complete(data.get("entry", {}), data.get("stats", {}))

    def _on_achievement_unlock_event(self, data: dict):
        """成就解锁事件 (EventBus)"""
        self._on_achievement_unlock(data.get("achievement_id", ""), data)

    # ========== 公共 API ==========

    def trigger_effect(self, effect_name: str, x: float = 0, y: float = 0, **kwargs):
        """手动触发粒子效果"""
        if not self._context or not self._context.particle_system:
            return

        ps = self._context.particle_system

        if effect_name == "celebration":
            spread = kwargs.get("spread", 6)
            ps.create_celebration(y, x, spread)
        elif effect_name == "sparkle":
            count = kwargs.get("count", 10)
            ps.create_sparkle(y, x, count)
        elif effect_name == "fire":
            width = kwargs.get("width", 5)
            ps.create_fire(y, x, width)
        elif effect_name == "confetti":
            width = kwargs.get("width", 20)
            ps.create_confetti(y, x, width)


# 插件入口
plugin_class = ParticleFXPlugin
