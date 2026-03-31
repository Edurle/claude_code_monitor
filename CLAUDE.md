# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

```
 ██╗ ██████╗ ██████╗ ███████╗    ██╗ ██████╗███████╗
 ██║██╔════╝██╔══██╗██╔════╝    ██║██╔════╝╚════██║
 ██║██║     ██║  ██║█████╗      ██║██║        ██║
 ██║██║     ██║  ██║██╔══╝██,   ██║██║        ██║
 ██║╚██████╗██████╔╝███████╗    ██║╚██████╗   ██║
 ╚═╝ ╚═════╝╚═════╝ ╚══════╝    ╚═╝ ╚═════╝   ╚═╝
        Claude Code × tmux HITL Monitor
```

## 项目概述

Claude Code × tmux HITL 监控器 — 在 tmux 环境中管理 Claude Code 事件的队列系统。当 Claude 触发 HITL（需要人工介入）或任务完成事件时，自动排队并在专用监控窗口显示，支持逐一跳转处理。

## 快速开始

```bash
bash setup.sh && source ~/.bashrc
claude-monitor  # 🚀 启动监控器
```

## 常用命令

| 命令 | 说明 |
|------|------|
| `claude-monitor` | 启动/附加到监控 session（setup.sh 添加的别名） |
| `bash notify.sh hitl "说明文字"` | 手动触发 HITL 事件 |
| `bash notify.sh task_complete` | 手动触发任务完成事件 |
| `cat ~/.claude-tmux-queue.jsonl` | 查看队列内容 |

## 环境变量

| 变量 | 默认值 | 用途 |
|------|--------|------|
| `CLAUDE_TMUX_QUEUE` | `~/.claude-tmux-queue.jsonl` | 队列文件路径 |
| `CLAUDE_TMUX_MONITOR_SESSION` | `monitor` | 监控器 tmux session 名称 |

## 监控器操作

| 按键 | 动作 |
|------|------|
| `Enter` | 跳转到队首任务所在的 tmux 窗口 |
| `d` | 丢弃队首条目 |
| `c` | 清空全部队列 |
| `q` | 退出监控器（队列保留） |

## Hook 集成

在 `~/.claude/settings.json` 中配置 hooks 以自动触发通知：

```json
{
  "hooks": {
    "Stop": [{ "matcher": "", "hooks": [{ "type": "command", "command": "bash ~/claude-tmux/notify.sh task_complete" }] }],
    "Notification": [{ "matcher": "", "hooks": [{ "type": "command", "command": "bash ~/claude-tmux/notify.sh hitl \"$CLAUDE_NOTIFICATION_MESSAGE\"" }] }]
  }
}
```

## 高级用法

### 多项目管理

```bash
# 为每个项目创建独立 session
tmux new-session -s project-alpha -c /path/to/alpha
tmux new-session -s project-beta -c /path/to/beta

# 在各 session 中运行 Claude Code
# HITL 事件会自动按 session 分组排队
```

### 快速切换工作流

```bash
# 从 monitor 跳转到任务 → 处理 → 返回 monitor
# 1. Enter: 跳转到队首任务
# 2. 处理完毕
# 3. prefix + L (或 tmux switch-client -l) 返回 monitor
```

## 常用中文用语

在交流时请使用以下中文表达：

| 场景 | 表达 |
|------|------|
| 确认理解 | "好的，我明白了" |
| 开始工作 | "我来处理" / "开始执行" |
| 完成任务 | "完成了" / "已搞定" |
| 遇到问题 | "遇到一个问题：..." / "这里有个障碍：..." |
| 需要确认 | "请确认一下：..." / "需要你决定：..." |
| 解释原因 | "因为..." / "原因是..." |
| 提建议 | "建议..." / "可以考虑..." |
| 报告进度 | "目前进度：..." / "正在进行：..." |

## 架构

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ Claude Code     │────▶│ notify.sh        │────▶│ Queue File      │
│ (hooks trigger) │     │ (captures tmux   │     │ (.jsonl)        │
└─────────────────┘     │  session info)   │     └────────┬────────┘
                        └──────────────────┘              │
                                                          ▼
                        ┌──────────────────┐     ┌─────────────────┐
                        │ claude-monitor   │◀────│ monitor.py      │
                        │ (alias)          │     │ (curses TUI)    │
                        └──────────────────┘     └─────────────────┘
```

| 文件 | 职责 |
|------|------|
| **notify.sh** | Hook 调用入口；捕获当前 tmux 上下文，写入 JSONL 队列 |
| **monitor.py** | 主监控器（curses TUI）；读取队列，支持跳转/丢弃/清空 |
| **monitor.sh** | Bash 备用监控器（ANSI 转义，无 curses 依赖） |
| **setup.sh** | 一次性配置：权限、环境变量、别名 |
