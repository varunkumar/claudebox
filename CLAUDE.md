# ClaudeBox: Developer Notes

## What this project is

ClaudeBox is a physical ambient dashboard for Claude Code. A Mac daemon ingests Claude Code hook events, scans JSONL logs for token usage, and pushes status to a UNIHIKER K10 over WiFi. The K10 renders session state, drives RGB mood LEDs, reads environmental sensors, and presents a touch-based approval UI for Bash commands.

## Architecture

```
Claude Code -> hook.py -> mac/server.py (port 8081)
                              |
                    +---------+-----------+
               state.json          K10 (WiFi)
                              |
                    +---------+-----------+
               /update (push)      /sensors (pull)
               /approve (push)     /decision (K10->Mac)
```

- **`hook.py`**: thin HTTP client installed to `~/.claudebox/hook.py`. Posts every Claude Code hook event to `localhost:8081/hook`. Never starts a server.
- **`mac/server.py`**: single persistent daemon. Handles hooks, approval flow, broadcasts to K10.
- **`mac/scanner.py`**: reads `~/.claude/projects/**/*.jsonl` to aggregate token counts and cost.
- **`mac/mood.py`**: maps token burn rate + idle time to a mood name and score.
- **`mac/focus_monitor.py`**: iTerm2 FocusMonitor daemon. Posts active session id to `/focus`.
- **`mac/state.py`**: thread-safe JSON state store at `~/.claudebox/state.json`.
- **`k10/device/`**: MicroPython firmware. Raw socket HTTP server, no frameworks.

## Key constraints

- **MicroPython on K10**: no `urllib.request`, no `threading`, no `asyncio`. Use `socket` directly and keep everything single-threaded. The HTTP server in `main.py` is a blocking accept loop.
- **No MCP, no API calls from K10**: the device is dumb. It displays what the Mac pushes.
- **Thread safety on Mac**: all state reads/writes go through `state.update()` / `state.read()` which hold a `threading.Lock`. Never read `state.STATE_FILE` directly.
- **ThreadingHTTPServer**: `server.py` uses `_ThreadingHTTPServer` (not plain `HTTPServer`) so the approval handler can block on `Queue.get()` while still accepting the K10's `/decision` callback on a separate thread.

## Running tests

```bash
python -m pytest tests/ -v
```

Tests live in `tests/` and cover the Mac side only (state, scanner, mood, hooks, approval round-trips). K10 firmware is validated on-device.

## Configuration

`mac/config.py` is gitignored. Copy from `config.example.py` and fill in:
- `K10_IP`: static IP assigned to K10 via router DHCP reservation
- WiFi credentials go in `k10/device/secrets.py` (also gitignored)

## Approval flow

1. Claude Code fires `PermissionRequest` hook -> `hook.py` -> `POST /hook`
2. Server checks `AUTO_ALLOW` -> allow immediately
3. Server checks `APPROVAL_REQUIRED` -> if not in list, allow
4. Server checks if requesting session matches focused iTerm2 tab -> if not, return `ask`
5. Server POSTs `/approve` to K10, blocks on `Queue.get(timeout=60)`
6. K10 shows touch UI, user taps YES/NO, K10 POSTs `/decision` back to Mac
7. Server resolves queue, returns `allow` or `deny` to Claude Code

## Broadcaster

`_broadcaster_loop` in `server.py` runs on a background thread. It wakes on `_broadcast_event` (debounced) or after `BROADCASTER_DEBOUNCE_S` seconds. When no sessions are active and nothing triggered the event, it skips the push so it does not hammer the K10 when Claude Code is idle.

## Adding a new hook type

1. Add handling in `_update_from_hook()` in `server.py`
2. Add the hook to `.claude/settings.json`
3. Add a test in `tests/test_server_hooks.py`

Do not add `Stop` or `Notification` hooks. They carry no useful state and would generate spurious K10 pushes.

## Mood thresholds

Defined in `mac/mood.py` as `_THRESHOLDS`. `SESSION_TYPICAL_MAX` in `mac/config.py` is the denominator. Tune it to your typical session size to calibrate when moods transition.
