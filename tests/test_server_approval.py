import http.server
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

def _mock_k10_server(k10_port: int, mac_port: int, decision: str):
    """Start a mock K10 that receives /approve and immediately sends /decision back."""
    class _K10Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            self.send_response(200)
            self.end_headers()
            cb = json.dumps({"request_id": body["request_id"], "decision": decision}).encode()
            req = urllib.request.Request(
                f"http://127.0.0.1:{mac_port}/decision",
                data=cb,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
        def log_message(self, *args): pass

    srv = http.server.HTTPServer(("", k10_port), _K10Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def test_approval_roundtrip_allow(tmp_path, unused_tcp_port_pair, monkeypatch):
    mac_port, k10_port = unused_tcp_port_pair
    state.STATE_FILE = str(tmp_path / "state.json")
    import config, server
    monkeypatch.setattr(config, "APPROVAL_REQUIRED", ["Bash"])
    monkeypatch.setattr(config, "AUTO_ALLOW", [])
    monkeypatch.setattr(config, "K10_IP", "127.0.0.1")
    monkeypatch.setattr(config, "K10_PORT", k10_port)
    monkeypatch.setattr(config, "APPROVAL_TIMEOUT_S", 10)
    state.update(lambda s: (
        s["sessions"].update({"sess-fg": {"iterm_id": "it-fg", "model": "", "started_at": 0,
                                           "last_tool": "", "last_tool_ts": 0, "last_file": "", "current_task": ""}}),
        s.update({"active_iterm": "it-fg"})
    ))
    k10_srv = _mock_k10_server(k10_port, mac_port, "allow")
    mac_srv = server.make_server(mac_port)
    threading.Thread(target=mac_srv.serve_forever, daemon=True).start()
    try:
        _, resp = _post(mac_port, "/hook", {
            "hook_event_name": "PermissionRequest",
            "session_id": "sess-fg",
            "_iterm_session_id": "it-fg",
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
        }, timeout=15)
        assert resp["behavior"] == "allow"
    finally:
        mac_srv.shutdown()
        k10_srv.shutdown()


def test_approval_roundtrip_deny(tmp_path, unused_tcp_port_pair, monkeypatch):
    mac_port, k10_port = unused_tcp_port_pair
    state.STATE_FILE = str(tmp_path / "state.json")
    import config, server
    monkeypatch.setattr(config, "APPROVAL_REQUIRED", ["Bash"])
    monkeypatch.setattr(config, "AUTO_ALLOW", [])
    monkeypatch.setattr(config, "K10_IP", "127.0.0.1")
    monkeypatch.setattr(config, "K10_PORT", k10_port)
    monkeypatch.setattr(config, "APPROVAL_TIMEOUT_S", 10)
    state.update(lambda s: (
        s["sessions"].update({"sess-fg": {"iterm_id": "it-fg", "model": "", "started_at": 0,
                                           "last_tool": "", "last_tool_ts": 0, "last_file": "", "current_task": ""}}),
        s.update({"active_iterm": "it-fg"})
    ))
    k10_srv = _mock_k10_server(k10_port, mac_port, "deny")
    mac_srv = server.make_server(mac_port)
    threading.Thread(target=mac_srv.serve_forever, daemon=True).start()
    try:
        _, resp = _post(mac_port, "/hook", {
            "hook_event_name": "PermissionRequest",
            "session_id": "sess-fg",
            "_iterm_session_id": "it-fg",
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /"},
        }, timeout=15)
        assert resp["behavior"] == "deny"
    finally:
        mac_srv.shutdown()
        k10_srv.shutdown()


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
