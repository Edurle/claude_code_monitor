#!/usr/bin/env python3
# monitor.py — Claude Code HITL 监控界面
# 依赖: Python 3.6+ 标准库，无需额外安装

import curses
import json
import os
import subprocess
import time
from pathlib import Path

QUEUE_FILE = Path(os.environ.get("CLAUDE_TMUX_QUEUE", Path.home() / ".claude-tmux-queue.jsonl"))
MONITOR_SESSION = os.environ.get("CLAUDE_TMUX_MONITOR_SESSION", "monitor")
REFRESH = 1  # 秒


def read_queue():
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

    # 按 session 去重，只保留最新的一条
    session_map = {}
    for entry in entries:
        session = entry.get("session", "")
        if session:
            # 如果该 session 还没有记录，或者当前条目时间更新
            if session not in session_map or entry.get("ts", "") > session_map[session].get("ts", ""):
                session_map[session] = entry

    # 按时间降序排列（最新的在前）
    return sorted(session_map.values(), key=lambda e: e.get("ts", ""), reverse=True)


def pop_first():
    entries = read_queue()
    if not entries:
        return
    with open(QUEUE_FILE, "w") as f:
        for e in entries[1:]:
            f.write(json.dumps(e) + "\n")


def clear_queue():
    QUEUE_FILE.write_text("")


def tmux(cmd):
    try:
        subprocess.run(["tmux"] + cmd, capture_output=True)
    except Exception:
        pass


def jump_to_task(entry):
    session = entry.get("session", "")
    win_idx = entry.get("win_idx", "0")
    win_name = entry.get("win_name", "")

    # 检查 session 是否存在
    r = subprocess.run(["tmux", "has-session", "-t", session], capture_output=True)
    if r.returncode != 0:
        return f"Session '{session}' 不存在"

    # 先选中对应 window，再 switch-client
    tmux(["select-window", "-t", f"{session}:{win_idx}"])
    tmux(["switch-client", "-t", session])
    return None


def draw(stdscr, entries, status_msg):
    stdscr.erase()
    h, w = stdscr.getmaxyx()

    # 颜色对
    curses.init_pair(1, curses.COLOR_CYAN,    -1)  # 标题
    curses.init_pair(2, curses.COLOR_YELLOW,  -1)  # hitl / 警告
    curses.init_pair(3, curses.COLOR_GREEN,   -1)  # task_complete
    curses.init_pair(4, curses.COLOR_RED,     -1)  # error
    curses.init_pair(5, curses.COLOR_WHITE,   -1)  # 普通
    curses.init_pair(6, curses.COLOR_MAGENTA, -1)  # info

    TYPE_COLOR = {
        "hitl":          (curses.color_pair(2), "⚡"),
        "task_complete": (curses.color_pair(3), "✓ "),
        "error":         (curses.color_pair(4), "✗ "),
    }

    row = 0

    def addstr(r, c, text, attr=0):
        try:
            stdscr.addstr(r, c, text[:w - c], attr)
        except curses.error:
            pass

    # ── 标题 ──
    title = " Claude Code · HITL Monitor "
    addstr(row, 0, "─" * w, curses.color_pair(1))
    addstr(row, max(0, (w - len(title)) // 2), title, curses.color_pair(1) | curses.A_BOLD)
    row += 1

    count = len(entries)
    if count == 0:
        addstr(row + 1, 2, "暂无待处理事件，等待 Claude Code 触发...", curses.color_pair(5) | curses.A_DIM)
    else:
        addstr(row, 2, f"待处理: {count} 条", curses.color_pair(2) | curses.A_BOLD)
        row += 1

        for idx, entry in enumerate(entries):
            if row >= h - 4:
                addstr(row, 2, f"... 还有 {count - idx} 条", curses.A_DIM)
                row += 1
                break

            ts       = entry.get("ts", "")
            etype    = entry.get("type", "")
            session  = entry.get("session", "")
            win_name = entry.get("win_name", "")
            info     = entry.get("info", "")
            wdir     = entry.get("dir", "")

            color, icon = TYPE_COLOR.get(etype, (curses.color_pair(5), "• "))
            target = f"{session}:{win_name}" if win_name else session

            if idx == 0:
                # 队首高亮
                addstr(row, 0, "▶ ", curses.color_pair(2) | curses.A_BOLD)
                addstr(row, 2, f"{icon} [{etype}]", color | curses.A_BOLD)
                addstr(row, 2 + len(f"{icon} [{etype}]") + 1, target, curses.A_BOLD)
                addstr(row, 2 + len(f"{icon} [{etype}]") + 1 + len(target) + 1, ts, curses.A_DIM)
                row += 1
                if wdir:
                    addstr(row, 4, wdir, curses.A_DIM)
                    row += 1
                if info:
                    addstr(row, 4, info, curses.color_pair(6))
                    row += 1
            else:
                addstr(row, 2, f"{icon} [{etype}]  {target}  {ts}", curses.A_DIM)
                row += 1
                if info:
                    addstr(row, 6, info, curses.A_DIM)
                    row += 1

            row += 0  # 条目间距（不加空行，紧凑）

    # ── 状态消息 ──
    if status_msg:
        addstr(h - 3, 2, status_msg, curses.color_pair(2))

    # ── 底部操作提示 ──
    addstr(h - 2, 0, "─" * w, curses.A_DIM)
    hint = " Enter 跳转处理  d 丢弃队首  c 清空  q 退出  " + time.strftime("%H:%M:%S")
    addstr(h - 1, 0, hint, curses.A_DIM)

    stdscr.refresh()


def main(stdscr):
    curses.curs_set(0)
    curses.use_default_colors()
    stdscr.nodelay(True)  # 非阻塞读键
    stdscr.timeout(REFRESH * 1000)

    QUEUE_FILE.touch(exist_ok=True)

    status_msg = ""
    status_clear_at = 0

    while True:
        entries = read_queue()

        # 清除过期状态消息
        if status_msg and time.time() > status_clear_at:
            status_msg = ""

        draw(stdscr, entries, status_msg)

        key = stdscr.getch()

        if key == ord("q") or key == ord("Q"):
            break

        elif key in (curses.KEY_ENTER, 10, 13):  # Enter
            if entries:
                err = jump_to_task(entries[0])
                if err:
                    status_msg = err
                    status_clear_at = time.time() + 3
                else:
                    pop_first()

        elif key == ord("d") or key == ord("D"):
            if entries:
                pop_first()
                status_msg = "已丢弃队首条目"
                status_clear_at = time.time() + 2

        elif key == ord("c") or key == ord("C"):
            clear_queue()
            status_msg = "队列已清空"
            status_clear_at = time.time() + 2


def run():
    curses.wrapper(main)


if __name__ == "__main__":
    run()
