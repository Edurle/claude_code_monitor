# Plugin Framework Design — 全插件化架构重构

> Date: 2026-04-03
> Status: Draft
> Review: Round 2 (addressed 10 review issues)

## Context

当前 `monitor.py` 有 1,168 行，约 400 行是硬编码渲染逻辑。已有完善的插件系统（core/manager/hooks），但只覆盖了宠物、成就、粒子特效等边缘功能。核心区域（任务列表、矩阵雨、神经网格、顶栏等）全部硬编码在 monitor.py 中，且存在插件/旧版双实现路径。

目标：将 monitor.py 精简为 ~150 行的纯框架，所有可见区域和业务逻辑由插件提供。

## Architecture Overview

```
┌──────────────────────────────────────────────┐
│                 Frame (框架)                  │
│  ┌──────────────────────────────────────────┐│
│  │           LayoutEngine (布局引擎)         ││
│  │  收集 Region 声明 → 计算 slot 分配 → 坐标 ││
│  └──────────────────────────────────────────┘│
│  ┌──────────────────────────────────────────┐│
│  │          PluginManager (插件管理)         ││
│  │  加载 → 启动 → 事件注册 → 生命周期        ││
│  └──────────────────────────────────────────┘│
│  ┌──────────────────────────────────────────┐│
│  │          EventBus (事件总线)              ││
│  │  emit → dispatch → subscriber callbacks  ││
│  └──────────────────────────────────────────┘│
└──────────────────────────────────────────────┘
```

Frame 只做三件事：
1. 初始化 curses
2. 创建 LayoutEngine + PluginManager + EventBus
3. 主循环：`read_queue → layout → render_regions → render_overlays → handle_input`

## 1. Region Declaration & Layout Engine

### Slot

预定义屏幕区域槽位：

```python
class Slot(Enum):
    TOP       = "top"         # 顶栏（全宽, 1行）
    LEFT      = "left"        # 左侧面板（40%宽）
    RIGHT_TOP = "right-top"   # 右上（60%宽, ~45%高）
    RIGHT_BOT = "right-bot"   # 右下（60%宽, ~55%高）
    BOTTOM    = "bottom"      # 底部（全宽, 3行）
```

### Region

```python
@dataclass
class Region:
    id: str              # 唯一标识, 如 "task_queue"
    slot: Slot           # 占据哪个 slot
    min_height: int      # 最小高度（硬约束）
    weight: int          # 同 slot 内空间分配权重（默认 100）
    priority: int        # 同 slot 内排序优先级（高优先）
```

- `min_height`：硬约束。slot 总空间不足时，低 priority 的 Region 被降级（不渲染）。
- `weight`：同 slot 内按 weight 比例分配空间。例如 task-queue weight=70, pet weight=30 → 左面板 70/30 分割。

### Rect (布局结果)

```python
@dataclass
class Rect:
    row: int
    col: int
    height: int
    width: int
```

### LayoutEngine

```python
class LayoutEngine:
    def compute(regions: List[Region], screen_h: int, screen_w: int) -> Dict[str, Rect]:
        # 1. 按 slot 分组
        # 2. 每个 slot 内按 priority 降序排列
        # 3. 检查 min_height 约束: 如果同 slot 内 min_height 总和超过 slot 可用高度，
        #    从最低 priority 开始移除，直到约束满足
        # 4. 分配坐标:
        #    TOP → row 0, 全宽, 固定 1 行
        #    LEFT → rows 1..h-4, 宽度 40%
        #    RIGHT_TOP → rows 1..split, 宽度 60%
        #    RIGHT_BOT → rows split..h-4, 宽度 60%
        #    BOTTOM → rows h-3..h-1, 全宽
        #    同 slot 多个插件按 weight 比例分配垂直空间
        # 返回 {region_id: Rect}
        # 被降级的 Region 不在返回值中
```

## 2. Core Service Protocols

新建 `lib/protocols.py`，用 `typing.Protocol` 定义核心服务接口。插件依赖接口而非实现。

```python
class IDatabase(Protocol):
    def execute(self, query: str, params: tuple = ()) -> Any: ...
    def fetchone(self, query: str, params: tuple = ()) -> Optional[tuple]: ...
    def fetchall(self, query: str, params: tuple = ()) -> List[tuple]: ...

class IParticleSystem(Protocol):
    def update(self) -> None: ...
    def emit(self, x: float, y: float, config: dict) -> None: ...
    def render(self, row: int, col: int, w: int, h: int) -> List[Tuple]: ...

class ISessionTracker(Protocol):
    def process_event(self, entry: dict) -> None: ...
    def tick(self) -> None: ...
    def get_sessions(self) -> List[dict]: ...

class IThemeManager(Protocol):
    def get_current(self) -> 'Theme': ...
    def switch(self) -> str: ...
    def color(self, name: str) -> int: ...

class IStatsManager(Protocol):
    def record_event(self, event_type: str, project: str) -> None: ...
    def get_summary(self) -> dict: ...

class IQueueManager(Protocol):
    def read(self) -> List[dict]: ...
    def remove(self, entry: dict) -> None: ...
    def clear(self) -> None: ...

class IEventBus(Protocol):
    def emit(self, event: str, data: Any = None) -> None: ...
    def on(self, event: str, callback: Callable, priority: int = 50) -> None: ...
```

### PluginContext

```python
@dataclass
class PluginContext:
    theme: IThemeManager
    db: IDatabase
    particles: IParticleSystem
    sessions: ISessionTracker
    stats: IStatsManager
    queue: IQueueManager
    events: IEventBus
```

注意：**不传递 stdscr**。所有渲染通过 `render_region` / `render_overlay` 返回 cells，由 Frame.blit() 统一写入。这确保 Frame 控制边界裁剪和渲染顺序。

现有实现（Database、ParticleSystem 等）自动满足 Protocol，无需修改内部代码。

## 3. Plugin Base Class

```python
class Plugin(ABC):
    @property
    @abstractmethod
    def info(self) -> PluginInfo: ...

    # ── 区域渲染（声明 Region 的插件实现）──

    def declare_regions(self) -> List[Region]:
        return []

    def render_region(self, region_id: str, rect: Rect, data: dict) -> List[Tuple]:
        """返回 [(row, col, text, attr), ...]，坐标相对于 Rect 左上角"""
        return []

    # ── 叠加渲染（不声明 Region 的插件，如粒子/弹窗/全屏视图）──

    def render_overlay(self, screen_h: int, screen_w: int, data: dict) -> List[Tuple]:
        """返回 [(row, col, text, attr), ...]，坐标为绝对屏幕坐标"""
        return []

    # ── 全屏视图（可选，如成就页/统计页）──

    def render_fullscreen(self, screen_h: int, screen_w: int, data: dict) -> List[Tuple]:
        """返回非空列表表示接管全屏渲染，Frame 跳过其他所有渲染"""
        return []

    # ── 输入处理（可选）──

    def handle_key(self, key: int, context: dict) -> bool:
        """返回 True 表示已消费该按键"""
        return False

    # ── 生命周期 ──

    def on_load(self, ctx: PluginContext): ...
    def on_start(self): ...
    def on_stop(self): ...
```

### 渲染三级模型

1. **Region 渲染** — `render_region()`：声明式布局内的正常区域渲染
2. **Overlay 渲染** — `render_overlay()`：叠加层（粒子、弹窗），在所有 Region 之后渲染
3. **Fullscreen 渲染** — `render_fullscreen()`：全屏视图（成就页/统计页），优先级最高，返回非空即独占屏幕

主循环渲染顺序：
```
fullscreen? → (如果有) 跳过其他
  ↓ (如果没有)
regions (按 slot 顺序) → overlays (按 priority 顺序)
```

## 4. Plugin Registry

| 插件 | 来源 | Slot | Weight | Priority |
|------|------|------|--------|----------|
| `builtin.top-bar` | `_draw_top_bar` | TOP | - | 100 |
| `builtin.task-queue` | `_draw_left_panel` + Enter/d/c | LEFT | 70 | 100 |
| `builtin.matrix-rain` | `_draw_matrix_rain` + `_draw_scan_line` | RIGHT_TOP | - | 80 |
| `builtin.neural-grid` | `_draw_neural_grid` + star_map | RIGHT_BOT | - | 80 |
| `builtin.pet` | 已有 | LEFT | 30 | 50 |
| `builtin.status-bar` | 状态消息行 | BOTTOM | - | 100 |
| `builtin.hints-bar` | 快捷键提示行 | BOTTOM | - | 90 |
| `builtin.achievements` | 已有 | (overlay: 弹窗) | - | 75 |
| `builtin.achievements-view` | `draw_achievements_view` | (fullscreen) | - | 75 |
| `builtin.stats-view` | `draw_stats_view` | (fullscreen) | - | 75 |
| `builtin.particle-fx` | 已有 | (overlay: 粒子) | - | 30 |
| `builtin.border-particles` | 已有 | (overlay: 边框) | - | 25 |

- scan-line 合并到 matrix-rain 插件的底部渲染
- `border_animator` 和 `border_particles` 合并为 `builtin.border-particles`
- `achievements-view` 和 `stats-view` 通过 `render_fullscreen()` 实现全屏页面

## 5. Event System

EventBus 替代现有 HookRegistry，采用发布/订阅模式。

### EventBus

```python
class EventBus:
    def emit(self, event: str, data: Any = None):
        """按优先级降序调用所有订阅者"""
        for priority, callback in sorted(self._subscribers.get(event, []), key=lambda x: -x[0]):
            callback(data)

    def on(self, event: str, callback: Callable, priority: int = 50):
        """注册订阅，priority 越高越先执行"""
        ...

    def once(self, event: str, callback: Callable, priority: int = 50):
        ...
```

### Event Flow

```
notify.sh → JSONL → Frame.read_queue()
                       ↓
                 EventBus.emit("queue_update", {entries, added, removed})
                       ↓
         ┌─────────────┼─────────────┐
         ↓             ↓             ↓
  task-queue     neural-grid    achievements
  (渲染列表)     (更新session)   (检查成就)
         ↓
  EventBus.emit("task_complete", entry)
         ↓
  pet / achievements / particle-fx / stats
```

### Key Events

| Event | Emitter | Subscribers |
|-------|---------|-------------|
| `queue_update` | Frame 主循环 | task-queue, neural-grid |
| `queue_changed` | Frame 主循环 (仅新增条目时) | pet (`on_new_task`) |
| `key_press` | Frame 主循环 | 所有插件 (按 priority) |
| `task_complete` | task-queue (Enter) | pet, achievements, particle-fx, stats |
| `task_discard` | task-queue (d) | pet |
| `queue_clear` | task-queue (c) | pet |
| `achievement_unlock` | achievements | pet, particle-fx |
| `set_status` | 任意插件 | status-bar |
| `theme_change` | hints-bar (t) | 所有渲染插件 |
| `view_switch` | hints-bar (a/s/ESC) | 所有 fullscreen 插件 |

`set_status` 事件数据: `{"text": "...", "duration": 2.0}` — status-bar 订阅并管理自己的清除计时器。

`view_switch` 事件数据: `{"view": "queue"|"achievements"|"stats"}` — 对应 fullscreen 插件激活/停用。

## 6. Main Loop

```python
def run(self):
    prev_entries = []
    while True:
        entries = self.queue.read()

        # 计算增量
        added = [e for e in entries if e not in prev_entries]

        self.sessions.process_events(entries)
        self.sessions.tick()
        self.particles.update()

        # 事件分发
        self.events.emit("queue_update", {"entries": entries, "added": added, "removed": []})
        if added:
            self.events.emit("queue_changed", {"entries": entries, "added": added})

        # 布局计算
        regions = self.collect_regions()
        layout = self.layout_engine.compute(regions, h, w)

        # 渲染
        self.stdscr.erase()

        # 1. 检查 fullscreen
        fullscreen_cells = []
        for plugin in self.sorted_plugins():
            cells = plugin.render_fullscreen(h, w, {"entries": entries})
            if cells:
                fullscreen_cells = cells
                break

        if fullscreen_cells:
            self.blit(fullscreen_cells)
        else:
            # 2. Region 渲染
            for plugin in self.sorted_plugins():
                for region in plugin.declare_regions():
                    rect = layout.get(region.id)
                    if rect is None:
                        continue  # 被布局引擎降级
                    cells = plugin.render_region(region.id, rect, {"entries": entries})
                    self.blit(cells, offset=(rect.row, rect.col))

            # 3. Overlay 渲染
            for plugin in self.sorted_plugins():
                cells = plugin.render_overlay(h, w, {"entries": entries})
                self.blit(cells)

        self.stdscr.refresh()

        # 输入处理
        key = self.stdscr.getch()
        self.dispatch_key(key, entries)

        prev_entries = entries
```

### blit 方法

```python
def blit(self, cells: List[Tuple], offset=(0, 0)):
    """批量写入 curses，带边界裁剪"""
    h, w = self.stdscr.getmaxyx()
    for row, col, text, attr in cells:
        r, c = row + offset[0], col + offset[1]
        if 0 <= r < h and 0 <= c < w:
            try:
                self.stdscr.addstr(r, c, text[:w-c], attr)
            except curses.error:
                pass
```

### Frame 错误兜底

如果 PluginManager 加载失败或所有插件都无法启动，Frame 显示最小硬编码错误信息：

```python
# 仅在无插件可用时
self.stdscr.addstr(0, 0, "claude-monitor: 插件系统错误，请检查 config/plugins.yaml")
```

### dispatch_key

```python
def dispatch_key(self, key: int, entries: dict):
    # q/Q 由 Frame 直接处理（不可拦截）
    if key in (ord('q'), ord('Q')):
        return False
    # 其余按插件 priority 降序分发
    for plugin in self.sorted_plugins():
        if plugin.handle_key(key, {"entries": entries}):
            break
    return True
```

### Removed from monitor.py

- `self.TYPE_COLOR` → 移到 task-queue 插件
- `self.pet`, `self.achievement_manager` → 由对应插件管理
- 所有 `_draw_*` 方法 → 由各插件 render_region 替代
- `_get_pet_plugin()`, `_get_achievement_plugin()` bridge 方法 → 不再需要
- `_trigger_hook()` → 由 EventBus.emit 替代
- `self.current_view` 状态 → 由 fullscreen 插件自行管理

## 7. File Structure

```
claude-tmux/
├── monitor.py                    # 框架入口 (~150 行)
├── lib/
│   ├── protocols.py              # [新] 核心服务 Protocol 定义
│   ├── frame.py                  # [新] Frame 类: 主循环、布局、渲染、blit
│   ├── layout.py                 # [新] LayoutEngine + Slot + Region + Rect
│   ├── eventbus.py               # [新] EventBus 发布/订阅
│   ├── plugins/
│   │   ├── core.py               # Plugin 基类 (扩展 declare_regions/render_overlay/render_fullscreen)
│   │   ├── manager.py            # PluginManager (适配新 PluginContext)
│   │   └── hooks.py              # [删] 被 eventbus.py 替代
│   ├── database.py               # 保持 (满足 IDatabase protocol)
│   ├── particles/system.py       # 保持 (满足 IParticleSystem protocol)
│   ├── session_tracker.py        # 保持 (满足 ISessionTracker protocol)
│   ├── theme.py                  # 保持 (满足 IThemeManager protocol)
│   ├── stats.py                  # 保持 (满足 IStatsManager protocol)
│   ├── banner.py                 # 保持
│   ├── pet.py                    # [删] 已在 plugins/builtin/pet/
│   ├── achievements.py           # [删] 已在 plugins/builtin/achievements/
│   └── star_map.py               # [删] 渲染迁入 neural-grid 插件
├── plugins/
│   └── builtin/
│       ├── top-bar/              # [新] 顶栏
│       ├── task-queue/           # [新] 左侧任务列表 + 输入处理 (Enter/d/c)
│       ├── matrix-rain/          # [新] 矩阵雨 + scan-line
│       ├── neural-grid/          # [新] 神经网格 (含 star_map)
│       ├── status-bar/           # [新] 状态消息行 (订阅 set_status)
│       ├── hints-bar/            # [新] 快捷键提示行 (处理 t/a/s/ESC)
│       ├── pet/                  # [已有→适配] 宠物
│       ├── achievements/         # [已有→适配] 成就系统 (overlay: 弹窗)
│       ├── achievements-view/    # [新] 成就全屏页 (fullscreen)
│       ├── stats-view/           # [新] 统计全屏页 (fullscreen)
│       ├── particle-fx/          # [已有→适配] 粒子特效 (overlay)
│       └── border-particles/     # [已有→适配] 边框粒子 (overlay, 合并 border_animator)
└── config/
    └── plugins.yaml              # 更新: 添加所有新插件配置 (内置插件默认 enabled)
```

## 8. Migration Order

渐进式迁移，每步可运行可验证：

1. **基础设施** — 新建 protocols.py、eventbus.py、layout.py、扩展 Plugin 基类
2. **Frame 骨架** — frame.py 主循环（含 blit/dispatch_key/错误兜底），先空跑不渲染
3. **top-bar 插件** — 最简单的 1 方法迁移，验证 render_region 流程
4. **task-queue 插件** — 含输入处理 (Enter/d/c) + set_status 事件，验证事件流
5. **matrix-rain + neural-grid 插件** — 右侧面板，scan-line 合并到 matrix-rain
6. **status-bar + hints-bar 插件** — 底部区域，验证 set_status 订阅和 view_switch
7. **fullscreen 插件** — achievements-view + stats-view，验证全屏渲染模式
8. **适配现有插件** — pet/achievements/particle-fx/border-particles 适配新 Plugin 接口
9. **配置迁移** — 更新 plugins.yaml，确保所有新内置插件默认 enabled
10. **清理** — 删除旧代码: hooks.py、lib/pet.py、lib/achievements.py、lib/star_map.py、plugins/builtin/border_animator/

## 9. Verification

每个迁移步骤完成后：
1. 运行 `claude-monitor`，确认所有区域正常渲染
2. 手动触发事件 `bash notify.sh hitl "test"`，验证队列和跳转
3. 按键测试: Enter (跳转)、d (丢弃)、c (清空)、t (主题)、a (成就页)、s (统计页)、q (退出)
4. 确认插件可独立禁用（修改 plugins.yaml enabled: false 后对应区域消失）
5. 确认无 fallback 双路径 — 禁用插件 = 区域消失
6. 确认 overlay 渲染正常（粒子特效、成就弹窗）
7. 确认 fullscreen 视图切换正常（a/s/ESC）
8. 故意制造插件加载错误，确认 Frame 显示错误兜底信息
