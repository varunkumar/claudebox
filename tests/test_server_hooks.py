import json
import os
import sys
import tempfile
import threading
import time
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'mac'))
os.environ.setdefault("CLAUDEBOX_TEST", "1")

import state

def _post(port, path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"http://localhost:{port}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    resp = urllib.request.urlopen(req, timeout=5)
    return resp.status, resp.read()

def test_session_start_hook_creates_session_entry(tmp_path, unused_tcp_port):
    state.STATE_FILE = str(tmp_path / "state.json")
    import server
    srv = server.make_server(unused_tcp_port)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        status, _ = _post(unused_tcp_port, "/hook", {
            "hook_event_name": "SessionStart",
            "session_id": "sess-001",
            "_iterm_session_id": "iterm-x1",
        })
        assert status == 200
        time.sleep(0.1)
        st = state.read()
        assert "sess-001" in st["sessions"]
        assert st["sessions"]["sess-001"]["iterm_id"] == "iterm-x1"
    finally:
        srv.shutdown()

def test_post_tool_use_updates_last_tool(tmp_path, unused_tcp_port):
    state.STATE_FILE = str(tmp_path / "state.json")
    import server
    srv = server.make_server(unused_tcp_port)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        _post(unused_tcp_port, "/hook", {
            "hook_event_name": "SessionStart",
            "session_id": "sess-002",
            "_iterm_session_id": "iterm-x2",
        })
        _post(unused_tcp_port, "/hook", {
            "hook_event_name": "PostToolUse",
            "session_id": "sess-002",
            "_iterm_session_id": "iterm-x2",
            "tool_name": "Edit",
            "tool_input": {"path": "src/auth.py"},
        })
        time.sleep(0.1)
        st = state.read()
        assert st["sessions"]["sess-002"]["last_tool"] == "Edit"
        assert st["sessions"]["sess-002"]["last_file"] == "src/auth.py"
    finally:
        srv.shutdown()

def test_focus_endpoint_updates_active_iterm(tmp_path, unused_tcp_port):
    state.STATE_FILE = str(tmp_path / "state.json")
    import server
    srv = server.make_server(unused_tcp_port)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        status, _ = _post(unused_tcp_port, "/focus", {"iterm_session_id": "iterm-x9"})
        assert status == 200
        time.sleep(0.1)
        st = state.read()
        assert st["active_iterm"] == "iterm-x9"
    finally:
        srv.shutdown()
