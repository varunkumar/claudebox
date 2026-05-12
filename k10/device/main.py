import gc
import network
import socket
import json
import time
import secrets
import config

_state = {
    "session": {"active": False, "model": "", "duration_minutes": 0,
                "current_task": "", "last_tool": "", "last_file": ""},
    "tokens": {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0},
    "mood": "sleeping",
    "mood_score": 0.0,
    "environment": {"temp_c": 0.0, "humidity_pct": 0.0, "light_lux": 0.0},
}

_needs_render = False
_last_render_ts = 0
_last_sensor_ts = 0
_RENDER_MIN_INTERVAL = 4   # seconds
_SENSOR_INTERVAL    = 30   # seconds


def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(False)
    time.sleep_ms(200)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(secrets.WIFI_SSID, secrets.WIFI_PASSWORD)
        for _ in range(20):
            if wlan.isconnected():
                break
            time.sleep(1)
    return wlan.isconnected(), wlan.ifconfig()[0]


def parse_request(conn):
    request = b""
    conn.settimeout(5.0)
    try:
        while True:
            chunk = conn.recv(1024)
            if not chunk:
                break
            request += chunk
            if b"\r\n\r\n" in request:
                header_end = request.index(b"\r\n\r\n") + 4
                headers_raw = request[:header_end].decode("utf-8", "ignore")
                content_length = 0
                for line in headers_raw.split("\r\n"):
                    if line.lower().startswith("content-length:"):
                        content_length = int(line.split(":")[1].strip())
                body_so_far = request[header_end:]
                while len(body_so_far) < content_length:
                    more = conn.recv(1024)
                    if not more:
                        break
                    body_so_far += more
                return headers_raw, body_so_far
    except OSError:
        pass
    return "", b""


def send_response(conn, status, body=b""):
    response = (
        f"HTTP/1.1 {status}\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n\r\n"
    ).encode()
    if body:
        response += body
    try:
        conn.sendall(response)
    except OSError:
        pass


def handle_request(conn):
    global _needs_render
    headers_raw, body_bytes = parse_request(conn)
    if not headers_raw:
        return

    first_line = headers_raw.split("\r\n")[0]
    parts = first_line.split(" ")
    if len(parts) < 2:
        return
    method, path = parts[0], parts[1]

    if method == "GET" and path == "/sensors":
        send_response(conn, "200 OK", json.dumps(_state["environment"]).encode())

    elif method == "POST" and path == "/update":
        try:
            payload = json.loads(body_bytes)
            _state.update(payload)
        except Exception:
            pass
        send_response(conn, "200 OK")
        _needs_render = True

    elif method == "POST" and path == "/approve":
        try:
            payload = json.loads(body_bytes)
        except Exception:
            payload = {}
        send_response(conn, "200 OK")
        try:
            from approval import show_approval
            show_approval(payload, config.MAC_HOST, config.MAC_PORT)
        except Exception as e:
            print(f"[k10] approval error: {e}")

    else:
        send_response(conn, "404 Not Found")


def do_render():
    global _last_render_ts
    now = time.time()
    if now - _last_render_ts < _RENDER_MIN_INTERVAL:
        return
    _last_render_ts = now
    gc.collect()
    try:
        from display import render
        render(_state)
    except Exception as e:
        print(f"[k10] render error: {e}")
    gc.collect()
    # rgb disabled — NeoPixel(Pin(48)) conflicts with screen SPI


def start_server():
    global _needs_render
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("", config.HTTP_PORT))
    s.listen(5)
    s.settimeout(5)
    print(f"[k10] HTTP server on port {config.HTTP_PORT}")

    while True:
        try:
            conn, addr = s.accept()
            try:
                handle_request(conn)
            finally:
                conn.close()
        except OSError:
            pass
        except Exception as e:
            print(f"[k10] request error: {e}")

        if _needs_render:
            _needs_render = False
            do_render()

        # sensors disabled — k10_base timer interferes with sockets


def boot():
    print("[k10] booting...")
    connected, ip = connect_wifi()
    if not connected:
        print("[k10] WiFi failed")
        return False
    print(f"[k10] WiFi connected, IP: {ip}")
    start_server()
    return True


while True:
    try:
        boot()
    except Exception as e:
        print(f"[k10] fatal: {e}")
    print("[k10] restarting in 5s...")
    time.sleep(5)
