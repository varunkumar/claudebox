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
            with open(STATE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return _default()


def write(data: dict) -> None:
    with _lock:
        _write_locked(data)


def update(fn) -> None:
    with _lock:
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = _default()
        fn(data)
        _write_locked(data)


def _write_locked(data: dict) -> None:
    data["last_updated"] = int(time.time())
    os.makedirs(os.path.dirname(os.path.abspath(STATE_FILE)), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
