# ClaudeBox — Mac + K10 Design Spec

**Date:** 2026-05-12
**Scope:** Mac host side + UNIHIKER K10 firmware. Cardputer Adv spec deferred (hardware arriving ~1 week).
**Status:** Approved for implementation

---

## 1. Overview

ClaudeBox is a physical ambient dashboard that surfaces Claude Code session state on a desk device. The UNIHIKER K10 (2.8" touch screen, RGB LEDs, sensors, speaker) sits on the desk and shows what Claude is doing, how much it has spent, and whether it needs approval to run a command — all without consuming any Claude tokens.

Data flows from Claude Code hooks and JSONL log files on the Mac to the K10 via HTTP. No MCP server, no Claude API calls from the device.

---

## 2. Goals

- Show active session state (task, tool, model, duration) on the K10 in real time
- Display token usage and cost estimate from JSONL logs
- Express session "mood" via RGB LEDs and emoji based on token burn rate
- Show environmental readings (temp, humidity, light) from K10 sensors
- Gate shell command execution behind a physical Y/N touch approval on the K10
- Follow the user's active iTerm2 tab — dashboard and approval always reflect the focused session

---

## 3. Non-Goals (this spec)

- Cardputer Adv firmware (separate spec)
- Voice interaction
- MCP server
- Any Claude API calls from devices
- Web UI or remote access
- Multiple physical K10 units

---

## 4. Architecture Overview

```
Claude Code sessions (iTerm2 tabs)
        │
        │ fires hooks via ~/.claude/settings.json
        ▼
Hook scripts  (thin curl one-liners, no state)
        │
        │ POST localhost:8081/hook  (non-blocking for most hooks)
        │ POST localhost:8081/hook  (BLOCKING for PermissionRequest)
        ▼
server.py  (single process, port 8081)
  ├── HTTP Server Thread      — receives /hook, /focus, /decision
  ├── Scanner Thread          — polls JSONL logs every 30s, updates tokens/cost
  ├── Broadcaster Thread      — pulls sensors, computes mood, POSTs to K10
  ├── Approval Queue          — threading.Queue, serializes PermissionRequest
  └── state.json              — shared state (threading.Lock)
        │
focus_monitor.py  (separate process)
  └── iTerm2 FocusMonitor API — fires on tab switch
        │ POST localhost:8081/focus
        ▼
        server.py updates active_iterm in state.json

server.py broadcaster
  ├── GET  k10:8080/sensors   — pulls temp/humidity/light
  ├── POST k10:8080/update    — pushes full dashboard payload
  └── POST k10:8080/approve   — pushes approval request (blocks hook until decision)

K10  (port 8080)
  ├── POST /update    — refresh display + RGB
  ├── POST /approve   — show full-screen Y/N UI
  ├── GET  /sensors   — return AHT20 + LTR303 readings
  └── POST to mac:8081/decision  — user tapped Y/N
```

---

## 5. Mac Components

### 5.1 `mac/server.py`

Single long-running process. Started manually (or via launchd). All Mac-side logic lives here except the iTerm2 focus watcher.

**Threads:**

| Thread | Role |
|--------|------|
| HTTP Server | Receives hook events, focus updates, device decisions |
| Scanner | Reads JSONL logs every 30s, updates token/cost in state |
| Broadcaster | Triggered by hook events and scanner; debounced 1s; pulls sensors, pushes payload to K10 |

**Endpoints:**

| Method | Path | Blocking | Description |
|--------|------|----------|-------------|
| POST | `/hook` | No (200 immediately), except PermissionRequest | Receives all Claude Code hook events |
| POST | `/focus` | No | Receives iTerm2 tab-switch events from focus_monitor.py |
| POST | `/decision` | No | Receives Y/N from K10 after approval |

**PermissionRequest flow inside `/hook`:**

1. Check `state.json["active_iterm"]` — does it match the session's `iterm_session_id`?
2. If **no match** (background session): return `{"behavior": "ask"}` immediately — Claude Code falls back to CLI prompt.
3. If **match** (active session):
   - Enqueue request with a unique `request_id`
   - POST `k10:8080/approve` with tool name + command/file
   - `Queue.get(timeout=60)` — blocks the HTTP response
   - On decision: return `{"behavior": "allow"}` or `{"behavior": "deny"}`
   - On timeout: return `{"behavior": "ask"}`

**Approval serialization:** The Queue ensures only one approval is in-flight on the device at a time. If a second active-session PermissionRequest arrives while one is pending, it waits in the Queue. The K10 shows one request at a time.

### 5.2 `mac/focus_monitor.py`

Separate process using the iTerm2 Python API (`iterm2` module, installed with iTerm2).

- Subscribes to `iterm2.FocusMonitor`
- On each focus change: reads the newly-active session's `iterm2.Session.session_id`
- POSTs `{ "iterm_session_id": "<id>" }` to `localhost:8081/focus`
- Server updates `state.json["active_iterm"]`

**SessionStart hook side:** On `SessionStart`, the hook script reads `$ITERM_SESSION_ID` from the environment and includes it in the hook POST body. Server saves it alongside the Claude Code `session_id` in `state.json["sessions"][session_id]["iterm_id"]`.

### 5.3 `mac/scanner.py`  (module, imported by server.py)

Adapted from `phuryn/claude-usage`. Pure stdlib.

- Scans `~/.claude/projects/**/*.jsonl` for entries matching the current day's active sessions
- Extracts per-entry: `message.usage.input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, `message.model`
- Aggregates across all active sessions (all `session_id`s in `state.json["sessions"]`)
- Calculates cost using the pricing table below
- Writes results into `state.json["tokens"]`

**Pricing (April 2026 API rates):**

| Model | Input | Output | Cache Write | Cache Read |
|-------|-------|--------|-------------|------------|
| claude-opus-4-6 | $6.15/MTok | $30.75/MTok | $7.69/MTok | $0.61/MTok |
| claude-sonnet-4-6 | $3.69/MTok | $18.45/MTok | $4.61/MTok | $0.37/MTok |
| claude-haiku-4-5 | $1.23/MTok | $6.15/MTok | $1.54/MTok | $0.12/MTok |

### 5.4 `mac/mood.py`  (module, imported by server.py)

```python
SESSION_TYPICAL_MAX = 150_000  # tune based on usage

def compute_mood(tokens: dict) -> tuple[str, float]:
    score = (tokens["input"] + tokens["output"]) / SESSION_TYPICAL_MAX
    if score < 0.20:   return "happy",   score
    if score < 0.50:   return "neutral",  score
    if score < 0.75:   return "tired",    score
    if score < 0.90:   return "stressed", score
    return "sleeping", score  # overridden by idle detection in broadcaster
```

Idle detection: if no `PostToolUse` or `UserPromptSubmit` hook has fired in >10 minutes across all sessions, mood is forced to `"sleeping"` regardless of score.

### 5.5 `mac/config.py`  (gitignored)

```python
K10_IP   = "192.168.x.x"   # set after router reservation
K10_PORT = 8080
MAC_PORT = 8081

STATE_FILE = "~/.claudebox/state.json"
LOG_DIR    = "~/.claude/projects"

APPROVAL_REQUIRED = ["Bash"]
AUTO_ALLOW        = ["Read", "Glob", "Grep", "LS", "WebSearch", "WebFetch"]

SESSION_TYPICAL_MAX = 150_000
IDLE_THRESHOLD_MINUTES = 10
BROADCASTER_DEBOUNCE_SECONDS = 1
SCANNER_INTERVAL_SECONDS = 30
APPROVAL_TIMEOUT_SECONDS = 60
```

`config.example.py` is committed; `config.py` is gitignored.

---

## 6. Hooks Configuration

`~/.claude/settings.json`:

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

`hook.py` (installed to `~/.claudebox/hook.py`):

```python
import sys, json, urllib.request, os

payload = json.loads(sys.stdin.read())
payload["_iterm_session_id"] = os.environ.get("ITERM_SESSION_ID", "")

req = urllib.request.Request(
    "http://localhost:8081/hook",
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json"},
    method="POST"
)
try:
    resp = urllib.request.urlopen(req, timeout=65)
    out = resp.read().decode()
    if out:
        print(out)   # PermissionRequest decision → Claude Code reads this
except Exception:
    pass  # server not running: silent fail, non-approval hooks are fire-and-forget
```

---

## 7. State Schema (`~/.claudebox/state.json`)

```json
{
  "active_iterm": "iterm_session_id_of_focused_tab",
  "sessions": {
    "<claude_session_id>": {
      "iterm_id": "<iterm_session_id>",
      "model": "claude-sonnet-4-6",
      "started_at": 1234567890,
      "last_tool": "Edit",
      "last_tool_ts": 1234567890,
      "last_file": "src/auth.py",
      "current_task": "first 120 chars of last UserPromptSubmit"
    }
  },
  "tokens": {
    "input": 45230,
    "output": 8920,
    "cache_write": 12000,
    "cache_read": 89000,
    "cost_usd": 0.34
  },
  "mood": "tired",
  "mood_score": 0.68,
  "last_updated": 1234567890
}
```

Active session for display = session whose `iterm_id` matches `active_iterm`.

---

## 8. Dashboard Payload (Mac → K10 `POST /update`)

```json
{
  "session": {
    "active": true,
    "model": "claude-sonnet-4-6",
    "duration_minutes": 23,
    "current_task": "Editing auth.py",
    "last_tool": "Edit",
    "last_file": "src/auth.py"
  },
  "tokens": {
    "input": 45230,
    "output": 8920,
    "cache_write": 12000,
    "cache_read": 89000,
    "cost_usd": 0.34
  },
  "mood": "tired",
  "mood_score": 0.68,
  "environment": {
    "temp_c": 28.5,
    "humidity_pct": 65,
    "light_lux": 342
  }
}
```

---

## 9. Approval Payload (Mac → K10 `POST /approve`)

```json
{
  "request_id": "uuid4",
  "tool": "Bash",
  "command": "rm -rf dist/",
  "countdown_seconds": 60
}
```

K10 shows full-screen takeover. On tap, POSTs back to `mac:8081/decision`:

```json
{
  "request_id": "uuid4",
  "decision": "allow",
  "device": "k10"
}
```

---

## 10. K10 Firmware

### 10.1 Boot sequence (`main.py`)

1. Connect to Wi-Fi (credentials in `secrets.py`, gitignored)
2. Start HTTP server on port 8080
3. Show "Waiting for session..." on display
4. RGB: white breathing (sleeping mood)

### 10.2 Endpoints

| Method | Path | Handler |
|--------|------|---------|
| POST | `/update` | Update local state, refresh display, update RGB |
| POST | `/approve` | Full-screen approval takeover |
| GET | `/sensors` | Return `{"temp_c": x, "humidity_pct": x, "light_lux": x}` |

### 10.3 Display layout (`display.py`)

```
┌─────────────────────────────┐  320×240
│  😓  Tired          23m     │  ← mood emoji + duration     (top bar)
├─────────────────────────────┤
│  Edit · src/auth.py         │  ← last tool + file          (task row)
│  Editing auth.py            │  ← current task snippet      (task row)
│  claude-sonnet-4-6          │  ← model                     (task row)
├─────────────────────────────┤
│  In: 45.2K  Out: 8.9K       │  ← token counts              (token row)
│  Cache: ↑12K ↓89K  $0.34   │  ← cache + cost              (token row)
├─────────────────────────────┤
│  28.5°C  65%RH  342 lux     │  ← env sensors               (env bar)
└─────────────────────────────┘
```

### 10.4 RGB mood (`rgb.py`)

| Mood | Color | Pattern |
|------|-------|---------|
| happy | Green | Pulsing |
| neutral | Blue | Solid |
| tired | Yellow | Solid |
| stressed | Red | Pulsing |
| sleeping | White | Breathing |

Mood changes trigger a soft speaker tone (single beep).

### 10.5 Approval UI (`approval.py`)

Full-screen takeover on `POST /approve`:

```
┌─────────────────────────────┐
│  ⚠️  APPROVAL REQUIRED      │  yellow background
│                             │
│  Tool: Bash                 │
│  rm -rf dist/               │
│                             │
│  ████ 47s remaining ████    │  countdown bar
│                             │
│  ┌──────────┐ ┌──────────┐ │
│  │   YES    │ │    NO    │ │  green / red touch buttons
│  └──────────┘ └──────────┘ │
└─────────────────────────────┘
```

- RGB: yellow flashing urgently
- Speaker: alert beep on display
- On tap: POST `mac:8081/decision`
- On countdown expiry: UI dismisses itself (the Mac server's 60s timeout has already returned `{"behavior": "ask"}` to Claude Code — K10 just cleans up its display)

### 10.6 Sensors (`sensors.py`)

- **AHT20** (I2C 0x38): temperature + humidity
- **LTR303ALS** (I2C 0x29): ambient light in lux
- Read on demand (GET /sensors); no push, no local timer

---

## 11. File Layout

```
claudebox/
├── mac/
│   ├── server.py          # single Mac daemon (HTTP + scanner + broadcaster)
│   ├── focus_monitor.py   # iTerm2 FocusMonitor → POST /focus
│   ├── scanner.py         # JSONL parser module (imported by server.py)
│   ├── mood.py            # mood scoring module
│   └── config.py          # gitignored — copy from config.example.py
├── k10/
│   └── device/
│       ├── main.py        # boot + WiFi + HTTP server
│       ├── display.py     # screen layout
│       ├── rgb.py         # WS2812 mood colors
│       ├── sensors.py     # AHT20 + LTR303ALS
│       └── approval.py    # full-screen Y/N touch UI
├── .claude/
│   └── settings.json      # hooks config
├── config.example.py      # committed template
├── hook.py                # installed to ~/.claudebox/hook.py
└── README.md
```

---

## 12. Build Order

1. `mac/scanner.py` — parse JSONL, get token data flowing, verify cost math
2. `mac/mood.py` — mood scoring, unit-testable standalone
3. `mac/server.py` — HTTP server + scanner thread + broadcaster stub (log to console first)
4. `hook.py` + `.claude/settings.json` — wire up hooks, verify state.json populates
5. `mac/focus_monitor.py` — iTerm2 focus events, verify active_iterm updates
6. End-to-end Mac test — Claude Code session → hooks → state.json → console log
7. `k10/device/sensors.py` — read AHT20 + LTR303, serve GET /sensors
8. `k10/device/main.py` — WiFi + HTTP server skeleton
9. `k10/device/display.py` — layout with placeholder data
10. `k10/device/rgb.py` — mood RGB
11. `k10/device/approval.py` — full-screen Y/N UI
12. `mac/server.py` broadcaster — complete (pull sensors, POST /update to K10)
13. Full loop test — Claude Code → hooks → server → K10 display
14. Approval flow test — Bash command → PermissionRequest → K10 → decision → Claude Code

---

## 13. Open Questions / Deferred

- `SESSION_TYPICAL_MAX = 150_000` is a starting guess — tune after first week of use
- Cardputer Adv firmware — separate spec, same HTTP protocol, keyboard Y/N/A
- `secrets.py` on K10 (Wi-Fi credentials) — needs gitignore entry
- launchd plist for auto-starting `server.py` and `focus_monitor.py` on login — deferred
