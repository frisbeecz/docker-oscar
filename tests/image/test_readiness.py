"""Owned local HTTP startup resets are transient, never readiness evidence."""
import http.server
import json
import socket
import socketserver
import struct
import threading
from unittest.mock import Mock

import pytest

from ci import runtime


def binding(monkeypatch, host="127.0.0.1", port="12345"):
    monkeypatch.setattr(runtime, "output", lambda _: json.dumps([{
        "State": {"Running": True},
        "NetworkSettings": {"Ports": {"3000/tcp": [{"HostIp": host, "HostPort": port}]}}
    }]))


def clock(monkeypatch):
    now = [0]
    monkeypatch.setattr(runtime.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(runtime.time, "sleep", lambda seconds: now.__setitem__(0, now[0] + seconds))
    return now


def test_direct_reset_then_http_200(monkeypatch):
    binding(monkeypatch)
    clock(monkeypatch)
    response = Mock()
    response.__enter__ = Mock(return_value=Mock(status=200))
    response.__exit__ = Mock(return_value=False)
    open_url = Mock(side_effect=[ConnectionResetError(104, "reset"), response])
    monkeypatch.setattr(runtime.urllib.request, "urlopen", open_url)
    assert runtime.wait_http("owned") == "http://127.0.0.1:12345"
    assert open_url.call_count == 2
    assert open_url.call_args.kwargs == {"timeout": 3}


def test_reset_never_succeeds_and_deadline_is_preserved(monkeypatch):
    binding(monkeypatch)
    now = clock(monkeypatch)
    monkeypatch.setattr(runtime.urllib.request, "urlopen", Mock(side_effect=ConnectionResetError(104, "reset")))
    with pytest.raises(TimeoutError, match="did not become ready"):
        runtime.wait_http("owned")
    assert now[0] == 90


@pytest.mark.parametrize("error", [ValueError("bug"), PermissionError("not startup"), OSError("unrelated")])
def test_unrelated_errors_are_not_polled(monkeypatch, error):
    binding(monkeypatch)
    monkeypatch.setattr(runtime.urllib.request, "urlopen", Mock(side_effect=error))
    with pytest.raises(type(error), match=str(error)):
        runtime.wait_http("owned")


def test_non_loopback_fails_before_http(monkeypatch):
    binding(monkeypatch, "0.0.0.0")
    open_url = Mock()
    monkeypatch.setattr(runtime.urllib.request, "urlopen", open_url)
    with pytest.raises(ValueError, match="loopback"):
        runtime.wait_http("owned")
    open_url.assert_not_called()


def test_http_200_after_readiness_deadline_is_not_success(monkeypatch):
    binding(monkeypatch)
    now = clock(monkeypatch)
    class LateResponse:
        status = 200
        def __enter__(self):
            now[0] = 91
            return self
        def __exit__(self, *args):
            pass
    monkeypatch.setattr(runtime.urllib.request, "urlopen", lambda *a, **kw: LateResponse())
    with pytest.raises(TimeoutError):
        runtime.wait_http("owned")


def test_real_loopback_reset_then_non200_then_200(monkeypatch):
    class Handler(http.server.BaseHTTPRequestHandler):
        count = 0

        def do_GET(self):
            type(self).count += 1
            if self.count == 1:
                # SO_LINGER aborts the owned connection with TCP RST.
                self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
                self.connection.close()
                return
            self.send_response(503 if self.count == 2 else 200)
            self.end_headers()

        def log_message(self, *args):
            pass

    with socketserver.TCPServer(("127.0.0.1", 0), Handler) as server:
        binding(monkeypatch, port=str(server.server_address[1]))
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            assert runtime.wait_http("owned").endswith(str(server.server_address[1]))
            assert Handler.count == 3
        finally:
            server.shutdown()
            thread.join()
