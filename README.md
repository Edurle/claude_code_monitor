# Claude Code × tmux HITL Monitor

在 WSL2/Ubuntu 的 tmux 中，Claude Code 触发 HITL 或任务完成时，
自动在专用监控窗口排队显示，逐一跳转处理。

## 快速开始

```bash
cd ~/claude-tmux
bash setup.sh && source ~/.bashrc
./start-tmux-claude          # 启动工作区
```

## 文件说明

```
claude-tmux/
├── start-tmux-claude   # 工作区启动器
├── setup.sh            # 一键配置（只需运行一次）
├── notify.sh           # Claude Code hook 调用的通知脚本
├── monitor.py          # 监控界面（curses TUI）
├── lib/
│   ├── workspace.py    # 工作区配置解析
│   └── theme.py        # 主题引擎
└── workspaces/         # 工作区配置目录
    └── default.yaml    # 默认配置
```

## 工作区启动器

```bash
./start-tmux-claude              # 使用默认配置
./start-tmux-claude -w myproject # 使用指定工作区
./start-tmux-claude -f           # 强制关闭现有会话
./start-tmux-claude -l           # 列出可用工作区
```

## 工作区配置

配置文件位于 `workspaces/` 目录，YAML 格式：

```yaml
name: "我的工作区"
shell: auto  # auto / bash / zsh

windows:
  - name: monitor
    root: ~/
    panes:
      - cmd: python3 ~/claude-tmux/monitor.py

  - name: main
    root: ~/projects
    layout: even-horizontal
    panes:
      - cmd: vim app.py
      - cmd: npm run dev
      -  # 空 pane
```

### 窗口配置项

| 字段 | 说明 |
|------|------|
| `name` | 窗口名称 |
| `root` | 工作目录 |
| `layout` | 布局：`even-horizontal` / `even-vertical` / `main-horizontal` / `main-vertical` / `tiled` |
| `panes` | pane 列表 |

### Pane 配置项

```yaml
panes:
  - cmd: ls -la        # 执行命令
    root: ~/other      # 可选：单独指定目录
  -                    # 空 pane
```

## Conda 环境配置

如果你的 Python 在 conda 环境中，修改 `workspaces/default.yaml`：

```yaml
# 方式 1：先激活 conda
panes:
  - cmd: source ~/miniconda3/etc/profile.d/conda.sh && conda activate myenv && python3 ~/claude-tmux/monitor.py

# 方式 2：使用 conda run
panes:
  - cmd: conda run -n myenv python3 ~/claude-tmux/monitor.py

# 方式 3：使用完整路径
panes:
  - cmd: ~/miniconda3/envs/myenv/bin/python ~/claude-tmux/monitor.py
```

## Monitor 窗口操作

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
| `CLAUDE_TMUX_MONITOR_SESSION` | `monitor`             | 监控器 tmux session 名称 |

## 手动测试

```bash
# 模拟 HITL 通知
bash ~/claude-tmux/notify.sh hitl "需要确认文件删除操作"

# 模拟任务完成
bash ~/claude-tmux/notify.sh task_complete

# 查看队列
cat ~/.claude-tmux-queue.jsonl
```

## 全局 Hook 配置

在 `~/.claude/settings.json` 中配置：

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [{ "type": "command", "command": "bash ~/claude-tmux/notify.sh task_complete" }]
      }
    ],
    "Notification": [
      {
        "matcher": "",
        "hooks": [{ "type": "command", "command": "bash ~/claude-tmux/notify.sh hitl \"$CLAUDE_NOTIFICATION_MESSAGE\"" }]
      }
    ]
  }
}
```

## tmux 推荐配置

在 `~/.tmux.conf` 中添加：

```
set -g bell-action any
set -g visual-bell on
set -g monitor-bell on
setw -g window-status-bell-style fg=yellow,bold,blink
```
