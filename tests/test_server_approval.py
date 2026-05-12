import json
import os
import sys
import threading
import time
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'mac'))

import state

def _post(port, path, body, timeout=5):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"http://localhost:{port}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    resp = urllib.request.urlopen(req, timeout=timeout)
    return resp.status, json.loads(resp.read())

def test_approval_auto_allows_non_approval_required_tools(tmp_path, unused_tcp_port, monkeypatch):
    state.STATE_FILE = str(tmp_path / "state.json")
    import config
    monkeypatch.setattr(config, "APPROVAL_REQUIRED", ["Bash"])
    monkeypatch.setattr(config, "AUTO_ALLOW", ["Read"])
    state.update(lambda s: (
        s["sessions"].update({"sess-a": {"iterm_id": "it-1", "model": "", "started_at": 0,
                                         "last_tool": "", "last_tool_ts": 0, "last_file": "", "current_task": ""}}),
        s.update({"active_iterm": "it-1"})
    ))
    import server
    srv = server.make_server(unused_tcp_port)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        _, resp = _post(unused_tcp_port, "/hook", {
            "hook_event_name": "PermissionRequest",
            "session_id": "sess-a",
            "_iterm_session_id": "it-1",
            "tool_name": "Read",
            "tool_input": {"path": "foo.py"},
        })
        assert resp["behavior"] == "allow"
    finally:
        srv.shutdown()

def test_approval_background_session_gets_ask(tmp_path, unused_tcp_port, monkeypatch):
    state.STATE_FILE = str(tmp_path / "state.json")
    import config
    monkeypatch.setattr(config, "APPROVAL_REQUIRED", ["Bash"])
    state.update(lambda s: (
        s["sessions"].update({"sess-bg": {"iterm_id": "it-bg", "model": "", "started_at": 0,
                                           "last_tool": "", "last_tool_ts": 0, "last_file": "", "current_task": ""}}),
        s.update({"active_iterm": "it-fg"})  # different session is active
    ))
    import server
    srv = server.make_server(unused_tcp_port)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        _, resp = _post(unused_tcp_port, "/hook", {
            "hook_event_name": "PermissionRequest",
            "session_id": "sess-bg",
            "_iterm_session_id": "it-bg",
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
        })
        assert resp["behavior"] == "ask"
    finally:
        srv.shutdown()

def test_approval_k10_unreachable_returns_ask(tmp_path, unused_tcp_port, monkeypatch):
    state.STATE_FILE = str(tmp_path / "state.json")
    import config
    monkeypatch.setattr(config, "APPROVAL_REQUIRED", ["Bash"])
    monkeypatch.setattr(config, "K10_IP", "127.0.0.1")
    monkeypatch.setattr(config, "K10_PORT", unused_tcp_port + 1)  # K10 not running
    state.update(lambda s: (
        s["sessions"].update({"sess-fg": {"iterm_id": "it-fg", "model": "", "started_at": 0,
                                           "last_tool": "", "last_tool_ts": 0, "last_file": "", "current_task": ""}}),
        s.update({"active_iterm": "it-fg"})
    ))
    import server
    srv = server.make_server(unused_tcp_port)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        # K10 unreachable → should fall back to "ask"
        _, resp = _post(unused_tcp_port, "/hook", {
            "hook_event_name": "PermissionRequest",
            "session_id": "sess-fg",
            "_iterm_session_id": "it-fg",
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
        }, timeout=10)
        assert resp["behavior"] == "ask"
    finally:
        srv.shutdown()
