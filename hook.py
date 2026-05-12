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
