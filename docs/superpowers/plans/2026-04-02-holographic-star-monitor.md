# 全息星图状态监控 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将队列视图替换为左右分栏布局（左侧操作面板 + 右侧全息星图），实时监控多 tmux session 中 Claude Code 的工作状态。

**Architecture:** Hook 驱动状态推送 → .jsonl 队列 → SessionTracker 状态机 → StarMap 渲染引擎（curses）。notify.sh 扩展事件类型，新增 SessionTracker 管理状态机，新增 StarMap 渲染飘动星图。monitor.py 的 draw_queue_view 替换为新的分栏布局。

**Tech Stack:** Python 3.6+, curses, sqlite3 (已有), dataclasses

**Spec:** `docs/superpowers/specs/2026-04-02-holographic-star-monitor-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `notify.sh` | Modify | 扩展事件类型：working/error/session_start/session_end/subagent_start/subagent_stop/api_error |
| `lib/session_tracker.py` | **Create** | Session 状态追踪：状态机、空闲检测、活动流管理 |
| `lib/star_map.py` | **Create** | 星图渲染引擎：节点飘动、背景效果、动画、流星 |
| `monitor.py` | Modify | 新布局：顶栏 + 左面板(HITL/活动流/宠物) + 右面板(星图) + 集成 SessionTracker/StarMap |

---

## Task 1: 扩展 notify.sh 事件类型

**Files:**
- Modify: `notify.sh`

- [ ] **Step 1: 读取当前 notify.sh，理解事件格式**

Run: `cat notify.sh`
Expected: 看到 EVENT_TYPE 和 ENTRY JSON 的当前结构

- [ ] **Step 2: 修改 notify.sh 支持新事件类型**

在现有的 `EVENT_TYPE="${1:-hitl}"` 之后，增加 EXTRA_INFO 提取逻辑，使所有新事件类型都能正确写入队列：

```bash
EVENT_TYPE="${1:-hitl}"
EXTRA_INFO="${2:-}"
```

确保 ENTRY JSON 中的 `type` 字段使用 `$EVENT_TYPE`，`info` 字段使用 `$EXTRA_INFO`。现有 `hitl`/`task_complete`/`error` 不受影响，新增 `working`/`session_start`/`session_end`/`subagent_start`/`subagent_stop`/`api_error` 自动工作，因为它们走的是同一套逻辑。

验证当前 notify.sh 中的 ENTRY 构造是否已使用 `$EVENT_TYPE` 和 `$EXTRA_INFO`。如果是，则只需在 CLAUDE.md 的 hooks 配置示例中补充新事件类型即可。

- [ ] **Step 3: 手动测试 notify.sh 新事件**

```bash
bash notify.sh working "Edit"
bash notify.sh session_start "sess-123"
bash notify.sh error "Bash"
bash notify.sh session_end ""
cat ~/.claude-tmux-queue.jsonl | tail -4
```

Expected: 看到四行 JSON，type 分别为 working/session_start/error/session_end，info 字段正确

- [ ] **Step 4: Commit**

```bash
git add notify.sh
git commit -m "feat: 扩展 notify.sh 支持全息星图状态事件类型"
```

---

## Task 2: 创建 SessionTracker — 状态机核心

**Files:**
- Create: `lib/session_tracker.py`
- Create: `tests/test_session_tracker.py`

- [ ] **Step 1: 写 SessionTracker 的失败测试**

```python
# tests/test_session_tracker.py
import json
import time
import tempfile
import pytest
from pathlib import Path
from lib.session_tracker import SessionTracker, SessionState

def test_new_tracker_has_no_sessions():
    tracker = SessionTracker()
    assert tracker.get_sessions() == []

def test_process_hitl_event():
    tracker = SessionTracker()
    event = {"ts": "12:00:00", "type": "hitl", "session": "proj-a", "win_idx": "0",
             "win_name": "editor", "project": "proj-a", "dir": "/tmp/proj-a", "info": "confirm?"}
    tracker.process_event(event)
    sessions = tracker.get_sessions()
    assert len(sessions) == 1
    assert sessions[0].session == "proj-a"
    assert sessions[0].status == "hitl"

def test_process_working_then_complete():
    tracker = SessionTracker()
    tracker.process_event({"ts": "12:00:00", "type": "working", "session": "proj-a",
                           "win_idx": "0", "win_name": "", "project": "proj-a",
                           "dir": "/tmp/proj-a", "info": "Edit"})
    sessions = tracker.get_sessions()
    assert sessions[0].status == "working"
    assert sessions[0].tool == "Edit"

    tracker.process_event({"ts": "12:01:00", "type": "task_complete", "session": "proj-a",
                           "win_idx": "0", "win_name": "", "project": "proj-a",
                           "dir": "/tmp/proj-a", "info": ""})
    sessions = tracker.get_sessions()
    assert sessions[0].status == "complete"

def test_session_start_and_end():
    tracker = SessionTracker()
    tracker.process_event({"ts": "12:00:00", "type": "session_start", "session": "proj-a",
                           "win_idx": "0", "win_name": "", "project": "proj-a",
                           "dir": "/tmp/proj-a", "info": ""})
    assert tracker.get_sessions()[0].status == "start"

    tracker.process_event({"ts": "12:05:00", "type": "session_end", "session": "proj-a",
                           "win_idx": "0", "win_name": "", "project": "proj-a",
                           "dir": "/tmp/proj-a", "info": ""})
    assert tracker.get_sessions()[0].status == "offline"

def test_idle_timeout():
    tracker = SessionTracker()
    old_ts = time.time() - 400  # 6+ minutes ago
    tracker.process_event({"ts": "old", "type": "working", "session": "proj-a",
                           "win_idx": "0", "win_name": "", "project": "proj-a",
                           "dir": "/tmp/proj-a", "info": "Edit",
                           "_ts": old_ts})
    tracker.tick()
    assert tracker.get_sessions()[0].status == "idle"

def test_get_hitl_sessions():
    tracker = SessionTracker()
    tracker.process_event({"ts": "12:00", "type": "hitl", "session": "proj-a",
                           "win_idx": "0", "win_name": "", "project": "proj-a",
                           "dir": "/tmp/a", "info": "confirm?"})
    tracker.process_event({"ts": "12:01", "type": "working", "session": "proj-b",
                           "win_idx": "0", "win_name": "", "project": "proj-b",
                           "dir": "/tmp/b", "info": "Edit"})
    hitl = tracker.get_hitl_sessions()
    assert len(hitl) == 1
    assert hitl[0].session == "proj-a"

def test_subagent_tracking():
    tracker = SessionTracker()
    tracker.process_event({"ts": "12:00", "type": "working", "session": "proj-a",
                           "win_idx": "0", "win_name": "", "project": "proj-a",
                           "dir": "/tmp/a", "info": "Agent"})
    tracker.process_event({"ts": "12:00", "type": "subagent_start", "session": "proj-a",
                           "win_idx": "0", "win_name": "", "project": "proj-a",
                           "dir": "/tmp/a", "info": "Explore"})
    s = tracker.get_sessions()[0]
    assert s.subagent_count == 1
    assert "Explore" in s.subagents

    tracker.process_event({"ts": "12:01", "type": "subagent_stop", "session": "proj-a",
                           "win_idx": "0", "win_name": "", "project": "proj-a",
                           "dir": "/tmp/a", "info": ""})
    s = tracker.get_sessions()[0]
    assert s.subagent_count == 0

def test_activity_stream():
    tracker = SessionTracker()
    tracker.process_event({"ts": "12:00", "type": "working", "session": "proj-a",
                           "win_idx": "0", "win_name": "", "project": "proj-a",
                           "dir": "/tmp/a", "info": "Edit"})
    tracker.process_event({"ts": "12:01", "type": "task_complete", "session": "proj-b",
                           "win_idx": "0", "win_name": "", "project": "proj-b",
                           "dir": "/tmp/b", "info": ""})
    stream = tracker.get_activity_stream(limit=10)
    assert len(stream) == 2
    assert stream[0]["type"] == "task_complete"  # most recent first
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /home/wang/claude-tmux && python3 -m pytest tests/test_session_tracker.py -v`
Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现 SessionTracker**

```python
# lib/session_tracker.py
"""Session 状态追踪器：读取队列事件，维护 session 状态机"""

import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from collections import OrderedDict

# 空闲超时（秒）
IDLE_TIMEOUT = 300  # 5 minutes

@dataclass
class SessionState:
    """单个 session 的状态"""
    session: str
    status: str = "start"          # start/idle/working/hitl/complete/error/api_error/offline
    project: str = ""
    win_idx: str = "0"
    win_name: str = ""
    dir: str = ""
    tool: str = ""
    info: str = ""
    last_event_ts: float = 0.0
    last_event_time: str = ""       # 显示用的时间字符串
    subagents: List[str] = field(default_factory=list)
    hitl_info: str = ""             # HITL 消息

    @property
    def subagent_count(self) -> int:
        return len(self.subagents)

class SessionTracker:
    """追踪所有 Claude Code session 的实时状态"""

    def __init__(self):
        self._sessions: OrderedDict[str, SessionState] = OrderedDict()
        self._activity: List[dict] = []

    def process_event(self, event: dict):
        """处理一个队列事件，更新对应 session 的状态"""
        session = event.get("session", "")
        if not session:
            return

        event_type = event.get("type", "")
        info = event.get("info", "")
        ts = event.get("_ts", time.time())
        ts_str = event.get("ts", "")

        # 获取或创建 session
        if session not in self._sessions:
            self._sessions[session] = SessionState(
                session=session,
                project=event.get("project", ""),
                win_idx=event.get("win_idx", "0"),
                win_name=event.get("win_name", ""),
                dir=event.get("dir", ""),
            )

        s = self._sessions[session]
        s.last_event_ts = ts
        s.last_event_time = ts_str
        s.project = event.get("project", s.project)
        s.win_idx = event.get("win_idx", s.win_idx)
        s.win_name = event.get("win_name", s.win_name)

        # 状态机转换
        if event_type == "session_start":
            s.status = "start"
        elif event_type == "session_end":
            s.status = "offline"
        elif event_type in ("working",):
            s.status = "working"
            s.tool = info
            s.info = info
        elif event_type == "hitl":
            s.status = "hitl"
            s.hitl_info = info
        elif event_type == "task_complete":
            s.status = "complete"
            s.tool = ""
            s.info = ""
        elif event_type == "error":
            s.status = "error"
            s.info = info
        elif event_type == "api_error":
            s.status = "api_error"
            s.info = info
        elif event_type == "subagent_start":
            if info and info not in s.subagents:
                s.subagents.append(info)
        elif event_type == "subagent_stop":
            s.subagents = [a for a in s.subagents if a != info]

        # 记录活动流
        self._activity.append({
            "ts": ts_str,
            "type": event_type,
            "session": session,
            "project": s.project,
            "info": info,
            "_ts": ts,
        })
        # 限制活动流长度
        if len(self._activity) > 200:
            self._activity = self._activity[-100:]

    def tick(self):
        """定时调用：检测空闲超时"""
        now = time.time()
        for s in self._sessions.values():
            if s.status in ("working", "complete", "start", "error") and s.last_event_ts > 0:
                if now - s.last_event_ts > IDLE_TIMEOUT:
                    s.status = "idle"
                    s.tool = ""
                    s.info = ""

    def get_sessions(self) -> List[SessionState]:
        """获取所有活跃 session（排除 offline 超过 5 分钟的）"""
        now = time.time()
        result = []
        for s in self._sessions.values():
            if s.status == "offline" and s.last_event_ts > 0 and now - s.last_event_ts > 300:
                continue
            result.append(s)
        return result

    def get_hitl_sessions(self) -> List[SessionState]:
        """获取所有需要人工处理的 session"""
        return [s for s in self._sessions.values() if s.status == "hitl"]

    def get_activity_stream(self, limit: int = 20) -> List[dict]:
        """获取最近的活动流"""
        return list(reversed(self._activity[-limit:]))
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /home/wang/claude-tmux && python3 -m pytest tests/test_session_tracker.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add lib/session_tracker.py tests/test_session_tracker.py
git commit -m "feat: 创建 SessionTracker 状态机（session 状态追踪和活动流）"
```

---

## Task 3: 创建 StarMap — 星图渲染引擎

**Files:**
- Create: `lib/star_map.py`

- [ ] **Step 1: 实现 StarMap 核心类**

```python
# lib/star_map.py
"""全息星图渲染引擎：节点飘动、背景效果、流星"""

import math
import random
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

# 状态对应的显示配置
STATUS_DISPLAY = {
    "start":       {"char": "◇", "color": 6, "pulse": True},   # 蓝色
    "idle":        {"char": "○", "color": 8, "pulse": False},   # 灰色
    "working":     {"char": "◆", "color": 3, "pulse": True},   # 橙色/黄色
    "hitl":        {"char": "⚠", "color": 4, "pulse": True},   # 红色
    "complete":    {"char": "✦", "color": 2, "pulse": False},  # 绿色
    "error":       {"char": "✖", "color": 4, "pulse": True},   # 红色
    "api_error":   {"char": "⛔","color": 4, "pulse": True},   # 红色
    "offline":     {"char": "·", "color": 8, "pulse": False},  # 灰暗
}

@dataclass
class StarNode:
    """星图中的一个节点（代表一个 session）"""
    session: str
    x: float = 0.0     # 百分比位置 0-100
    y: float = 0.0
    base_x: float = 0.0
    base_y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    status: str = "start"
    tool: str = ""
    project: str = ""
    subagents: List[str] = field(default_factory=list)
    fade_alpha: float = 1.0      # 0.0=不可见, 1.0=完全可见
    anim_phase: float = 0.0      # 动画相位
    ripple: float = 0.0          # 涟漪半径

class Meteor:
    """流星粒子"""
    def __init__(self, max_w: int, max_h: int):
        # 从顶部或右侧出发
        if random.random() > 0.5:
            self.x = random.uniform(0, max_w)
            self.y = -2
        else:
            self.x = max_w + 2
            self.y = random.uniform(0, max_h * 0.5)
        angle = math.pi * (0.55 + random.random() * 0.3)
        speed = 1.5 + random.random() * 2
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.life = 1.0
        self.decay = 0.01 + random.random() * 0.02
        self.trail: List[Tuple[float, float]] = []
        self.max_trail = 12 + int(random.random() * 8)
        self.alive = True

    def update(self):
        self.trail.insert(0, (self.x, self.y))
        if len(self.trail) > self.max_trail:
            self.trail.pop()
        self.x += self.vx
        self.y += self.vy
        self.life -= self.decay
        if self.life <= 0:
            self.alive = False


class StarMap:
    """全息星图渲染引擎"""

    def __init__(self):
        self._stars: Dict[str, StarNode] = {}
        self._meteors: List[Meteor] = []
        self._radar_angle: float = 0.0
        self._field_w: int = 0
        self._field_h: int = 0

    def update_from_sessions(self, sessions: list):
        """根据 SessionTracker 的 sessions 更新星星"""
        # 标记当前已有的 session
        current_sessions = set()
        for s in sessions:
            current_sessions.add(s.session)
            if s.session not in self._stars:
                # 新 session：在面板中心附近随机位置创建
                star = StarNode(
                    session=s.session,
                    x=30 + random.uniform(5, 40),
                    y=20 + random.uniform(5, 50),
                    project=s.project,
                )
                star.base_x = star.x
                star.base_y = star.y
                star.vx = (random.random() - 0.5) * 0.06
                star.vy = (random.random() - 0.5) * 0.06
                self._stars[s.session] = star
            else:
                star = self._stars[s.session]

            star.status = s.status
            star.tool = s.tool
            star.project = s.project
            star.subagents = list(s.subagents)
            if s.status == "offline":
                star.fade_alpha = max(0, star.fade_alpha - 0.02)
            else:
                star.fade_alpha = min(1.0, star.fade_alpha + 0.1)

        # 渐隐消失的 offline session
        to_remove = []
        for sid, star in self._stars.items():
            if sid not in current_sessions:
                star.fade_alpha -= 0.01
                if star.fade_alpha <= 0:
                    to_remove.append(sid)
        for sid in to_remove:
            del self._stars[sid]

    def tick(self):
        """每帧调用：更新飘动、流星、雷达"""
        for star in self._stars.values():
            # 布朗运动
            star.vx += (random.random() - 0.5) * 0.012
            star.vy += (random.random() - 0.5) * 0.012
            # 速度上限
            star.vx = max(-0.12, min(0.12, star.vx))
            star.vy = max(-0.12, min(0.12, star.vy))
            # 弹性回弹
            star.vx += (star.base_x - star.x) * 0.001
            star.vy += (star.base_y - star.y) * 0.001
            # 边界
            if star.x < 5: star.vx += 0.03
            if star.x > 88: star.vx -= 0.03
            if star.y < 5: star.vy += 0.03
            if star.y > 88: star.vy -= 0.03
            # 阻尼
            star.vx *= 0.995
            star.vy *= 0.995
            star.x += star.vx
            star.y += star.vy
            # 动画相位
            star.anim_phase += 0.1
            # 涟漪
            if star.status == "hitl":
                star.ripple += 0.5

        # 雷达扫描
        self._radar_angle += math.pi * 2 / (6 * 20)  # 6秒一周 @20fps

        # 流星
        if len(self._meteors) < 3 and random.random() < 0.03:
            self._meteors.append(Meteor(100, 100))
        self._meteors = [m for m in self._meteors if m.alive]
        for m in self._meteors:
            m.update()

    def render(self, stdscr, x_off: int, y_off: int, width: int, height: int, addstr_fn) -> list:
        """渲染星图到 curses 窗口，返回需要绘制的元素列表"""
        import curses
        self._field_w = width
        self._field_h = height
        elements = []  # [(row, col, text, attr), ...]

        # 1. 背景网格（稀疏点阵）
        for gy in range(2, height - 1, 3):
            for gx in range(2, width - 1, 6):
                elements.append((y_off + gy, x_off + gx, "·", curses.A_DIM))

        # 2. 同心圆（面板中心）
        cx, cy = width // 2, height // 2
        for r_pct in [0.25, 0.40, 0.55]:
            r = int(min(width, height) * r_pct / 2)
            for angle in range(0, 360, 8):
                rad = math.radians(angle)
                px = int(cx + r * math.cos(rad))
                py = int(cy + r * math.sin(rad) * 0.5)  # 椭圆
                if 0 <= px < width and 0 <= py < height:
                    elements.append((y_off + py, x_off + px, "·", curses.A_DIM))

        # 3. 雷达扫描线
        scan_len = min(width, height) * 0.45
        sx = int(cx + scan_len * math.cos(self._radar_angle))
        sy = int(cy + scan_len * math.sin(self._radar_angle) * 0.5)
        # 画线（简单的直线点）
        steps = max(abs(sx - cx), abs(sy - cy), 1)
        for i in range(steps):
            t = i / steps
            px = int(cx + (sx - cx) * t)
            py = int(cy + (sy - cy) * t)
            if 0 <= px < width and 0 <= py < height:
                alpha = 1.0 - t * 0.7
                elements.append((y_off + py, x_off + px, "─", curses.color_pair(1) | curses.A_DIM))

        # 4. 流星
        for m in self._meteors:
            if len(m.trail) < 2:
                continue
            for i, (tx, ty) in enumerate(m.trail):
                # 将流星坐标映射到面板区域
                px = int(tx * width / 100)
                py = int(ty * height / 100)
                if 0 <= px < width and 0 <= py < height:
                    alpha = m.life * (1 - i / len(m.trail))
                    if alpha > 0.1:
                        elements.append((y_off + py, x_off + px, "·", curses.color_pair(6)))

        # 5. 星星节点
        for star in self._stars.values():
            display = STATUS_DISPLAY.get(star.status, STATUS_DISPLAY["idle"])
            # 百分比 → 面板坐标
            sx = int(star.x * width / 100)
            sy = int(star.y * height / 100)
            if sx < 1 or sx >= width - 1 or sy < 1 or sy >= height - 2:
                continue

            # 透明度
            if star.fade_alpha < 0.3:
                continue

            attr = curses.color_pair(display["color"])
            if display["pulse"]:
                # 脉冲效果：交替亮度
                phase = math.sin(star.anim_phase)
                if phase < -0.3:
                    attr |= curses.A_DIM
                elif phase > 0.3:
                    attr |= curses.A_BOLD

            # 涟漪
            if star.status == "hitl" and star.ripple > 0:
                ripple_r = int(star.ripple)
                for a in range(0, 360, 30):
                    rad = math.radians(a)
                    rx = int(sx + ripple_r * math.cos(rad))
                    ry = int(sy + ripple_r * math.sin(rad) * 0.5)
                    if 0 <= rx < width and 0 <= ry < height:
                        elements.append((y_off + ry, x_off + rx, "·", curses.color_pair(4) | curses.A_DIM))
                if star.ripple > 8:
                    star.ripple = 0

            # 星星字符
            elements.append((y_off + sy, x_off + sx, display["char"], attr))

            # session 名称（星星下方）
            name = star.project or star.session
            name = name[:12]
            elements.append((y_off + sy + 1, x_off + sx - len(name) // 2, name, curses.A_DIM))

            # 工具/状态信息（名称下方）
            if star.tool and star.status == "working":
                tool_text = f"▓▓▓░░ {star.tool}"[:14]
                elements.append((y_off + sy + 2, x_off + sx - len(tool_text) // 2, tool_text, curses.A_DIM))
            elif star.status == "hitl" and star.fade_alpha >= 0.5:
                hitl_text = "⚡ HITL"[:14]
                elements.append((y_off + sy + 2, x_off + sx - len(hitl_text) // 2, hitl_text, curses.color_pair(4)))

            # 子代理标识
            if star.subagents:
                sa_text = f"·{star.subagents[0][:6]}"[:8]
                elements.append((y_off + sy, x_off + sx + 2, sa_text, curses.A_DIM))

        return elements
```

- [ ] **Step 2: 验证 StarMap 可导入**

Run: `cd /home/wang/claude-tmux && python3 -c "from lib.star_map import StarMap; sm = StarMap(); print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add lib/star_map.py
git commit -m "feat: 创建 StarMap 星图渲染引擎（飘动/流星/雷达/涟漪）"
```

---

## Task 4: 重构 monitor.py — 集成新布局

**Files:**
- Modify: `monitor.py`

这是最大的任务。需要修改 `draw_queue_view` 为新的左右分栏布局，集成 `SessionTracker` 和 `StarMap`。

- [ ] **Step 1: 在 monitor.py 顶部添加导入**

在现有的导入区域添加：

```python
from lib.session_tracker import SessionTracker
from lib.star_map import StarMap
```

- [ ] **Step 2: 在 `__init__` 中初始化新组件**

在 `self.db = Database.get_instance()` 之后添加：

```python
self.session_tracker = SessionTracker()
self.star_map = StarMap()
self.fleet_scroll = 0  # HITL 列表滚动
```

- [ ] **Step 3: 修改 `run()` 方法中的事件处理**

在 `entries = self.read_queue()` 之后，将事件推送给 SessionTracker：

```python
# 现有：entries = self.read_queue()
# 新增：推送事件给 session tracker
for entry in entries:
    self.session_tracker.process_event(entry)
self.session_tracker.tick()
self.star_map.update_from_sessions(self.session_tracker.get_sessions())
self.star_map.tick()
```

- [ ] **Step 4: 替换 `draw_queue_view` 为新的 `draw_fleet_view` 方法**

创建新方法，实现左右分栏布局。保留对宠物区域和粒子效果的调用。

关键结构：
```python
def draw_fleet_view(self, entries: List[dict]):
    h, w = self.get_effective_size()
    import curses

    left_w = max(30, w * 2 // 5)  # 40%
    right_w = w - left_w - 1       # 60% - 分隔线

    # 顶栏 (row 0)
    self._draw_top_bar(h, w)

    # 左面板 (row 1 到 h-4)
    self._draw_left_panel(1, 0, left_w, h - 4, entries)

    # 分隔线
    for r in range(1, h - 3):
        self.addstr(r, left_w, "│", curses.A_DIM)

    # 右面板 - 星图 (row 1 到 h-4)
    self._draw_star_field(1, left_w + 1, right_w, h - 4)

    # 宠物区域（左面板底部 h-8）
    self._draw_pet_area(h - 8)

    # 粒子效果（全屏覆盖）
    particle_results = self._trigger_hook("render_particles")
    if particle_results:
        for result in particle_results:
            if isinstance(result, list):
                for item in result:
                    if isinstance(item, tuple) and len(item) >= 3:
                        try:
                            self.addstr(item[0], item[1], str(item[2]),
                                        item[3] if len(item) > 3 and isinstance(item[3], int) and item[3] > 0 else 0)
                        except curses.error:
                            pass

    # 状态消息 (h-3)
    if self.status_msg:
        self.addstr(h - 3, 2, self.status_msg, curses.color_pair(2))

    # 分隔线 (h-2)
    self.addstr(h - 2, 0, "─" * w, curses.A_DIM)

    # 提示栏 (h-1)
    hints = "[Enter]跳转 [↑↓]选择 [d]丢弃 [T]主题 [A]成就 [S]统计 [P]宠物 [q]退出"
    self.addstr(h - 1, 0, hints, curses.A_DIM)
```

- [ ] **Step 5: 实现 `_draw_top_bar`**

```python
def _draw_top_bar(self, h: int, w: int):
    import curses
    sessions = self.session_tracker.get_sessions()
    total = len(sessions)
    hitl = sum(1 for s in sessions if s.status == "hitl")
    working = sum(1 for s in sessions if s.status == "working")
    complete = sum(1 for s in sessions if s.status == "complete")

    bar = f" ◈ CLAUDE FLEET MONITOR  {total} sessions"
    if hitl: bar += f"  ⚡{hitl}"
    if working: bar += f"  ◆{working}"
    if complete: bar += f"  ✦{complete}"
    self.addstr(0, 0, bar.ljust(w), curses.color_pair(1) | curses.A_BOLD)
```

- [ ] **Step 6: 实现 `_draw_left_panel`**

```python
def _draw_left_panel(self, start_row: int, start_col: int, width: int, end_row: int, entries: list):
    import curses
    row = start_row

    # HITL 待处理区
    hitl_sessions = self.session_tracker.get_hitl_sessions()
    hitl_count = len(hitl_sessions)

    if hitl_count > 0:
        self.addstr(row, start_col + 1, f"⚡ HITL 待处理 ({hitl_count})",
                     curses.color_pair(4) | curses.A_BOLD)
        row += 1
        for i, s in enumerate(hitl_sessions):
            if row >= end_row - 8:  # 留出宠物空间
                break
            marker = "▶" if i == self.fleet_scroll % hitl_count else " "
            line = f" {marker} {s.project or s.session}"
            self.addstr(row, start_col + 1, line[:width],
                         curses.color_pair(4) if i == self.fleet_scroll % hitl_count else curses.color_pair(5))
            if s.hitl_info:
                row += 1
                self.addstr(row, start_col + 3, s.hitl_info[:width - 4], curses.A_DIM)
            row += 1
    else:
        self.addstr(row, start_col + 1, " ✓ 所有会话运行正常", curses.color_pair(2))
        row += 1

    # 分隔线
    row += 1
    self.addstr(row, start_col, "─" * width, curses.A_DIM)
    row += 1

    # 活动流
    self.addstr(row, start_col + 1, "◈ 活动流", curses.color_pair(1))
    row += 1
    stream = self.session_tracker.get_activity_stream(limit=20)
    for item in stream:
        if row >= end_row - 8:
            break
        ts = item.get("ts", "")
        typ = item.get("type", "")
        proj = item.get("project", "")
        info = item.get("info", "")
        type_icon = {"working": "◆", "hitl": "⚠", "task_complete": "✦",
                     "error": "✖", "session_start": "◇"}.get(typ, "·")
        type_color = {"working": 3, "hitl": 4, "task_complete": 2,
                      "error": 4}.get(typ, 5)
        line = f" {ts} {type_icon} {proj[:8]} {info[:10]}"
        self.addstr(row, start_col + 1, line[:width], curses.color_pair(type_color))
        row += 1
```

- [ ] **Step 7: 实现 `_draw_star_field`**

```python
def _draw_star_field(self, start_row: int, start_col: int, width: int, height: int):
    elements = self.star_map.render(
        self.stdscr, start_col, start_row, width, height, self.addstr
    )
    import curses
    for (r, c, text, attr) in elements:
        try:
            self.addstr(r, c, text, attr)
        except curses.error:
            pass
```

- [ ] **Step 8: 修改 `run()` 中的视图分发**

将 `draw_queue_view(entries)` 替换为 `draw_fleet_view(entries)`：

```python
# 原来：
if self.current_view == VIEW_QUEUE:
    self.draw_queue_view(entries)
# 改为：
if self.current_view == VIEW_QUEUE:
    self.draw_fleet_view(entries)
```

- [ ] **Step 9: 更新 `handle_key` 中的 HITL 跳转逻辑**

HITL 列表现在从 `session_tracker.get_hitl_sessions()` 获取，跳转逻辑需要使用选中 session 的 `win_idx` 和 `session` 字段。修改 Enter 键处理：

```python
if key in (curses.KEY_ENTER, 10, 13):
    hitl = self.session_tracker.get_hitl_sessions()
    if hitl:
        idx = self.fleet_scroll % len(hitl)
        s = hitl[idx]
        session = s.session
        win_idx = s.win_idx
        # 复用现有的 jump_to_task 逻辑
        self.jump_to_task({"session": session, "win_idx": win_idx})
        self.status_msg = f"跳转 → {s.project or session}"
        self.status_clear_at = time.time() + 2
```

- [ ] **Step 10: 测试启动**

Run: `cd /home/wang/claude-tmux && timeout 3 python3 monitor.py 2>&1 || true`
Expected: 能看到新的左右分栏布局（即使没有 session，星图区域也应显示网格和"等待 session..."）

- [ ] **Step 11: Commit**

```bash
git add monitor.py
git commit -m "feat: monitor.py 集成左右分栏布局和全息星图视图"
```

---

## Task 5: 集成测试与修复

**Files:**
- May modify any file from Tasks 1-4

- [ ] **Step 1: 无 session 启动测试**

启动 monitor，确认：
- 星图区域显示空网格 + 流星
- 左面板显示 "✓ 所有会话运行正常"
- 宠物区域正常渲染
- 提示栏显示快捷键

- [ ] **Step 2: 模拟 HITL 事件测试**

```bash
bash notify.sh hitl "测试确认"
bash notify.sh working "Edit"
bash notify.sh task_complete
```

确认：
- 星图出现星星节点
- HITL 星星变红闪烁
- 左侧出现待处理条目
- 活动流显示事件

- [ ] **Step 3: Enter 跳转测试**

模拟事件后按 Enter，确认跳转逻辑正常。

- [ ] **Step 4: 主题切换测试**

按 T 切换主题，确认星图颜色跟随变化。

- [ ] **Step 5: 视图切换测试**

按 A/S 切换到成就/统计视图，确认原有视图不受影响。
按 ESC/再次按 A 返回星图视图。

- [ ] **Step 6: 修复发现的问题**

根据测试结果修复 bug。

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "fix: 集成测试修复"
```

---

## Task 6: 更新 hooks 配置文档

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: 更新 CLAUDE.md 中的 hooks 配置示例**

将原来的 2 个 hooks 扩展为设计文档中完整的 hooks 配置。

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: 更新 hooks 配置为全息星图完整事件集"
```
