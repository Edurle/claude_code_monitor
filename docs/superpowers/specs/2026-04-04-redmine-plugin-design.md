# Redmine 任务查看插件设计

## Context

在 monitor 的 RIGHT_TOP 区域（原矩阵雨位置）显示当前用户的 Redmine 待办任务列表，方便在 tmux 环境中快速查看任务状态，无需切换到浏览器。

## 需求

- 显示分配给当前用户的、状态为开启的任务（`assigned_to_id=me`, `status_id=open`）
- 只读列表，支持翻页（`<` / `>` 键）
- 定时自动刷新（默认 60 秒）
- 配置通过 `plugins.yaml` 提供 Redmine URL 和 API Key
- 禁用 matrix-rain 插件，由 redmine 插件接管 RIGHT_TOP 区域

## 架构

```
┌──────────────────────────────────────┐
│ RIGHT_TOP 区域                        │
│ ┌────────────────────────────────────┐│
│ │ Redmine: 我的新建/进行中任务 (5)   ││  ← 标题栏
│ │────────────────────────────────────││
│ │ 1 ● 办公室网络迁移        新建     ││
│ │ 2 ● 修复登录页面CSS问题   进行中   ││  ← 任务列表
│ │ 3 ○ 更新用户手册           反馈    ││
│ │────────────────────────────────────││
│ │ 1/3页 <翻页> Ent:打开 R:刷新      ││  ← 底部状态栏
│ └────────────────────────────────────┘│
└──────────────────────────────────────┘
```

## 文件变更

### 新建文件

- `plugins/builtin/redmine/plugin.py` — Redmine 插件主文件

### 修改文件

- `config/plugins.yaml` — 禁用 `builtin.matrix-rain`，添加 `builtin.redmine` 配置

## 插件设计

### 类结构

```python
class RedminePlugin(Plugin):
    # 声明 Region: Slot.RIGHT_TOP, min_height=3, priority=80
    # 配置: redmine_url, api_key, refresh_interval(默认60)
```

### 渲染格式

- **标题行**: `Redmine: 我的待办 (N)`
- **分隔线**: `────────────────────────────`
- **任务行**: `{序号} {优先级标记} {主题} {状态}`
  - 优先级标记: `●`(高/红) `◆`(中/黄) `○`(低/绿)
  - 主题截断到区域宽度，状态靠右对齐
- **底栏**: `{当前页}/{总页数} <:上页 >:下页 R:刷新`

### API 调用

- 端点: `GET /issues.json?assigned_to_id=me&status_id=open&sort=updated_on:desc&limit=100`
- 认证: `X-Redmine-API-Key` header
- 使用 `urllib.request`（标准库，无额外依赖）
- HTTP 请求在 `threading.Thread` 中执行，不阻塞 curses 主循环
- 结果缓存到 `self._issues` 列表

### 翻页逻辑

- 每页条数 = `rect.height - 3`（减去标题、分隔线、底栏）
- `<` 键上一页，`>` 键下一页

### 键盘操作

| 键 | 动作 |
|----|------|
| `<` / `,` | 上一页 |
| `>` / `.` | 下一页 |
| `R` | 手动刷新 |

### 错误处理

- URL/Key 未配置: 显示 "请在 plugins.yaml 配置 redmine_url 和 api_key"
- 网络错误: 显示 "连接失败: {error}"，保留上次数据
- 无任务: 显示 "没有待办任务 🎉"

## 配置示例

```yaml
# config/plugins.yaml
builtin.redmine:
  enabled: true
  settings:
    redmine_url: "https://redmine.example.com"
    api_key: "your-api-key-here"
    refresh_interval: 60

builtin.matrix-rain:
  enabled: false
```

## 验证

1. 配置正确的 Redmine URL 和 API Key，启动 monitor
2. 确认 RIGHT_TOP 区域显示任务列表
3. 按 `<` / `>` 翻页
4. 按 R 手动刷新
5. 断网测试：显示错误信息但不崩溃
7. 未配置测试：显示配置提示
