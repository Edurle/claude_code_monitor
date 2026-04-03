#!/usr/bin/env python3
# lib/plugins/core.py - 插件核心基类
"""插件系统核心定义"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from lib.animation.engine import AnimationEngine
    from lib.particles.system import ParticleSystem


class PluginPriority(Enum):
    """插件优先级"""
    LOWEST = 0
    LOW = 25
    NORMAL = 50
    HIGH = 75
    HIGHEST = 100
    MONITOR = 150  # 监控级，最后执行


class PluginState(Enum):
    """插件状态"""
    UNLOADED = "unloaded"
    LOADED = "loaded"
    ENABLED = "enabled"
    RUNNING = "running"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass
class PluginInfo:
    """插件元信息"""
    id: str                          # 唯一标识符 (如 builtin.pet)
    name: str                        # 显示名称
    version: str = "1.0.0"          # 版本号
    author: str = ""                 # 作者
    description: str = ""            # 描述
    dependencies: List[str] = field(default_factory=list)  # 依赖的其他插件
    priority: PluginPriority = PluginPriority.NORMAL
    provides: List[str] = field(default_factory=list)     # 提供的功能
    hooks: List[str] = field(default_factory=list)        # 注册的钩子


@dataclass
class PluginContext:
    """插件上下文 - 提供给插件的环境"""
    theme: Any = None            # IThemeManager
    db: Any = None               # IDatabase
    particles: Any = None        # IParticleSystem
    sessions: Any = None         # ISessionTracker
    stats: Any = None             # IStatsManager
    queue: Any = None             # IQueueManager
    events: Any = None            # IEventBus
    config: Dict[str, Any] = field(default_factory=dict)
    data_dir: str = ""
    animation_engine: Any = None

    def log(self, message: str, level: str = "INFO"):
        """记录日志"""
        import sys
        print(f"[{level}] {message}", file=sys.stderr)


class Plugin(ABC):
    """插件基类 - 所有插件必须继承此类"""

    def __init__(self):
        self._state = PluginState.UNLOADED
        self._context: Optional[PluginContext] = None
        self._hooks: Dict[str, Callable] = {}

    @property
    @abstractmethod
    def info(self) -> PluginInfo:
        """返回插件信息"""
        pass

    @property
    def state(self) -> PluginState:
        """获取当前状态"""
        return self._state

    def set_context(self, context: PluginContext):
        """设置插件上下文"""
        self._context = context

    # ========== 生命周期方法 ==========

    def on_load(self):
        """加载时调用（从磁盘加载模块）"""
        self._state = PluginState.LOADED

    def on_enable(self):
        """启用时调用（配置启用）"""
        self._state = PluginState.ENABLED

    def on_start(self):
        """启动时调用（开始运行）"""
        self._state = PluginState.RUNNING

    def on_stop(self):
        """停止时调用"""
        self._state = PluginState.ENABLED

    def on_disable(self):
        """禁用时调用"""
        self._state = PluginState.DISABLED

    def on_unload(self):
        """卸载时调用"""
        self._state = PluginState.UNLOADED

    def on_error(self, error: Exception):
        """错误处理"""
        self._state = PluginState.ERROR
        if self._context:
            self._context.log(f"Plugin error: {error}", "ERROR")

    # ========== 钩子注册 ==========

    def register_hook(self, hook_name: str, callback: Callable):
        """注册渲染钩子"""
        self._hooks[hook_name] = callback

    def get_hook(self, hook_name: str) -> Optional[Callable]:
        """获取钩子回调"""
        return self._hooks.get(hook_name)

    def get_all_hooks(self) -> Dict[str, Callable]:
        """获取所有注册的钩子"""
        return dict(self._hooks)

    # ========== 热重载支持 ==========

    def on_reload(self):
        """热重载时调用"""
        self.on_stop()
        self.on_unload()
        self.on_load()
        self.on_enable()
        self.on_start()

    # ========== 工具方法 ==========

    def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        if self._context and self._context.config:
            return self._context.config.get(key, default)
        return default

    # ── Region 渲染接口 ──

    def declare_regions(self) -> list:
        """声明此插件需要的布局区域。返回 Region 列表。"""
        return []

    def render_region(self, region_id: str, rect, data: dict) -> list:
        """渲染指定区域。返回 [(row, col, text, attr), ...], 坐标相对于 Rect 左上角。"""
        return []

    # ── 叠加渲染 (绝对坐标) ──

    def render_overlay(self, screen_h: int, screen_w: int, data: dict) -> list:
        """叠加层渲染。返回 [(row, col, text, attr), ...], 绝对屏幕坐标。"""
        return []

    # ── 全屏渲染 (返回非空即独占) ──

    def render_fullscreen(self, screen_h: int, screen_w: int, data: dict) -> list:
        """全屏渲染。返回非空列表表示独占整个屏幕。"""
        return []

    # ── 输入处理 ──

    def handle_key(self, key: int, context: dict) -> bool:
        """处理按键。返回 True 表示已消费该按键。"""
        return False
