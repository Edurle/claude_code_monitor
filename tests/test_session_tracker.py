import time
from lib.session_tracker import SessionTracker, SessionState


def test_new_tracker_has_no_sessions():
    tracker = SessionTracker()
    assert tracker.get_sessions() == []


def test_process_hitl_event():
    tracker = SessionTracker()
    event = {"ts": "12:00:00", "type": "hitl", "session": "proj-a", "win_idx": "0",
             "win_name": "editor", "project": "proj-a", "dir": "/tmp/proj-a", "info": "confirm?"}
    tracker.process_event(event)
    sessions = tracker.get_sessions()
    assert len(sessions) == 1
    assert sessions[0].session == "proj-a"
    assert sessions[0].status == "hitl"


def test_process_working_then_complete():
    tracker = SessionTracker()
    tracker.process_event({"ts": "12:00:00", "type": "working", "session": "proj-a",
                           "win_idx": "0", "win_name": "", "project": "proj-a",
                           "dir": "/tmp/proj-a", "info": "Edit"})
    sessions = tracker.get_sessions()
    assert sessions[0].status == "working"
    assert sessions[0].tool == "Edit"

    tracker.process_event({"ts": "12:01:00", "type": "task_complete", "session": "proj-a",
                           "win_idx": "0", "win_name": "", "project": "proj-a",
                           "dir": "/tmp/proj-a", "info": ""})
    sessions = tracker.get_sessions()
    assert sessions[0].status == "complete"


def test_session_start_and_end():
    tracker = SessionTracker()
    tracker.process_event({"ts": "12:00:00", "type": "session_start", "session": "proj-a",
                           "win_idx": "0", "win_name": "", "project": "proj-a",
                           "dir": "/tmp/proj-a", "info": ""})
    assert tracker.get_sessions()[0].status == "start"

    tracker.process_event({"ts": "12:05:00", "type": "session_end", "session": "proj-a",
                           "win_idx": "0", "win_name": "", "project": "proj-a",
                           "dir": "/tmp/proj-a", "info": ""})
    assert tracker.get_sessions()[0].status == "offline"


def test_idle_timeout():
    tracker = SessionTracker()
    old_ts = time.time() - 400  # 6+ minutes ago
    tracker.process_event({"ts": "old", "type": "working", "session": "proj-a",
                           "win_idx": "0", "win_name": "", "project": "proj-a",
                           "dir": "/tmp/proj-a", "info": "Edit",
                           "_ts": old_ts})
    tracker.tick()
    assert tracker.get_sessions()[0].status == "idle"


def test_get_hitl_sessions():
    tracker = SessionTracker()
    tracker.process_event({"ts": "12:00", "type": "hitl", "session": "proj-a",
                           "win_idx": "0", "win_name": "", "project": "proj-a",
                           "dir": "/tmp/a", "info": "confirm?"})
    tracker.process_event({"ts": "12:01", "type": "working", "session": "proj-b",
                           "win_idx": "0", "win_name": "", "project": "proj-b",
                           "dir": "/tmp/b", "info": "Edit"})
    hitl = tracker.get_hitl_sessions()
    assert len(hitl) == 1
    assert hitl[0].session == "proj-a"


def test_subagent_tracking():
    tracker = SessionTracker()
    tracker.process_event({"ts": "12:00", "type": "working", "session": "proj-a",
                           "win_idx": "0", "win_name": "", "project": "proj-a",
                           "dir": "/tmp/a", "info": "Agent"})
    tracker.process_event({"ts": "12:00", "type": "subagent_start", "session": "proj-a",
                           "win_idx": "0", "win_name": "", "project": "proj-a",
                           "dir": "/tmp/a", "info": "Explore"})
    s = tracker.get_sessions()[0]
    assert s.subagent_count == 1
    assert "Explore" in s.subagents

    tracker.process_event({"ts": "12:01", "type": "subagent_stop", "session": "proj-a",
                           "win_idx": "0", "win_name": "", "project": "proj-a",
                           "dir": "/tmp/a", "info": ""})
    s = tracker.get_sessions()[0]
    assert s.subagent_count == 0


def test_activity_stream():
    tracker = SessionTracker()
    tracker.process_event({"ts": "12:00", "type": "working", "session": "proj-a",
                           "win_idx": "0", "win_name": "", "project": "proj-a",
                           "dir": "/tmp/a", "info": "Edit"})
    tracker.process_event({"ts": "12:01", "type": "task_complete", "session": "proj-b",
                           "win_idx": "0", "win_name": "", "project": "proj-b",
                           "dir": "/tmp/b", "info": ""})
    stream = tracker.get_activity_stream(limit=10)
    assert len(stream) == 2
    assert stream[0]["type"] == "task_complete"  # most recent first
