#!/usr/bin/env bash
# notify.sh — Claude Code hook 调用此脚本
# 用法: notify.sh <event_type> [extra_info]
#   event_type: hitl | task_complete | error
#   extra_info: 可选，附加说明（如 $CLAUDE_NOTIFICATION_MESSAGE）
#
# 自动记录当前 tmux session 名、window index、window 名，供 monitor 精确跳转

set -euo pipefail

EVENT_TYPE="${1:-hitl}"
EXTRA_INFO="${2:-}"

QUEUE_FILE="${CLAUDE_TMUX_QUEUE:-$HOME/.claude-tmux-queue.jsonl}"
MONITOR_SESSION="${CLAUDE_TMUX_MONITOR_SESSION:-monitor}"

TIMESTAMP=$(date +"%H:%M:%S")
WORK_DIR="$(pwd)"
PROJECT="$(basename "$WORK_DIR")"

# 获取当前 tmux session 名、window index、window 名
if [[ -n "${TMUX:-}" ]]; then
    TASK_SESSION=$(tmux display-message -p "#{session_name}"  2>/dev/null || echo "$PROJECT")
    TASK_WIN_IDX=$(tmux display-message -p "#{window_index}"  2>/dev/null || echo "0")
    TASK_WIN_NAME=$(tmux display-message -p "#{window_name}"  2>/dev/null || echo "")
else
    TASK_SESSION="$PROJECT"
    TASK_WIN_IDX="0"
    TASK_WIN_NAME=""
fi

# ── 写入队列 ─────────────────────────────────────────────────────────────────
_esc() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }

ENTRY="{\"ts\":\"$(_esc "$TIMESTAMP")\",\"type\":\"$(_esc "$EVENT_TYPE")\",\"session\":\"$(_esc "$TASK_SESSION")\",\"win_idx\":\"$(_esc "$TASK_WIN_IDX")\",\"win_name\":\"$(_esc "$TASK_WIN_NAME")\",\"project\":\"$(_esc "$PROJECT")\",\"dir\":\"$(_esc "$WORK_DIR")\",\"info\":\"$(_esc "$EXTRA_INFO")\"}"

echo "$ENTRY" >> "$QUEUE_FILE"

# ── 通知 monitor session ──────────────────────────────────────────────────────
if command -v tmux &>/dev/null; then
    PENDING=$(wc -l < "$QUEUE_FILE" | tr -d ' ')
    tmux send-keys -t "${MONITOR_SESSION}" "" 2>/dev/null || true
    tmux display-message -t "${MONITOR_SESSION}" \
        "[Claude] ${EVENT_TYPE} · ${TASK_SESSION}:${TASK_WIN_NAME} · ${PENDING} pending" 2>/dev/null || true
fi

exit 0
