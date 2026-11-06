"""SIMULATED smart water meter - for testing and demos only (it is NOT real meter data).

Serves a cumulative reading that keeps rising, like a real meter:
    python -m scripts.mock_smart_meter --start 200

In HydroHome > Smart Meter use:
    Source type : URL
    Location    : http://localhost:8765/meter
    JSON path   : data.total_m3        (or data.total_liters with unit = liters)
--start must be >= the household's latest meter reading. Use --key SECRET to also test API-key auth.
"""
import argparse
import json
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer


def make_handler(start, rate, key):
    t0 = time.time()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/meter":
                return self._send(404, {"error": "not found"})
            if key and self.headers.get("X-API-Key") != key:
                return self._send(401, {"error": "invalid API key"})
            total = round(start + (time.time() - t0) * rate, 3)
            self._send(200, {"device_id": "SIM-001", "timestamp": datetime.now().isoformat(timespec="seconds"),
                             "data": {"total_m3": total, "total_liters": round(total * 1000, 1)}})

        def _send(self, code, body):
            raw = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, fmt, *args):
            print(f"[sim meter] {self.address_string()} {fmt % args}")

    return Handler


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--start", type=float, default=200.0, help="starting meter value in m3")
    ap.add_argument("--rate", type=float, default=0.002, help="m3 added per second (fast, for demos)")
    ap.add_argument("--key", default="", help="require this API key")
    a = ap.parse_args()
    print(f"Simulated smart meter on http://localhost:{a.port}/meter  (start {a.start} m3). Ctrl+C to stop.")
    HTTPServer(("127.0.0.1", a.port), make_handler(a.start, a.rate, a.key)).serve_forever()


if __name__ == "__main__":
    main()
