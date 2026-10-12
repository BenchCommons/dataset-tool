"""Spec 004, R7.3: the autouse fixture in conftest.py refuses the network outside the loopback."""

import socket
import urllib.request

import pytest

from conftest import NetworkAccessError


def test_connect_outside_the_loopback_is_refused():
    with socket.socket() as s, pytest.raises(NetworkAccessError, match="93.184.215.14"):
        s.connect(("93.184.215.14", 80))


def test_name_lookup_is_refused():
    with pytest.raises(NetworkAccessError, match="example.org"):
        socket.getaddrinfo("example.org", 443)


def test_urllib_to_a_public_host_is_refused():
    with pytest.raises(Exception) as e:
        urllib.request.urlopen("https://example.org/", timeout=1)
    assert "attempted" in str(e.value)


def test_loopback_server_still_works(server):
    server.files["/a"] = b"ok"
    assert urllib.request.urlopen(server.url("/a"), timeout=5).read() == b"ok"
