import math
import time
import k10_base
import config as _cfg

_render_count = 0
_HAS_SCREEN = False
_screen = None

try:
    from unihiker_k10 import screen as _screen
    _screen.init(dir=2)
    _HAS_SCREEN = True
except Exception:
    pass

_SPIKES = [
    (0, 20), (18, 14), (40, 18), (60, 11), (80, 19),
    (98, 13), (115, 17), (135, 10), (150, 20), (168, 14),
    (185, 18), (205, 11), (220, 19), (240, 13), (258, 17),
    (275, 10), (290, 21), (308, 14), (325, 16), (345, 12),
]


def _draw_spikes(cx, cy, color):
    for angle_deg, length in _SPIKES:
        a = math.radians(angle_deg)
        ex = int(cx + length * math.cos(a))
        ey = int(cy + length * math.sin(a))
        _screen.draw_line(x0=cx, y0=cy, x1=ex, y1=ey, color=color)


MOOD_COLOR = {
    "happy":    0x4ade80,
    "neutral":  0xFF6B35,
    "tired":    0x888888,
    "stressed": 0xFF0000,
    "sleeping": 0x666666,
}

_BG = 0x191919
_FG = 0xFFFFFF
_DIM = 0x666666


def _k(n):
    return f"{n//1000}K" if n >= 1000 else str(n)


def _usage_color(pct):
    if pct < 0.30:
        return 0x4ade80   # green
    elif pct < 0.60:
        return 0xFFFF00   # yellow
    elif pct < 0.90:
        return 0xFF6B35   # orange
    else:
        return 0xFF0000   # red


def render(state: dict):
    global _render_count
    _render_count += 1
    print(
        f"[display] render start has_screen={_HAS_SCREEN} count={_render_count}")
    if not _HAS_SCREEN:
        _render_console(state)
        return

    session = state.get("session", {})
    tokens = state.get("tokens", {})
    env = state.get("environment", {})
    mood = state.get("mood", "sleeping")
    dur = session.get("duration_minutes", 0)
    color = MOOD_COLOR.get(mood, 0xFF6B35)

    # Replace draw_rect clear with:
    # Force full reset on each render
    _screen.init(dir=2)
    _screen.show_bg(color=0x000000)
    _screen.draw_rect(x=0, y=0, w=240, h=320, bcolor=0x000000, fcolor=0x000000)
    print("[display] A cleared")

    t = time.localtime(time.time() + _cfg.TZ_OFFSET_S)
    hhmm = f"{t[3]:02d}:{t[4]:02d}"

    _draw_spikes(cx=22, cy=22, color=0xFF6B35)
    _screen.draw_text(text="ClaudeBox", x=48, y=4,
                      font_size=24, color=0xFF6B35)
    _screen.draw_text(text=f"{mood.upper()}  {dur}m",
                      x=48, y=30, font_size=14, color=color)
    _screen.draw_text(text=hhmm, x=188, y=30, font_size=14, color=_DIM)
    _screen.draw_line(x0=0, y0=50, x1=240, y1=50, color=0x444444)
    print("[display] B header")

    task = session.get("current_task", "Waiting...")
    _screen.draw_text(text=task[:28],   x=8, y=58, font_size=14, color=_FG)
    _screen.draw_text(text=task[28:56], x=8, y=80, font_size=14, color=_FG)
    print("[display] C task")

    five_h = state.get("five_hour_pct", 0.0)
    _screen.draw_rect(x=8, y=104, w=224, h=24,
                      bcolor=0x333333, fcolor=0x333333)
    if five_h > 0.0:
        five_w = int(min(five_h, 1.0) * 224)
        five_color = _usage_color(five_h)
        _screen.draw_rect(x=8, y=104, w=five_w, h=24,
                          bcolor=five_color, fcolor=five_color)
        _screen.draw_text(
            text=f"Session {int(five_h*100)}%", x=12, y=106, font_size=10, color=_BG)
    else:
        _screen.draw_text(text="Session: no data", x=12,
                          y=106, font_size=10, color=_DIM)
    print("[display] D bars")

    weekly_pct = state.get("weekly_pct", 0.0)
    _screen.draw_rect(x=8, y=134, w=224, h=24,
                      bcolor=0x333333, fcolor=0x333333)
    if weekly_pct > 0.0:
        weekly_w = int(min(weekly_pct, 1.0) * 224)
        weekly_color = _usage_color(weekly_pct)
        _screen.draw_rect(x=8, y=134, w=weekly_w, h=24,
                          bcolor=weekly_color, fcolor=weekly_color)
        _screen.draw_text(
            text=f"Week {int(weekly_pct*100)}%", x=12, y=136, font_size=10, color=_BG)
    else:
        _screen.draw_text(text="Week: no data", x=12,
                          y=136, font_size=10, color=_DIM)
    print("[display] E weekly")

    tool = session.get("last_tool", "")
    file = session.get("last_file", "")
    _screen.draw_text(text=tool,       x=8, y=166, font_size=14, color=color)
    _screen.draw_text(text=file[-32:], x=8, y=186, font_size=8,  color=_DIM)
    _screen.draw_line(x0=0, y0=206, x1=240, y1=206, color=0x444444)
    print("[display] F tool")

    inp = tokens.get("input", 0)
    out = tokens.get("output", 0)
    cw = tokens.get("cache_write", 0)
    cr = tokens.get("cache_read", 0)
    model = session.get("model", "")
    _screen.draw_text(text="Tokens", x=8, y=210, font_size=8, color=0xFF6B35)
    _screen.draw_text(text=f"In {_k(inp)}  Out {_k(out)}",
                      x=8, y=228, font_size=14, color=0xCCCCCC)
    _screen.draw_text(text=f"Cw {_k(cw)}  Cr {_k(cr)}",
                      x=8, y=250, font_size=14, color=0xCCCCCC)
    _screen.draw_text(text=model[:30], x=8, y=272, font_size=10, color=_DIM)
    _screen.draw_line(x0=0, y0=290, x1=240, y1=290, color=0x444444)
    print("[display] G tokens")

    temp = env.get("temp_c", 0.0)
    hum = env.get("humidity_pct", 0.0)
    lux = env.get("light_lux", 0.0)
    lux_i = int(lux)
    print(f"[display] H env: temp={temp} hum={hum} lux={lux_i}")
    env_str = str(temp) + "C  " + str(hum) + "rh  " + str(lux_i) + "lx"
    print(f"[display] env_str={env_str}")
    _screen.draw_text(text=env_str, x=8, y=294, font_size=10, color=_DIM)

    _screen.show_draw()
    k10_base.lv.refr_now(None)  # force LVGL to flush to display
    print("[display] I done")


def _render_console(state: dict):
    mood = state.get("mood", "sleeping")
    task = state.get("session", {}).get("current_task", "")
    print(f"[display] {mood} | {task[:30]}")
