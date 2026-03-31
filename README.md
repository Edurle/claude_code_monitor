# Claude Code × tmux HITL Monitor

在 WSL2/Ubuntu 的 tmux 中，Claude Code 触发 HITL 或任务完成时，
自动在专用监控窗口排队显示，逐一跳转处理。

## 文件说明

```
claude-tmux/
├── setup.sh      # 一键配置（只需运行一次）
├── notify.sh     # Claude Code hook 调用的通知脚本
├── monitor.sh    # 在 tmux 窗口中运行的监控界面
└── README.md
```

## 快速开始

```bash
cd ~/claude-tmux
bash setup.sh
source ~/.bashrc
claude-monitor   # 打开监控窗口
```

## monitor 窗口操作

| 按键    | 动作                                       |
|---------|--------------------------------------------|
| `Enter` | 跳转到队首任务目录（自动创建/切换窗口）    |
| `d`     | 丢弃（dismiss）队首条目                    |
| `c`     | 清空全部队列                               |
| `q`     | 退出 monitor（队列保留）                   |

## Hook 触发时机

- **HITL（需要人工介入）**：Claude Code 暂停等待用户输入时
- **task_complete（任务完成）**：Claude Code 的 Stop 事件触发时

## 环境变量

| 变量                   | 默认值                         | 说明                   |
|------------------------|--------------------------------|------------------------|
| `CLAUDE_TMUX_QUEUE`    | `~/.claude-tmux-queue.jsonl`   | 队列文件路径           |
| `CLAUDE_TMUX_WINDOW`   | `claude-monitor`               | tmux 监控窗口名称      |

## 手动测试

```bash
# 模拟一条 HITL 通知
bash ~/claude-tmux/notify.sh hitl "my-project" "需要确认文件删除操作"

# 模拟任务完成
bash ~/claude-tmux/notify.sh task_complete "my-project"

# 查看队列
cat ~/.claude-tmux-queue.jsonl
```

## 在项目级别覆盖 hook（可选）

在项目根目录创建 `.claude/settings.json`，局部覆盖全局配置：

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/claude-tmux/notify.sh task_complete \"my-project-name\""
          }
        ]
      }
    ]
  }
}
```

## tmux 推荐配置（可选）

在 `~/.tmux.conf` 中添加，让 bell 触发视觉提醒：

```
set -g bell-action any
set -g visual-bell on
set -g monitor-bell on
setw -g window-status-bell-style fg=yellow,bold,blink
```
