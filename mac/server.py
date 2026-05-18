import usage as usage_mod
import state
import scanner
import mood as mood_mod
import config
import http.server
import json
import os
import queue
import socketserver
import sys
import threading
import time
import urllib.request
import uuid

sys.path.insert(0, os.path.dirname(__file__))

_broadcast_event = threading.Event()
_pending_approvals: dict = {}
_approval_lock = threading.Lock()


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
        hook_type = body.get("hook_event_name", "")
        session_id = body.get("session_id", "")
        iterm_id = body.get("_iterm_session_id", "")

        if hook_type == "PermissionRequest":
            self._handle_permission_request(body, session_id, iterm_id)
            return

        _update_from_hook(hook_type, session_id, iterm_id, body)
        _broadcast_event.set()
        self._respond(200, b"")

    def _handle_permission_request(self, body: dict, session_id: str, iterm_id: str):
        tool = body.get("tool_name", "")
        print(
            f"[approval] PermissionRequest tool={tool} session={session_id[:8]} iterm={iterm_id[:16]}", flush=True)

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
        session_iterm = st.get("sessions", {}).get(
            session_id, {}).get("iterm_id", "")
        print(
            f"[approval] active_iterm={active_iterm[:16]} session_iterm={session_iterm[:24]} match={active_iterm and active_iterm in session_iterm}", flush=True)

        if not active_iterm or active_iterm not in session_iterm:
            print("[approval] session mismatch → ask", flush=True)
            self._respond(200, json.dumps({"behavior": "ask"}).encode())
            return

        # Active session — route to K10
        request_id = str(uuid.uuid4())
        response_q: queue.Queue = queue.Queue()
        print(
            f"[approval] routing request_id={request_id} tool={tool} session={session_id[:8]}", flush=True)

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
            urllib.request.urlopen(req, timeout=15)
        except Exception as e:
            print(f"[approval] K10 unreachable: {e}", flush=True)
            with _approval_lock:
                _pending_approvals.pop(request_id, None)
            self._respond(200, json.dumps({"behavior": "ask"}).encode())
            return

        try:
            decision = response_q.get(timeout=config.APPROVAL_TIMEOUT_S)
            behavior = "allow" if decision in (
                "allow", "always_allow") else "deny"
        except queue.Empty:
            behavior = "ask"
        finally:
            with _approval_lock:
                _pending_approvals.pop(request_id, None)

        self._respond(200, json.dumps({"behavior": behavior}).encode())

    def _handle_focus(self, body: dict):
        iterm_id = body.get("iterm_session_id", "")
        st = state.read()
        has_session = any(
            iterm_id in sdata.get("iterm_id", "")
            for sdata in st["sessions"].values()
        )
        if has_session:
            state.update(lambda s: s.update({"active_iterm": iterm_id}))
            _broadcast_event.set()
        self._respond(200, b"")

    def _handle_decision(self, body: dict):
        request_id = body.get("request_id", "")
        decision = body.get("decision", "deny")
        print(
            f"[approval] decision received request_id={request_id} decision={decision}", flush=True)
        with _approval_lock:
            q = _pending_approvals.get(request_id)
        if q:
            q.put(decision)
        else:
            print(
                f"[approval] no pending approval for request_id={request_id}", flush=True)
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


class _ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def make_server(port: int) -> http.server.HTTPServer:
    return _ThreadingHTTPServer(("", port), _Handler)


_USAGE_FETCH_INTERVAL_S = 1800
_last_usage_fetch_ts = 0.0


def _scanner_loop():
    global _last_usage_fetch_ts
    while True:
        time.sleep(config.SCANNER_INTERVAL_S)
        st = state.read()
        session_ids = set(st["sessions"].keys())
        if session_ids:
            tokens = scanner.scan_sessions(config.LOG_DIR, session_ids)
            state.update(lambda s: s.update({"tokens": tokens}))
        now = time.time()
        if now - _last_usage_fetch_ts >= _USAGE_FETCH_INTERVAL_S:
            usage = usage_mod.fetch_usage()
            if usage is not None:
                state.update(lambda s: s.update({
                    "five_hour_pct": usage["five_hour_pct"],
                    "weekly_pct": usage["seven_day_pct"],
                }))
            _last_usage_fetch_ts = now
        _broadcast_event.set()


_MIN_PUSH_INTERVAL_S = 5
_last_push_ts = 0.0


def _broadcaster_loop():
    global _last_push_ts
    while True:
        triggered = _broadcast_event.wait(
            timeout=config.BROADCASTER_DEBOUNCE_S)
        if triggered:
            _broadcast_event.clear()

        st = state.read()

        # Skip poll when nothing is active and nothing triggered
        if not triggered and not st.get("sessions"):
            continue

        # Rate-limit: don't push to K10 faster than _MIN_PUSH_INTERVAL_S
        now = time.time()
        if now - _last_push_ts < _MIN_PUSH_INTERVAL_S:
            continue

        # Find the active session (matches active_iterm)
        active_iterm = st.get("active_iterm", "")
        active_session = {}
        for sid, sdata in st["sessions"].items():
            if active_iterm and active_iterm in sdata.get("iterm_id", ""):
                active_session = sdata
                break

        # Compute idle time from last tool use
        last_tool_ts = active_session.get("last_tool_ts", 0)
        idle_minutes = (time.time() - last_tool_ts) / \
            60 if last_tool_ts else 999

        # Compute mood
        mood_name, mood_score = mood_mod.compute_mood(
            st["tokens"], idle_minutes)

        # Update mood in state
        state.update(lambda s: s.update(
            {"mood": mood_name, "mood_score": mood_score}))

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
            "five_hour_pct": st.get("five_hour_pct", 0.0),
            "weekly_pct": st.get("weekly_pct", 0.0),
            "mood": mood_name,
            "mood_score": mood_score,
            "context_pct": st["tokens"].get("context_pct", 0.0),
        }

        try:
            req = urllib.request.Request(
                f"http://{config.K10_IP}:{config.K10_PORT}/update",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=8)
            _last_push_ts = time.time()
            print(
                f"[broadcaster] pushed mood={mood_name} 5h={st.get('five_hour_pct', 0.0):.0%} week={st.get('weekly_pct', 0.0):.0%}", flush=True)
        except Exception as e:
            print(
                f"[broadcaster] push failed {config.K10_IP}:{config.K10_PORT}: {e}", flush=True)


def main():
    srv = make_server(config.MAC_PORT)
    threading.Thread(target=_scanner_loop, daemon=True).start()
    threading.Thread(target=_broadcaster_loop, daemon=True).start()
    print(f"[server] listening on port {config.MAC_PORT}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
