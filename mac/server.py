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
import scanner
import state

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
        hook_type  = body.get("hook_event_name", "")
        session_id = body.get("session_id", "")
        iterm_id   = body.get("_iterm_session_id", "")

        if hook_type == "PermissionRequest":
            # Approval flow — implemented in Task 9
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
        # Approval flow — implemented in Task 9
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


def _broadcaster_loop():
    while True:
        triggered = _broadcast_event.wait(timeout=config.BROADCASTER_DEBOUNCE_S)
        if triggered:
            _broadcast_event.clear()
        st = state.read()
        print(f"[broadcast] mood={st['mood']} sessions={list(st['sessions'].keys())}", flush=True)


def main():
    srv = make_server(config.MAC_PORT)
    threading.Thread(target=_scanner_loop, daemon=True).start()
    threading.Thread(target=_broadcaster_loop, daemon=True).start()
    print(f"[server] listening on port {config.MAC_PORT}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
