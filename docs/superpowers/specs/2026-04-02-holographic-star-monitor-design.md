# Claude Code 全息状态监控设计文档

## 背景

当前监控器以队列列表为核心视图，仅在被动的 HITL/完成事件到达时更新。用户无法实时感知各 tmux session 中 Claude Code 的工作状态。本设计将队列视图替换为"全息星图"视图，在保留核心跳转功能的同时提供实时的、视觉惊艳的多会话状态监控。

## 设计目标

1. **一眼看全局**：所有 Claude Code session 的状态一目了然
2. **快速响应 HITL**：保留 Enter 一键跳转的核心操作
3. **视觉震撼**：全息星图 + 流星 + 雷达 + 粒子烟花
4. **不影响现有插件**：宠物区域、粒子效果、边框动画、成就系统的渲染区域和调用方式不变

## 数据流

### Hook 驱动的状态检测

每个 tmux session 中的 Claude Code 通过 hooks 推送状态事件到共享队列文件。

**新增 hooks 配置：**

```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "",
      "hooks": [{ "type": "command", "command": "bash ~/claude-tmux/notify.sh working \"$CLAUDE_TOOL_NAME\"" }]
    }],
    "PostToolUse": [{
      "matcher": "",
      "hooks": [{ "type": "command", "command": "bash ~/claude-tmux/notify.sh working \"$CLAUDE_TOOL_NAME\"" }]
    }],
    "Notification": [{
      "matcher": "",
      "hooks": [{ "type": "command", "command": "bash ~/claude-tmux/notify.sh hitl \"$CLAUDE_NOTIFICATION_MESSAGE\"" }]
    }],
    "Stop": [{
      "matcher": "",
      "hooks": [{ "type": "command", "command": "bash ~/claude-tmux/notify.sh task_complete" }]
    }]
  }
}
```

**事件类型扩展：**

notify.sh 新增 `working` 类型，携带工具名称：

```bash
EVENT_TYPE="${1:-hitl}"        # hitl | task_complete | working | idle
EXTRA_INFO="${2:-}"            # 工具名 / HITL 消息 / 空
```

**队列条目格式（.jsonl）：**

```json
{
  "ts": "12:34:56",
  "type": "working",
  "tool": "Edit",
  "session": "myproject",
  "win_idx": "1",
  "win_name": "editor",
  "project": "myproject",
  "dir": "/home/user/myproject",
  "info": "Edit"
}
```

### Monitor 端处理

monitor.py 读取队列后：

1. 按 session 分组，每个 session 维护最新状态
2. 5 分钟无事件自动标记为 `idle`
3. 状态机转换：

```
idle ──hook──▶ working ──hook──▶ hitl ──Enter──▶ (用户处理)
                     │                │
                     └──hook──▶ complete ──5min──▶ idle
```

## 屏幕布局

```
┌─────────────────────────────────────────────────────────┐
│ ◈ CLAUDE FLEET MONITOR    5 sessions  ⬤1 ⬤2 ⬤1 ⬤1  │  顶栏 (1行)
├───────────────────┬─────────────────────────────────────┤
│ ⚡ HITL 待处理 (2) │                                     │
│ ▶ data-pipeline   │         全息星图                     │
│   ai-web-dev      │      (右侧 60%)                     │
│───────────────────│                                     │
│ ◈ 活动流           │   ◆ ai-web-dev                      │
│ 12:34 Edit main   │      ⚠ data-pipeline                │
│ 12:33 HITL 确认   │   ◆ api-server                      │
│ 12:30 ✦ 完成      │      ✦ mobile-app                   │
│ 12:28 HITL 审批   │         ○ blog-site                  │
│───────────────────│                                     │
│ 宠物区域           │   流星 · 雷达 · 涟漪 · 烟花           │
│ (原位置 h-8)      │                                     │
├───────────────────┴─────────────────────────────────────┤
│ 状态消息                                                │  h-3
│ ────────────────────────────────────────────            │  h-2
│ [Enter]跳转 [F]星图 [T]主题 [A]成就 [q]退出             │  h-1
└─────────────────────────────────────────────────────────┘
```

**区域划分（使用 effective 坐标，MARGIN=2 已叠加）：**

| 区域 | 位置 | 宽度 | 说明 |
|------|------|------|------|
| 顶栏 | row 0 | 全宽 100% | Logo + 统计数字 |
| 左面板 | row 1 到 h-4 | 40% | HITL列表 → 活动流 → 宠物 |
| 右面板 | row 1 到 h-4 | 60% | 全息星图 |
| 宠物区 | 左面板底部，从 h-8 开始 | 左面板宽度 | 原位置不变 |
| 状态栏 | row h-3 | 全宽 | 临时消息 |
| 分隔线 | row h-2 | 全宽 | ── |
| 提示栏 | row h-1 | 全宽 | 快捷键 |

## 全息星图渲染

### 星星节点

每个 Claude Code session 是一颗星，用 ASCII 字符绘制：

| 状态 | 字符 | 颜色 | 动画 |
|------|------|------|------|
| working | `◆` | 橙色 (#fa0) | 脉冲发光 + 状态环 |
| hitl | `⚠` | 红色 (#f33) | 闪烁 + 涟漪扩散 |
| complete | `✦` | 绿色 (#4c6) | 短暂爆发后渐稳 |
| idle | `○` | 灰色 (#456) | 无动画，低透明度 |

每颗星下方显示 session 名称和当前操作。

### 飘动算法

星星在右面板内缓缓随机飘动：

```python
# 每帧更新（~20fps 上限）
for star in stars:
    # 布朗运动：随机微调速度
    star.vx += (random() - 0.5) * 0.012
    star.vy += (random() - 0.5) * 0.012

    # 速度上限
    star.vx = clamp(star.vx, -0.12, 0.12)
    star.vy = clamp(star.vy, -0.12, 0.12)

    # 弹性回弹到基准位置
    star.vx += (star.base_x - star.x) * 0.001
    star.vy += (star.base_y - star.y) * 0.001

    # 边界约束
    if star.x < pad: star.vx += 0.03
    if star.x > 88:  star.vx -= 0.03
    if star.y < pad: star.vy += 0.03
    if star.y > 88:  star.vy -= 0.03

    # 阻尼
    star.vx *= 0.995
    star.vy *= 0.995

    star.x += star.vx
    star.y += star.vy
```

位置用百分比存储（相对于右面板），窗口缩放时自适应。

### 背景效果

| 效果 | 描述 |
|------|------|
| 网格 | 浅色点阵背景，40x40 间距 |
| 同心圆 | 3 层同心圆，以面板中心为圆心 |
| 十字准线 | 水平 + 垂直半透明中线 |
| 雷达扫描线 | 绕中心旋转的亮线，6秒一周 |
| 流星 | 蓝白色流星随机划过，拖尾渐隐，头部发光 |

### 成就融入

成就解锁时不占用独立区域，而是：
- 对应的星星爆发绿色粒子烟花
- 左侧活动流中追加解锁记录
- 按 A 仍可切换到完整成就详情页

### 状态变更动画

| 转换 | 动画 |
|------|------|
| idle → working | 星星从暗淡变亮，开始脉冲 |
| working → hitl | 变红 + 闪烁 + 涟漪扩散 |
| working → complete | 绿色爆发粒子后渐稳 |
| 新 session 出现 | 从中心跃迁到位置，带蓝色闪光 |
| session 消失 | 渐隐消失 |

## 新增 hook 类型

notify.sh 增加对 `working` 事件的支持：

```bash
# 已有: hitl, task_complete, error
# 新增: working, idle
```

monitor.py 增加空闲检测定时器：每 30 秒扫描所有 session，超过 5 分钟无事件的标记为 idle。

## 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `lib/star_map.py` | **新建** | 星图渲染引擎：节点管理、飘动算法、背景效果、动画系统 |
| `lib/session_tracker.py` | **新建** | Session 状态追踪器：读取队列、状态机、空闲检测 |
| `notify.sh` | **修改** | 支持 `working` 事件类型，写入 `tool` 字段 |
| `monitor.py` | **修改** | 新布局渲染：顶栏 + 左右分栏 + 星图集成；状态管理委托给 SessionTracker |
| `lib/plugins/core.py` | **可能修改** | PluginContext 增加 session_tracker 引用（可选） |

## 现有插件兼容性

| 插件 | 影响 | 处理 |
|------|------|------|
| 宠物 (Pet) | 无 | 保持在左面板底部 h-8 位置渲染 |
| 粒子效果 (Particle Fx) | 无 | 全屏覆盖渲染不变 |
| 边框粒子 (Border Particles) | 无 | 屏幕边缘渲染不变 |
| 边框动画 (Border Animator) | 无 | 边框字符不变 |
| 成就 (Achievements) | 增强 | 解锁事件触发星图烟花，按 A 切换到完整页不变 |

所有插件通过 `render_pet_area`、`render_particles` 等钩子渲染的调用方式和参数签名不变。

## 验证计划

1. **无 session 启动**：星图显示空网格 + 流星 + "等待 session..."
2. **单 session**：一颗星在星图中缓缓飘动
3. **多 session**：多颗星各自飘动，互不重叠
4. **HITL 触发**：对应星变红闪烁，左侧出现待处理条目
5. **Enter 跳转**：跳转到目标 session 的 tmux 窗口
6. **成就解锁**：星图爆发绿色烟花
7. **宠物交互**：P/F 键在左面板底部正常工作
8. **主题切换**：T 键切换主题，星图颜色跟随主题
9. **A 成就页**：按 A 切换到完整成就列表视图
10. **S 统计页**：按 S 切换到统计视图
