"""Fake application process simulating a web service.

This process:
- Listens on port 8080
- Responds to /health with 200
- Can be killed to simulate ServiceDown alerts
- Can be restarted by Ansible remediation
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
import signal
import sys


class AppHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "healthy",
                "service": "web-frontend",
                "pid": os.getpid(),
            }).encode())
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"AIOps Demo Target Application\n")

    def log_message(self, format, *args):
        pass  # Suppress access logs


def main():
    server = HTTPServer(("0.0.0.0", 8080), AppHandler)
    print(f"[fake_app] Started on port 8080 (PID: {os.getpid()})", flush=True)

    def shutdown(sig, frame):
        print("[fake_app] Shutting down...", flush=True)
        server.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    server.serve_forever()


if __name__ == "__main__":
    main()
