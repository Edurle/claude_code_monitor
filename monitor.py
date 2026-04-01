#!/usr/bin/env python3
# monitor.py — Claude Code HITL 监控界面 (插件化版)
# 依赖: Python 3.6+ 标准库，无需额外安装
#
# 新功能:
# - 🔌 插件系统
# - 🎬 动画引擎（最高20fps）
# - ✨ 粒子效果
# - 🌈 动态主题引擎
# - 🏆 成就系统（插件）
# - 🐕 电子宠物助手（插件）

import curses
import json
import os
import subprocess
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any

# 导入自定义模块
from lib.theme import ThemeManager, Theme
from lib.stats import StatsManager

# 插件系统（可选导入）
try:
    from lib.plugins.manager import PluginManager
    from lib.plugins.core import PluginContext
    from lib.animation.engine import AnimationEngine, get_builtin_animations
    from lib.particles.system import ParticleSystem
    PLUGINS_AVAILABLE = True
except ImportError as e:
    import sys
    print(f"Plugin system unavailable: {e}", file=sys.stderr)
    PLUGINS_AVAILABLE = False
    PluginManager = None
    PluginContext = None
    AnimationEngine = None
    ParticleSystem = None

# 兼容旧模块（作为后备）
try:
    from lib.achievements import AchievementManager, Achievement
    from lib.pet import Pet, PetState
    LEGACY_MODULES = True
except ImportError:
    LEGACY_MODULES = False

# 配置
QUEUE_FILE = Path(os.environ.get("CLAUDE_TMUX_QUEUE", Path.home() / ".claude-tmux-queue.jsonl"))
MONITOR_SESSION = os.environ.get("CLAUDE_TMUX_MONITOR_SESSION", "monitor")
REFRESH = 1  # 秒

# 视图模式
VIEW_QUEUE = "queue"
VIEW_ACHIEVEMENTS = "achievements"
VIEW_STATS = "stats"


class HitlMonitor:
    """HITL 监控器主类"""

    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.status_msg = ""
        self.status_clear_at = 0

        # 视图状态
        self.current_view = VIEW_QUEUE
        self.achievement_scroll = 0

        # 队列
        self.last_queue_length = 0

        # 初始化核心模块
        self.theme_manager = ThemeManager()
        self.stats_manager = StatsManager()

        # 初始化插件系统
        self._init_plugins()

        # 初始化兼容模块（如果插件不可用）
        if not self._use_plugins and LEGACY_MODULES:
            self.achievement_manager = AchievementManager()
            self.pet = Pet(achievement_count=self.achievement_manager.unlocked_count)
        else:
            self.achievement_manager = None
            self.pet = None

        # 初始化 curses
        self._init_curses()

    def _init_plugins(self):
        """初始化插件系统"""
        self._use_plugins = False
        self.plugin_manager = None
        self.animation_engine = None
        self.particle_system = None

        if not PLUGINS_AVAILABLE or PluginManager is None:
            return

        try:
            # 路径设置
            base_dir = Path(__file__).parent
            plugin_dir = base_dir / "plugins"
            config_path = base_dir / "config" / "plugins.yaml"
            data_dir = base_dir / "data"

            # 创建核心组件
            if AnimationEngine is not None:
                self.animation_engine = AnimationEngine()
                # 注册内置动画
                for anim_id, anim in get_builtin_animations().items():
                    self.animation_engine.register_animation(anim)

            if ParticleSystem is not None:
                self.particle_system = ParticleSystem()

            # 创建插件管理器
            self.plugin_manager = PluginManager(plugin_dir, config_path)

            # 创建插件上下文
            if PluginContext is not None:
                context = PluginContext(
                    stdscr=None,  # 稍后设置
                    theme_manager=self.theme_manager,
                    data_dir=str(data_dir),
                    config={},
                    render_buffer=None,
                    animation_engine=self.animation_engine,
                    particle_system=self.particle_system,
                    monitor=self,
                )
                self.plugin_manager.set_context(context)

            # 加载配置并发现插件
            self.plugin_manager.load_config()
            discovered = self.plugin_manager.discover_plugins()

            # 加载并启动所有已启用的插件
            for plugin_id in discovered:
                self.plugin_manager.load_plugin(plugin_id)

            self.plugin_manager.start_all()
            self._use_plugins = True

        except Exception as e:
            # 插件系统初始化失败，使用兼容模式
            import sys
            print(f"Warning: Plugin system failed: {e}", file=sys.stderr)
            self._use_plugins = False

    def _trigger_hook(self, hook_name: str, *args, **kwargs):
        """触发钩子"""
        if self.plugin_manager:
            return self.plugin_manager.hook_registry.execute(hook_name, *args, **kwargs)
        return []

    def _trigger_hook_first(self, hook_name: str, *args, **kwargs):
        """触发钩子并返回第一个结果"""
        if self.plugin_manager:
            return self.plugin_manager.hook_registry.execute_first(hook_name, *args, **kwargs)
        return None
        """初始化 curses 设置"""
        curses.curs_set(0)
        curses.use_default_colors()
        self.stdscr.nodelay(True)
        self.stdscr.timeout(REFRESH * 1000)

        # 初始化主题颜色
        self._init_colors()

    def _init_colors(self):
        """初始化颜色"""
        self.theme_manager.init_curses_colors(self.stdscr)

        import curses

        # 预定义颜色对（兼容旧代码）
        curses.init_pair(1, curses.COLOR_CYAN, -1)
        curses.init_pair(2, curses.COLOR_YELLOW, -1)
        curses.init_pair(3, curses.COLOR_GREEN, -1)
        curses.init_pair(4, curses.COLOR_RED, -1)
        curses.init_pair(5, curses.COLOR_WHITE, -1)
        curses.init_pair(6, curses.COLOR_MAGENTA, -1)

        self.TYPE_COLOR = {
            "hitl": (curses.color_pair(2), "⚡"),
            "task_complete": (curses.color_pair(3), "✓"),
            "error": (curses.color_pair(4), "✗"),
        }

    def read_queue(self) -> List[dict]:
        """读取队列"""
        if not QUEUE_FILE.exists():
            return []

        entries = []
        with open(QUEUE_FILE) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

        # 按 session 去重
        session_map = {}
        for entry in entries:
            session = entry.get("session", "")
            if session:
                if session not in session_map or entry.get("ts", "") > session_map[session].get("ts", ""):
                    session_map[session] = entry

        return sorted(session_map.values(), key=lambda e: e.get("ts", ""), reverse=True)

    def pop_first(self):
        """弹出队首"""
        entries = self.read_queue()
        if not entries:
            return
        with open(QUEUE_FILE, "w") as f:
            for e in entries[1:]:
                f.write(json.dumps(e) + "\n")

    def clear_queue(self):
        """清空队列"""
        QUEUE_FILE.write_text("")

    def tmux(self, cmd: List[str]):
        """执行 tmux 命令"""
        try:
            subprocess.run(["tmux"] + cmd, capture_output=True)
        except Exception:
            pass

    def jump_to_task(self, entry: dict) -> Optional[str]:
        """跳转到任务"""
        session = entry.get("session", "")
        win_idx = entry.get("win_idx", "0")

        r = subprocess.run(["tmux", "has-session", "-t", session], capture_output=True)
        if r.returncode != 0:
            return f"Session '{session}' 不存在"

        self.tmux(["select-window", "-t", f"{session}:{win_idx}"])
        self.tmux(["switch-client", "-t", session])
        return None

    def addstr(self, row: int, col: int, text: str, attr=0):
        """安全添加字符串"""
        try:
            h, w = self.stdscr.getmaxyx()
            if row < h and col < w:
                self.stdscr.addstr(row, col, text[:w - col], attr)
        except curses.error:
            pass

    def draw_box(self, y: int, x: int, h: int, w: int, title: str = ""):
        """绘制边框"""
        chars = self.theme_manager.get_border_chars()
        tl, t, tr, r, br, b, bl, l = chars

        # 顶部
        self.addstr(y, x, tl + t * (w - 2) + tr)
        if title:
            title_text = f" {title} "
            self.addstr(y, x + 2, title_text)

        # 侧边
        for i in range(1, h - 1):
            self.addstr(y + i, x, l)
            self.addstr(y + i, x + w - 1, r)

        # 底部
        self.addstr(y + h - 1, x, bl + b * (w - 2) + br)

    def draw_queue_view(self, entries: List[dict]):
        """绘制队列视图"""
        h, w = self.stdscr.getmaxyx()
        row = 0

        import curses

        # 标题栏
        theme_name = self.theme_manager.current.name
        title = f" Claude Code · HITL Monitor · {theme_name} "
        self.addstr(row, 0, "─" * w, curses.color_pair(1))
        self.addstr(row, max(0, (w - len(title)) // 2), title, curses.color_pair(1) | curses.A_BOLD)
        row += 1

        count = len(entries)
        if count == 0:
            self.addstr(row + 1, 2, "暂无待处理事件，等待 Claude Code 触发...", curses.color_pair(5) | curses.A_DIM)
        else:
            self.addstr(row, 2, f"待处理: {count} 条", curses.color_pair(2) | curses.A_BOLD)
            row += 1

            for idx, entry in enumerate(entries):
                if row >= h - 10:  # 留出宠物和状态栏空间
                    self.addstr(row, 2, f"... 还有 {count - idx} 条", curses.A_DIM)
                    break

                ts = entry.get("ts", "")
                etype = entry.get("type", "")
                session = entry.get("session", "")
                win_name = entry.get("win_name", "")
                info = entry.get("info", "")
                wdir = entry.get("dir", "")

                color, icon = self.TYPE_COLOR.get(etype, (curses.color_pair(5), "•"))
                target = f"{session}:{win_name}" if win_name else session

                if idx == 0:
                    self.addstr(row, 0, "▶ ", curses.color_pair(2) | curses.A_BOLD)
                    self.addstr(row, 2, f"{icon} [{etype}]", color | curses.A_BOLD)
                    self.addstr(row, 2 + len(f"{icon} [{etype}]") + 1, target, curses.A_BOLD)
                    self.addstr(row, 2 + len(f"{icon} [{etype}]") + 1 + len(target) + 1, ts, curses.A_DIM)
                    row += 1
                    if wdir:
                        self.addstr(row, 4, wdir, curses.A_DIM)
                        row += 1
                    if info:
                        self.addstr(row, 4, info, curses.color_pair(6))
                        row += 1
                else:
                    self.addstr(row, 2, f"{icon} [{etype}]  {target}  {ts}", curses.A_DIM)
                    row += 1
                    if info:
                        self.addstr(row, 6, info, curses.A_DIM)
                        row += 1

        # 绘制宠物区域
        self._draw_pet_area(h - 8)

        # 状态消息
        if self.status_msg:
            self.addstr(h - 3, 2, self.status_msg, curses.color_pair(2))

        # 底部提示
        self.addstr(h - 2, 0, "─" * w, curses.A_DIM)
        hints = "[Enter]跳转 [d]丢弃 [c]清空 [T]主题 [A]成就 [S]统计 [P]摸宠物 [F]喂食 [q]退出"
        self.addstr(h - 1, 0, hints, curses.A_DIM)

    def _draw_pet_area(self, start_row: int):
        """绘制宠物区域"""
        import curses

        h, w = self.stdscr.getmaxyx()
        pet_width = 35

        # 宠物边框
        self.addstr(start_row, 2, "┌" + "─" * (pet_width - 2) + "┐", curses.A_DIM)

        # 宠物名称和进化形态
        evolution_name = self.pet.get_evolution_name()
        self.addstr(start_row, 4, f"🐕 {evolution_name}", curses.color_pair(6))

        # 宠物 ASCII 艺术
        art_lines = self.pet.get_art_lines()
        for i, line in enumerate(art_lines):
            self.addstr(start_row + 1 + i, 4, line)

        # 宠物心情文字
        mood_text = self.pet.update(len(self.read_queue()))
        mood_row = start_row + len(art_lines) + 1
        self.addstr(mood_row, 4, f'"{mood_text}"', curses.color_pair(5))

        # 底部边框
        end_row = mood_row + 1
        self.addstr(end_row, 2, "└" + "─" * (pet_width - 2) + "┘", curses.A_DIM)

        # 成就进度（右侧）
        unlocked = self.achievement_manager.unlocked_count
        total = self.achievement_manager.total_count
        progress_text = f"🏆 成就: {unlocked}/{total}"
        self.addstr(start_row, w - len(progress_text) - 3, progress_text, curses.color_pair(3))

        # 进化进度
        next_evo, current, needed = self.pet.get_next_evolution_progress(unlocked)
        if next_evo != "已满级":
            evo_text = f"进化: {next_evo} ({current}/{needed})"
            self.addstr(start_row + 1, w - len(evo_text) - 3, evo_text, curses.A_DIM)

    def draw_achievements_view(self):
        """绘制成就视图"""
        h, w = self.stdscr.getmaxyx()
        import curses

        # 标题
        title = " 🏆 成就系统 "
        self.addstr(0, 0, "═" * w, curses.color_pair(3))
        self.addstr(0, max(0, (w - len(title)) // 2), title, curses.color_pair(3) | curses.A_BOLD)

        # 成就列表
        all_achievements = self.achievement_manager.get_all()
        row = 2

        for i, (achievement, unlocked) in enumerate(all_achievements):
            if row >= h - 4:
                break

            prefix = "✓ " if unlocked else "○ "
            color = curses.color_pair(3) if unlocked else curses.A_DIM

            self.addstr(row, 2, f"{prefix}{achievement.icon} {achievement.name}", color | (curses.A_BOLD if unlocked else 0))
            row += 1
            self.addstr(row, 6, achievement.desc, curses.A_DIM)
            row += 2

        # 统计
        stats = self.achievement_manager.stats
        stats_row = h - 5
        self.addstr(stats_row, 2, "─" * 40, curses.A_DIM)
        self.addstr(stats_row + 1, 2, f"📊 统计: 总任务 {stats.total_tasks} | HITL {stats.hitl_count} | 错误 {stats.error_count}", curses.color_pair(5))
        self.addstr(stats_row + 2, 2, f"📅 连续 {stats.consecutive_days} 天 | 今日 {stats.tasks_today} 个任务", curses.color_pair(5))

        # 提示
        self.addstr(h - 1, 2, "[A/ESC] 返回队列", curses.A_DIM)

    def draw_stats_view(self):
        """绘制统计视图"""
        h, w = self.stdscr.getmaxyx()
        import curses

        # 标题
        title = " 📊 统计面板 "
        self.addstr(0, 0, "═" * w, curses.color_pair(6))
        self.addstr(0, max(0, (w - len(title)) // 2), title, curses.color_pair(6) | curses.A_BOLD)

        row = 2

        # 总体统计
        summary = self.stats_manager.get_summary()
        self.addstr(row, 2, "📈 总体统计", curses.color_pair(3) | curses.A_BOLD)
        row += 1
        self.addstr(row, 4, f"总任务数: {summary['total_tasks']}", curses.color_pair(5))
        row += 1
        self.addstr(row, 4, f"HITL 次数: {summary['total_hitl']}", curses.color_pair(5))
        row += 1
        self.addstr(row, 4, f"错误次数: {summary['total_errors']}", curses.color_pair(5))
        row += 1
        self.addstr(row, 4, f"活跃项目: {summary['total_projects']}", curses.color_pair(5))
        row += 1
        self.addstr(row, 4, f"日均任务: {summary['avg_tasks_per_day']:.1f}", curses.color_pair(5))
        row += 2

        # 周图表
        self.addstr(row, 2, "📅 本周任务", curses.color_pair(3) | curses.A_BOLD)
        row += 1
        week_chart = self.stats_manager.get_week_chart(width=30)
        for line in week_chart.split("\n"):
            self.addstr(row, 4, line, curses.color_pair(5))
            row += 1

        row += 1

        # 活跃项目
        self.addstr(row, 2, "🔥 活跃项目 TOP 5", curses.color_pair(3) | curses.A_BOLD)
        row += 1
        for project, stats in self.stats_manager.get_top_projects(5):
            self.addstr(row, 4, f"• {project}: {stats['total']} 个任务", curses.color_pair(5))
            row += 1

        # 提示
        self.addstr(h - 1, 2, "[S/ESC] 返回队列", curses.A_DIM)

    def show_achievement_unlocked(self, achievement: Achievement):
        """显示成就解锁动画"""
        import curses

        h, w = self.stdscr.getmaxyx()

        # 动画框
        box_h, box_w = 7, 44
        box_y = (h - box_h) // 2
        box_x = (w - box_w) // 2

        # 清除区域
        for i in range(box_h):
            self.addstr(box_y + i, box_x, " " * box_w)

        # 绘制边框
        self.draw_box(box_y, box_x, box_h, box_w)

        # 内容
        self.addstr(box_y + 1, box_x + 2, " " * (box_w - 4), curses.A_REVERSE)
        self.addstr(box_y + 1, box_x + (box_w - 26) // 2, "🎉  ACHIEVEMENT UNLOCKED!  🎉", curses.A_REVERSE | curses.A_BOLD)

        self.addstr(box_y + 3, box_x + (box_w - len(achievement.icon) * 2 - len(achievement.name) - 3) // 2,
                    f"{achievement.icon} {achievement.name} {achievement.icon}", curses.color_pair(3) | curses.A_BOLD)

        self.addstr(box_y + 5, box_x + (box_w - len(achievement.desc) - 2) // 2,
                    f'"{achievement.desc}"', curses.color_pair(5))

        self.stdscr.refresh()
        time.sleep(2)  # 显示2秒

    def handle_key(self, key: int, entries: List[dict]) -> bool:
        """处理按键，返回是否继续运行"""
        # 清除过期状态
        if self.status_msg and time.time() > self.status_clear_at:
            self.status_msg = ""

        import curses

        # 全局快捷键
        if key == ord("q") or key == ord("Q"):
            return False

        # 视图切换
        if key == ord("a") or key == ord("A"):
            if self.current_view == VIEW_ACHIEVEMENTS:
                self.current_view = VIEW_QUEUE
            else:
                self.current_view = VIEW_ACHIEVEMENTS
            return True

        if key == ord("s") or key == ord("S"):
            if self.current_view == VIEW_STATS:
                self.current_view = VIEW_QUEUE
            else:
                self.current_view = VIEW_STATS
            return True

        if key == 27:  # ESC
            self.current_view = VIEW_QUEUE
            return True

        # 主题切换
        if key == ord("t") or key == ord("T"):
            new_theme = self.theme_manager.switch()
            self._init_colors()
            self.status_msg = f"主题切换: {self.theme_manager.current.name}"
            self.status_clear_at = time.time() + 2
            return True

        # 宠物互动
        if key == ord("p") or key == ord("P"):
            response = self.pet.on_pet()
            self.status_msg = f"宠物说: {response}"
            self.status_clear_at = time.time() + 2
            return True

        if key == ord("f") or key == ord("F"):
            response = self.pet.on_feed()
            self.status_msg = f"宠物说: {response}"
            self.status_clear_at = time.time() + 2
            return True

        # 队列操作（仅在队列视图）
        if self.current_view != VIEW_QUEUE:
            return True

        if key in (curses.KEY_ENTER, 10, 13):  # Enter
            if entries:
                err = self.jump_to_task(entries[0])
                if err:
                    self.status_msg = err
                    self.status_clear_at = time.time() + 3
                else:
                    entry = entries[0]
                    self.pop_first()

                    # 记录事件
                    event_type = entry.get("type", "hitl")
                    project = entry.get("project", "")
                    self.achievement_manager.record_task(event_type, project)
                    self.stats_manager.record_event(event_type, project)

                    # 检查成就
                    newly_unlocked = self.achievement_manager.check_achievements()
                    if newly_unlocked:
                        from lib.achievements import ACHIEVEMENTS
                        for aid in newly_unlocked:
                            self.show_achievement_unlocked(ACHIEVEMENTS[aid])
                        # 更新宠物进化
                        self.pet.update_evolution(self.achievement_manager.unlocked_count)

                    self.pet.on_task_complete()
                    self.status_msg = "已跳转并处理任务"
                    self.status_clear_at = time.time() + 2

        elif key == ord("d") or key == ord("D"):
            if entries:
                self.pop_first()
                self.pet.on_task_discard()
                self.status_msg = "已丢弃队首条目"
                self.status_clear_at = time.time() + 2

        elif key == ord("c") or key == ord("C"):
            self.clear_queue()
            self.pet.on_queue_clear()
            self.status_msg = "队列已清空"
            self.status_clear_at = time.time() + 2

        return True

    def run(self):
        """主循环"""
        QUEUE_FILE.touch(exist_ok=True)

        while True:
            entries = self.read_queue()

            # 检测队列变化
            current_length = len(entries)
            if current_length > self.last_queue_length:
                self.pet.on_new_task()
            self.last_queue_length = current_length

            # 更新活跃项目数
            projects = set(e.get("project", "") for e in entries if e.get("project"))
            self.achievement_manager.set_active_projects(len(projects))

            # 绘制
            self.stdscr.erase()
            if self.current_view == VIEW_QUEUE:
                self.draw_queue_view(entries)
            elif self.current_view == VIEW_ACHIEVEMENTS:
                self.draw_achievements_view()
            elif self.current_view == VIEW_STATS:
                self.draw_stats_view()
            self.stdscr.refresh()

            # 处理按键
            key = self.stdscr.getch()
            if not self.handle_key(key, entries):
                break


def main():
    """入口函数"""
    def run_wrapper(stdscr):
        monitor = HitlMonitor(stdscr)
        monitor.run()

    curses.wrapper(run_wrapper)


if __name__ == "__main__":
    main()
