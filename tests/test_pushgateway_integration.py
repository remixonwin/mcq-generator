import os
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from types import ModuleType


class CaptureHandler(BaseHTTPRequestHandler):
    server: "CaptureHTTPServer"

    def do_POST(self):
        # record push
        length = int(self.headers.get("content-length", "0"))
        _ = self.rfile.read(length) if length else b""
        self.server.events.append(("POST", self.path))
        self.send_response(200)
        self.end_headers()

    def do_DELETE(self):
        self.server.events.append(("DELETE", self.path))
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        # silence
        return


class CaptureHTTPServer(HTTPServer):
    def __init__(self, server_address, RequestHandlerClass):
        super().__init__(server_address, RequestHandlerClass)
        self.events = []


def run_server_in_thread():
    server = CaptureHTTPServer(("127.0.0.1", 0), CaptureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def make_fake_prometheus_client(pushgateway_url):
    """Return a fake prometheus_client module that makes HTTP calls to the
    provided pushgateway base URL.
    """
    mod = ModuleType("prometheus_client")

    class CollectorRegistry:
        pass

    class Gauge:
        def __init__(self, name, desc, labels=None, registry=None):
            self._labels = {}

        def labels(self, *args):
            class _L:
                def set(self, v):
                    return None

            return _L()

    def push_to_gateway(pushgateway, job, registry=None, grouping_key=None):
        # POST to /metrics/job/<job>/... with grouping_key path
        import urllib.request

        path = f"/metrics/job/{job}"
        if grouping_key:
            for k, v in grouping_key.items():
                path += f"/{k}/{v}"
        url = pushgateway.rstrip("/") + path
        req = urllib.request.Request(url, data=b"metrics", method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp.read()

    def delete_from_gateway(pushgateway, job=None, grouping_key=None):
        import urllib.request

        path = f"/metrics/job/{job}"
        if grouping_key:
            for k, v in grouping_key.items():
                path += f"/{k}/{v}"
        url = pushgateway.rstrip("/") + path
        req = urllib.request.Request(url, method="DELETE")
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp.read()

    mod.CollectorRegistry = CollectorRegistry
    mod.Gauge = Gauge
    mod.push_to_gateway = push_to_gateway
    mod.delete_from_gateway = delete_from_gateway

    # Minimal Counter and Histogram implementations used by metrics module
    class Counter:
        def __init__(self, *a, **k):
            pass

        def labels(self, *a, **k):
            class _L:
                def inc(self, v=1):
                    return None

            return _L()

    class Histogram:
        def __init__(self, *a, **k):
            pass

        def labels(self, *a, **k):
            class _L:
                def observe(self, v):
                    return None

            return _L()

    def generate_latest():
        return b""

    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"

    mod.Counter = Counter
    mod.Histogram = Histogram
    mod.generate_latest = generate_latest
    mod.CONTENT_TYPE_LATEST = CONTENT_TYPE_LATEST

    return mod


def test_pushgateway_push_and_delete(tmp_path, monkeypatch):
    server = run_server_in_thread()
    port = server.server_address[1]
    url = f"http://127.0.0.1:{port}"

    # Install fake prometheus_client that will call our server
    fake = make_fake_prometheus_client(url)
    sys.modules["prometheus_client"] = fake

    monkeypatch.setenv("PUSHGATEWAY_URL", url)

    # Ensure the metrics module is re-imported so it picks up our fake
    import importlib

    if "mcq_generator.metrics" in sys.modules:
        del sys.modules["mcq_generator.metrics"]

    # Import the function under test
    from mcq_generator.metrics import push_job_metrics

    # Use a short TTL so test runs fast
    push_job_metrics("job_abc123", "topic_xyz", 1.23, True, ttl=1)

    # Wait a small amount to allow push request to arrive
    timeout = time.time() + 5
    while time.time() < timeout:
        if server.events:
            break
        time.sleep(0.05)

    assert server.events, "Expected at least one push event"
    assert any(m == "POST" for m, _ in server.events)

    # Wait for the scheduled delete (ttl=1)
    timeout = time.time() + 5
    while time.time() < timeout:
        if any(m == "DELETE" for m, _ in server.events):
            break
        time.sleep(0.05)

    assert any(m == "DELETE" for m, _ in server.events), f"Events: {server.events}"

    # Cleanup
    try:
        server.shutdown()
    except Exception:
        pass
    del sys.modules["prometheus_client"]
