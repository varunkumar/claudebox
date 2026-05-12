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
