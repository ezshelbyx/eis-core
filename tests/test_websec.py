import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from redkit.modules import websec
from redkit.scope import OutOfScope, Scope


class _Handler(BaseHTTPRequestHandler):
    server_version = "VulnerableTest/1.0"
    altsvc_header = None

    def log_message(self, *args):  # silence
        pass

    def do_GET(self):
        if self.path == "/.git/HEAD":
            body = b"ref: refs/heads/main\n"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/.env":
            body = b"SECRET_KEY=abc\n"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            body = b"<html><body>hi</body></html>"
            # Deliberately missing every security header; sets a sloppy cookie.
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Set-Cookie", "session=abc; Path=/")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)


@pytest.fixture(scope="module")
def server():
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def test_audit_refuses_out_of_scope():
    with pytest.raises(OutOfScope):
        websec.audit("http://127.0.0.1/", Scope([]))


def test_audit_finds_missing_headers_and_disclosures(server):
    scope = Scope(["127.0.0.1"])
    report = websec.audit(server, scope, timeout=3.0, probe_paths=False)
    assert report.status == 200
    assert "strict-transport-security" in report.missing_headers
    assert "content-security-policy" in report.missing_headers
    assert "server" in report.disclosures
    assert "VulnerableTest" in report.disclosures["server"]
    titles = [f["title"] for f in report.findings]
    assert "Missing header: content-security-policy" in titles
    # cookie lacks Secure (http target -> only HttpOnly check triggers) and HttpOnly
    assert any("HttpOnly" in f["title"] for f in report.findings)
    assert not report.exposed_paths  # path probing disabled


def test_audit_detects_exposed_paths(server):
    scope = Scope(["127.0.0.1"])
    report = websec.audit(server, scope, timeout=3.0, probe_paths=True)
    assert "/.git/HEAD" in report.exposed_paths
    assert "/.env" in report.exposed_paths
    sev = {f["title"]: f["severity"] for f in report.findings}
    assert sev.get("Exposed path: /.git/HEAD") == "high"
    assert sev.get("Exposed path: /.env") == "high"


def test_audit_returns_severity_for_report_gate(server):
    scope = Scope(["127.0.0.1"])
    report = websec.audit(server, scope, timeout=3.0, probe_paths=True)
    sevs = {f["severity"] for f in report.findings}
    assert sevs & {"medium", "high", "critical"}
