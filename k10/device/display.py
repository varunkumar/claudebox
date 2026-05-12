try:
    from unihiker import GUI
    _gui = GUI()
    _USE_UNIHIKER = True
except ImportError:
    _USE_UNIHIKER = False

MOOD_EMOJI = {
    "happy":    "😊",
    "neutral":  "😐",
    "tired":    "😓",
    "stressed": "😰",
    "sleeping": "😴",
}


def render(state: dict):
    if not _USE_UNIHIKER:
        _render_console(state)
        return
    _render_gui(state)


def _render_gui(state: dict):
    _gui.clear()

    session = state.get("session", {})
    tokens  = state.get("tokens", {})
    env     = state.get("environment", {})
    mood    = state.get("mood", "sleeping")
    dur     = session.get("duration_minutes", 0)
    emoji   = MOOD_EMOJI.get(mood, "😐")

    # Top bar: mood emoji + duration
    _gui.draw_text(text=f"{emoji} {mood.capitalize()}  {dur}m",
                   x=8, y=8, font_size=18, color="#FFFFFF")
    _gui.draw_line(x_start=0, y_start=32, x_end=320, y_end=32, color="#444444")

    # Task section
    tool  = session.get("last_tool", "")
    file  = session.get("last_file", "")
    task  = session.get("current_task", "Waiting...")[:38]
    model = session.get("model", "")
    _gui.draw_text(text=f"{tool}  {file}"[:42], x=8, y=40, font_size=14, color="#AAAAAA")
    _gui.draw_text(text=task, x=8, y=60, font_size=14, color="#FFFFFF")
    _gui.draw_text(text=model, x=8, y=80, font_size=12, color="#888888")
    _gui.draw_line(x_start=0, y_start=100, x_end=320, y_end=100, color="#444444")

    # Token section
    inp  = tokens.get("input", 0)
    out  = tokens.get("output", 0)
    cw   = tokens.get("cache_write", 0)
    cr   = tokens.get("cache_read", 0)
    cost = tokens.get("cost_usd", 0.0)
    _gui.draw_text(text=f"In: {inp//1000}K  Out: {out//1000}K",
                   x=8, y=108, font_size=14, color="#CCCCCC")
    _gui.draw_text(text=f"Cache ↑{cw//1000}K ↓{cr//1000}K  ${cost:.3f}",
                   x=8, y=128, font_size=14, color="#CCCCCC")
    _gui.draw_line(x_start=0, y_start=150, x_end=320, y_end=150, color="#444444")

    # Environment bar
    temp = env.get("temp_c", 0.0)
    hum  = env.get("humidity_pct", 0.0)
    lux  = env.get("light_lux", 0.0)
    _gui.draw_text(text=f"{temp}°C  {hum}%RH  {lux:.0f}lx",
                   x=8, y=158, font_size=13, color="#888888")


def _render_console(state: dict):
    mood  = state.get("mood", "sleeping")
    emoji = MOOD_EMOJI.get(mood, "?")
    task  = state.get("session", {}).get("current_task", "")
    cost  = state.get("tokens", {}).get("cost_usd", 0.0)
    print(f"[display] {emoji} {mood} | {task[:30]} | ${cost:.3f}", flush=True)
