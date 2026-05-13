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
- **Python 3.9 on Mac**: do not use `X | Y` union type syntax in annotations (e.g. `dict | None`). Use bare signatures or `Optional` from `typing`.

## Running tests

```bash
python -m pytest tests/ -v
```

Tests live in `tests/` and cover the Mac side only (state, scanner, mood, hooks, approval round-trips). K10 firmware is validated on-device.

## Configuration

`mac/config.py` is gitignored. Copy from `config.example.py` and fill in:
- `K10_IP`: static IP assigned to K10 via router DHCP reservation
- WiFi credentials go in `k10/device/secrets.py` (also gitignored)
- `TZ_OFFSET_S` in `k10/device/config.py`: seconds east of UTC for the local timezone (IST = 19800)

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

The broadcaster never pushes an `environment` field. Sensor state is owned by the K10 and populated locally from its I2C sensors. If the Mac were to push `environment`, it would overwrite the K10's real readings with zeroes.

## Adding a new hook type

1. Add handling in `_update_from_hook()` in `server.py`
2. Add the hook to `.claude/settings.json`
3. Add a test in `tests/test_server_hooks.py`

Do not add `Stop` or `Notification` hooks. They carry no useful state and would generate spurious K10 pushes.

## Mood thresholds

Defined in `mac/mood.py` as `_THRESHOLDS`. `SESSION_TYPICAL_MAX` in `mac/config.py` is the denominator. Tune it to your typical session size to calibrate when moods transition.

## K10 display

The K10 screen API (`unihiker_k10.screen`) uses two compositing layers: a background layer and a draw layer. There are critical gotchas:

- **`show_draw()` is a one-shot call.** After `_screen.init(dir=2)`, calling `show_draw()` flips the draw layer to the display exactly once. Subsequent calls do nothing. The screen appears to freeze after the first render.
- **Correct re-render pattern**: call `_screen.init(dir=2)` at the top of every `render()` invocation to reset the compositing state, then `show_bg(color=0x000000)` to set a dark background, draw everything, then `show_bg()` (no args) to composite and flush to the display. Do not use `show_draw()`.
- **Colors**: passed as 24-bit integers (`0xRRGGBB`). Standard HTML hex colors work directly. No alpha channel.
- **Font sizes and character widths**: there is no text measurement API. Approximate widths at common sizes: font_size=10 ~6px/char, font_size=14 ~8px/char, font_size=24 ~14px/char. Right-align by computing `x = screen_width - padding - len(text) * approx_char_width`.
- **Screen dimensions**: with `init(dir=2)`, the drawable area is 240px wide × 320px tall.
- **`draw_rect` clears its own area**: use an opaque background rect to erase content before re-drawing it, or rely on the full `init()` reset at the top of `render()`.

## K10 RGB and k10_base timer

Importing `from unihiker_k10 import rgb` (or `import k10_base`) starts an internal timer in the k10_base library that fires every ~100ms against the GPIO expander (XL9535 at I2C address 0x20). This timer causes `ETIMEDOUT` errors on all subsequent TCP socket operations.

Fix: after obtaining `rgb.my_rgb`, immediately deinit all machine timers:

```python
from unihiker_k10 import rgb
np = rgb.my_rgb
from machine import Timer
for i in range(4):
    try:
        Timer(i).deinit()
    except Exception:
        pass
```

Import `rgb` lazily (on first `set_mood()` call), never at module import time, so the timer is killed before the HTTP server accepts its first connection.

## K10 sensors

Do not use `k10_base.aht20` or `k10_base.Light()`. These wrappers are unreliable once the k10_base timer has been killed, and they share the I2C bus in ways that conflict with direct access.

Use raw I2C instead:

```python
from machine import I2C, Pin
i2c = I2C(1, scl=Pin(48), sda=Pin(47), freq=400000)
```

- **AHT20** (temp/humidity): address `0x38`. Send init bytes `[0xBE, 0x08, 0x00]` once (flag resets on error). Trigger measurement with `[0xAC, 0x33, 0x00]`, wait 80ms, poll bit 7 of status byte for busy.
- **LTR303** (light): address `0x29`. Activate with `[0x80, 0x01]`, wait 110ms, read 4 bytes from register `0x88` using `readfrom_mem`. Apply the ratio-based lux formula (see `sensors.py`).
- Create a **fresh I2C instance on every `read_sensors()` call**. Caching the instance leads to intermittent `ETIMEDOUT` errors after several reads.

## K10 port binding

`SO_REUSEADDR` does not work reliably on MicroPython ESP32. If `main.py` crashes and restarts quickly, the port is still held by the kernel. Use a retry loop:

```python
for attempt in range(10):
    try:
        s.bind(("", config.HTTP_PORT))
        break
    except OSError:
        time.sleep(3)
else:
    raise OSError("port still busy after retries")
```

## K10 time

The K10's RTC is not battery-backed and starts from epoch (2000-01-01 00:00:00) on every boot. Always call `ntptime.settime()` after WiFi connects to sync to UTC. Apply a `TZ_OFFSET_S` offset (from `config.py`) in display code:

```python
t = time.localtime(time.time() + config.TZ_OFFSET_S)
```

`ntptime.settime()` can fail silently if DNS is slow. Log the error and continue - the display will show wrong time but the rest of the system works.
