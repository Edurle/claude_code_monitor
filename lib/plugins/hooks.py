#!/usr/bin/env python3
# lib/plugins/hooks.py - 渲染钩子定义
"""定义所有可用的渲染钩子"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Callable, Tuple
from enum import Enum


class HookType(Enum):
    """钩子类型"""
    RENDER = "render"        # 渲染钩子 - 返回渲染内容
    FILTER = "filter"        # 过滤钩子 - 修改数据
    ACTION = "action"        # 动作钩子 - 事件响应
    ANIMATION = "animation"  # 动画钩子 - 更新动画


@dataclass
class HookPoint:
    """钩子点定义"""
    name: str                          # 钩子名称
    type: HookType                     # 钩子类型
    description: str                   # 描述
    parameters: List[str]              # 参数列表
    return_type: str                   # 返回类型
    default_priority: int = 50         # 默认优先级


# 预定义的钩子点
HOOK_POINTS = {
    # ========== 任务/记录渲染钩子 ==========
    "render_task_item": HookPoint(
        name="render_task_item",
        type=HookType.RENDER,
        description="渲染单条任务记录",
        parameters=["entry", "index", "is_first", "width"],
        return_type="Optional[List[Tuple[int, int, str, int]]]"  # [(row, col, text, attr)]
    ),

    "render_task_icon": HookPoint(
        name="render_task_icon",
        type=HookType.RENDER,
        description="渲染任务类型图标",
        parameters=["event_type", "is_highlighted"],
        return_type="Tuple[str, int]"  # (icon_text, color_attr)
    ),

    "filter_task_data": HookPoint(
        name="filter_task_data",
        type=HookType.FILTER,
        description="过滤/修改任务数据",
        parameters=["entry"],
        return_type="dict"
    ),

    # ========== 边框渲染钩子 ==========
    "render_border": HookPoint(
        name="render_border",
        type=HookType.RENDER,
        description="渲染窗口边框",
        parameters=["y", "x", "height", "width", "title"],
        return_type="Optional[List[Tuple[int, int, str, int]]]"
    ),

    "render_border_char": HookPoint(
        name="render_border_char",
        type=HookType.RENDER,
        description="渲染单个边框字符（用于动画）",
        parameters=["position", "char", "frame"],  # position: tl, t, tr, r, br, b, bl, l
        return_type="Tuple[str, int]"  # (char, color_attr)
    ),

    # ========== 头部/标题区域钩子 ==========
    "render_header": HookPoint(
        name="render_header",
        type=HookType.RENDER,
        description="渲染头部区域",
        parameters=["width", "theme_name"],
        return_type="Optional[List[Tuple[int, int, str, int]]]"
    ),

    "render_title": HookPoint(
        name="render_title",
        type=HookType.RENDER,
        description="渲染标题文本",
        parameters=["title", "width", "position"],
        return_type="Tuple[str, int]"  # (styled_title, attr)
    ),

    # ========== 宠物区域钩子 ==========
    "render_pet_area": HookPoint(
        name="render_pet_area",
        type=HookType.RENDER,
        description="渲染宠物区域",
        parameters=["start_row", "width"],
        return_type="Optional[List[Tuple[int, int, str, int]]]"
    ),

    "render_pet_art": HookPoint(
        name="render_pet_art",
        type=HookType.RENDER,
        description="渲染宠物 ASCII 艺术",
        parameters=["pet_state", "evolution", "frame"],
        return_type="List[str]"  # ASCII 艺术行
    ),

    # ========== 成就区域钩子 ==========
    "render_achievement_popup": HookPoint(
        name="render_achievement_popup",
        type=HookType.RENDER,
        description="渲染成就解锁弹窗",
        parameters=["achievement", "center_y", "center_x"],
        return_type="Optional[List[Tuple[int, int, str, int]]]"
    ),

    "render_achievement_list": HookPoint(
        name="render_achievement_list",
        type=HookType.RENDER,
        description="渲染成就列表项",
        parameters=["achievement", "is_unlocked", "row", "width"],
        return_type="Optional[List[Tuple[int, int, str, int]]]"
    ),

    # ========== 状态栏钩子 ==========
    "render_status_bar": HookPoint(
        name="render_status_bar",
        type=HookType.RENDER,
        description="渲染状态栏",
        parameters=["message", "width"],
        return_type="Tuple[str, int]"
    ),

    "render_hints_bar": HookPoint(
        name="render_hints_bar",
        type=HookType.RENDER,
        description="渲染底部提示栏",
        parameters=["hints", "width"],
        return_type="Optional[List[Tuple[int, int, str, int]]]"
    ),

    # ========== 事件动作钩子 ==========
    "on_task_complete": HookPoint(
        name="on_task_complete",
        type=HookType.ACTION,
        description="任务完成时触发",
        parameters=["entry", "stats"],
        return_type="None"
    ),

    "on_new_task": HookPoint(
        name="on_new_task",
        type=HookType.ACTION,
        description="新任务入队时触发",
        parameters=["entry"],
        return_type="None"
    ),

    "on_achievement_unlock": HookPoint(
        name="on_achievement_unlock",
        type=HookType.ACTION,
        description="成就解锁时触发",
        parameters=["achievement_id", "achievement_data"],
        return_type="None"
    ),

    "on_theme_change": HookPoint(
        name="on_theme_change",
        type=HookType.ACTION,
        description="主题切换时触发",
        parameters=["old_theme", "new_theme"],
        return_type="None"
    ),

    "on_key_press": HookPoint(
        name="on_key_press",
        type=HookType.ACTION,
        description="按键时触发",
        parameters=["key", "context"],
        return_type="bool"  # 返回 True 拦截按键
    ),

    # ========== 动画钩子 ==========
    "update_animation": HookPoint(
        name="update_animation",
        type=HookType.ANIMATION,
        description="更新动画帧",
        parameters=["delta_time"],
        return_type="None"
    ),

    "render_particles": HookPoint(
        name="render_particles",
        type=HookType.RENDER,
        description="渲染粒子效果",
        parameters=["bounds"],  # (min_y, min_x, max_y, max_x)
        return_type="List[Tuple[int, int, str, int]]"
    ),
}


class HookRegistry:
    """钩子注册表 - 管理所有插件的钩子注册"""

    def __init__(self):
        # {hook_name: [(priority, plugin_id, callback)]}
        self._hooks: Dict[str, List[Tuple[int, str, Callable]]] = {}

    def register(self, hook_name: str, plugin_id: str, callback: Callable, priority: int = 50):
        """注册钩子"""
        if hook_name not in self._hooks:
            self._hooks[hook_name] = []

        # 移除同一插件的旧注册
        self._hooks[hook_name] = [
            h for h in self._hooks[hook_name] if h[1] != plugin_id
        ]

        self._hooks[hook_name].append((priority, plugin_id, callback))
        # 按优先级排序（高优先级先执行）
        self._hooks[hook_name].sort(key=lambda x: -x[0])

    def unregister(self, hook_name: str, plugin_id: str):
        """注销钩子"""
        if hook_name in self._hooks:
            self._hooks[hook_name] = [
                h for h in self._hooks[hook_name] if h[1] != plugin_id
            ]

    def unregister_all(self, plugin_id: str):
        """注销插件的所有钩子"""
        for hook_name in list(self._hooks.keys()):
            self.unregister(hook_name, plugin_id)

    def execute(self, hook_name: str, *args, **kwargs) -> List[Any]:
        """执行钩子，返回所有结果"""
        results = []
        if hook_name in self._hooks:
            for priority, plugin_id, callback in self._hooks[hook_name]:
                try:
                    result = callback(*args, **kwargs)
                    if result is not None:
                        results.append(result)
                except Exception as e:
                    import sys
                    print(f"[Hook] {hook_name} error in {plugin_id}: {e}", file=sys.stderr)
        return results

    def execute_first(self, hook_name: str, *args, **kwargs) -> Optional[Any]:
        """执行钩子，返回第一个非空结果"""
        results = self.execute(hook_name, *args, **kwargs)
        return results[0] if results else None

    def execute_filter(self, hook_name: str, value: Any, *args, **kwargs) -> Any:
        """执行过滤钩子，依次传递值"""
        if hook_name in self._hooks:
            for priority, plugin_id, callback in self._hooks[hook_name]:
                try:
                    value = callback(value, *args, **kwargs)
                except Exception:
                    pass
        return value

    def has_hooks(self, hook_name: str) -> bool:
        """检查是否有钩子注册"""
        return hook_name in self._hooks and len(self._hooks[hook_name]) > 0

    def get_hook_count(self, hook_name: str) -> int:
        """获取钩子数量"""
        return len(self._hooks.get(hook_name, []))
