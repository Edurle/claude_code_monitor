# Plugin Framework 重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 monitor.py 从 1,168 行精简为 ~150 行纯框架，所有渲染和业务逻辑由插件提供。

**Architecture:** Frame(LayoutEngine + PluginManager + EventBus) 主循环 → 插件声明 Region → 布局引擎计算坐标 → 插件 render_region 返回 cells → blit 写入 curses。

**Tech Stack:** Python 3.6+, curses, typing.Protocol

**Spec:** `docs/superpowers/specs/2026-04-03-plugin-framework-design.md`

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `lib/protocols.py` | 核心服务 Protocol 接口定义 |
| Create | `lib/eventbus.py` | EventBus 发布/订阅 |
| Create | `lib/layout.py` | LayoutEngine + Slot + Region + Rect |
| Create | `lib/frame.py` | Frame 主循环、blit、dispatch |
| Modify | `lib/plugins/core.py` | Plugin 基类扩展 (declare_regions/render_overlay/render_fullscreen) |
| Modify | `lib/plugins/manager.py` | 适配新 PluginContext (去掉 stdscr) |
| Create | `plugins/builtin/top-bar/plugin.py` | 顶栏渲染 |
| Create | `plugins/builtin/task-queue/plugin.py` | 左侧任务列表 + 输入处理 |
| Create | `plugins/builtin/matrix-rain/plugin.py` | 矩阵雨 + scan-line |
| Create | `plugins/builtin/neural-grid/plugin.py` | 神经网格 |
| Create | `plugins/builtin/status-bar/plugin.py` | 状态消息行 |
| Create | `plugins/builtin/hints-bar/plugin.py` | 快捷键提示行 + 视图切换 |
| Create | `plugins/builtin/achievements-view/plugin.py` | 成就全屏页 |
| Create | `plugins/builtin/stats-view/plugin.py` | 统计全屏页 |
| Modify | `plugins/builtin/pet/plugin.py` | 适配新 Plugin 接口 |
| Modify | `plugins/builtin/achievements/plugin.py` | 适配新 Plugin 接口 |
| Modify | `plugins/builtin/particle-fx/plugin.py` | 适配新 Plugin 接口 |
| Modify | `plugins/builtin/border_particles/plugin.py` | 适配新 Plugin 接口 |
| Modify | `monitor.py` | 替换为 Frame 入口 (~150行) |
| Modify | `config/plugins.yaml` | 添加新插件配置 |
| Delete | `lib/plugins/hooks.py` | 被 eventbus 替代 |
| Delete | `lib/pet.py` | 已在 plugins/builtin/pet/ |
| Delete | `lib/achievements.py` | 已在 plugins/builtin/achievements/ |
| Delete | `lib/star_map.py` | 渲染迁入 neural-grid 插件 |
| Delete | `plugins/builtin/border_animator/` | 合并到 border-particles |

---

## Task 1: 基础设施 — lib/protocols.py

**Files:**
- Create: `lib/protocols.py`

- [ ] **Step 1: 创建 protocols.py**

```python
"""核心服务 Protocol 接口定义。插件依赖接口而非实现。"""
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple


class IDatabase(Protocol):
    def execute(self, query: str, params: tuple = ()) -> Any: ...
    def query_one(self, query: str, params: tuple = ()) -> Optional[tuple]: ...
    def query_all(self, query: str, params: tuple = ()) -> List[tuple]: ...
    def commit(self) -> None: ...


class IParticleSystem(Protocol):
    def update(self) -> None: ...
    def create_matrix_rain(self, x: float, y: float, width: int, height: int) -> str: ...
    def remove_emitter(self, emitter_id: str) -> None: ...
    def get_emitter(self, emitter_id: str) -> Any: ...
    def create_sparkle(self, x: float, y: float, count: int = 5) -> None: ...
    def create_celebration(self, x: float, y: float) -> None: ...


class ISessionTracker(Protocol):
    def process_event(self, entry: dict) -> None: ...
    def tick(self) -> None: ...
    def get_sessions(self) -> list: ...


class IThemeManager(Protocol):
    @property
    def current(self) -> Any: ...
    def switch(self, theme_name: str = "") -> str: ...
    def init_curses_colors(self, stdscr: Any) -> None: ...
    def get_color(self, name: str) -> int: ...
    def get_style(self, event_type: str) -> Tuple[int, str]: ...
    def get_border_chars(self) -> Tuple[str, ...]: ...


class IStatsManager(Protocol):
    def record_event(self, event_type: str, project: str) -> None: ...
    def get_summary(self) -> dict: ...
    def get_today_stats(self) -> dict: ...
    def get_week_chart(self, width: int) -> str: ...
    def get_top_projects(self, limit: int = 5) -> list: ...


class IQueueManager(Protocol):
    def read(self) -> List[dict]: ...
    def remove(self, entry: dict) -> None: ...
    def clear(self) -> None: ...


class IEventBus(Protocol):
    def emit(self, event: str, data: Any = None) -> None: ...
    def on(self, event: str, callback: Callable, priority: int = 50) -> None: ...
```

- [ ] **Step 2: Commit**

```bash
git add lib/protocols.py
git commit -m "feat: 添加核心服务 Protocol 接口定义"
```

---

## Task 2: 基础设施 — lib/eventbus.py

**Files:**
- Create: `lib/eventbus.py`

- [ ] **Step 1: 创建 eventbus.py**

```python
"""EventBus 发布/订阅系统，替代 HookRegistry。"""
from typing import Any, Callable, Dict, List, Tuple


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
        # 稳定排序：同 priority 保持注册顺序
        sorted_subs = sorted(subscribers, key=lambda x: -x[0])
        for _, callback in sorted_subs:
            try:
                callback(data)
            except Exception:
                pass

    def _unsubscribe(self, event: str, callback: Callable):
        if event in self._subscribers:
            self._subscribers[event] = [
                (p, cb) for p, cb in self._subscribers[event] if cb is not callback
            ]

    def clear(self):
        self._subscribers.clear()
```

- [ ] **Step 2: Commit**

```bash
git add lib/eventbus.py
git commit -m "feat: 添加 EventBus 发布/订阅系统"
```

---

## Task 3: 基础设施 — lib/layout.py

**Files:**
- Create: `lib/layout.py`

- [ ] **Step 1: 创建 layout.py**

```python
"""布局引擎：Slot 定义、Region 声明、Rect 计算。"""
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class Slot(Enum):
    TOP = "top"
    LEFT = "left"
    RIGHT_TOP = "right-top"
    RIGHT_BOT = "right-bot"
    BOTTOM = "bottom"


@dataclass
class Region:
    id: str
    slot: Slot
    min_height: int = 1
    weight: int = 100
    priority: int = 50


@dataclass
class Rect:
    row: int
    col: int
    height: int
    width: int


class LayoutEngine:
    """收集 Region 声明，计算屏幕坐标。"""

    def compute(self, regions: List[Region], screen_h: int, screen_w: int) -> Dict[str, Rect]:
        by_slot: Dict[Slot, List[Region]] = {}
        for r in regions:
            by_slot.setdefault(r.slot, []).append(r)

        result: Dict[str, Rect] = {}

        # TOP: row 0, 全宽, 固定 1 行
        top_regions = by_slot.get(Slot.TOP, [])
        if top_regions:
            winner = max(top_regions, key=lambda r: r.priority)
            result[winner.id] = Rect(row=0, col=0, height=1, width=screen_w)

        # BOTTOM: 最后 3 行, 全宽
        bottom_start = screen_h - 3
        bottom_regions = sorted(by_slot.get(Slot.BOTTOM, []), key=lambda r: -r.priority)
        total_weight = sum(r.weight for r in bottom_regions) or 1
        avail_h = 3
        row = bottom_start
        for i, r in enumerate(bottom_regions):
            if i < len(bottom_regions) - 1:
                h = max(1, avail_h * r.weight // total_weight)
            else:
                h = avail_h
            result[r.id] = Rect(row=row, col=0, height=h, width=screen_w)
            row += h
            avail_h -= h

        # 左右分割
        left_w = max(30, screen_w * 2 // 5)
        right_w = screen_w - left_w - 1
        content_start = 1
        content_end = bottom_start

        # LEFT: 左侧面板
        left_regions = sorted(by_slot.get(Slot.LEFT, []), key=lambda r: -r.priority)
        left_h = content_end - content_start
        total_lw = sum(r.weight for r in left_regions) or 1
        avail_lh = left_h
        row = content_start
        for i, r in enumerate(left_regions):
            if avail_lh < r.min_height:
                break  # 降级
            if i < len(left_regions) - 1:
                h = max(r.min_height, left_h * r.weight // total_lw)
            else:
                h = avail_lh
            result[r.id] = Rect(row=row, col=0, height=h, width=left_w)
            row += h
            avail_lh -= h

        # 分隔线: left_w 列

        # RIGHT: 上下分割 (45%/55%)
        right_total_h = content_end - content_start
        right_split = int(right_total_h * 0.45)

        # RIGHT_TOP
        rt_regions = sorted(by_slot.get(Slot.RIGHT_TOP, []), key=lambda r: -r.priority)
        rt_winner = rt_regions[0] if rt_regions else None
        if rt_winner:
            result[rt_winner.id] = Rect(
                row=content_start, col=left_w + 1,
                height=right_split, width=right_w
            )

        # RIGHT_BOT (从 right_split+1 开始)
        rb_regions = sorted(by_slot.get(Slot.RIGHT_BOT, []), key=lambda r: -r.priority)
        rb_winner = rb_regions[0] if rb_regions else None
        if rb_winner:
            result[rb_winner.id] = Rect(
                row=content_start + right_split + 1, col=left_w + 1,
                height=right_total_h - right_split - 1, width=right_w
            )

        return result
```

- [ ] **Step 2: Commit**

```bash
git add lib/layout.py
git commit -m "feat: 添加 LayoutEngine + Slot + Region + Rect"
```

---

## Task 4: 扩展 Plugin 基类

**Files:**
- Modify: `lib/plugins/core.py`

- [ ] **Step 1: 在 Plugin 基类中添加 declare_regions / render_region / render_overlay / render_fullscreen 方法**

在 `lib/plugins/core.py` 的 `Plugin` 类中添加：

```python
    # Region 声明
    def declare_regions(self) -> list:
        return []

    # Region 渲染 (坐标相对于 Rect 左上角)
    def render_region(self, region_id: str, rect, data: dict) -> list:
        """返回 [(row, col, text, attr), ...]"""
        return []

    # 叠加渲染 (绝对坐标)
    def render_overlay(self, screen_h: int, screen_w: int, data: dict) -> list:
        """返回 [(row, col, text, attr), ...]"""
        return []

    # 全屏渲染 (返回非空即独占)
    def render_fullscreen(self, screen_h: int, screen_w: int, data: dict) -> list:
        return []

    # 输入处理
    def handle_key(self, key: int, context: dict) -> bool:
        return False
```

同时更新 `PluginContext` dataclass：移除 `stdscr` 字段，添加 `events` 字段（IEventBus）。

- [ ] **Step 2: Commit**

```bash
git add lib/plugins/core.py
git commit -m "feat: Plugin 基类扩展 declare_regions/render_region/render_overlay/render_fullscreen"
```

---

## Task 5: 适配 PluginManager

**Files:**
- Modify: `lib/plugins/manager.py`

- [ ] **Step 1: 更新 PluginManager 的 context 创建逻辑**

将 `PluginContext` 构造从当前字段映射改为新字段（去掉 stdscr，添加 events）。确保 `start_all()` 后调用每个插件的 `on_load(ctx)` 和 `on_start()`。

关键修改点：`manager.py` 中创建 `PluginContext` 的地方，改为传入新的字段集。

- [ ] **Step 2: 添加 sorted_plugins() 方法**

```python
    def sorted_plugins(self) -> list:
        """返回按 priority 降序排列的活跃插件。"""
        plugins = [p for p in self._plugins.values() if p.state == PluginState.STARTED]
        return sorted(plugins, key=lambda p: -p.info.priority.value)
```

- [ ] **Step 3: Commit**

```bash
git add lib/plugins/manager.py
git commit -m "feat: PluginManager 适配新 PluginContext + sorted_plugins"
```

---

## Task 6: Frame 骨架 — lib/frame.py

**Files:**
- Create: `lib/frame.py`

- [ ] **Step 1: 创建 frame.py 核心框架**

Frame 类包含：
- `__init__`: 初始化 curses、所有核心服务、PluginManager、LayoutEngine、EventBus
- `blit(cells, offset)`: 批量写入 curses，带边界裁剪
- `dispatch_key(key, entries)`: 按插件优先级分发按键（q 由 Frame 直接处理）
- `collect_regions()`: 遍历所有活跃插件收集 Region 声明
- `run()`: 主循环（参考 spec 第6节的伪代码）

主循环逻辑：
1. `entries = self.queue.read()`
2. 增量检测 + emit `queue_update` / `queue_changed`
3. `sessions.tick()` + `particles.update()`
4. `layout_engine.compute(regions, h, w)`
5. 检查 fullscreen → 有则跳过其他
6. Region 渲染 → Overlay 渲染
7. `stdscr.refresh()`
8. `stdscr.getch()` → `dispatch_key()`

错误兜底：无插件时显示 `"claude-monitor: 插件系统错误"`。

QueueManager 封装：在 Frame 中创建 `QueueManager` 类，包装当前 `read_queue()`/`pop_entry()`/`clear_queue()` 的逻辑（从 monitor.py 搬入）。

- [ ] **Step 2: Commit**

```bash
git add lib/frame.py
git commit -m "feat: Frame 主循环骨架 — 布局/渲染/事件分发"
```

---

## Task 7: monitor.py 入口重写

**Files:**
- Modify: `monitor.py`

- [ ] **Step 1: 将 monitor.py 精简为 ~30 行入口**

```python
#!/usr/bin/env python3
"""claude-monitor — 插件化 HITL 监控器入口"""
import curses
from lib.frame import Frame


def main():
    def run(stdscr):
        frame = Frame(stdscr)
        frame.run()

    try:
        curses.wrapper(run)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
```

注意：此步暂时不做，等所有插件就绪后再切换。**在所有插件实现完成前，保留旧 monitor.py 不变，新代码在 lib/frame.py 中独立开发。**

- [ ] **Step 2: Commit (暂跳过，留到 Task 16)**

---

## Task 8: top-bar 插件

**Files:**
- Create: `plugins/builtin/top-bar/plugin.py`
- Create: `plugins/builtin/top-bar/plugin.yaml`

- [ ] **Step 1: 创建 top-bar 插件**

从 monitor.py `_draw_top_bar()` (lines 412-424) 迁移。

- 声明 Region: `Slot.TOP`, priority=100
- `render_region()`: 返回 cells 列表
- `plugin.yaml` 中声明 `id: builtin.top-bar`

关键逻辑：统计 entries 中 hitl/task_complete/error 数量，显示 "CLAUDE CODE MONITOR {total} in queue HITL:{n} DONE:{n}"。

- [ ] **Step 2: Commit**

```bash
git add plugins/builtin/top-bar/
git commit -m "feat: top-bar 插件 — 顶栏统计渲染"
```

---

## Task 9: task-queue 插件

**Files:**
- Create: `plugins/builtin/task-queue/plugin.py`
- Create: `plugins/builtin/task-queue/plugin.yaml`

- [ ] **Step 1: 创建 task-queue 插件**

从 monitor.py `_draw_left_panel()` (lines 426-475) + `handle_key()` Enter/d/c 部分 (lines 1036-1102) 迁移。

- 声明 Region: `Slot.LEFT`, weight=70, priority=100
- `render_region()`: 渲染可操作事件列表（hitl/task_complete/error）
- `handle_key()`:
  - Enter → `jump_to_task(actionable[0])` → emit `task_complete` → `queue.remove()` → emit `set_status`
  - d → `queue.remove(actionable[0])` → emit `task_discard` → emit `set_status`
  - c → `queue.clear()` → emit `queue_clear` → emit `set_status`
- 包含 `TYPE_COLOR` 字典（从 monitor.py 搬入）
- 包含 `jump_to_task()` 和 `tmux()` 辅助方法（从 monitor.py 搬入）

- [ ] **Step 2: Commit**

```bash
git add plugins/builtin/task-queue/
git commit -m "feat: task-queue 插件 — 左侧任务列表 + Enter/d/c 输入处理"
```

---

## Task 10: matrix-rain 插件

**Files:**
- Create: `plugins/builtin/matrix-rain/plugin.py`
- Create: `plugins/builtin/matrix-rain/plugin.yaml`

- [ ] **Step 1: 创建 matrix-rain 插件**

从 monitor.py `_draw_matrix_rain()` (lines 501-524) + `_draw_scan_line()` (lines 477-499) 迁移。

- 声明 Region: `Slot.RIGHT_TOP`, priority=80
- `render_region()`:
  - 管理矩阵雨 emitter（首次创建或布局变化时重建）
  - 使用 `ctx.particles` 创建/获取 emitter
  - 渲染粒子 + scan-line（作为底部一行）
- `on_load()`: 缓存 emitter_id

- [ ] **Step 2: Commit**

```bash
git add plugins/builtin/matrix-rain/
git commit -m "feat: matrix-rain 插件 — 矩阵雨 + scan-line"
```

---

## Task 11: neural-grid 插件

**Files:**
- Create: `plugins/builtin/neural-grid/plugin.py`
- Create: `plugins/builtin/neural-grid/plugin.yaml`

- [ ] **Step 1: 创建 neural-grid 插件**

从 monitor.py `_draw_neural_grid()` (lines 528-730) 迁移，包含所有辅助方法。

- 声明 Region: `Slot.RIGHT_BOT`, priority=80
- `render_region()`: 渲染 session 卡片
- 订阅 `queue_update` 事件来更新 session tracker
- 搬入: `_render_session_card`, `_build_activity_bar`, `_format_session_detail`, `_sort_sessions_for_grid`
- 搬入: `STATUS_DISPLAY` 和 `GRID_PRIORITY` 常量
- 引用 `lib/star_map.py` 的渲染逻辑（后续清理时合并到此插件）

- [ ] **Step 2: Commit**

```bash
git add plugins/builtin/neural-grid/
git commit -m "feat: neural-grid 插件 — 右下神经网格会话卡片"
```

---

## Task 12: status-bar + hints-bar 插件

**Files:**
- Create: `plugins/builtin/status-bar/plugin.py`
- Create: `plugins/builtin/status-bar/plugin.yaml`
- Create: `plugins/builtin/hints-bar/plugin.py`
- Create: `plugins/builtin/hints-bar/plugin.yaml`

- [ ] **Step 1: 创建 status-bar 插件**

从 monitor.py 状态消息渲染逻辑 (lines 401-403, 102-103, 971-972) 迁移。

- 声明 Region: `Slot.BOTTOM`, weight=50, priority=100
- 订阅 `set_status` 事件：`self.ctx.events.on("set_status", self._on_set_status)`
- 内部管理: `self._msg`, `self._clear_at`
- `render_region()`: 检查 `time.time() > self._clear_at` 则清空，否则显示消息

- [ ] **Step 2: 创建 hints-bar 插件**

- 声明 Region: `Slot.BOTTOM`, weight=50, priority=90
- `render_region()`: 显示 "[Enter]jump [d]drop [c]clear [T]theme [A]achieve [S]stats [P]pet [q]quit"
- `handle_key()`:
  - t/T → `ctx.theme.switch()` → emit `theme_change` → emit `set_status`
  - a/A → emit `view_switch` {view: "achievements"}
  - s/S → emit `view_switch` {view: "stats"}
  - ESC → emit `view_switch` {view: "queue"}

- [ ] **Step 3: Commit**

```bash
git add plugins/builtin/status-bar/ plugins/builtin/hints-bar/
git commit -m "feat: status-bar + hints-bar 插件"
```

---

## Task 13: fullscreen 插件 (achievements-view + stats-view)

**Files:**
- Create: `plugins/builtin/achievements-view/plugin.py`
- Create: `plugins/builtin/achievements-view/plugin.yaml`
- Create: `plugins/builtin/stats-view/plugin.py`
- Create: `plugins/builtin/stats-view/plugin.yaml`

- [ ] **Step 1: 创建 achievements-view 插件**

从 monitor.py `draw_achievements_view()` (lines 810-877) 迁移。

- 不声明 Region
- 维护 `self._active = False` 状态
- 订阅 `view_switch`: 如果 `data["view"] == "achievements"` 则 `_active = True`，如果 `"queue"` 则 `_active = False`
- `render_fullscreen()`: 仅当 `_active` 时返回渲染 cells，否则返回空
- `handle_key()`: 活跃时处理滚动 (↑/↓)

- [ ] **Step 2: 创建 stats-view 插件**

从 monitor.py `draw_stats_view()` (lines 879-930) 迁移。同上模式。

- [ ] **Step 3: Commit**

```bash
git add plugins/builtin/achievements-view/ plugins/builtin/stats-view/
git commit -m "feat: achievements-view + stats-view 全屏插件"
```

---

## Task 14: 适配现有插件

**Files:**
- Modify: `plugins/builtin/pet/plugin.py`
- Modify: `plugins/builtin/achievements/plugin.py`
- Modify: `plugins/builtin/particle-fx/plugin.py`
- Modify: `plugins/builtin/border_particles/plugin.py`

- [ ] **Step 1: pet 插件适配**

- 添加 `declare_regions()`: Region(id="pet", slot=Slot.LEFT, weight=30, priority=50)
- 将 `_draw_pet_area` 逻辑改为 `render_region()` 返回 cells
- 移除直接 `stdscr` 调用
- 改用 `ctx.events.on("task_complete", ...)` 替代 hook 注册

- [ ] **Step 2: achievements 插件适配**

- 不声明 Region (改为 overlay)
- `render_overlay()`: 返回弹窗 cells（有成就解锁时显示）
- 改用 EventBus 订阅 `task_complete` / `queue_changed`

- [ ] **Step 3: particle-fx 插件适配**

- 不声明 Region (overlay)
- `render_overlay()`: 返回粒子 cells

- [ ] **Step 4: border_particles 插件适配**

- 合并 border_animator 功能
- 不声明 Region (overlay)
- `render_overlay()`: 返回边框粒子 cells

- [ ] **Step 5: Commit**

```bash
git add plugins/builtin/pet/ plugins/builtin/achievements/ plugins/builtin/particle-fx/ plugins/builtin/border_particles/
git commit -m "feat: 适配现有插件到新 Plugin 接口"
```

---

## Task 15: 配置迁移

**Files:**
- Modify: `config/plugins.yaml`

- [ ] **Step 1: 更新 plugins.yaml，添加所有新插件**

在现有配置后追加：

```yaml
  builtin.top-bar:
    enabled: true
    priority: 100
  builtin.task-queue:
    enabled: true
    priority: 100
  builtin.matrix-rain:
    enabled: true
    priority: 80
  builtin.neural-grid:
    enabled: true
    priority: 80
  builtin.status-bar:
    enabled: true
    priority: 100
  builtin.hints-bar:
    enabled: true
    priority: 90
  builtin.achievements-view:
    enabled: true
    priority: 75
  builtin.stats-view:
    enabled: true
    priority: 75
```

- [ ] **Step 2: Commit**

```bash
git add config/plugins.yaml
git commit -m "chore: 更新 plugins.yaml 添加所有新插件配置"
```

---

## Task 16: 切换入口 + 清理

**Files:**
- Modify: `monitor.py` (精简为入口)
- Delete: `lib/plugins/hooks.py`
- Delete: `lib/pet.py`
- Delete: `lib/achievements.py`
- Delete: `lib/star_map.py`
- Delete: `plugins/builtin/border_animator/`

- [ ] **Step 1: 将 monitor.py 替换为 ~30 行入口**

```python
#!/usr/bin/env python3
"""claude-monitor — 插件化 HITL 监控器入口"""
import curses
from lib.frame import Frame


def main():
    def run(stdscr):
        frame = Frame(stdscr)
        frame.run()

    try:
        curses.wrapper(run)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 删除旧文件**

```bash
rm lib/plugins/hooks.py lib/pet.py lib/achievements.py lib/star_map.py
rm -r plugins/builtin/border_animator/
```

- [ ] **Step 3: 验证**

1. `python monitor.py` 启动正常
2. `bash notify.sh hitl "test"` → 左侧列表显示
3. Enter 跳转正常，d 丢弃正常，c 清空正常
4. t 切换主题，a 成就页，s 统计页，ESC 返回，q 退出
5. 禁用某个插件 → 对应区域消失

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: 切换到插件化框架 — monitor.py 精简为入口，删除旧代码"
```

---

## 执行顺序约束

```
Task 1 (protocols) ─┐
Task 2 (eventbus)  ─┼─→ Task 4 (Plugin 基类) ─→ Task 5 (PluginManager)
Task 3 (layout)    ─┘         │
                               ↓
                    Task 6 (Frame 骨架)
                               │
              ┌────────────────┼────────────────┐
              ↓                ↓                ↓
         Task 8 (top-bar) Task 9 (task-queue) Task 10 (matrix-rain)
              │                │                │
              ↓                ↓                ↓
         Task 11 (neural-grid) Task 12 (status/hints) Task 13 (fullscreen)
              │                │                │
              └────────────────┼────────────────┘
                               ↓
                    Task 14 (适配现有插件)
                               ↓
                    Task 15 (配置迁移)
                               ↓
                    Task 16 (切换入口 + 清理)
```

Task 1-3 可并行。Task 8-13 可并行。Task 7 留到 Task 16 合并。
