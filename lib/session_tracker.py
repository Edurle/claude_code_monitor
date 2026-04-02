"""Session 状态追踪器：读取队列事件，维护 session 状态机"""

import time
from dataclasses import dataclass, field
from typing import List
from collections import OrderedDict

# 空闲超时（秒）
IDLE_TIMEOUT = 300  # 5 minutes


@dataclass
class SessionState:
    """单个 session 的状态"""
    session: str
    status: str = "start"          # start/idle/working/hitl/complete/error/api_error/offline
    project: str = ""
    win_idx: str = "0"
    win_name: str = ""
    dir: str = ""
    tool: str = ""
    info: str = ""
    last_event_ts: float = 0.0
    last_event_time: str = ""       # 显示用的时间字符串
    subagents: List[str] = field(default_factory=list)
    hitl_info: str = ""             # HITL 消息

    @property
    def subagent_count(self) -> int:
        return len(self.subagents)


class SessionTracker:
    """追踪所有 Claude Code session 的实时状态"""

    def __init__(self):
        self._sessions: OrderedDict[str, SessionState] = OrderedDict()
        self._activity: List[dict] = []

    def process_event(self, event: dict):
        """处理一个队列事件，更新对应 session 的状态"""
        session = event.get("session", "")
        if not session:
            return

        event_type = event.get("type", "")
        info = event.get("info", "")
        ts = event.get("_ts", time.time())
        ts_str = event.get("ts", "")

        # 获取或创建 session
        if session not in self._sessions:
            self._sessions[session] = SessionState(
                session=session,
                project=event.get("project", ""),
                win_idx=event.get("win_idx", "0"),
                win_name=event.get("win_name", ""),
                dir=event.get("dir", ""),
            )

        s = self._sessions[session]
        s.last_event_ts = ts
        s.last_event_time = ts_str
        s.project = event.get("project", s.project)
        s.win_idx = event.get("win_idx", s.win_idx)
        s.win_name = event.get("win_name", s.win_name)

        # 状态机转换
        if event_type == "session_start":
            s.status = "start"
        elif event_type == "session_end":
            s.status = "offline"
        elif event_type in ("working",):
            s.status = "working"
            s.tool = info
            s.info = info
        elif event_type == "hitl":
            s.status = "hitl"
            s.hitl_info = info
        elif event_type == "task_complete":
            s.status = "complete"
            s.tool = ""
            s.info = ""
        elif event_type == "error":
            s.status = "error"
            s.info = info
        elif event_type == "api_error":
            s.status = "api_error"
            s.info = info
        elif event_type == "subagent_start":
            if info and info not in s.subagents:
                s.subagents.append(info)
        elif event_type == "subagent_stop":
            if info:
                s.subagents = [a for a in s.subagents if a != info]
            else:
                s.subagents = []

        # 记录活动流
        self._activity.append({
            "ts": ts_str,
            "type": event_type,
            "session": session,
            "project": s.project,
            "info": info,
            "_ts": ts,
        })
        # 限制活动流长度
        if len(self._activity) > 200:
            self._activity = self._activity[-100:]

    def tick(self):
        """定时调用：检测空闲超时"""
        now = time.time()
        for s in self._sessions.values():
            if s.status in ("working", "complete", "start", "error") and s.last_event_ts > 0:
                if now - s.last_event_ts > IDLE_TIMEOUT:
                    s.status = "idle"
                    s.tool = ""
                    s.info = ""

    def get_sessions(self) -> List[SessionState]:
        """获取所有活跃 session（排除 offline 超过 5 分钟的）"""
        now = time.time()
        result = []
        for s in self._sessions.values():
            if s.status == "offline" and s.last_event_ts > 0 and now - s.last_event_ts > 300:
                continue
            result.append(s)
        return result

    def get_hitl_sessions(self) -> List[SessionState]:
        """获取所有需要人工处理的 session"""
        return [s for s in self._sessions.values() if s.status == "hitl"]

    def get_activity_stream(self, limit: int = 20) -> List[dict]:
        """获取最近的活动流"""
        return list(reversed(self._activity[-limit:]))
