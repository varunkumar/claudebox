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
