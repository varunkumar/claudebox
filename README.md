# ClaudeBox

ClaudeBox is a physical ambient dashboard that displays Claude Code session status on a UNIHIKER K10 sitting on your desk. It shows real-time session activity, token usage, mood via RGB LEDs, environmental sensor data, and lets you approve or deny Bash commands with a physical touch UI.

## How It Works

```
Claude Code sessions (iTerm2 tabs)
        |
        |  fires hooks via ~/.claude/settings.json
        v
hook.py  (thin HTTP client, no state)
        |
        |  POST localhost:8081/hook   (non-blocking for most hooks)
        |  POST localhost:8081/hook   (blocking for PermissionRequest)
        v
server.py  (single process, port 8081)
  |-- HTTP server thread     receives /hook, /focus, /decision
  |-- Scanner thread         reads JSONL logs every 30s, updates token counts
  |-- Broadcaster thread     pulls sensors, computes mood, pushes to K10
  |-- Approval queue         serializes PermissionRequest per session
  +-- state.json             shared state, thread-safe

focus_monitor.py  (separate process)
  +-- iTerm2 FocusMonitor    fires on tab switch
        |  POST localhost:8081/focus
        v  server.py records which session is active

                        WiFi
server.py broadcaster <-------> K10 (port 8080)
  GET  k10:8080/sensors           POST /update   refresh display + RGB LEDs
  POST k10:8080/update            POST /approve  show Y/N touch UI
  POST k10:8080/approve           GET  /sensors  return sensor readings
                                  POST mac:8081/decision  (user tapped Y/N)
```

Claude Code hooks post events to a Mac daemon (`server.py`) over HTTP. The daemon tracks active sessions, scans JSONL logs for token usage, and pushes status updates to the K10 over WiFi. The K10 renders a dashboard on its display, drives RGB mood LEDs, and hosts an approval UI for Bash commands. iTerm2's FocusMonitor determines which session is "active": only the focused terminal tab routes approval requests to the device.

## Hardware

**Required:**
- UNIHIKER K10 (touch display, WiFi, AHT20 temp/humidity, LTR303 light sensor, WS2812 LEDs)

**Coming soon:**
- Cardputer Adv

## Setup

### 1. Router

Give the K10 a static IP via DHCP reservation in your router settings. You'll need this IP in the next step.

### 2. Mac: Configuration

```bash
cp config.example.py mac/config.py
```

Edit `mac/config.py`:
- Set `K10_IP` to the K10's static IP
- Adjust `APPROVAL_REQUIRED` / `AUTO_ALLOW` tool lists as needed

`mac/config.py` is gitignored. Never commit credentials or IPs.

### 3. Mac: Hook

```bash
mkdir -p ~/.claudebox
cp hook.py ~/.claudebox/hook.py
```

Copy `.claude/settings.json` to `~/.claude/settings.json` (or merge the `hooks` block if you have an existing settings file). This wires up Claude Code to call the hook on every session event.

### 4. Mac: iTerm2 Focus Monitor

Open iTerm2 > Scripts menu > Manage > Install Python Runtime (one-time).

The focus monitor tracks which terminal tab is active so the approval gate routes to the right session.

### 5. K10: Firmware

Flash MicroPython onto the K10 following the [UNIHIKER K10 documentation](https://wiki.unihiker.com).

### 6. K10: Configuration

```bash
cp k10/device/secrets_example.py k10/device/secrets.py
```

Edit `k10/device/secrets.py` with your WiFi SSID and password.

Edit `k10/device/config.py` and set `MAC_HOST` to your Mac's local IP address.

`secrets.py` is gitignored. Never commit WiFi credentials.

### 7. K10: Deploy

Sync the `k10/device/` directory to the K10 using the Pymakr VS Code extension or `mpremote`.

## Running

Start both Mac daemons (separate terminal windows):

```bash
# Terminal 1: main server
python3 mac/server.py

# Terminal 2: iTerm2 focus tracker
python3 mac/focus_monitor.py
```

The K10 boots automatically and connects to the Mac. Session status appears on the display within a few seconds of starting a Claude Code session.

## Approval Gate

When Claude Code requests permission to run a Bash command, a full-screen prompt appears on the K10 with a countdown timer. Tap **YES** or **NO** on the touch display. If no response within 60 seconds, the command falls back to Claude Code's built-in CLI approval prompt.

Only the iTerm2 tab that currently has focus routes to the device. Background sessions always fall back to the CLI prompt immediately.

## Mood System

RGB LEDs reflect session intensity based on cumulative token usage:

| Mood     | Color  | Condition                          |
|----------|--------|------------------------------------|
| sleeping | off    | No active session / idle >10 min   |
| happy    | green  | <20% of session budget used        |
| neutral  | blue   | 20-50%                             |
| tired    | yellow | 50-75%                             |
| stressed | red    | >75%                               |

Tune `SESSION_TYPICAL_MAX` in `mac/config.py` to calibrate the thresholds to your typical session size.

## Project Layout

```
mac/           Mac daemon: server, scanner, mood, focus monitor
k10/device/    K10 MicroPython firmware: display, sensors, RGB, approval
hook.py        Claude Code hook (install to ~/.claudebox/)
config.example.py  Config template (copy to mac/config.py)
.claude/settings.json  Hook wiring for Claude Code
tests/         Mac-side test suite (pytest)
docs/          Design specs and implementation plans
```

## Development

```bash
# Run tests
python -m pytest tests/ -v

# Tests cover: state persistence, token scanning, mood thresholds,
# hook ingestion, broadcaster, and full approval round-trips.
```

K10 firmware is MicroPython with no CPython test suite. Validate sensor reads and display layout on the device directly.
