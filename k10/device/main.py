import network
import socket
import json
import time
import secrets
import config

_state = {
    "session": {"active": False, "model": "", "duration_minutes": 0,
                "current_task": "", "last_tool": "", "last_file": ""},
    "tokens": {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0, "cost_usd": 0.0},
    "mood": "sleeping",
    "mood_score": 0.0,
    "environment": {"temp_c": 0.0, "humidity_pct": 0.0, "light_lux": 0.0},
}


def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
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
    conn.settimeout(3.0)
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
                    body_so_far += conn.recv(1024)
                return headers_raw, body_so_far
    except OSError:
        pass
    return "", b""


def send_response(conn, status, body=b"", content_type="application/json"):
    status_line = f"HTTP/1.1 {status}\r\n"
    headers = (
        f"Content-Type: {content_type}\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n\r\n"
    )
    conn.sendall((status_line + headers).encode() + body)


def handle_request(conn):
    headers_raw, body_bytes = parse_request(conn)
    if not headers_raw:
        return

    lines = headers_raw.split("\r\n")
    method, path = lines[0].split(" ")[:2]

    if method == "GET" and path == "/sensors":
        from sensors import read_sensors
        data = read_sensors()
        _state["environment"] = data
        send_response(conn, "200 OK", json.dumps(data).encode())

    elif method == "POST" and path == "/update":
        payload = json.loads(body_bytes)
        _state.update(payload)
        from display import render
        render(_state)
        from rgb import set_mood
        set_mood(_state["mood"])
        send_response(conn, "200 OK")

    elif method == "POST" and path == "/approve":
        payload = json.loads(body_bytes)
        from approval import show_approval
        show_approval(payload, config.MAC_HOST, config.MAC_PORT)
        send_response(conn, "200 OK")

    else:
        send_response(conn, "404 Not Found")


def start_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("", config.HTTP_PORT))
    s.listen(3)
    print(f"[k10] HTTP server on port {config.HTTP_PORT}", flush=True)
    while True:
        try:
            conn, addr = s.accept()
            try:
                handle_request(conn)
            finally:
                conn.close()
        except Exception as e:
            print(f"[k10] request error: {e}", flush=True)


def boot():
    print("[k10] booting...", flush=True)
    connected, ip = connect_wifi()
    if not connected:
        print("[k10] WiFi failed", flush=True)
        return
    print(f"[k10] WiFi connected, IP: {ip}", flush=True)
    start_server()


boot()
