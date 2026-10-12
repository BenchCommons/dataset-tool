"""Local HTTP server for download tests (spec 004, R7.3): tests never use the network.

Ported from BenchCommons/dataset-names@e7e8405 tests/conftest.py (ServidorLocal).
"""

import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

_LOOPBACK = {"127.0.0.1", "::1", "localhost"}


class NetworkAccessError(RuntimeError):
    """A test tried to reach a host other than the loopback (spec 004, R7.3)."""


def _host(address) -> str:
    return address[0] if isinstance(address, tuple) else str(address)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Refuse every connection and name lookup outside the loopback, in every test."""
    connect, connect_ex, getaddrinfo = socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo

    def guard(address):
        # str or bytes addresses are AF_UNIX sockets, local by definition.
        if not isinstance(address, (str, bytes)) and _host(address) not in _LOOPBACK:
            raise NetworkAccessError(f"network access attempted: {address!r}")

    def guarded_connect(self, address):
        guard(address)
        return connect(self, address)

    def guarded_connect_ex(self, address):
        guard(address)
        return connect_ex(self, address)

    def guarded_getaddrinfo(host, *args, **kwargs):
        if host is not None and (host.decode() if isinstance(host, bytes) else host) not in _LOOPBACK:
            raise NetworkAccessError(f"name lookup attempted: {host!r}")
        return getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)


class LocalServer:
    """HTTP server on 127.0.0.1 with responses programmable per path."""

    def __init__(self):
        self.files: dict[str, bytes] = {}
        self.failures: dict[str, int] = {}  # path -> how many 500 responses before serving
        self.truncated: set[str] = set()  # paths that announce twice their size and close
        self.slow: dict[str, float] = {}  # path -> seconds to wait before answering
        self.refused: set[str] = set()  # paths answering 403, like a server that blocks robots
        self.content_types: dict[str, str] = {}  # path -> Content-Type sent with the response
        self.responses: dict[str, list[int]] = {}  # path -> HTTP codes served in sequence before serving
        self.content_length: dict[str, str] = {}  # path -> literal Content-Length (for malformed values)
        self.requests: list[tuple[str, str]] = []  # (path, User-Agent)
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                server.requests.append((self.path, self.headers.get("User-Agent", "")))
                if self.path in server.refused:
                    self.send_error(403)
                    return
                if server.responses.get(self.path):
                    self.send_error(server.responses[self.path].pop(0))
                    return
                if server.failures.get(self.path, 0) > 0:
                    server.failures[self.path] -= 1
                    self.send_error(500)
                    return
                time.sleep(server.slow.get(self.path, 0))
                body = server.files.get(self.path)
                if body is None:
                    self.send_error(404)
                    return
                announced = len(body) * 2 if self.path in server.truncated else len(body)
                self.send_response(200)
                self.send_header("Content-Length", server.content_length.get(self.path, str(announced)))
                if self.path in server.content_types:
                    self.send_header("Content-Type", server.content_types[self.path])
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        class Server(ThreadingHTTPServer):
            def handle_error(self, request, client_address):
                # A client that gives up (timeout) closes the connection; that is not a test failure.
                if isinstance(sys.exc_info()[1], (BrokenPipeError, ConnectionResetError)):
                    return
                super().handle_error(request, client_address)

        self.httpd = Server(("127.0.0.1", 0), Handler)

    def url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.httpd.server_port}{path}"

    def paths(self) -> list[str]:
        return [path for path, _ in self.requests]


@pytest.fixture
def server():
    s = LocalServer()
    thread = threading.Thread(target=s.httpd.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    yield s
    s.httpd.shutdown()
    s.httpd.server_close()
