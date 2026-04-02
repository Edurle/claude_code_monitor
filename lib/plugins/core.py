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
    stdscr: Any = None                      # curses 窗口
    theme_manager: Any = None               # 主题管理器
    data_dir: str = ""                      # 数据目录
    config: Dict[str, Any] = field(default_factory=dict)  # 插件配置
    render_buffer: Any = None               # 渲染缓冲区
    animation_engine: Optional['AnimationEngine'] = None  # 动画引擎
    particle_system: Optional['ParticleSystem'] = None    # 粒子系统
    monitor: Any = None                     # 监控器引用
    db: Any = None                          # Database 实例

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
