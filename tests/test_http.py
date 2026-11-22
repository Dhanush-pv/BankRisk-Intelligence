import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from bankrisk.http import HttpClient


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/ok"):
            body = b'{"hello": "world"}'
            self.send_response(200)
        else:
            body = b'{"error": "nope"}'
            self.send_response(400)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # silence test output
        pass


def _serve():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def test_client_returns_body_untouched_and_status():
    server = _serve()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        client = HttpClient()
        ok = client.get(f"{base}/ok", params={"a": "1"})
        assert ok.ok and ok.content == b'{"hello": "world"}' and "a=1" in ok.url
        bad = client.get(f"{base}/bad")
        assert not bad.ok and bad.status_code == 400 and bad.content == b'{"error": "nope"}'
    finally:
        server.shutdown()


def test_client_turns_connection_failure_into_error_response():
    resp = HttpClient(timeout_s=2, retries=0).get("http://127.0.0.1:1/unreachable")
    assert resp.status_code == 0 and resp.error and not resp.ok
