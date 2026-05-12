# ClaudeBox Mac + K10 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a physical ambient dashboard (UNIHIKER K10) that shows Claude Code session state, token usage, mood, and gates Bash commands behind a physical Y/N touch approval — all driven from Mac-side hooks and JSONL logs with zero token cost.

**Architecture:** A single persistent Mac daemon (`server.py`) receives all Claude Code hook events via HTTP, maintains shared state in `~/.claudebox/state.json`, polls JSONL logs every 30s for token data, and pushes dashboard payloads to the K10 over Wi-Fi. A separate `focus_monitor.py` daemon tracks the active iTerm2 tab so the dashboard and approval gate always follow the user's focused session. The K10 runs a MicroPython HTTP server that renders the dashboard, reads its own sensors on demand, and sends Y/N decisions back to the Mac.

**Tech Stack:** Python 3.10+ stdlib only (no pip deps on Mac side). MicroPython on K10 (ESP32-S3). iTerm2 Python API for focus tracking. Standard HTTP (no WebSockets, no MQ).

**Spec:** `docs/specs/2026-05-12-claudebox-mac-k10-design.md`

---

## Phase 1: Mac Foundation

### Task 1: Project skeleton + config

**Files:**
- Create: `mac/config.py` (gitignored)
- Create: `config.example.py`
- Create: `.gitignore`
- Create: `tests/__init__.py`
- Modify: nothing existing

- [ ] **Step 1: Create `.gitignore`**

```
mac/config.py
k10/device/secrets.py
~/.claudebox/
```

Save to `.gitignore` at repo root.

- [ ] **Step 2: Create `config.example.py`**

```python
# Copy to mac/config.py and fill in your values
K10_IP   = "192.168.x.x"   # set after router DHCP reservation for K10's MAC address
K10_PORT = 8080
MAC_PORT = 8081

STATE_FILE = "~/.claudebox/state.json"
LOG_DIR    = "~/.claude/projects"

APPROVAL_REQUIRED = ["Bash"]
AUTO_ALLOW        = ["Read", "Glob", "Grep", "LS", "WebSearch", "WebFetch"]

SESSION_TYPICAL_MAX     = 150_000
IDLE_THRESHOLD_MINUTES  = 10
BROADCASTER_DEBOUNCE_S  = 1
SCANNER_INTERVAL_S      = 30
APPROVAL_TIMEOUT_S      = 60
```

- [ ] **Step 3: Create `mac/config.py`** (fill in your real K10 IP)

Same content as `config.example.py` but with real `K10_IP` filled in.

- [ ] **Step 4: Create `tests/__init__.py`**

Empty file.

- [ ] **Step 5: Verify `.gitignore` works**

```bash
git status
```

Expected: `mac/config.py` does NOT appear in untracked files. `config.example.py` does appear.

- [ ] **Step 6: Commit**

```bash
git add .gitignore config.example.py tests/__init__.py
git commit -m "feat: project skeleton and config template"
```

---

### Task 2: `mac/state.py` — shared state module

**Files:**
- Create: `mac/state.py`
- Create: `tests/test_state.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_state.py`:

```python
import json
import os
import tempfile
import threading
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'mac'))

import state

def test_read_returns_default_when_missing(tmp_path):
    state.STATE_FILE = str(tmp_path / "state.json")
    result = state.read()
    assert result["active_iterm"] == ""
    assert result["sessions"] == {}
    assert result["tokens"]["input"] == 0
    assert result["mood"] == "sleeping"

def test_write_then_read_roundtrip(tmp_path):
    state.STATE_FILE = str(tmp_path / "state.json")
    data = state.read()
    data["active_iterm"] = "test-session-123"
    state.write(data)
    result = state.read()
    assert result["active_iterm"] == "test-session-123"

def test_update_modifies_and_persists(tmp_path):
    state.STATE_FILE = str(tmp_path / "state.json")
    state.update(lambda s: s["sessions"].update({"abc": {"iterm_id": "x1"}}))
    result = state.read()
    assert result["sessions"]["abc"]["iterm_id"] == "x1"

def test_write_sets_last_updated(tmp_path):
    state.STATE_FILE = str(tmp_path / "state.json")
    data = state.read()
    state.write(data)
    result = state.read()
    assert result["last_updated"] > 0

def test_concurrent_updates_do_not_corrupt(tmp_path):
    state.STATE_FILE = str(tmp_path / "state.json")
    errors = []

    def worker(val):
        try:
            state.update(lambda s: s["sessions"].update({str(val): {}}))
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads: t.start()
    for t in threads: t.join()

    assert errors == []
    result = state.read()
    assert len(result["sessions"]) == 20
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/varunkumar/projects/claudebox
python -m pytest tests/test_state.py -v
```

Expected: `ModuleNotFoundError: No module named 'state'`

- [ ] **Step 3: Create `mac/state.py`**

```python
import json
import os
import threading
import time

STATE_FILE = os.path.expanduser("~/.claudebox/state.json")
_lock = threading.Lock()


def _default() -> dict:
    return {
        "active_iterm": "",
        "sessions": {},
        "tokens": {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0, "cost_usd": 0.0},
        "mood": "sleeping",
        "mood_score": 0.0,
        "last_updated": 0,
    }


def read() -> dict:
    with _lock:
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return _default()


def write(data: dict) -> None:
    with _lock:
        _write_locked(data)


def update(fn) -> None:
    with _lock:
        try:
            with open(STATE_FILE) as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = _default()
        fn(data)
        _write_locked(data)


def _write_locked(data: dict) -> None:
    data["last_updated"] = int(time.time())
    os.makedirs(os.path.dirname(os.path.abspath(STATE_FILE)), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(data, f, indent=2)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_state.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add mac/state.py tests/test_state.py
git commit -m "feat: shared state module with threading.Lock"
```

---

### Task 3: `mac/scanner.py` — JSONL token scanner

**Files:**
- Create: `mac/scanner.py`
- Create: `tests/test_scanner.py`
- Create: `tests/fixtures/sample.jsonl`

- [ ] **Step 1: Create test fixture**

Create `tests/fixtures/sample.jsonl` (two entries: one sonnet, one opus, one unknown session to be ignored):

```jsonl
{"session_id": "session-aaa", "message": {"model": "claude-sonnet-4-6", "usage": {"input_tokens": 1000, "output_tokens": 200, "cache_creation_input_tokens": 500, "cache_read_input_tokens": 300}}}
{"session_id": "session-aaa", "message": {"model": "claude-sonnet-4-6", "usage": {"input_tokens": 2000, "output_tokens": 400, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 1000}}}
{"session_id": "session-bbb", "message": {"model": "claude-opus-4-6", "usage": {"input_tokens": 500, "output_tokens": 100, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}}}
{"session_id": "session-ignored", "message": {"model": "claude-sonnet-4-6", "usage": {"input_tokens": 9999, "output_tokens": 9999, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}}}
```

- [ ] **Step 2: Write failing tests**

Create `tests/test_scanner.py`:

```python
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'mac'))

import scanner

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')

def test_scan_aggregates_tokens_for_known_sessions():
    result = scanner.scan_sessions(FIXTURES, {"session-aaa", "session-bbb"})
    assert result["input"] == 1000 + 2000 + 500
    assert result["output"] == 200 + 400 + 100
    assert result["cache_write"] == 500 + 0 + 0
    assert result["cache_read"] == 300 + 1000 + 0

def test_scan_ignores_unknown_sessions():
    result = scanner.scan_sessions(FIXTURES, {"session-aaa"})
    assert result["input"] == 3000
    # session-ignored's 9999 tokens should not appear
    assert result["input"] < 9000

def test_scan_calculates_cost_usd():
    result = scanner.scan_sessions(FIXTURES, {"session-aaa"})
    # sonnet: input=$3.69/MTok, output=$18.45/MTok, cache_write=$4.61/MTok, cache_read=$0.37/MTok
    expected_cost = (
        3000 * 3.69 / 1_000_000 +
        600  * 18.45 / 1_000_000 +
        500  * 4.61 / 1_000_000 +
        1300 * 0.37 / 1_000_000
    )
    assert abs(result["cost_usd"] - expected_cost) < 0.0001

def test_scan_empty_sessions_returns_zeros():
    result = scanner.scan_sessions(FIXTURES, set())
    assert result["input"] == 0
    assert result["cost_usd"] == 0.0

def test_scan_missing_usage_fields_treated_as_zero():
    result = scanner.scan_sessions(FIXTURES, {"session-aaa", "session-bbb"})
    assert result["cost_usd"] >= 0
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
python -m pytest tests/test_scanner.py -v
```

Expected: `ModuleNotFoundError: No module named 'scanner'`

- [ ] **Step 4: Create `mac/scanner.py`**

```python
import glob
import json
import os

PRICING = {
    "claude-opus-4-6":   {"input": 6.15,  "output": 30.75, "cache_write": 7.69,  "cache_read": 0.61},
    "claude-sonnet-4-6": {"input": 3.69,  "output": 18.45, "cache_write": 4.61,  "cache_read": 0.37},
    "claude-haiku-4-5":  {"input": 1.23,  "output": 6.15,  "cache_write": 1.54,  "cache_read": 0.12},
}
_DEFAULT_PRICING = PRICING["claude-sonnet-4-6"]


def scan_sessions(log_dir: str, session_ids: set) -> dict:
    """Aggregate token usage from JSONL files for the given session IDs."""
    totals = {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0, "cost_usd": 0.0}
    if not session_ids:
        return totals

    pattern = os.path.join(os.path.expanduser(log_dir), "**", "*.jsonl")
    for path in glob.glob(pattern, recursive=True):
        _scan_file(path, session_ids, totals)

    return totals


def _scan_file(path: str, session_ids: set, totals: dict) -> None:
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("session_id") not in session_ids:
                    continue
                _accumulate(entry, totals)
    except OSError:
        pass


def _accumulate(entry: dict, totals: dict) -> None:
    msg = entry.get("message", {})
    usage = msg.get("usage", {})
    model = msg.get("model", "claude-sonnet-4-6")
    price = PRICING.get(model, _DEFAULT_PRICING)

    inp = usage.get("input_tokens", 0)
    out = usage.get("output_tokens", 0)
    cw  = usage.get("cache_creation_input_tokens", 0)
    cr  = usage.get("cache_read_input_tokens", 0)

    totals["input"]       += inp
    totals["output"]      += out
    totals["cache_write"] += cw
    totals["cache_read"]  += cr
    totals["cost_usd"]    += (
        inp * price["input"]       / 1_000_000 +
        out * price["output"]      / 1_000_000 +
        cw  * price["cache_write"] / 1_000_000 +
        cr  * price["cache_read"]  / 1_000_000
    )
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/test_scanner.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add mac/scanner.py tests/test_scanner.py tests/fixtures/sample.jsonl
git commit -m "feat: JSONL scanner with per-model token aggregation and cost calculation"
```

---

### Task 4: `mac/mood.py` — mood scoring

**Files:**
- Create: `mac/mood.py`
- Create: `tests/test_mood.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_mood.py`:

```python
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'mac'))

import mood

def _tokens(inp, out):
    return {"input": inp, "output": out, "cache_write": 0, "cache_read": 0, "cost_usd": 0.0}

def test_happy_below_20_percent():
    t = _tokens(25_000, 4_000)  # 29k / 150k = 19.3%
    name, score = mood.compute_mood(t, idle_minutes=0)
    assert name == "happy"
    assert score < 0.20

def test_neutral_between_20_and_50():
    t = _tokens(50_000, 10_000)  # 60k / 150k = 40%
    name, score = mood.compute_mood(t, idle_minutes=0)
    assert name == "neutral"
    assert 0.20 <= score < 0.50

def test_tired_between_50_and_75():
    t = _tokens(90_000, 15_000)  # 105k / 150k = 70%
    name, score = mood.compute_mood(t, idle_minutes=0)
    assert name == "tired"
    assert 0.50 <= score < 0.75

def test_stressed_above_75():
    t = _tokens(120_000, 20_000)  # 140k / 150k = 93%
    name, score = mood.compute_mood(t, idle_minutes=0)
    assert name == "stressed"
    assert score >= 0.75

def test_sleeping_overrides_score_when_idle():
    t = _tokens(0, 0)
    name, score = mood.compute_mood(t, idle_minutes=11)
    assert name == "sleeping"

def test_sleeping_idle_overrides_even_high_tokens():
    t = _tokens(200_000, 50_000)
    name, score = mood.compute_mood(t, idle_minutes=15)
    assert name == "sleeping"

def test_score_capped_at_1():
    t = _tokens(500_000, 500_000)
    name, score = mood.compute_mood(t, idle_minutes=0)
    assert score <= 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_mood.py -v
```

Expected: `ModuleNotFoundError: No module named 'mood'`

- [ ] **Step 3: Create `mac/mood.py`**

```python
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
import config

SESSION_TYPICAL_MAX    = config.SESSION_TYPICAL_MAX
IDLE_THRESHOLD_MINUTES = config.IDLE_THRESHOLD_MINUTES

_THRESHOLDS = [
    (0.20, "happy"),
    (0.50, "neutral"),
    (0.75, "tired"),
    (1.01, "stressed"),
]


def compute_mood(tokens: dict, idle_minutes: float) -> tuple:
    """Return (mood_name, mood_score). Sleeping overrides score if idle long enough."""
    if idle_minutes >= IDLE_THRESHOLD_MINUTES:
        return "sleeping", 0.0

    raw = (tokens["input"] + tokens["output"]) / SESSION_TYPICAL_MAX
    score = min(raw, 1.0)

    for threshold, name in _THRESHOLDS:
        if score < threshold:
            return name, score

    return "stressed", score
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_mood.py -v
```

Expected: 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add mac/mood.py tests/test_mood.py
git commit -m "feat: mood scoring with idle detection"
```

---

### Task 5: `mac/server.py` — HTTP server + non-blocking hook handling

**Files:**
- Create: `mac/server.py`
- Create: `tests/test_server_hooks.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_server_hooks.py`:

```python
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
```

Add a `conftest.py` in `tests/` for the `unused_tcp_port` fixture:

```python
# tests/conftest.py
import socket
import pytest

@pytest.fixture
def unused_tcp_port():
    with socket.socket() as s:
        s.bind(('', 0))
        return s.getsockname()[1]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_server_hooks.py -v
```

Expected: `ModuleNotFoundError: No module named 'server'`

- [ ] **Step 3: Create `mac/server.py`** (non-blocking hooks only, broadcaster stubs to console)

```python
import http.server
import json
import os
import queue
import sys
import threading
import time
import urllib.request
import uuid

sys.path.insert(0, os.path.dirname(__file__))
import config
import mood as mood_mod
import state

_broadcast_event = threading.Event()


def _update_from_hook(hook_type: str, session_id: str, iterm_id: str, body: dict) -> None:
    def fn(st):
        if session_id and session_id not in st["sessions"]:
            st["sessions"][session_id] = {
                "iterm_id": iterm_id,
                "model": "",
                "started_at": int(time.time()),
                "last_tool": "",
                "last_tool_ts": 0,
                "last_file": "",
                "current_task": "",
            }
        elif session_id and iterm_id:
            st["sessions"][session_id]["iterm_id"] = iterm_id

        session = st["sessions"].get(session_id, {})

        if hook_type == "SessionStart":
            session["model"] = body.get("model", "")
            session["started_at"] = int(time.time())

        elif hook_type == "UserPromptSubmit":
            prompt = body.get("prompt", "") or body.get("message", "")
            session["current_task"] = prompt[:120]

        elif hook_type == "PostToolUse":
            session["last_tool"] = body.get("tool_name", "")
            session["last_tool_ts"] = int(time.time())
            tool_input = body.get("tool_input", {})
            session["last_file"] = (
                tool_input.get("path", "")
                or tool_input.get("file_path", "")
                or tool_input.get("command", "")[:60]
            )

        elif hook_type == "SessionEnd":
            st["sessions"].pop(session_id, None)
            return

        if session_id and session_id in st["sessions"]:
            st["sessions"][session_id] = session

    state.update(fn)


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, ValueError):
            self._respond(400, b"")
            return

        if self.path == "/hook":
            self._handle_hook(body)
        elif self.path == "/focus":
            self._handle_focus(body)
        elif self.path == "/decision":
            self._handle_decision(body)
        else:
            self._respond(404, b"")

    def _handle_hook(self, body: dict):
        hook_type  = body.get("hook_event_name", "")
        session_id = body.get("session_id", "")
        iterm_id   = body.get("_iterm_session_id", "")

        if hook_type == "PermissionRequest":
            # Approval flow — implemented in Task 10
            self._respond(200, json.dumps({"behavior": "ask"}).encode())
            return

        _update_from_hook(hook_type, session_id, iterm_id, body)
        _broadcast_event.set()
        self._respond(200, b"")

    def _handle_focus(self, body: dict):
        iterm_id = body.get("iterm_session_id", "")
        state.update(lambda s: s.update({"active_iterm": iterm_id}))
        _broadcast_event.set()
        self._respond(200, b"")

    def _handle_decision(self, body: dict):
        # Approval flow — implemented in Task 10
        self._respond(200, b"")

    def _respond(self, code: int, body: bytes):
        self.send_response(code)
        if body:
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # suppress default request logging


def make_server(port: int) -> http.server.HTTPServer:
    server = http.server.HTTPServer(("", port), _Handler)
    return server


def _broadcaster_loop():
    while True:
        triggered = _broadcast_event.wait(timeout=config.BROADCASTER_DEBOUNCE_S)
        if triggered:
            _broadcast_event.clear()
        st = state.read()
        print(f"[broadcast] mood={st['mood']} sessions={list(st['sessions'].keys())}", flush=True)


def main():
    srv = make_server(config.MAC_PORT)
    threading.Thread(target=_broadcaster_loop, daemon=True).start()
    print(f"[server] listening on port {config.MAC_PORT}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_server_hooks.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add mac/server.py tests/test_server_hooks.py tests/conftest.py
git commit -m "feat: HTTP server with non-blocking hook handling and focus endpoint"
```

---

### Task 6: `mac/server.py` — Scanner thread

**Files:**
- Modify: `mac/server.py`
- Create: `tests/test_server_scanner.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_server_scanner.py`:

```python
import json
import os
import sys
import time
import tempfile
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'mac'))

import state

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')

def test_scanner_thread_updates_tokens_in_state(tmp_path, monkeypatch):
    state.STATE_FILE = str(tmp_path / "state.json")

    # Prime state with a session ID that matches fixture data
    state.update(lambda s: s["sessions"].update({
        "session-aaa": {"iterm_id": "x1", "model": "", "started_at": 0,
                        "last_tool": "", "last_tool_ts": 0, "last_file": "", "current_task": ""}
    }))

    import config
    monkeypatch.setattr(config, "SCANNER_INTERVAL_S", 0.1)
    monkeypatch.setattr(config, "LOG_DIR", FIXTURES)

    import server
    t = threading.Thread(target=server._scanner_loop, daemon=True)
    t.start()
    time.sleep(0.5)

    result = state.read()
    assert result["tokens"]["input"] > 0
    assert result["tokens"]["cost_usd"] > 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_server_scanner.py -v
```

Expected: `AttributeError: module 'server' has no attribute '_scanner_loop'`

- [ ] **Step 3: Add scanner thread to `mac/server.py`**

Add these imports at the top of `server.py`:

```python
import scanner
```

Add `_scanner_loop` function before `main()`:

```python
def _scanner_loop():
    while True:
        time.sleep(config.SCANNER_INTERVAL_S)
        st = state.read()
        session_ids = set(st["sessions"].keys())
        if not session_ids:
            continue
        tokens = scanner.scan_sessions(config.LOG_DIR, session_ids)
        state.update(lambda s: s.update({"tokens": tokens}))
        _broadcast_event.set()
```

Update `main()` to start the scanner thread:

```python
def main():
    srv = make_server(config.MAC_PORT)
    threading.Thread(target=_scanner_loop, daemon=True).start()
    threading.Thread(target=_broadcaster_loop, daemon=True).start()
    print(f"[server] listening on port {config.MAC_PORT}", flush=True)
    srv.serve_forever()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_server_scanner.py -v
```

Expected: 1 test PASS.

- [ ] **Step 5: Commit**

```bash
git add mac/server.py tests/test_server_scanner.py
git commit -m "feat: scanner background thread updates token totals every 30s"
```

---

### Task 7: `hook.py` + `.claude/settings.json` — wire hooks to server

**Files:**
- Create: `hook.py`
- Create: `.claude/settings.json`

No automated tests here — validation is manual (trigger Claude Code, verify state.json).

- [ ] **Step 1: Create `hook.py`**

```python
#!/usr/bin/env python3
"""Thin hook relay. Installed to ~/.claudebox/hook.py. POSTs hook event to server."""
import json
import os
import sys
import urllib.request

payload = json.loads(sys.stdin.read())
payload["_iterm_session_id"] = os.environ.get("ITERM_SESSION_ID", "")

try:
    req = urllib.request.Request(
        "http://localhost:8081/hook",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    resp = urllib.request.urlopen(req, timeout=65)
    out = resp.read().decode().strip()
    if out:
        print(out)  # PermissionRequest decision → Claude Code reads stdout
except Exception:
    pass  # server not running: silent fail
```

- [ ] **Step 2: Install hook to `~/.claudebox/`**

```bash
mkdir -p ~/.claudebox
cp hook.py ~/.claudebox/hook.py
```

- [ ] **Step 3: Create `.claude/settings.json`**

```bash
mkdir -p .claude
```

Create `.claude/settings.json`:

```json
{
  "hooks": {
    "PermissionRequest": [{"hooks": [{"type": "command", "command": "python3 ~/.claudebox/hook.py", "timeout": 65}]}],
    "SessionStart":      [{"hooks": [{"type": "command", "command": "python3 ~/.claudebox/hook.py"}]}],
    "UserPromptSubmit":  [{"hooks": [{"type": "command", "command": "python3 ~/.claudebox/hook.py"}]}],
    "PostToolUse":       [{"matcher": "*", "hooks": [{"type": "command", "command": "python3 ~/.claudebox/hook.py"}]}],
    "Stop":              [{"hooks": [{"type": "command", "command": "python3 ~/.claudebox/hook.py"}]}],
    "Notification":      [{"hooks": [{"type": "command", "command": "python3 ~/.claudebox/hook.py"}]}],
    "SessionEnd":        [{"hooks": [{"type": "command", "command": "python3 ~/.claudebox/hook.py"}]}]
  }
}
```

- [ ] **Step 4: Start the server and run a manual smoke test**

In one terminal:
```bash
cd mac && python3 server.py
```

In another terminal, open a Claude Code session in this directory. Send a message and use a tool.

Expected server output:
```
[server] listening on port 8081
[broadcast] mood=sleeping sessions=['<your-session-id>']
[broadcast] mood=sleeping sessions=['<your-session-id>']
```

Expected `~/.claudebox/state.json` to contain your session ID with `last_tool` populated.

- [ ] **Step 5: Commit**

```bash
git add hook.py .claude/settings.json
git commit -m "feat: hook relay script and Claude Code settings.json"
```

---

### Task 8: `mac/focus_monitor.py` — iTerm2 focus tracking

**Files:**
- Create: `mac/focus_monitor.py`

Manual test only — requires iTerm2 running.

- [ ] **Step 1: Verify iTerm2 Python API is available**

```bash
python3 -c "import iterm2; print('OK')"
```

If `ModuleNotFoundError`: open iTerm2 → Scripts menu → Manage → Install Python Runtime. Then retry.

- [ ] **Step 2: Create `mac/focus_monitor.py`**

```python
#!/usr/bin/env python3
"""Watches iTerm2 for tab switches and notifies server of active session."""
import json
import sys
import urllib.request

import iterm2


def _notify(iterm_session_id: str) -> None:
    try:
        req = urllib.request.Request(
            "http://localhost:8081/focus",
            data=json.dumps({"iterm_session_id": iterm_session_id}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=3)
    except Exception as e:
        print(f"[focus_monitor] server unreachable: {e}", file=sys.stderr)


async def main(connection):
    async with iterm2.FocusMonitor(connection) as monitor:
        print("[focus_monitor] watching iTerm2 focus changes", flush=True)
        while True:
            update = await monitor.async_get_next_update()
            if update.selected_session_changed:
                session_id = update.selected_session_changed.session_id
                print(f"[focus_monitor] active session → {session_id}", flush=True)
                _notify(session_id)


iterm2.run_forever(main)
```

- [ ] **Step 3: Start focus_monitor and verify it works**

In a separate terminal (with server.py already running):
```bash
python3 mac/focus_monitor.py
```

Switch between iTerm2 tabs. Expected output per switch:
```
[focus_monitor] active session → w0t0p0:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

Check `~/.claudebox/state.json` — `active_iterm` should update on each tab switch.

- [ ] **Step 4: Commit**

```bash
git add mac/focus_monitor.py
git commit -m "feat: iTerm2 focus monitor updates active session on tab switch"
```

---

### Task 9: `mac/server.py` — Approval flow (PermissionRequest)

**Files:**
- Modify: `mac/server.py`
- Create: `tests/test_server_approval.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_server_approval.py`:

```python
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

def test_approval_decision_resolves_pending_request(tmp_path, unused_tcp_port, monkeypatch):
    state.STATE_FILE = str(tmp_path / "state.json")
    import config
    monkeypatch.setattr(config, "APPROVAL_REQUIRED", ["Bash"])
    monkeypatch.setattr(config, "K10_IP", "127.0.0.1")
    monkeypatch.setattr(config, "K10_PORT", unused_tcp_port + 1)  # K10 not running — expect graceful fallback
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_server_approval.py -v
```

Expected: tests fail because `_handle_permission_request` currently returns `{"behavior": "ask"}` for everything.

- [ ] **Step 3: Add approval queue and full PermissionRequest handling to `mac/server.py`**

`queue`, `uuid`, and `urllib.request` are already imported from Task 5. Add module-level approval state after `_broadcast_event`:

```python
_pending_approvals: dict = {}  # request_id -> queue.Queue
_approval_lock = threading.Lock()
```

Replace the `_handle_hook` method's PermissionRequest stub with a call to the real handler, and add `_handle_permission_request` as a new method on `_Handler`:

```python
def _handle_hook(self, body: dict):
    hook_type  = body.get("hook_event_name", "")
    session_id = body.get("session_id", "")
    iterm_id   = body.get("_iterm_session_id", "")

    if hook_type == "PermissionRequest":
        self._handle_permission_request(body, session_id, iterm_id)
        return

    _update_from_hook(hook_type, session_id, iterm_id, body)
    _broadcast_event.set()
    self._respond(200, b"")

def _handle_permission_request(self, body: dict, session_id: str, iterm_id: str):
    tool = body.get("tool_name", "")

    # Tools on the auto-allow list never need approval
    if tool in config.AUTO_ALLOW:
        self._respond(200, json.dumps({"behavior": "allow"}).encode())
        return

    # Tools not in APPROVAL_REQUIRED pass through
    if tool not in config.APPROVAL_REQUIRED:
        self._respond(200, json.dumps({"behavior": "allow"}).encode())
        return

    # Check if this is the active iTerm2 session
    st = state.read()
    active_iterm = st.get("active_iterm", "")
    session_iterm = st.get("sessions", {}).get(session_id, {}).get("iterm_id", "")

    if session_iterm != active_iterm or not active_iterm:
        self._respond(200, json.dumps({"behavior": "ask"}).encode())
        return

    # Active session — route to K10
    request_id = str(uuid.uuid4())
    response_q: queue.Queue = queue.Queue()

    with _approval_lock:
        _pending_approvals[request_id] = response_q

    approve_payload = {
        "request_id": request_id,
        "tool": tool,
        "command": body.get("tool_input", {}).get("command", "")
                   or body.get("tool_input", {}).get("path", ""),
        "countdown_seconds": config.APPROVAL_TIMEOUT_S,
    }

    try:
        req = urllib.request.Request(
            f"http://{config.K10_IP}:{config.K10_PORT}/approve",
            data=json.dumps(approve_payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print(f"[approval] K10 unreachable: {e}", flush=True)
        with _approval_lock:
            _pending_approvals.pop(request_id, None)
        self._respond(200, json.dumps({"behavior": "ask"}).encode())
        return

    try:
        decision = response_q.get(timeout=config.APPROVAL_TIMEOUT_S)
        behavior = "allow" if decision in ("allow", "always_allow") else "deny"
    except queue.Empty:
        behavior = "ask"
    finally:
        with _approval_lock:
            _pending_approvals.pop(request_id, None)

    self._respond(200, json.dumps({"behavior": behavior}).encode())
```

Replace the `_handle_decision` stub:

```python
def _handle_decision(self, body: dict):
    request_id = body.get("request_id", "")
    decision   = body.get("decision", "deny")
    with _approval_lock:
        q = _pending_approvals.get(request_id)
    if q:
        q.put(decision)
    self._respond(200, b"")
```

`urllib.request` is already imported from Task 5.

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_server_approval.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add mac/server.py tests/test_server_approval.py
git commit -m "feat: PermissionRequest approval flow with K10 routing and queue"
```

---

## Phase 2: K10 Firmware

> **Note:** K10 MicroPython code cannot be unit-tested on the Mac. Each task includes a manual on-device verification step. Flash firmware before starting Phase 2 (UNIHIKER K10 MicroPython firmware — see spec hardware reference section).
>
> **Pin reference:** Verify I2C SDA/SCL pins and NeoPixel pin against the UNIHIKER K10 pinout at https://www.unihiker.com/wiki/K10 before running sensor and RGB tasks.

---

### Task 10: K10 boot — WiFi + HTTP server skeleton

**Files:**
- Create: `k10/device/secrets_example.py`
- Create: `k10/device/secrets.py` (gitignored)
- Create: `k10/device/config.py`
- Create: `k10/device/main.py`

- [ ] **Step 1: Add `k10/device/secrets.py` to `.gitignore`**

Append to `.gitignore`:

```
k10/device/secrets.py
```

- [ ] **Step 2: Create `k10/device/secrets_example.py`**

```python
WIFI_SSID     = "your-network-name"
WIFI_PASSWORD = "your-password"
```

- [ ] **Step 3: Create `k10/device/secrets.py`** with your real credentials.

- [ ] **Step 4: Create `k10/device/config.py`**

```python
MAC_HOST = "192.168.x.x"   # your Mac's IP on local network
MAC_PORT = 8081
HTTP_PORT = 8080
```

- [ ] **Step 5: Create `k10/device/main.py`**

```python
import network
import socket
import json
import time
import secrets
import config

_state = {
    "session": {"active": False, "model": "", "duration_minutes": 0,
                "current_task": "", "last_tool": "", "last_file": ""},
    "tokens": {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0, "cost_usd": 0.0},
    "mood": "sleeping",
    "mood_score": 0.0,
    "environment": {"temp_c": 0.0, "humidity_pct": 0.0, "light_lux": 0.0},
}


def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(secrets.WIFI_SSID, secrets.WIFI_PASSWORD)
        for _ in range(20):
            if wlan.isconnected():
                break
            time.sleep(1)
    return wlan.isconnected(), wlan.ifconfig()[0]


def parse_request(conn):
    request = b""
    conn.settimeout(3.0)
    try:
        while True:
            chunk = conn.recv(1024)
            if not chunk:
                break
            request += chunk
            if b"\r\n\r\n" in request:
                header_end = request.index(b"\r\n\r\n") + 4
                # Read Content-Length more if needed
                headers_raw = request[:header_end].decode("utf-8", "ignore")
                content_length = 0
                for line in headers_raw.split("\r\n"):
                    if line.lower().startswith("content-length:"):
                        content_length = int(line.split(":")[1].strip())
                body_so_far = request[header_end:]
                while len(body_so_far) < content_length:
                    body_so_far += conn.recv(1024)
                return headers_raw, body_so_far
    except OSError:
        pass
    return "", b""


def send_response(conn, status, body=b"", content_type="application/json"):
    status_line = f"HTTP/1.1 {status}\r\n"
    headers = (
        f"Content-Type: {content_type}\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n\r\n"
    )
    conn.sendall((status_line + headers).encode() + body)


def handle_request(conn):
    headers_raw, body_bytes = parse_request(conn)
    if not headers_raw:
        return

    lines = headers_raw.split("\r\n")
    method, path = lines[0].split(" ")[:2]

    if method == "GET" and path == "/sensors":
        from sensors import read_sensors
        data = read_sensors()
        _state["environment"] = data
        send_response(conn, "200 OK", json.dumps(data).encode())

    elif method == "POST" and path == "/update":
        payload = json.loads(body_bytes)
        _state.update(payload)
        from display import render
        render(_state)
        from rgb import set_mood
        set_mood(_state["mood"])
        send_response(conn, "200 OK")

    elif method == "POST" and path == "/approve":
        payload = json.loads(body_bytes)
        from approval import show_approval
        show_approval(payload, config.MAC_HOST, config.MAC_PORT)
        send_response(conn, "200 OK")

    else:
        send_response(conn, "404 Not Found")


def start_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("", config.HTTP_PORT))
    s.listen(3)
    print(f"[k10] HTTP server on port {config.HTTP_PORT}", flush=True)
    while True:
        try:
            conn, addr = s.accept()
            try:
                handle_request(conn)
            finally:
                conn.close()
        except Exception as e:
            print(f"[k10] request error: {e}", flush=True)


def boot():
    print("[k10] booting...", flush=True)
    connected, ip = connect_wifi()
    if not connected:
        print("[k10] WiFi failed", flush=True)
        return
    print(f"[k10] WiFi connected, IP: {ip}", flush=True)
    start_server()


boot()
```

- [ ] **Step 6: Deploy to K10 and verify via Pymakr**

Use Pymakr (VS Code extension) to sync `k10/device/` to the K10. Open the Pymakr REPL. Expected output on boot:

```
[k10] booting...
[k10] WiFi connected, IP: 192.168.x.x
[k10] HTTP server on port 8080
```

From Mac:
```bash
curl http://<K10_IP>:8080/sensors
```

Expected: connection refused (sensors.py not yet implemented). That's OK — the HTTP server is running.

- [ ] **Step 7: Commit**

```bash
git add k10/ .gitignore
git commit -m "feat: K10 WiFi boot and HTTP server skeleton"
```

---

### Task 11: K10 `sensors.py` — AHT20 + LTR303ALS

**Files:**
- Create: `k10/device/sensors.py`

- [ ] **Step 1: Create `k10/device/sensors.py`**

```python
from machine import I2C, Pin
import time

# Verify these pin numbers against UNIHIKER K10 pinout before running
_i2c = I2C(0, scl=Pin(9), sda=Pin(8), freq=100_000)

_AHT20_ADDR  = 0x38
_LTR303_ADDR = 0x29


def _aht20_read():
    _i2c.writeto(_AHT20_ADDR, bytes([0xAC, 0x33, 0x00]))
    time.sleep_ms(80)
    data = _i2c.readfrom(_AHT20_ADDR, 6)
    raw_hum  = ((data[1] << 12) | (data[2] << 4) | (data[3] >> 4))
    raw_temp = (((data[3] & 0x0F) << 16) | (data[4] << 8) | data[5])
    humidity = (raw_hum  / 0x100000) * 100
    temp     = (raw_temp / 0x100000) * 200 - 50
    return round(temp, 1), round(humidity, 1)


def _ltr303_init():
    try:
        _i2c.writeto(_LTR303_ADDR, bytes([0x80, 0x01]))  # active mode
        time.sleep_ms(100)
    except Exception:
        pass


def _ltr303_read():
    try:
        data = _i2c.readfrom_mem(_LTR303_ADDR, 0x88, 4)
        ch1 = (data[1] << 8) | data[0]
        ch0 = (data[3] << 8) | data[2]
        lux = ch0 if ch0 > 0 else 0
        return float(lux)
    except Exception:
        return 0.0


_ltr303_init()


def read_sensors() -> dict:
    try:
        temp, humidity = _aht20_read()
    except Exception:
        temp, humidity = 0.0, 0.0
    lux = _ltr303_read()
    return {"temp_c": temp, "humidity_pct": humidity, "light_lux": lux}
```

- [ ] **Step 2: Deploy and verify on device**

Sync to K10 via Pymakr. From Mac:

```bash
curl http://<K10_IP>:8080/sensors
```

Expected:
```json
{"temp_c": 27.3, "humidity_pct": 62.1, "light_lux": 289.0}
```

Adjust `scl` and `sda` pin numbers in `sensors.py` if readings are 0.0 or you get an OSError. Check UNIHIKER K10 pinout docs.

- [ ] **Step 3: Commit**

```bash
git add k10/device/sensors.py
git commit -m "feat: K10 AHT20 temp/humidity and LTR303 light sensor"
```

---

### Task 12: K10 `display.py` — dashboard layout

**Files:**
- Create: `k10/device/display.py`

> **Note:** The UNIHIKER K10 display library may use `unihiker`, `lcd`, or `st7789` depending on the MicroPython firmware version. Verify the import with `help('modules')` in the Pymakr REPL before running.

- [ ] **Step 1: Verify display library in Pymakr REPL**

```python
help('modules')
```

Look for: `unihiker`, `lcd`, `st7789`, or `ili9341`. Use whichever is available.

- [ ] **Step 2: Create `k10/device/display.py`**

This implementation uses the `unihiker` library (adjust import if your firmware differs):

```python
try:
    from unihiker import GUI
    _gui = GUI()
    _USE_UNIHIKER = True
except ImportError:
    _USE_UNIHIKER = False

MOOD_EMOJI = {
    "happy":    "😊",
    "neutral":  "😐",
    "tired":    "😓",
    "stressed": "😰",
    "sleeping": "😴",
}


def render(state: dict):
    if not _USE_UNIHIKER:
        _render_console(state)
        return
    _render_gui(state)


def _render_gui(state: dict):
    _gui.clear()

    session = state.get("session", {})
    tokens  = state.get("tokens", {})
    env     = state.get("environment", {})
    mood    = state.get("mood", "sleeping")
    dur     = session.get("duration_minutes", 0)
    emoji   = MOOD_EMOJI.get(mood, "😐")

    # Top bar: mood emoji + duration
    _gui.draw_text(text=f"{emoji} {mood.capitalize()}  {dur}m",
                   x=8, y=8, font_size=18, color="#FFFFFF")
    _gui.draw_line(x_start=0, y_start=32, x_end=320, y_end=32, color="#444444")

    # Task section
    tool = session.get("last_tool", "")
    file = session.get("last_file", "")
    task = session.get("current_task", "Waiting...")[:38]
    model = session.get("model", "")
    _gui.draw_text(text=f"{tool}  {file}"[:42], x=8, y=40, font_size=14, color="#AAAAAA")
    _gui.draw_text(text=task, x=8, y=60, font_size=14, color="#FFFFFF")
    _gui.draw_text(text=model, x=8, y=80, font_size=12, color="#888888")
    _gui.draw_line(x_start=0, y_start=100, x_end=320, y_end=100, color="#444444")

    # Token section
    inp = tokens.get("input", 0)
    out = tokens.get("output", 0)
    cw  = tokens.get("cache_write", 0)
    cr  = tokens.get("cache_read", 0)
    cost = tokens.get("cost_usd", 0.0)
    _gui.draw_text(text=f"In: {inp//1000}K  Out: {out//1000}K",
                   x=8, y=108, font_size=14, color="#CCCCCC")
    _gui.draw_text(text=f"Cache ↑{cw//1000}K ↓{cr//1000}K  ${cost:.3f}",
                   x=8, y=128, font_size=14, color="#CCCCCC")
    _gui.draw_line(x_start=0, y_start=150, x_end=320, y_end=150, color="#444444")

    # Environment bar
    temp = env.get("temp_c", 0.0)
    hum  = env.get("humidity_pct", 0.0)
    lux  = env.get("light_lux", 0.0)
    _gui.draw_text(text=f"{temp}°C  {hum}%RH  {lux:.0f}lx",
                   x=8, y=158, font_size=13, color="#888888")


def _render_console(state: dict):
    mood = state.get("mood", "sleeping")
    emoji = MOOD_EMOJI.get(mood, "?")
    task = state.get("session", {}).get("current_task", "")
    cost = state.get("tokens", {}).get("cost_usd", 0.0)
    print(f"[display] {emoji} {mood} | {task[:30]} | ${cost:.3f}", flush=True)
```

- [ ] **Step 3: Deploy and verify**

Sync to K10. From Mac, send a test update payload:

```bash
curl -X POST http://<K10_IP>:8080/update \
  -H "Content-Type: application/json" \
  -d '{
    "session": {"active": true, "model": "claude-sonnet-4-6", "duration_minutes": 5,
                "current_task": "Testing display", "last_tool": "Edit", "last_file": "main.py"},
    "tokens": {"input": 30000, "output": 5000, "cache_write": 2000, "cache_read": 10000, "cost_usd": 0.21},
    "mood": "neutral",
    "mood_score": 0.35,
    "environment": {"temp_c": 27.3, "humidity_pct": 62.0, "light_lux": 289.0}
  }'
```

Expected: K10 screen shows the layout with session data.

- [ ] **Step 4: Commit**

```bash
git add k10/device/display.py
git commit -m "feat: K10 dashboard display layout"
```

---

### Task 13: K10 `rgb.py` — mood-based WS2812 LEDs

**Files:**
- Create: `k10/device/rgb.py`

> **Note:** Verify the NeoPixel pin number and LED count against UNIHIKER K10 hardware docs.

- [ ] **Step 1: Create `k10/device/rgb.py`**

```python
from neopixel import NeoPixel
from machine import Pin
import time

# Verify pin number against UNIHIKER K10 pinout
_PIN_NUM  = 48
_NUM_LEDS = 3
_np = NeoPixel(Pin(_PIN_NUM), _NUM_LEDS)

_MOOD_COLORS = {
    "happy":    (0, 180, 0),    # green
    "neutral":  (0, 0, 180),    # blue
    "tired":    (180, 140, 0),  # yellow
    "stressed": (180, 0, 0),    # red
    "sleeping": (120, 120, 120),# white-ish
}

_PULSE_MOODS   = {"happy", "stressed"}
_BREATHE_MOODS = {"sleeping"}

_current_mood  = "sleeping"
_running       = False


def _fill(color):
    for i in range(_NUM_LEDS):
        _np[i] = color
    _np.write()


def set_mood(mood: str):
    global _current_mood
    color = _MOOD_COLORS.get(mood, _MOOD_COLORS["neutral"])

    if mood != _current_mood:
        _beep()

    _current_mood = mood

    if mood in _BREATHE_MOODS:
        _breathe_once(color)
    elif mood in _PULSE_MOODS:
        _pulse_once(color)
    else:
        _fill(color)


def _breathe_once(color):
    for step in list(range(0, 100, 5)) + list(range(100, 0, -5)):
        factor = step / 100
        _fill(tuple(int(c * factor) for c in color))
        time.sleep_ms(30)


def _pulse_once(color):
    for _ in range(3):
        _fill(color)
        time.sleep_ms(150)
        _fill((0, 0, 0))
        time.sleep_ms(150)
    _fill(color)


def _beep():
    try:
        from machine import PWM
        # Verify speaker pin against UNIHIKER K10 pinout
        buzzer = PWM(Pin(2), freq=880, duty=512)
        time.sleep_ms(80)
        buzzer.deinit()
    except Exception:
        pass
```

- [ ] **Step 2: Deploy and verify**

Sync to K10. From Mac:

```bash
curl -X POST http://<K10_IP>:8080/update \
  -H "Content-Type: application/json" \
  -d '{"mood": "happy", "session": {}, "tokens": {}, "environment": {}}'
```

Expected: K10 RGB LEDs pulse green.

Repeat with `"mood": "stressed"` → red pulsing. `"mood": "sleeping"` → white breathing.

- [ ] **Step 3: Commit**

```bash
git add k10/device/rgb.py
git commit -m "feat: K10 WS2812 RGB mood colors with pulse/breathe patterns"
```

---

### Task 14: K10 `approval.py` — full-screen Y/N touch UI

**Files:**
- Create: `k10/device/approval.py`

- [ ] **Step 1: Create `k10/device/approval.py`**

```python
import json
import time
import urllib.request

try:
    from unihiker import GUI
    _gui = GUI()
    _USE_UNIHIKER = True
except ImportError:
    _USE_UNIHIKER = False

from rgb import set_mood, _fill


def _post_decision(mac_host: str, mac_port: int, request_id: str, decision: str):
    try:
        body = json.dumps({
            "request_id": request_id,
            "decision": decision,
            "device": "k10",
        }).encode()
        req = urllib.request.Request(
            f"http://{mac_host}:{mac_port}/decision",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print(f"[approval] failed to send decision: {e}", flush=True)


def show_approval(payload: dict, mac_host: str, mac_port: int):
    request_id      = payload.get("request_id", "")
    tool            = payload.get("tool", "")
    command         = payload.get("command", "")[:48]
    countdown       = payload.get("countdown_seconds", 60)

    if not _USE_UNIHIKER:
        print(f"[approval] {tool}: {command} — approve? (auto-deny in {countdown}s)", flush=True)
        _post_decision(mac_host, mac_port, request_id, "deny")
        return

    _gui.clear()
    _gui.draw_rect(x=0, y=0, w=320, h=240, color="#FFCC00")  # yellow background

    _gui.draw_text(text="⚠️  APPROVAL REQUIRED", x=20, y=15, font_size=18, color="#000000")
    _gui.draw_line(x_start=0, y_start=45, x_end=320, y_end=45, color="#CC9900")
    _gui.draw_text(text=f"Tool: {tool}", x=12, y=58, font_size=16, color="#000000")
    _gui.draw_text(text=command, x=12, y=82, font_size=14, color="#333333")

    # Countdown bar placeholder (updated in loop)
    _gui.draw_rect(x=12, y=118, w=296, h=16, color="#CC9900")

    # YES button
    _gui.draw_rect(x=12,  y=155, w=130, h=60, color="#00AA00")
    _gui.draw_text(text="YES", x=52, y=175, font_size=22, color="#FFFFFF")

    # NO button
    _gui.draw_rect(x=178, y=155, w=130, h=60, color="#CC0000")
    _gui.draw_text(text="NO",  x=222, y=175, font_size=22, color="#FFFFFF")

    # Urgent yellow flashing RGB
    set_mood("stressed")

    decision = None
    start = time.time()

    while time.time() - start < countdown:
        elapsed  = time.time() - start
        remaining = max(0, countdown - int(elapsed))
        bar_w    = int(296 * remaining / countdown)

        _gui.draw_rect(x=12, y=118, w=296, h=16, color="#FFCC00")  # clear bar area
        _gui.draw_rect(x=12, y=118, w=bar_w, h=16, color="#CC9900")
        _gui.draw_text(text=f"{remaining}s", x=148, y=119, font_size=13, color="#000000")

        # Poll for touch — unihiker touch API (verify method name in docs)
        try:
            touch = _gui.get_touch()
            if touch:
                tx, ty = touch["x"], touch["y"]
                if 12 <= tx <= 142 and 155 <= ty <= 215:
                    decision = "allow"
                    break
                if 178 <= tx <= 308 and 155 <= ty <= 215:
                    decision = "deny"
                    break
        except Exception:
            pass

        time.sleep_ms(100)

    # Restore display
    _gui.clear()
    _fill((0, 0, 0))

    _post_decision(mac_host, mac_port, request_id, decision or "deny")
```

- [ ] **Step 2: Deploy and test approval UI**

Sync to K10. From Mac, simulate an approval request:

```bash
curl -X POST http://<K10_IP>:8080/approve \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "test-001",
    "tool": "Bash",
    "command": "rm -rf dist/",
    "countdown_seconds": 30
  }'
```

Expected: K10 shows yellow full-screen takeover with YES/NO buttons. Tap YES. On Mac:

```bash
# In another terminal, watch for the decision POST arriving at server
python3 mac/server.py  # should log the decision
```

Expected server to receive `POST /decision` with `{"decision": "allow", "device": "k10"}`.

- [ ] **Step 3: Commit**

```bash
git add k10/device/approval.py
git commit -m "feat: K10 full-screen Y/N touch approval UI with countdown"
```

---

## Phase 3: Integration

### Task 15: Complete broadcaster — pull sensors + push to K10

**Files:**
- Modify: `mac/server.py`

- [ ] **Step 1: Replace the console-only broadcaster with the real K10 push**

Replace the `_broadcaster_loop` function in `mac/server.py`:

```python
def _broadcaster_loop():
    while True:
        triggered = _broadcast_event.wait(timeout=config.BROADCASTER_DEBOUNCE_S)
        if triggered:
            _broadcast_event.clear()

        st = state.read()

        # Pull sensors from K10
        env = {"temp_c": 0.0, "humidity_pct": 0.0, "light_lux": 0.0}
        try:
            resp = urllib.request.urlopen(
                f"http://{config.K10_IP}:{config.K10_PORT}/sensors",
                timeout=3
            )
            env = json.loads(resp.read())
        except Exception as e:
            print(f"[broadcaster] sensor pull failed: {e}", flush=True)

        # Find the active session
        active_iterm = st.get("active_iterm", "")
        active_session = {}
        for sid, sdata in st["sessions"].items():
            if sdata.get("iterm_id") == active_iterm:
                active_session = sdata
                break

        # Compute idle time
        last_tool_ts = active_session.get("last_tool_ts", 0)
        idle_minutes = (time.time() - last_tool_ts) / 60 if last_tool_ts else 999

        # Compute mood
        mood_name, mood_score = mood_mod.compute_mood(st["tokens"], idle_minutes)

        # Update state with mood
        state.update(lambda s: s.update({"mood": mood_name, "mood_score": mood_score}))

        started_at = active_session.get("started_at", int(time.time()))
        duration_minutes = int((time.time() - started_at) / 60)

        payload = {
            "session": {
                "active": bool(st["sessions"]),
                "model": active_session.get("model", ""),
                "duration_minutes": duration_minutes,
                "current_task": active_session.get("current_task", ""),
                "last_tool": active_session.get("last_tool", ""),
                "last_file": active_session.get("last_file", ""),
            },
            "tokens": st["tokens"],
            "mood": mood_name,
            "mood_score": mood_score,
            "environment": env,
        }

        try:
            req = urllib.request.Request(
                f"http://{config.K10_IP}:{config.K10_PORT}/update",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
            print(f"[broadcaster] pushed mood={mood_name} cost=${st['tokens']['cost_usd']:.3f}", flush=True)
        except Exception as e:
            print(f"[broadcaster] push failed: {e}", flush=True)
```

- [ ] **Step 2: Add `json` and `time` imports to top of `server.py`** (already there from earlier — verify)

- [ ] **Step 3: Run the full loop manually**

Start server and focus_monitor:

```bash
# Terminal 1
cd mac && python3 server.py

# Terminal 2
python3 mac/focus_monitor.py
```

Open a Claude Code session in this repo. Send a message, run a tool.

Expected K10: screen updates with your session data, mood, and env readings. RGB changes color.

- [ ] **Step 4: Run full test suite to confirm nothing regressed**

```bash
python -m pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add mac/server.py
git commit -m "feat: broadcaster pushes live dashboard payload to K10"
```

---

### Task 16: Approval flow integration test

Manual end-to-end test — no automated test for this.

- [ ] **Step 1: Ensure `APPROVAL_REQUIRED = ["Bash"]` in `mac/config.py`**

- [ ] **Step 2: Start server and focus_monitor**

```bash
# Terminal 1
cd mac && python3 server.py

# Terminal 2
python3 mac/focus_monitor.py
```

- [ ] **Step 3: In a Claude Code session in this iTerm2 tab, run a Bash command**

Example prompt: `Run ls -la in the terminal`

Expected sequence:
1. Claude Code triggers PermissionRequest hook
2. hook.py POSTs to `localhost:8081/hook` and blocks
3. server.py checks: is this the active iTerm2 session? Yes.
4. server.py POSTs to K10 `/approve` with tool=Bash, command=`ls -la`
5. K10 shows yellow full-screen approval UI
6. Tap **YES** on K10
7. K10 POSTs `{"decision": "allow"}` to `localhost:8081/decision`
8. server.py unblocks, returns `{"behavior": "allow"}` to hook.py
9. hook.py prints to stdout → Claude Code proceeds to run `ls -la`

- [ ] **Step 4: Test background session fallback**

Open a second Claude Code session in a different iTerm2 tab. Switch focus back to the first tab (via focus_monitor). In the second (background) tab, trigger a Bash command.

Expected: no K10 approval UI. Claude Code shows native CLI prompt in that terminal.

- [ ] **Step 5: Test timeout fallback**

In the active session, trigger a Bash command but do NOT tap the K10. Wait 60 seconds.

Expected: K10 UI dismisses itself. Claude Code shows native CLI prompt (behavior=ask returned).

- [ ] **Step 6: Commit final integration notes**

```bash
git add .
git commit -m "chore: integration test complete, full ClaudeBox Mac+K10 loop verified"
```

---

## Appendix: Running ClaudeBox

**Start the Mac side:**

```bash
# Terminal A — main server
python3 mac/server.py

# Terminal B — iTerm2 focus watcher
python3 mac/focus_monitor.py
```

**Hooks are always active** once `.claude/settings.json` is in place and `~/.claudebox/hook.py` is installed.

**K10 boots automatically** on power — WiFi connects and HTTP server starts.

**Config to tune:**
- `SESSION_TYPICAL_MAX` in `mac/config.py` — adjust after a week of use if mood feels wrong
- `APPROVAL_REQUIRED` — add `"Write"` if you want file-write approvals too
