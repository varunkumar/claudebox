import json
import socket
import time

try:
    from unihiker import GUI
    _gui = GUI()
    _USE_UNIHIKER = True
except ImportError:
    _USE_UNIHIKER = False

from rgb import set_mood, _fill


def _post_decision(mac_host: str, mac_port: int, request_id: str, decision: str):
    body = json.dumps({
        "request_id": request_id,
        "decision": decision,
        "device": "k10",
    }).encode()
    req_line = (
        f"POST /decision HTTP/1.1\r\n"
        f"Host: {mac_host}\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Connection: close\r\n\r\n"
    )
    try:
        s = socket.socket()
        s.settimeout(5)
        s.connect((mac_host, mac_port))
        s.sendall(req_line.encode() + body)
        s.close()
    except Exception as e:
        print(f"[approval] failed to send decision: {e}", flush=True)


def show_approval(payload: dict, mac_host: str, mac_port: int):
    request_id = payload.get("request_id", "")
    tool       = payload.get("tool", "")
    command    = payload.get("command", "")[:48]
    countdown  = payload.get("countdown_seconds", 60)

    if not _USE_UNIHIKER:
        print(f"[approval] {tool}: {command} — approve? (auto-deny in {countdown}s)", flush=True)
        _post_decision(mac_host, mac_port, request_id, "deny")
        return

    _gui.clear()
    _gui.draw_rect(x=0, y=0, w=320, h=240, color="#FFCC00")

    _gui.draw_text(text="⚠️  APPROVAL REQUIRED", x=20, y=15, font_size=18, color="#000000")
    _gui.draw_line(x_start=0, y_start=45, x_end=320, y_end=45, color="#CC9900")
    _gui.draw_text(text=f"Tool: {tool}", x=12, y=58, font_size=16, color="#000000")
    _gui.draw_text(text=command, x=12, y=82, font_size=14, color="#333333")

    _gui.draw_rect(x=12, y=118, w=296, h=16, color="#CC9900")

    _gui.draw_rect(x=12,  y=155, w=130, h=60, color="#00AA00")
    _gui.draw_text(text="YES", x=52, y=175, font_size=22, color="#FFFFFF")

    _gui.draw_rect(x=178, y=155, w=130, h=60, color="#CC0000")
    _gui.draw_text(text="NO",  x=222, y=175, font_size=22, color="#FFFFFF")

    set_mood("stressed")

    decision = None
    start = time.time()

    while time.time() - start < countdown:
        elapsed   = time.time() - start
        remaining = max(0, countdown - int(elapsed))
        bar_w     = int(296 * remaining / countdown)

        _gui.draw_rect(x=12, y=118, w=296, h=16, color="#FFCC00")
        _gui.draw_rect(x=12, y=118, w=bar_w, h=16, color="#CC9900")
        _gui.draw_text(text=f"{remaining}s", x=148, y=119, font_size=13, color="#000000")

        try:
            touch = _gui.get_touch()
            if touch:
                tx, ty = touch["x"], touch["y"]
                if 12 <= tx <= 142 and 155 <= ty <= 215:
                    decision = "allow"
                    break
                if 178 <= tx <= 308 and 155 <= ty <= 215:
                    decision = "deny"
                    break
        except Exception:
            pass

        time.sleep_ms(100)

    _gui.clear()
    _fill((0, 0, 0))

    _post_decision(mac_host, mac_port, request_id, decision or "deny")
