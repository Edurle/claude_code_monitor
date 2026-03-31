#!/usr/bin/env bash
# setup.sh — 一键配置 Claude Code hooks + tmux monitor 窗口
# 在 WSL/Ubuntu 中运行一次即可

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NOTIFY="$SCRIPT_DIR/notify.sh"
MONITOR="$SCRIPT_DIR/monitor.py"
QUEUE_FILE="$HOME/.claude-tmux-queue.jsonl"
MONITOR_SESSION="monitor"

BOLD="\033[1m"; DIM="\033[2m"; GREEN="\033[32m"; YELLOW="\033[33m"; CYAN="\033[36m"; RESET="\033[0m"

step() { printf "${BOLD}${CYAN}▶ $*${RESET}\n"; }
ok()   { printf "  ${GREEN}✓ $*${RESET}\n"; }
warn() { printf "  ${YELLOW}⚠ $*${RESET}\n"; }

# ── 1. 赋予执行权限 ───────────────────────────────────────────────────────────
step "赋予脚本执行权限"
chmod +x "$NOTIFY" "$MONITOR"
ok "notify.sh  monitor.sh"

# ── 2. 写入全局 Claude Code hooks ─────────────────────────────────────────────
# [已注释] 以下代码会覆盖已有的 settings.json，如需自动配置请取消注释
# step "写入 Claude Code 全局 hooks 配置"
#
# SETTINGS_DIR="$HOME/.claude"
# SETTINGS_FILE="$SETTINGS_DIR/settings.json"
# mkdir -p "$SETTINGS_DIR"
#
# # 如果已有 settings.json，先备份
# if [[ -f "$SETTINGS_FILE" ]]; then
#     cp "$SETTINGS_FILE" "${SETTINGS_FILE}.bak.$(date +%Y%m%d%H%M%S)"
#     warn "已备份原配置到 ${SETTINGS_FILE}.bak.*"
# fi
#
# # 生成 hooks 配置（覆盖写入；如有其他自定义配置请手动合并）
# cat > "$SETTINGS_FILE" << EOF
# {
#   "hooks": {
#     "Stop": [
#       {
#         "matcher": "",
#         "hooks": [
#           {
#             "type": "command",
#             "command": "bash $(printf '%q' "$NOTIFY") task_complete \"\$(basename \$PWD)\""
#           }
#         ]
#       }
#     ],
#     "Notification": [
#       {
#         "matcher": "",
#         "hooks": [
#           {
#             "type": "command",
#             "command": "bash $(printf '%q' "$NOTIFY") hitl \"\$(basename \$PWD)\" \"\$CLAUDE_NOTIFICATION_MESSAGE\""
#           }
#         ]
#       }
#     ]
#   }
# }
# EOF
#
# ok "已写入 $SETTINGS_FILE"

# ── 3. 写入 shell 环境变量 ────────────────────────────────────────────────────

# 自动判断用哪个 rc 文件
if [[ "$SHELL" == */zsh ]]; then
    RC_FILE="$HOME/.zshrc"
else
    RC_FILE="$HOME/.bashrc"
fi
step "写入环境变量到 $RC_FILE"

MARKER="# claude-tmux-monitor"
if ! grep -q "$MARKER" "$RC_FILE" 2>/dev/null; then
    cat >> "$RC_FILE" << EOF

$MARKER
export CLAUDE_TMUX_QUEUE="$QUEUE_FILE"
export CLAUDE_TMUX_MONITOR_SESSION="$MONITOR_SESSION"
alias claude-monitor='tmux new-session -d -s "$MONITOR_SESSION" "python3 $MONITOR" 2>/dev/null || tmux attach -t "$MONITOR_SESSION"'
EOF
    ok "已追加到 $RC_FILE"
else
    warn "$RC_FILE 中已存在配置，跳过"
fi

# ── 4. 创建 tmux monitor 窗口（若已在 tmux 内）────────────────────────────────
step "尝试创建 tmux monitor 窗口"

if [[ -n "${TMUX:-}" ]]; then
    if tmux has-session -t "$MONITOR_SESSION" 2>/dev/null; then
        warn "monitor session '$MONITOR_SESSION' 已存在，跳过创建"
    else
        tmux new-session -d -s "$MONITOR_SESSION" "python3 $MONITOR"
        ok "已创建 tmux session: $MONITOR_SESSION（后台运行 monitor）"
    fi
else
    warn "当前不在 tmux 内，请手动运行: tmux new-session -s '$MONITOR_SESSION' 'bash $MONITOR'"
    warn "或 .bashrc 生效后执行别名: claude-monitor"
fi

# ── 5. 完成提示 ───────────────────────────────────────────────────────────────
printf "\n${BOLD}${GREEN}✅ 配置完成！${RESET}\n\n"
printf "使用说明:\n"
printf "  1. 重新加载环境: ${CYAN}source ${RC_FILE}${RESET}\n"
printf "  2. 启动 monitor:  ${CYAN}claude-monitor${RESET}\n"
printf "     （会创建名为 '${MONITOR_SESSION}' 的独立 tmux session）\n"
printf "  3. 为每个项目创建任务 session: ${CYAN}tmux new-session -s <项目名> -c <项目目录>${RESET}\n"
printf "     在其中运行 claude，HITL/完成时 monitor 自动收到通知\n"
printf "  4. 在 monitor 中按 ${CYAN}Enter${RESET} → switch-client 切到任务 session\n"
printf "     处理完后 ${CYAN}prefix + L${RESET}（或 switch-client -l）返回 monitor\n"
printf "  5. 按 ${CYAN}d${RESET} 丢弃当前条目，${CYAN}c${RESET} 清空队列\n"
printf "\n  队列文件: ${DIM}$QUEUE_FILE${RESET}\n"
# printf "  Hooks 配置: ${DIM}$SETTINGS_FILE${RESET}\n\n"
