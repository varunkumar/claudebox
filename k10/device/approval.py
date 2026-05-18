import json
import math
import socket
import time

_screen = None
_HAS_SCREEN = False

try:
    from unihiker_k10 import screen as _screen
    _screen.init(dir=2)
    _HAS_SCREEN = True
except Exception:
    pass


def _init_approval_buttons():
    """Force-reload k10_base to get a fresh I2C state, then create buttons."""
    import sys
    # Evict k10_base from module cache so re-import re-runs hardware init,
    # clears any stuck I2C bus state, and starts a fresh timer.
    for mod_name in list(sys.modules.keys()):
        if "k10_base" in mod_name:
            del sys.modules[mod_name]
    try:
        import k10_base  # fresh init: I2C reset + timer starts
        from unihiker_k10 import button as _button
        btn_a = _button(_button.a)
        btn_b = _button(_button.b)
        print("[approval] buttons initialized")
        return btn_a, btn_b
    except Exception as e:
        print(f"[approval] button init failed: {e}")
        return None, None


_SPIKES = [
    (0, 20), (18, 14), (40, 18), (60, 11), (80, 19),
    (98, 13), (115, 17), (135, 10), (150, 20), (168, 14),
    (185, 18), (205, 11), (220, 19), (240, 13), (258, 17),
    (275, 10), (290, 21), (308, 14), (325, 16), (345, 12),
]


def _draw_header():
    for angle_deg, length in _SPIKES:
        a = math.radians(angle_deg)
        ex = int(22 + length * math.cos(a))
        ey = int(22 + length * math.sin(a))
        _screen.draw_line(x0=22, y0=22, x1=ex, y1=ey, color=0xFF6B35)
    _screen.draw_text(text="ClaudeBox", x=48, y=4,
                      font_size=24, color=0xFF6B35)
    _screen.draw_text(text="Approval",  x=48, y=30,
                      font_size=14, color=0xDD3300)
    _screen.draw_line(x0=0, y0=50, x1=240, y1=50, color=0x444444)


def _post_decision(mac_host, mac_port, request_id, decision):
    body = json.dumps({
        "request_id": request_id,
        "decision": decision,
        "device": "k10",
    }).encode()
    req = (
        f"POST /decision HTTP/1.1\r\n"
        f"Host: {mac_host}\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Connection: close\r\n\r\n"
    ).encode() + body
    try:
        # Kill the k10_base timer before TCP: it fires every ~100ms against the
        # GPIO expander and causes ETIMEDOUT on socket operations.
        from machine import Timer
        for _i in range(4):
            try:
                Timer(_i).deinit()
            except Exception:
                pass
    except Exception:
        pass
    for _attempt in range(3):
        s = None
        try:
            s = socket.socket()
            s.settimeout(5)
            s.connect((mac_host, mac_port))
            s.sendall(req)
            s.close()
            print(f"[approval] decision sent: {decision}")
            return
        except Exception as e:
            print(f"[approval] decision send attempt {_attempt+1} failed: {e}")
            if s:
                try:
                    s.close()
                except Exception:
                    pass
            time.sleep_ms(500)
    print("[approval] decision send failed after 3 attempts")


def _draw_screen(tool, command, remaining, countdown):
    _screen.init(dir=2)
    _screen.show_bg(color=0x000000)
    _screen.draw_rect(x=0, y=0, w=240, h=320, bcolor=0x000000, fcolor=0x000000)

    _draw_header()

    _screen.draw_text(text=tool[:28], x=8, y=56, font_size=14, color=0xFFAA00)
    lines = [command[i*37:(i+1)*37] for i in range(10)]
    for i, line in enumerate(lines):
        if line:
            _screen.draw_text(text=line, x=8, y=76 + i * 14,
                              font_size=10, color=0xCCCCCC)

    # Countdown bar just above buttons
    bar_w = int(224 * remaining / max(countdown, 1))
    _screen.draw_rect(x=8, y=228, w=224, h=20,
                      bcolor=0x2A2A2A, fcolor=0x2A2A2A)
    if bar_w > 0:
        _screen.draw_rect(x=8, y=228, w=bar_w, h=20,
                          bcolor=0x445566, fcolor=0x445566)
    _screen.draw_text(text=f"{remaining}s", x=108,
                      y=230, font_size=10, color=0xAAAAAA)

    _screen.draw_line(x0=0, y0=252, x1=240, y1=252, color=0x333333)

    _screen.draw_rect(x=4,   y=256, w=112, h=58,
                      bcolor=0x2A6E2A, fcolor=0x2A6E2A)
    _screen.draw_text(text="Yes",   x=30,  y=260, font_size=24, color=0xDDFFDD)
    _screen.draw_text(text="Btn A", x=30,  y=288, font_size=10, color=0x88BB88)

    _screen.draw_rect(x=124, y=256, w=112, h=58,
                      bcolor=0x6E2A2A, fcolor=0x6E2A2A)
    _screen.draw_text(text="No",    x=158, y=260, font_size=24, color=0xFFDDDD)
    _screen.draw_text(text="Btn B", x=150, y=288, font_size=10, color=0xBB8888)

    _screen.show_draw()
    try:
        import k10_base
        k10_base.lv.refr_now(None)
    except Exception:
        pass


def _reset_screen():
    """Blank screen and reset layer state so display.py's show_draw() works cleanly."""
    _screen.init(dir=2)
    _screen.show_bg(color=0x000000)
    _screen.draw_rect(x=0, y=0, w=240, h=320, bcolor=0x000000, fcolor=0x000000)
    _screen.show_draw()
    try:
        import k10_base
        k10_base.lv.refr_now(None)
    except Exception:
        pass


def show_approval(payload, mac_host, mac_port):
    request_id = payload.get("request_id", "")
    tool = payload.get("tool", "Unknown")
    command = payload.get("command", "")
    countdown = payload.get("countdown_seconds", 60)

    print(f"[approval] show_approval request_id={request_id} tool={tool}")

    # Initialize buttons with proper timer management
    btn_a, btn_b = _init_approval_buttons()

    if not _HAS_SCREEN:
        print(f"[approval] {tool}: {command[:40]} — auto-deny (no screen)")
        _post_decision(mac_host, mac_port, request_id, "deny")
        return

    _decision = [None]

    def _btn_a_pressed():
        if _decision[0] is None:
            print(f"[approval] Button A pressed → allow")
            _decision[0] = "allow"

    def _btn_b_pressed():
        if _decision[0] is None:
            print(f"[approval] Button B pressed → deny")
            _decision[0] = "deny"

    # Set event callback attributes
    if btn_a:
        print("[approval] Button A handler set")
        btn_a.event_pressed = _btn_a_pressed
    if btn_b:
        print("[approval] Button B handler set")
        btn_b.event_pressed = _btn_b_pressed

    # Wait for timer to fire at least twice so status() reflects real hardware state
    time.sleep_ms(250)
    idle_a = btn_a.status() if btn_a else None
    idle_b = btn_b.status() if btn_b else None
    print(f"[approval] handlers set; idle states a={idle_a} b={idle_b}")

    """
    start = time.time()
    prev_remaining = countdown
    _draw_screen(tool, command, countdown, countdown)

    while _decision[0] is None:
        elapsed = int(time.time() - start)
        remaining = max(0, countdown - elapsed)

        if remaining == 0:
            print("[approval] timeout, denying")
            break

        # Redraw only when the countdown second changes
        if remaining != prev_remaining:
            prev_remaining = remaining
            _draw_screen(tool, command, remaining, countdown)

        # Polling fallback: detect any change from idle OR explicit press (status==1)
        if btn_a:
            sa = btn_a.status()
            if sa is not None and (sa == 1 or (idle_a is not None and sa != idle_a)):
                _btn_a_pressed()
        if btn_b:
            sb = btn_b.status()
            if sb is not None and (sb == 1 or (idle_b is not None and sb != idle_b)):
                _btn_b_pressed()

        time.sleep_ms(100)

    _reset_screen()
    """

    _post_decision(mac_host, mac_port, request_id, _decision[0] or "deny")
    print(
        f"[approval] decision={_decision[0] or 'deny'} timeout={_decision[0] is None}")
