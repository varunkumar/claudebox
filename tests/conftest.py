import socket
import pytest

@pytest.fixture
def unused_tcp_port():
    with socket.socket() as s:
        s.bind(('', 0))
        return s.getsockname()[1]
