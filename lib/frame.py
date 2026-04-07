"""Frame -- 插件化监控器主循环。"""
import curses
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from lib.eventbus import EventBus
from lib.layout import LayoutEngine, Region, Rect, Slot
from lib.plugins.manager import PluginManager
from lib.theme import ThemeManager
from lib.database import Database
from lib.stats import StatsManager
from lib.session_tracker import SessionTracker
from lib.particles.system import ParticleSystem

QUEUE_FILE = Path(os.environ.get("CLAUDE_TMUX_QUEUE", Path.home() / ".claude-tmux-queue.jsonl"))
MARGIN = 2


class QueueManager:
    """Concrete IQueueManager -- reads/writes JSONL queue file."""

    def __init__(self, queue_file: Path):
        self._path = queue_file

    def read(self) -> List[dict]:
        if not self._path.exists():
            return []
        entries = []
        with open(self._path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        # 按 session 去重 (保留最新)
        session_map = {}
        for entry in entries:
            session = entry.get("session", "")
            if session:
                if session not in session_map or entry.get("ts", "") > session_map[session].get("ts", ""):
                    session_map[session] = entry
        return sorted(session_map.values(), key=lambda e: e.get("ts", ""), reverse=True)

    def remove(self, entry: dict) -> None:
        entries = self.read()
        if not entries:
            return
        session = entry.get("session", "")
        with open(self._path, "w") as f:
            for e in entries:
                if e.get("session", "") == session:
                    continue
                f.write(json.dumps(e) + "\n")

    def clear(self) -> None:
        self._path.write_text("")


class Frame:
    """插件化监控器主循环 -- 布局、渲染、事件分发。"""

    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.frame_count = 0

        # ── 核心服务 ──
        self.db = Database.get_instance()
        self.theme = ThemeManager()
        self.stats = StatsManager(self.db)
        self.sessions = SessionTracker()
        self.particles = ParticleSystem()
        self.events = EventBus()
        self.queue = QueueManager(QUEUE_FILE)
        self.layout_engine = LayoutEngine()

        # ── curses 初始化 ──
        curses.curs_set(0)
        curses.use_default_colors()
        self.stdscr.nodelay(True)
        self.stdscr.timeout(1000)  # 1s refresh
        self.theme.init_curses_colors(self.stdscr)
        # 初始化基本颜色对
        curses.init_pair(1, curses.COLOR_CYAN, -1)
        curses.init_pair(2, curses.COLOR_YELLOW, -1)
        curses.init_pair(3, curses.COLOR_GREEN, -1)
        curses.init_pair(4, curses.COLOR_RED, -1)
        curses.init_pair(5, curses.COLOR_WHITE, -1)
        curses.init_pair(6, curses.COLOR_MAGENTA, -1)

        # ── 插件系统 ──
        base_dir = Path(__file__).parent.parent
        plugin_dir = base_dir / "plugins"
        config_path = base_dir / "config" / "plugins.yaml"
        data_dir = base_dir / "data"

        from lib.plugins.core import PluginContext
        ctx = PluginContext(
            theme=self.theme,
            db=self.db,
            particles=self.particles,
            sessions=self.sessions,
            stats=self.stats,
            queue=self.queue,
            events=self.events,
            config={},
            data_dir=str(data_dir),
        )

        self.plugin_manager = PluginManager(plugin_dir, config_path)
        self.plugin_manager.set_context(ctx)
        ctx.plugin_manager = self.plugin_manager

        try:
            self.plugin_manager.load_config()
            discovered = self.plugin_manager.discover_plugins()
            for pid in discovered:
                self.plugin_manager.load_plugin(pid)
            self.plugin_manager.start_all()
        except Exception as e:
            import sys
            print(f"[Frame] Plugin system error: {e}", file=sys.stderr)

        self._prev_entry_count = 0

    # ── 渲染基础设施 ──

    def blit(self, cells: list, offset: Tuple[int, int] = (0, 0)):
        """批量写入 curses，带边界裁剪。cells: [(row, col, text, attr), ...]"""
        h, w = self.stdscr.getmaxyx()
        for row, col, text, attr in cells:
            r, c = row + offset[0], col + offset[1]
            if 0 <= r < h and 0 <= c < w:
                try:
                    self.stdscr.addstr(r, c, text[:w - c], attr or 0)
                except curses.error:
                    pass

    def _draw_separators(self, layout: Dict[str, Rect], h: int, w: int):
        """绘制区域间分隔线"""
        # 找到 left_w（从 LEFT 区域或默认）
        left_w = max(30, w * 2 // 5)
        # 垂直分隔线
        content_start = 1
        content_end = h - 3
        for r in range(content_start, content_end):
            try:
                self.stdscr.addstr(r, left_w, "|", curses.A_DIM)
            except curses.error:
                pass
        # 水平分隔线（右侧上下之间）
        for rid, r in layout.items():
            if r.col == left_w + 1 and r.row == content_start:
                gap_row = r.row + r.height
                try:
                    self.stdscr.addstr(gap_row, left_w + 1, "─" * r.width, curses.A_DIM)
                except curses.error:
                    pass
                break

    # ── 收集 Region 声明 ──

    def collect_regions(self) -> list:
        """遍历所有活跃插件收集 Region 声明"""
        regions = []
        for plugin in self.plugin_manager.sorted_plugins():
            try:
                regions.extend(plugin.declare_regions())
            except Exception:
                pass
        return regions

    # ── 按键分发 ──

    def dispatch_key(self, key: int, entries: list) -> bool:
        """按插件优先级分发按键。返回 False 表示应退出。"""
        if key in (ord('q'), ord('Q')):
            return False
        context = {"entries": entries}
        for plugin in self.plugin_manager.sorted_plugins():
            try:
                if plugin.handle_key(key, context):
                    break
            except Exception:
                pass
        return True

    # ── 主循环 ──

    def run(self):
        QUEUE_FILE.touch(exist_ok=True)

        while True:
            entries = self.queue.read()
            h, w = self.stdscr.getmaxyx()
            eff_h, eff_w = max(h - 2 * MARGIN, 10), max(w - 2 * MARGIN, 20)

            # 增量检测
            current_count = len(entries)
            data = {"entries": entries, "frame": self.frame_count}

            if current_count > self._prev_entry_count:
                self.events.emit("queue_changed", {"entries": entries, "added_count": current_count - self._prev_entry_count})
            self.events.emit("queue_update", data)
            self._prev_entry_count = current_count

            # 更新核心服务
            for entry in entries:
                self.sessions.process_event(entry)
            self.sessions.tick()
            self.particles.update()

            # 布局计算
            regions = self.collect_regions()
            layout = self.layout_engine.compute(regions, h, w)

            # 渲染
            self.stdscr.erase()

            plugins = self.plugin_manager.sorted_plugins()

            # 1. 检查 fullscreen
            fullscreen_cells = []
            for p in plugins:
                try:
                    cells = p.render_fullscreen(h, w, data)
                    if cells:
                        fullscreen_cells = cells
                        break
                except Exception as e:
                    print(f"[Frame] fullscreen render error ({p.info.id}): {e}", file=sys.stderr)

            if fullscreen_cells:
                self.blit(fullscreen_cells)
            else:
                # 2. Region 渲染
                for p in plugins:
                    try:
                        for region in p.declare_regions():
                            rect = layout.get(region.id)
                            if rect is None:
                                continue
                            cells = p.render_region(region.id, rect, data)
                            self.blit(cells, offset=(rect.row, rect.col))
                    except Exception as e:
                        print(f"[Frame] region render error ({p.info.id}): {e}", file=sys.stderr)

                # 3. 分隔线
                self._draw_separators(layout, h, w)

                # 4. Overlay 渲染
                for p in plugins:
                    try:
                        cells = p.render_overlay(h, w, data)
                        if cells:
                            self.blit(cells)
                    except Exception:
                        pass

            self.stdscr.refresh()

            # 输入处理
            key = self.stdscr.getch()
            if key != -1:
                if not self.dispatch_key(key, entries):
                    break

            self.frame_count += 1
