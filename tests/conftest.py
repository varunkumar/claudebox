import socket
import pytest

@pytest.fixture
def unused_tcp_port():
    with socket.socket() as s:
        s.bind(('', 0))
        return s.getsockname()[1]

@pytest.fixture
def unused_tcp_port_pair():
    with socket.socket() as s1, socket.socket() as s2:
        s1.bind(('', 0))
        s2.bind(('', 0))
        return s1.getsockname()[1], s2.getsockname()[1]
