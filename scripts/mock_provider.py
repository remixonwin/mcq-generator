#!/usr/bin/env python3
"""Minimal mock LLM provider to support integration testing.

Listens on localhost:7543 and responds to /v1/chat/completions with a
deterministic MCQ-like payload.
"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def _set_json(self, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

    def do_GET(self):
        if self.path in ("/health", "/healthz"):
            self._set_json(200)
            self.wfile.write(json.dumps({"status": "ok"}).encode())
            return
        if self.path == "/stats":
            self._set_json(200)
            self.wfile.write(json.dumps({"requests": 0}).encode())
            return
        self._set_json(404)
        self.wfile.write(json.dumps({"error": "not found"}).encode())

    def do_POST(self):
        if self.path == "/v1/chat/completions":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            try:
                req = json.loads(body)
            except Exception:
                req = {}

            # Return a deterministic MCQ content regardless of input
            content = (
                "QUESTION: What is 1+1?\nA) 1\nB) 2\nC) 3\nCORRECT: B\n"
                "EXPLANATION: 1+1=2.\nNAMES: \nPLACES: \nDATES: \nEVENTS: \nDIFFICULTY: Easy\nTOPIC: Math"
            )
            resp = {"choices": [{"message": {"content": content}}]}
            self._set_json(200)
            self.wfile.write(json.dumps(resp).encode())
            return

        self._set_json(404)
        self.wfile.write(json.dumps({"error": "not found"}).encode())


def run(port: int = 7543):
    server = HTTPServer(("127.0.0.1", port), Handler)
    print(f"Mock provider running on http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    run()
