"""EventBus 发布/订阅系统，替代 HookRegistry。"""
from enum import Enum
from typing import Any, Callable, Dict, List, Tuple


class EventType(str, Enum):
    """事件类型枚举 — 继承 str 以兼容字符串事件名。"""
    TASK_COMPLETE = "task_complete"
    QUEUE_CHANGED = "queue_changed"
    ACHIEVEMENT_UNLOCK = "achievement_unlock"
    RESIZE = "resize"


class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, List[Tuple[int, Callable]]] = {}

    def on(self, event: str, callback: Callable, priority: int = 50):
        """注册订阅，priority 越高越先执行。"""
        if event not in self._subscribers:
            self._subscribers[event] = []
        self._subscribers[event].append((priority, callback))

    def once(self, event: str, callback: Callable, priority: int = 50):
        """一次性订阅。"""
        def wrapper(data):
            self._unsubscribe(event, wrapper)
            return callback(data)
        wrapper._original = callback
        self.on(event, wrapper, priority)

    def emit(self, event: str, data: Any = None):
        """按优先级降序调用所有订阅者。"""
        subscribers = self._subscribers.get(event, [])
        sorted_subs = sorted(subscribers, key=lambda x: -x[0])
        for _, callback in sorted_subs:
            try:
                callback(data)
            except Exception as e:
                import sys
                print(f"[EventBus] Error in handler for '{event}': {e}", file=sys.stderr)

    def _unsubscribe(self, event: str, callback: Callable):
        if event in self._subscribers:
            self._subscribers[event] = [
                (p, cb) for p, cb in self._subscribers[event] if cb is not callback
            ]

    def subscribe(self, event, callback: Callable, priority: int = 50):
        """Alias for on() — 兼容旧调用。"""
        self.on(event, callback, priority)

    def clear(self):
        self._subscribers.clear()
