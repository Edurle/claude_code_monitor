# Plugin Framework Design — 全插件化架构重构

> Date: 2026-04-03
> Status: Draft

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
3. 主循环：`read_queue → layout → render → handle_input`

## 1. Region Declaration & Layout Engine

### Slot

预定义屏幕区域槽位：

```python
class Slot(Enum):
    TOP       = "top"         # 顶栏（全宽, 1行）
    LEFT      = "left"        # 左侧面板（40%宽）
    RIGHT_TOP = "right-top"   # 右上（60%宽, 45%高）
    RIGHT_BOT = "right-bot"   # 右下（60%宽, 55%高）
    BOTTOM    = "bottom"      # 底部（全宽, 3行）
```

### Region

```python
@dataclass
class Region:
    id: str              # 唯一标识, 如 "task_queue"
    slot: Slot           # 占据哪个 slot
    min_height: int      # 最小高度（行数）
    priority: int        # 同 slot 内排序优先级（高优先）
```

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
        # 3. 分配坐标:
        #    TOP → row 0, 全宽, 固定 1 行
        #    LEFT → rows 1..h-4, 宽度 40%
        #    RIGHT_TOP → rows 1..split, 宽度 60%
        #    RIGHT_BOT → rows split..h-4, 宽度 60%
        #    BOTTOM → rows h-3..h-1, 全宽
        # 同 slot 多个插件时按 priority 排序后均分空间
        # 返回 {region_id: Rect}
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
    def on(self, event: str, callback: Callable) -> None: ...
```

### PluginContext

```python
@dataclass
class PluginContext:
    stdscr: Any
    theme: IThemeManager
    db: IDatabase
    particles: IParticleSystem
    sessions: ISessionTracker
    stats: IStatsManager
    queue: IQueueManager
    events: IEventBus
```

现有实现（Database、ParticleSystem 等）自动满足 Protocol，无需修改内部代码。

## 3. Plugin Base Class

```python
class Plugin(ABC):
    @property
    @abstractmethod
    def info(self) -> PluginInfo: ...

    # Region 声明（渲染插件必须实现）
    def declare_regions(self) -> List[Region]:
        return []

    # Region 渲染
    def render_region(self, region_id: str, rect: Rect, data: dict) -> List[Tuple]:
        """返回 [(row, col, text, attr), ...]"""
        return []

    # 输入处理（可选）
    def handle_key(self, key: int, context: dict) -> bool:
        """返回 True 表示已消费该按键"""
        return False

    # 生命周期
    def on_load(self, ctx: PluginContext): ...
    def on_start(self): ...
    def on_stop(self): ...
```

## 4. Plugin Registry

| 插件 | 来源 | Slot | Priority |
|------|------|------|----------|
| `builtin.top-bar` | `_draw_top_bar` | TOP | 100 |
| `builtin.task-queue` | `_draw_left_panel` + Enter/d/c | LEFT | 100 |
| `builtin.matrix-rain` | `_draw_matrix_rain` + `_draw_scan_line` | RIGHT_TOP | 80 |
| `builtin.neural-grid` | `_draw_neural_grid` + star_map | RIGHT_BOT | 80 |
| `builtin.pet` | 已有 | LEFT | 50 |
| `builtin.status-bar` | 状态消息行 | BOTTOM | 100 |
| `builtin.hints-bar` | 快捷键提示行 | BOTTOM | 90 |
| `builtin.achievements` | 已有 | (无区域, 事件驱动) | 75 |
| `builtin.particle-fx` | 已有 | (无区域, 叠加渲染) | 30 |

scan-line 合并到 matrix-rain 插件的底部渲染。

## 5. Event System

EventBus 替代现有 HookRegistry，采用发布/订阅模式。

### EventBus

```python
class EventBus:
    def emit(self, event: str, data: Any = None):
        for callback in self._subscribers.get(event, []):
            callback(data)

    def on(self, event: str, callback: Callable):
        ...

    def once(self, event: str, callback: Callable):
        ...
```

### Event Flow

```
notify.sh → JSONL → Frame.read_queue()
                       ↓
                 EventBus.emit("queue_update", entries)
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
| `key_press` | Frame 主循环 | 所有插件 (按优先级) |
| `task_complete` | task-queue (Enter) | pet, achievements, particle-fx, stats |
| `task_discard` | task-queue (d) | pet |
| `queue_clear` | task-queue (c) | pet |
| `achievement_unlock` | achievements | pet, particle-fx |
| `theme_change` | hints-bar (t) | 所有渲染插件 |

优先级通过订阅顺序保证（PluginManager 按 priority 启动插件）。

## 6. Main Loop

```python
def run(self):
    while True:
        entries = self.queue.read()

        self.sessions.process_events(entries)
        self.sessions.tick()
        self.particles.update()

        regions = self.collect_regions()
        layout = self.layout_engine.compute(regions, h, w)

        self.stdscr.erase()
        for plugin in self.sorted_plugins():
            for region in plugin.declare_regions():
                rect = layout[region.id]
                data = {"entries": entries, "frame": self.frame}
                cells = plugin.render_region(region.id, rect, data)
                self.blit(cells)
        self.stdscr.refresh()

        key = self.stdscr.getch()
        self.dispatch_key(key, entries)
```

### Removed from monitor.py

- `self.TYPE_COLOR` → 移到 task-queue 插件
- `self.pet`, `self.achievement_manager` → 由对应插件管理
- 所有 `_draw_*` 方法 → 由各插件 `render_region` 替代
- `_get_pet_plugin()`, `_get_achievement_plugin()` bridge 方法 → 不再需要
- `_trigger_hook()` → 由 EventBus.emit 替代

## 7. File Structure

```
claude-tmux/
├── monitor.py                    # 框架入口 (~150 行)
├── lib/
│   ├── protocols.py              # [新] 核心服务 Protocol 定义
│   ├── frame.py                  # [新] Frame 类: 主循环、布局、渲染
│   ├── layout.py                 # [新] LayoutEngine + Slot + Region + Rect
│   ├── eventbus.py               # [新] EventBus 发布/订阅
│   ├── plugins/
│   │   ├── core.py               # Plugin 基类 (扩展 declare_regions)
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
│       ├── task-queue/           # [新] 左侧任务列表 + 输入处理
│       ├── matrix-rain/          # [新] 矩阵雨 + scan-line
│       ├── neural-grid/          # [新] 神经网格 (含 star_map)
│       ├── status-bar/           # [新] 状态消息行
│       ├── hints-bar/            # [新] 快捷键提示行
│       ├── pet/                  # [已有] 适配新接口
│       ├── achievements/         # [已有] 适配新接口
│       ├── particle-fx/          # [已有] 适配新接口
│       └── border_animator/      # [已有] 适配新接口
└── config/
    └── plugins.yaml              # 更新: 添加新插件配置
```

## 8. Migration Order

渐进式迁移，每步可运行可验证：

1. **基础设施** — 新建 protocols.py、eventbus.py、layout.py、扩展 Plugin 基类
2. **Frame 骨架** — frame.py 主循环，先空跑不渲染，验证基础架构
3. **top-bar 插件** — 最简单的 1 方法迁移，验证 render_region 流程
4. **task-queue 插件** — 含输入处理 (Enter/d/c)，验证事件流
5. **matrix-rain + neural-grid 插件** — 右侧面板，scan-line 合并到 matrix-rain
6. **status-bar + hints-bar 插件** — 底部区域
7. **适配现有插件** — pet/achievements/particle-fx 适配新 Plugin 接口
8. **清理** — 删除旧代码: hooks.py、lib/pet.py、lib/achievements.py、lib/star_map.py

## 9. Verification

每个迁移步骤完成后：
1. 运行 `claude-monitor`，确认所有区域正常渲染
2. 手动触发事件 `bash notify.sh hitl "test"`，验证队列和跳转
3. 按键测试: Enter (跳转)、d (丢弃)、c (清空)、t (主题)、q (退出)
4. 确认插件可独立禁用（修改 plugins.yaml enabled: false 后对应区域消失）
5. 确认无 fallback 双路径 — 禁用插件 = 区域消失
