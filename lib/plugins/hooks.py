#!/usr/bin/env python3
# lib/plugins/hooks.py - 钩子注册表
"""简单的钩子注册系统"""

from enum import Enum, auto
from typing import Callable, Dict, List, Tuple, Optional
from dataclasses import dataclass


class HookType(Enum):
    """钩子类型"""
    RENDER = auto()
    UPDATE = auto()
    EVENT = auto()
    LIFECYCLE = auto()


class HookPoint(Enum):
    """钩子挂载点"""
    PRE_RENDER = "pre_render"
    POST_RENDER = "post_render"
    PRE_UPDATE = "pre_update"
    POST_UPDATE = "post_update"
    ON_EVENT = "on_event"
    ON_LOAD = "on_load"
    ON_UNLOAD = "on_unload"


# 常用钩子点
HOOK_POINTS = {
    "pre_render": HookPoint.PRE_RENDER,
    "post_render": HookPoint.POST_RENDER,
    "pre_update": HookPoint.PRE_UPDATE,
    "post_update": HookPoint.POST_UPDATE,
    "on_event": HookPoint.ON_EVENT,
}


@dataclass
class HookEntry:
    """钩子条目"""
    plugin_id: str
    callback: Callable
    priority: int


class HookRegistry:
    """钩子注册表"""

    def __init__(self):
        self._hooks: Dict[str, List[HookEntry]] = {}

    def register(self, hook_name: str, plugin_id: str, callback: Callable, priority: int = 50):
        """注册钩子"""
        if hook_name not in self._hooks:
            self._hooks[hook_name] = []

        entry = HookEntry(plugin_id=plugin_id, callback=callback, priority=priority)
        self._hooks[hook_name].append(entry)

        # 按优先级排序（高优先级在前）
        self._hooks[hook_name].sort(key=lambda e: -e.priority)

    def unregister(self, hook_name: str, plugin_id: str):
        """注销钩子"""
        if hook_name in self._hooks:
            self._hooks[hook_name] = [
                e for e in self._hooks[hook_name] if e.plugin_id != plugin_id
            ]

    def unregister_all(self, plugin_id: str):
        """注销插件的所有钩子"""
        for hook_name in self._hooks:
            self._hooks[hook_name] = [
                e for e in self._hooks[hook_name] if e.plugin_id != plugin_id
            ]

    def get_hooks(self, hook_name: str) -> List[HookEntry]:
        """获取指定钩子的所有条目"""
        return self._hooks.get(hook_name, [])

    def execute(self, hook_name: str, *args, **kwargs) -> List:
        """执行钩子，返回所有结果"""
        results = []
        for entry in self.get_hooks(hook_name):
            try:
                result = entry.callback(*args, **kwargs)
                results.append(result)
            except Exception as e:
                print(f"Hook error [{hook_name}] from {entry.plugin_id}: {e}", file=__import__('sys').stderr)
        return results
