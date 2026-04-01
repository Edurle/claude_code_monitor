#!/usr/bin/env python3
# lib/plugins/__init__.py
"""插件系统"""

from .core import Plugin, PluginInfo, PluginState, PluginPriority, PluginContext
from .hooks import HookRegistry, HookType, HookPoint, HOOK_POINTS
from .manager import PluginManager, PluginConfig

__all__ = [
    "Plugin",
    "PluginInfo",
    "PluginState",
    "PluginPriority",
    "PluginContext",
    "HookRegistry",
    "HookType",
    "HookPoint",
    "HOOK_POINTS",
    "PluginManager",
    "PluginConfig",
]
