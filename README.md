# ClaudeBox

ClaudeBox is a physical ambient dashboard that displays Claude Code session status on a UNIHIKER K10 device sitting on your desk. It provides real-time feedback on session activity, token usage, and mood via an e-ink display, RGB lights, and environmental sensors.

## Features

- **Session Status** - Real-time Claude Code activity and state
- **Token Usage** - Track input/output tokens and session burn-down
- **Mood Indicator** - Visual feedback based on session performance and token usage
- **Environmental Sensors** - Temperature and ambient light sensing
- **Physical Approval Gate** - Approve Bash commands via touch UI on the K10 display
- **Status Broadcasting** - HTTP server pushes updates from your Mac to the K10

## Hardware

**Required:**
- UNIHIKER K10 (e-ink display + WiFi + sensors)

**Coming soon:**
- Cardputer Adv

## Setup

### Mac Setup

1. **Configure the project:**
   ```bash
   cp config.example.py mac/config.py
   ```
   Edit `mac/config.py` and set `K10_IP` to your K10's IP address.

2. **Install the hook:**
   ```bash
   mkdir -p ~/.claudebox
   cp hook.py ~/.claudebox/hook.py
   ```

3. **Install iTerm2 Python runtime:**
   Open iTerm2 → Scripts menu → Manage → Install Python Runtime

4. **Start the Mac server:**
   ```bash
   python3 mac/server.py
   ```
   This HTTP server monitors Claude Code sessions and broadcasts updates to the K10.

5. **Start the focus monitor:**
   ```bash
   python3 mac/focus_monitor.py
   ```
   This watches iTerm2 focus changes and reports them to the server.

### K10 Setup

1. **Flash MicroPython firmware:**
   Follow the [UNIHIKER K10 documentation](https://wiki.unihiker.com) to install MicroPython.

2. **Configure WiFi credentials:**
   ```bash
   cp k10/device/secrets_example.py k10/device/secrets.py
   ```
   Edit `k10/device/secrets.py` and add your WiFi SSID and password.

3. **Configure the Mac host:**
   Edit `k10/device/config.py` and set `MAC_HOST` to your Mac's IP address.

4. **Sync to device:**
   Use the Pymakr VS Code extension to sync `k10/device/` files to the K10.

### Router

Set a static IP for the K10 via DHCP reservation in your router settings. Use this IP as `K10_IP` in `mac/config.py`.

## Running

Start the two Mac daemons in separate terminal windows:

```bash
# Terminal 1
python3 mac/server.py

# Terminal 2
python3 mac/focus_monitor.py
```

The K10 will boot automatically and connect to the Mac via WiFi. Session status will appear on the display.

## Approval Gate

When a Bash command requires approval, a full-screen prompt appears on the K10 display asking for Y/N confirmation via touch input. Tap the on-screen buttons to approve or deny the command.

## Tuning

Adjust mood thresholds by editing `SESSION_TYPICAL_MAX` in `mac/config.py`. This controls how the mood indicator responds to token usage and session performance.

## Project Layout

- `mac/` - Mac daemon code (server, scanner, focus monitor)
- `k10/device/` - K10 MicroPython code (display, sensors, networking)
- `hook.py` - Claude Code hook installed to `~/.claudebox/`
- `config.example.py` - Configuration template
- `tests/` - Test suite (Mac side only)
- `docs/` - Design specs and implementation plans
