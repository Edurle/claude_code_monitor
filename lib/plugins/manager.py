#!/usr/bin/env python3
# lib/plugins/manager.py - 插件生命周期管理
"""插件管理器 - 负责加载、启用、禁用插件"""

import importlib
import importlib.util
import sys
import yaml
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from .core import Plugin, PluginState, PluginContext, PluginInfo, PluginPriority
from .hooks import HookRegistry


@dataclass
class PluginConfig:
    """插件配置"""
    enabled: bool = True
    priority: int = 50
    settings: Dict[str, Any] = field(default_factory=dict)


class PluginManager:
    """插件管理器"""

    def __init__(self, plugin_dir: Path, config_path: Path):
        self.plugin_dir = Path(plugin_dir)
        self.config_path = Path(config_path)
        self.hook_registry = HookRegistry()

        # 插件存储
        self._plugins: Dict[str, Plugin] = {}
        self._configs: Dict[str, PluginConfig] = {}
        self._load_order: List[str] = []

        # 上下文（稍后设置）
        self._context: Optional[PluginContext] = None

    def set_context(self, context: PluginContext):
        """设置插件上下文"""
        self._context = context

    def load_config(self):
        """加载插件配置文件"""
        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    config_data = yaml.safe_load(f) or {}

                for plugin_id, settings in config_data.get("plugins", {}).items():
                    if isinstance(settings, bool):
                        self._configs[plugin_id] = PluginConfig(enabled=settings)
                    elif isinstance(settings, dict):
                        self._configs[plugin_id] = PluginConfig(
                            enabled=settings.get("enabled", True),
                            priority=settings.get("priority", 50),
                            settings=settings.get("settings", {})
                        )
            except Exception as e:
                print(f"Warning: Failed to load plugin config: {e}", file=sys.stderr)

    def save_config(self):
        """保存插件配置"""
        config_data = {"plugins": {}}
        for plugin_id, config in self._configs.items():
            config_data["plugins"][plugin_id] = {
                "enabled": config.enabled,
                "priority": config.priority,
                "settings": config.settings
            }

        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)

    def discover_plugins(self) -> List[str]:
        """发现所有可用插件"""
        discovered = []

        # 扫描 builtin 和 custom 目录
        for subdir in ["builtin", "custom"]:
            subdir_path = self.plugin_dir / subdir
            if not subdir_path.exists():
                continue

            for plugin_folder in subdir_path.iterdir():
                if plugin_folder.is_dir():
                    # 检查是否有 plugin.py 或 plugin.yaml
                    plugin_file = plugin_folder / "plugin.py"
                    if plugin_file.exists():
                        discovered.append(f"{subdir}.{plugin_folder.name}")

        return sorted(discovered)

    def _find_plugin_class(self, module) -> Optional[type]:
        """在模块中查找 Plugin 子类"""
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type) and
                issubclass(attr, Plugin) and
                attr is not Plugin):
                return attr
        return None

    def load_plugin(self, plugin_id: str) -> Optional[Plugin]:
        """加载单个插件"""
        if plugin_id in self._plugins:
            return self._plugins[plugin_id]

        # 解析插件路径
        parts = plugin_id.split(".")
        if len(parts) != 2:
            return None

        category, name = parts
        plugin_path = self.plugin_dir / category / name / "plugin.py"

        if not plugin_path.exists():
            return None

        try:
            # 动态导入模块
            module_name = f"plugins.{plugin_id.replace('.', '_')}"
            spec = importlib.util.spec_from_file_location(module_name, plugin_path)
            if spec is None or spec.loader is None:
                return None

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # 查找 Plugin 子类
            plugin_class = self._find_plugin_class(module)
            if plugin_class is None:
                return None

            # 实例化插件
            plugin = plugin_class()

            # 设置上下文
            if self._context:
                plugin_config = self._configs.get(plugin_id, PluginConfig())
                merged_config = {**self._context.config, **plugin_config.settings}
                plugin_context = PluginContext(
                    theme=self._context.theme,
                    db=self._context.db,
                    particles=self._context.particles,
                    sessions=self._context.sessions,
                    stats=self._context.stats,
                    queue=self._context.queue,
                    events=self._context.events,
                    config=merged_config,
                    data_dir=self._context.data_dir,
                    animation_engine=self._context.animation_engine,
                )
                plugin.set_context(plugin_context)

            # 调用加载
            plugin.on_load()

            # 注册钩子
            for hook_name, callback in plugin.get_all_hooks().items():
                priority = plugin.info.priority.value
                self.hook_registry.register(hook_name, plugin_id, callback, priority)

            self._plugins[plugin_id] = plugin
            self._load_order.append(plugin_id)

            return plugin

        except Exception as e:
            print(f"Error loading plugin {plugin_id}: {e}", file=sys.stderr)
            return None

    def unload_plugin(self, plugin_id: str):
        """卸载插件"""
        if plugin_id not in self._plugins:
            return

        plugin = self._plugins[plugin_id]

        # 停止并卸载
        if plugin.state == PluginState.RUNNING:
            plugin.on_stop()
        if plugin.state in [PluginState.ENABLED, PluginState.ERROR]:
            plugin.on_disable()
        plugin.on_unload()

        # 注销钩子
        self.hook_registry.unregister_all(plugin_id)

        del self._plugins[plugin_id]
        self._load_order.remove(plugin_id)

    def enable_plugin(self, plugin_id: str) -> bool:
        """启用插件"""
        config = self._configs.get(plugin_id, PluginConfig())
        config.enabled = True
        self._configs[plugin_id] = config

        if plugin_id in self._plugins:
            plugin = self._plugins[plugin_id]
            if plugin.state == PluginState.DISABLED:
                plugin.on_enable()
                return True
        else:
            plugin = self.load_plugin(plugin_id)
            return plugin is not None

        return False

    def disable_plugin(self, plugin_id: str):
        """禁用插件"""
        config = self._configs.get(plugin_id, PluginConfig())
        config.enabled = False
        self._configs[plugin_id] = config

        if plugin_id in self._plugins:
            plugin = self._plugins[plugin_id]
            if plugin.state == PluginState.RUNNING:
                plugin.on_stop()
            plugin.on_disable()

    def start_plugin(self, plugin_id: str) -> bool:
        """启动插件"""
        if plugin_id not in self._plugins:
            if not self.load_plugin(plugin_id):
                return False

        plugin = self._plugins[plugin_id]

        # 检查依赖
        for dep_id in plugin.info.dependencies:
            if dep_id not in self._plugins or self._plugins[dep_id].state != PluginState.RUNNING:
                if not self.start_plugin(dep_id):
                    return False

        if plugin.state == PluginState.ENABLED:
            plugin.on_start()
            return True
        elif plugin.state in [PluginState.DISABLED, PluginState.LOADED]:
            plugin.on_enable()
            plugin.on_start()
            return True

        return False

    def stop_plugin(self, plugin_id: str):
        """停止插件"""
        if plugin_id in self._plugins:
            plugin = self._plugins[plugin_id]
            if plugin.state == PluginState.RUNNING:
                plugin.on_stop()

    def reload_plugin(self, plugin_id: str) -> bool:
        """热重载插件"""
        if plugin_id not in self._plugins:
            return self.load_plugin(plugin_id) is not None

        plugin = self._plugins[plugin_id]
        was_running = plugin.state == PluginState.RUNNING

        plugin.on_reload()

        if was_running:
            plugin.on_start()

        return True

    def start_all(self):
        """启动所有已启用的插件"""
        # 按依赖顺序启动
        for plugin_id in self._load_order:
            config = self._configs.get(plugin_id, PluginConfig())
            if config.enabled:
                self.start_plugin(plugin_id)

    def stop_all(self):
        """停止所有插件"""
        for plugin_id in reversed(self._load_order):
            self.stop_plugin(plugin_id)

    def get_plugin(self, plugin_id: str) -> Optional[Plugin]:
        """获取插件实例"""
        return self._plugins.get(plugin_id)

    def get_all_plugins(self) -> Dict[str, Plugin]:
        """获取所有插件"""
        return dict(self._plugins)

    def get_plugin_info(self, plugin_id: str) -> Optional[PluginInfo]:
        """获取插件信息"""
        plugin = self._plugins.get(plugin_id)
        return plugin.info if plugin else None

    def is_enabled(self, plugin_id: str) -> bool:
        """检查插件是否启用"""
        config = self._configs.get(plugin_id)
        return config.enabled if config else False

    def get_plugin_state(self, plugin_id: str) -> Optional[PluginState]:
        """获取插件状态"""
        plugin = self._plugins.get(plugin_id)
        return plugin.state if plugin else None

    def sorted_plugins(self) -> list:
        """返回按 priority 降序排列的活跃插件。"""
        plugins = [p for p in self._plugins.values() if p.state == PluginState.RUNNING]
        return sorted(plugins, key=lambda p: -p.info.priority.value)
