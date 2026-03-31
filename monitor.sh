#!/usr/bin/env bash
# monitor.sh — 在 tmux 专用窗口中运行，实时显示待处理队列
# 启动: bash monitor.sh
# 操作:
#   Enter  — 跳转到队首任务所在目录的 tmux 窗口（自动创建若不存在）
#   d      — 丢弃（dismiss）队首条目，标记为已处理
#   c      — 清空全部队列
#   q      — 退出 monitor（不清空队列）

set -euo pipefail

QUEUE_FILE="${CLAUDE_TMUX_QUEUE:-$HOME/.claude-tmux-queue.jsonl}"
MONITOR_SESSION="${CLAUDE_TMUX_MONITOR_SESSION:-monitor}"
REFRESH_INTERVAL=1   # 秒，轮询间隔

# 颜色（终端 ANSI）
BOLD="\033[1m"
DIM="\033[2m"
RED="\033[31m"
YELLOW="\033[33m"
GREEN="\033[32m"
CYAN="\033[36m"
MAGENTA="\033[35m"
RESET="\033[0m"
CLEAR_SCREEN="\033[2J\033[H"

# 工具函数 ─────────────────────────────────────────────────────────────────────

parse_field() {
    # 极简 JSON 字段提取（不依赖 jq）
    local json="$1" field="$2"
    echo "$json" | grep -o "\"${field}\":\"[^\"]*\"" | head -1 \
        | sed 's/.*":"\(.*\)"/\1/'
}

count_queue() {
    [[ -f "$QUEUE_FILE" ]] && wc -l < "$QUEUE_FILE" | tr -d ' ' || echo 0
}

read_queue() {
    [[ -f "$QUEUE_FILE" ]] && cat "$QUEUE_FILE" || true
}

pop_first() {
    # 移除队列首行
    [[ -f "$QUEUE_FILE" ]] || return
    local tmp
    tmp=$(mktemp)
    tail -n +2 "$QUEUE_FILE" > "$tmp"
    mv "$tmp" "$QUEUE_FILE"
}

clear_queue() {
    > "$QUEUE_FILE" 2>/dev/null || true
}

# 跳转到任务 session 的具体 window ───────────────────────────────────────────

jump_to_task() {
    local entry="$1"
    local task_session win_idx win_name
    task_session=$(parse_field "$entry" "session")
    win_idx=$(parse_field "$entry" "win_idx")
    win_name=$(parse_field "$entry" "win_name")

    if ! tmux has-session -t "$task_session" 2>/dev/null; then
        tmux display-message -t "$MONITOR_SESSION" \
            "Session '$task_session' 不存在，已跳过" 2>/dev/null || true
        return
    fi

    # 先切到目标 session，再选中具体 window
    # select-window 在 switch-client 之前执行，避免视角切换时闪烁
    tmux select-window -t "${task_session}:${win_idx}" 2>/dev/null \
        || tmux select-window -t "${task_session}:${win_name}" 2>/dev/null \
        || true
    tmux switch-client -t "$task_session"
}

# 渲染界面 ─────────────────────────────────────────────────────────────────────

render() {
    printf "%b" "$CLEAR_SCREEN"
    local count
    count=$(count_queue)

    # 标题栏
    printf "${BOLD}${CYAN}╔══════════════════════════════════════════════════════╗${RESET}\n"
    printf "${BOLD}${CYAN}║     Claude Code · HITL Monitor                      ║${RESET}\n"
    printf "${BOLD}${CYAN}╚══════════════════════════════════════════════════════╝${RESET}\n"
    printf "\n"

    if [[ "$count" -eq 0 ]]; then
        printf "  ${DIM}暂无待处理事件。等待 Claude Code 触发...${RESET}\n"
    else
        printf "  ${BOLD}待处理: ${YELLOW}${count} 条${RESET}\n\n"

        local idx=0
        while IFS= read -r line; do
            [[ -z "$line" ]] && continue
            local ts type session win_name info dir
            ts=$(parse_field "$line" "ts")
            type=$(parse_field "$line" "type")
            session=$(parse_field "$line" "session")
            win_name=$(parse_field "$line" "win_name")
            info=$(parse_field "$line" "info")
            dir=$(parse_field "$line" "dir")

            # 类型颜色
            local type_color="$RESET"
            local icon="•"
            case "$type" in
                hitl)          type_color="$YELLOW";  icon="⚡" ;;
                task_complete) type_color="$GREEN";   icon="✓" ;;
                error)         type_color="$RED";     icon="✗" ;;
            esac

            # 显示 session:window
            local target="${session}"
            [[ -n "$win_name" ]] && target="${session}:${win_name}"

            if [[ "$idx" -eq 0 ]]; then
                printf "  ${BOLD}▶ ${type_color}${icon} [${type}]${RESET}  ${BOLD}${target}${RESET}  ${DIM}${ts}${RESET}\n"
                printf "    ${DIM}${dir}${RESET}\n"
                [[ -n "$info" ]] && printf "    ${MAGENTA}${info}${RESET}\n"
            else
                printf "  ${DIM}  ${icon} [${type}]  ${target}  ${ts}${RESET}\n"
                [[ -n "$info" ]] && printf "    ${DIM}${info}${RESET}\n"
            fi

            idx=$((idx + 1))
            # 最多显示 10 条
            [[ "$idx" -ge 10 ]] && printf "  ${DIM}... 还有 $((count - 10)) 条${RESET}\n" && break
        done < <(read_queue)
    fi

    # 操作提示
    printf "\n"
    printf "  ${DIM}─────────────────────────────────────────────────────${RESET}\n"
    printf "  ${BOLD}Enter${RESET}${DIM} 跳转处理队首   ${BOLD}d${RESET}${DIM} 丢弃队首   ${BOLD}c${RESET}${DIM} 清空   ${BOLD}q${RESET}${DIM} 退出${RESET}\n"
    printf "  ${DIM}队列文件: ${QUEUE_FILE}${RESET}\n"
    printf "  ${DIM}刷新间隔: ${REFRESH_INTERVAL}s  —  $(date +%H:%M:%S)${RESET}\n"
}

# 主循环 ───────────────────────────────────────────────────────────────────────

# 确保队列文件存在
touch "$QUEUE_FILE"

# 关闭终端 echo，设置 raw 输入
old_stty=$(stty -g)
trap 'stty "$old_stty"; printf "%b" "\033[?25h\n"; exit 0' EXIT INT TERM

stty -echo -icanon min 0 time 0
printf "\033[?25l"  # 隐藏光标

last_render=""

while true; do
    # 非阻塞读取按键
    key=""
    IFS= read -r -n1 key 2>/dev/null || true

    # 处理特殊按键
    if [[ "$key" == $'\n' ]] || [[ "$key" == $'\r' ]]; then
        # Enter: 跳转队首
        if [[ $(count_queue) -gt 0 ]]; then
            local_entry=$(head -1 "$QUEUE_FILE")
            jump_to_task "$local_entry"
            pop_first
        fi
    elif [[ "$key" == "d" ]] || [[ "$key" == "D" ]]; then
        pop_first
    elif [[ "$key" == "c" ]] || [[ "$key" == "C" ]]; then
        clear_queue
    elif [[ "$key" == "q" ]] || [[ "$key" == "Q" ]]; then
        break
    fi

    # 检查内容是否变化，变化时重新渲染
    current_state="$(count_queue)-$(date +%S)"
    if [[ "$current_state" != "$last_render" ]]; then
        render
        last_render="$current_state"
    fi

    sleep "$REFRESH_INTERVAL"
done

printf "%b" "\033[?25h"
printf "\n${DIM}Monitor 已退出。${RESET}\n"
