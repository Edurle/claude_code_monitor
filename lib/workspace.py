#!/usr/bin/env python3
# lib/workspace.py - YAML 工作区解析器
"""
解析工作区配置文件，生成 tmux 命令

使用:
    python3 lib/workspace.py default
    python3 lib/workspace.py workspaces/example.yaml
    python3 lib/workspace.py frontend backend  # 合并多个
"""

import yaml
import sys
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

# 工作区配置目录
WORKSPACES_DIR = Path(__file__).parent.parent / "workspaces"


def expand_path(path: str) -> str:
    """展开 ~ 和环境变量"""
    return os.path.expanduser(os.path.expandvars(path))


def load_workspace(name_or_path: str, loaded: Optional[set] = None) -> Dict[str, Any]:
    """
    加载工作区配置，支持 include 递归

    Args:
        name_or_path: 工作区名称（不带.yaml）或完整路径
        loaded: 已加载的配置集合（防止循环引用）

    Returns:
        工作区配置字典
    """
    if loaded is None:
        loaded = set()

    # 判断是路径还是名称
    if os.path.isfile(name_or_path):
        config_path = Path(name_or_path)
    else:
        config_path = WORKSPACES_DIR / f"{name_or_path}.yaml"

    config_key = str(config_path.resolve())
    if config_key in loaded:
        return {'windows': []}  # 防止循环引用
    loaded.add(config_key)

    if not config_path.exists():
        print(f"error: 配置文件不存在: {config_path}", file=sys.stderr)
        return {'windows': []}

    with open(config_path) as f:
        config = yaml.safe_load(f) or {}

    # 处理 include
    all_windows = []
    for inc in config.get('include', []):
        inc_config = load_workspace(inc, loaded.copy())
        all_windows.extend(inc_config.get('windows', []))

    # 添加当前配置的窗口
    all_windows.extend(config.get('windows', []))

    return {
        'name': config.get('name', name_or_path),
        'shell': config.get('shell', 'auto'),
        'windows': all_windows
    }


def generate_tmux_commands(config: Dict[str, Any], session_name: str = 'monitor') -> List[str]:
    """
    生成 tmux 命令列表

    Args:
        config: 工作区配置
        session_name: tmux 会话名称

    Returns:
        tmux 命令列表
    """
    commands = []
    windows = config.get('windows', [])

    if not windows:
        windows = [{'name': 'monitor', 'root': '~', 'panes': [{}]}]

    # 窗口名去重
    used_names: Dict[str, int] = {}

    for i, win in enumerate(windows):
        win_name = win.get('name', f'win{i}')
        if win_name in used_names:
            used_names[win_name] += 1
            win_name = f"{win_name}-{used_names[win_name]}"
        else:
            used_names[win_name] = 1

        root = expand_path(win.get('root', '~'))
        panes = win.get('panes', [{}])

        if i == 0:
            # 第一个窗口：创建 session
            commands.append(f'command tmux new-session -d -s {session_name} -n {win_name} -c "{root}"')
        else:
            # 后续窗口：追加到末尾（-a 参数避免索引冲突）
            commands.append(f'command tmux new-window -a -t {session_name} -n {win_name} -c "{root}"')

        # 第一个 pane 的命令
        first_pane = (panes[0] or {}) if panes else {}
        first_cmd = first_pane.get('cmd', '')
        if first_cmd:
            # 转义引号
            escaped_cmd = first_cmd.replace('"', '\\"')
            commands.append(f'command tmux send-keys -t {session_name}:{win_name} "{escaped_cmd}" Enter')

        # 创建额外 panes
        for j, pane in enumerate(panes[1:], 1):
            pane = pane or {}  # 处理 None
            pane_root = expand_path(pane.get('root', root))

            # 分割方向：h=水平(左右)，v=垂直(上下)
            split_flag = '-h' if pane.get('split', 'h') == 'h' else '-v'

            # 分割大小：百分比
            size = pane.get('size')
            size_arg = f'-p {size}' if size else ''

            commands.append(f'command tmux split-window {split_flag} {size_arg} -t {session_name}:{win_name} -c "{pane_root}"')
            pane_cmd = pane.get('cmd', '')
            if pane_cmd:
                escaped_cmd = pane_cmd.replace('"', '\\"')
                commands.append(f'command tmux send-keys -t {session_name}:{win_name}.{j} "{escaped_cmd}" Enter')

        # 设置布局
        layout = win.get('layout')
        if layout:
            commands.append(f'command tmux select-layout -t {session_name}:{win_name} {layout}')

    # 选择第一个窗口
    commands.append(f'command tmux select-window -t {session_name}:0')

    return commands


def list_workspaces() -> List[str]:
    """列出所有可用的工作区配置"""
    if not WORKSPACES_DIR.exists():
        return []
    return [f.stem for f in WORKSPACES_DIR.glob("*.yaml")]


def main():
    """命令行入口"""
    args = sys.argv[1:]

    # 解析参数
    workspaces = []
    action = "generate"
    session_name = "monitor"

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == '-l' or arg == '--list':
            action = "list"
            i += 1
        elif arg == '-s' or arg == '--session':
            session_name = args[i + 1]
            i += 2
        elif arg == '-w' or arg == '--workspace':
            workspaces.append(args[i + 1])
            i += 2
        elif arg.startswith('-'):
            print(f"error: 未知参数: {arg}", file=sys.stderr)
            sys.exit(1)
        else:
            workspaces.append(arg)
            i += 1

    if action == "list":
        for name in list_workspaces():
            print(name)
        return

    if not workspaces:
        workspaces = ['default']

    # 合并所有工作区
    merged = {'windows': [], 'shell': 'auto'}
    for ws in workspaces:
        config = load_workspace(ws)
        merged['windows'].extend(config.get('windows', []))
        if config.get('shell') != 'auto':
            merged['shell'] = config['shell']

    # 生成并输出命令
    for cmd in generate_tmux_commands(merged, session_name):
        print(cmd)


if __name__ == '__main__':
    main()
