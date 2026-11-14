#!/usr/bin/env python3
"""Small allow-list based HTTP bridge for locally controlled WiZ lights."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import socket
import threading
import time
from urllib.parse import urlparse


PORT = 38899
HTTP_PORT = 8090
MAX_BODY = 4096
LOCK = threading.Lock()

PRESETS = {
    "reading": {"state": True, "temp": 2700, "dimming": 45},
    "night": {"state": True, "temp": 2200, "dimming": 15},
    "focus": {"state": True, "temp": 4000, "dimming": 80},
    "bright": {"state": True, "temp": 5000, "dimming": 100},
}


def load_lights():
    lights = {}
    raw = os.environ.get("WIZ_LIGHTS", "")
    for item in raw.split(","):
        if not item.strip() or "=" not in item:
            continue
        light_id, value = item.split("=", 1)
        if "|" in value:
            address, label = value.split("|", 1)
        else:
            address, label = value, light_id
        socket.inet_aton(address.strip())
        lights[light_id.strip()] = {"ip": address.strip(), "label": label.strip()}
    if not lights:
        raise RuntimeError("WIZ_LIGHTS is empty")
    return lights


LIGHTS = load_lights()


def udp_request(address, method, params, timeout=0.8):
    payload = json.dumps({"method": method, "params": params}).encode("utf-8")
    last_error = None
    for _ in range(2):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        try:
            sock.sendto(payload, (address, PORT))
            data, _ = sock.recvfrom(65535)
            return json.loads(data.decode("utf-8"))
        except (OSError, ValueError, json.JSONDecodeError) as error:
            last_error = error
        finally:
            sock.close()
    raise TimeoutError(str(last_error or "No response"))


def read_light(light_id, config):
    try:
        response = udp_request(config["ip"], "getPilot", {})
        result = response.get("result", {})
        return {
            "id": light_id,
            "label": config["label"],
            "reachable": True,
            "state": bool(result.get("state")),
            "dimming": result.get("dimming"),
            "temperature": result.get("temp"),
            "scene_id": result.get("sceneId"),
            "rssi": result.get("rssi"),
        }
    except TimeoutError:
        return {"id": light_id, "label": config["label"], "reachable": False}


def status_payload():
    with LOCK:
        lights = [read_light(light_id, config) for light_id, config in LIGHTS.items()]
    return {"ok": all(light["reachable"] for light in lights), "lights": lights, "checked_at": int(time.time())}


def command_params(action, value):
    if action == "preset" and value in PRESETS:
        return dict(PRESETS[value])
    if action == "power" and value in ("on", "off"):
        return {"state": value == "on"}
    if action == "brightness":
        number = int(value)
        if 10 <= number <= 100:
            return {"state": True, "dimming": number}
    if action == "temperature":
        number = int(value)
        if 2200 <= number <= 6500:
            return {"state": True, "temp": number}
    if action == "color" and isinstance(value, str) and len(value) == 7 and value.startswith("#"):
        red = int(value[1:3], 16)
        green = int(value[3:5], 16)
        blue = int(value[5:7], 16)
        return {"state": True, "r": red, "g": green, "b": blue}
    raise ValueError("Unsupported command")


def run_command(payload):
    target = payload.get("target")
    action = payload.get("action")
    value = payload.get("value")
    targets = LIGHTS if target == "all" else {target: LIGHTS[target]} if target in LIGHTS else None
    if not targets:
        raise ValueError("Unknown target")
    params = command_params(action, value)
    results = []
    with LOCK:
        for light_id, config in targets.items():
            try:
                response = udp_request(config["ip"], "setPilot", params)
                success = bool(response.get("result", {}).get("success"))
            except TimeoutError:
                success = False
            results.append({"id": light_id, "success": success})
    return {"ok": all(item["success"] for item in results), "results": results}


class Handler(BaseHTTPRequestHandler):
    server_version = "WizBridge/1.0"

    def send_json(self, status, payload):
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/healthz":
            self.send_json(200, {"status": "ok"})
        elif path == "/status":
            self.send_json(200, status_payload())
        else:
            self.send_json(404, {"error": "Not found"})

    def do_POST(self):
        if urlparse(self.path).path != "/command":
            self.send_json(404, {"error": "Not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > MAX_BODY:
                raise ValueError("Invalid body size")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            self.send_json(200, run_command(payload))
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
            self.send_json(400, {"ok": False, "error": str(error)})

    def log_message(self, format_string, *args):
        print("%s - %s" % (self.address_string(), format_string % args), flush=True)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", HTTP_PORT), Handler).serve_forever()

