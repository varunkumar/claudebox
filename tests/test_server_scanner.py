import json
import os
import sys
import time
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
