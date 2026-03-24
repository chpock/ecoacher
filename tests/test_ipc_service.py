import io

import pytest

from ecoacher.ipc import service


class _FakeSocket:
    connect_ok = True
    bytes_written_ok = True

    def __init__(self):
        self.server_name = None
        self.writes = []
        self.disconnected = False

    def connectToServer(self, server_name):
        self.server_name = server_name

    def waitForConnected(self, _timeout):
        return self.connect_ok

    def write(self, payload):
        self.writes.append(payload)

    def waitForBytesWritten(self, _timeout):
        return self.bytes_written_ok

    def disconnectFromServer(self):
        self.disconnected = True


class _FakeSignal:
    def __init__(self):
        self.callback = None

    def connect(self, callback):
        self.callback = callback


class _FakeConnection:
    def __init__(self, payload: str = "", ready: bool = True):
        self.payload = payload
        self.ready = ready
        self.disconnected = False

    def waitForReadyRead(self, _timeout):
        return self.ready

    def readAll(self):
        return self.payload.encode("utf-8")

    def disconnectFromServer(self):
        self.disconnected = True


class _FakeServer:
    listen_sequence = [True]
    listening_state = True
    removed = []
    instances = []

    def __init__(self):
        self.newConnection = _FakeSignal()
        self.connections = []
        self.listen_calls = []
        _FakeServer.instances.append(self)

    @classmethod
    def removeServer(cls, name):
        cls.removed.append(name)

    def listen(self, name):
        self.listen_calls.append(name)
        if self.listen_sequence:
            return self.listen_sequence.pop(0)
        return True

    def isListening(self):
        return self.listening_state

    def hasPendingConnections(self):
        return bool(self.connections)

    def nextPendingConnection(self):
        if self.connections:
            return self.connections.pop(0)
        return None


def test_read_spell_text_from_args_and_stdin(monkeypatch):
    assert service.read_spell_text(["a", "b"]) == "a b"
    monkeypatch.setattr(service.sys, "stdin", io.StringIO(" from stdin \n"))
    assert service.read_spell_text([]) == "from stdin"


def test_send_spell_text_branches(monkeypatch, capsys):
    monkeypatch.setattr(service, "QLocalSocket", _FakeSocket)

    _FakeSocket.connect_ok = False
    assert service.send_spell_text("hello", "srv") is False

    _FakeSocket.connect_ok = True
    _FakeSocket.bytes_written_ok = False
    assert service.send_spell_text("hello", "srv") is False
    assert "failed to deliver text to ecoacher" in capsys.readouterr().err

    _FakeSocket.bytes_written_ok = True
    assert service.send_spell_text("hello", "srv") is True


def test_request_show_window_branches(monkeypatch):
    monkeypatch.setattr(service, "QLocalSocket", _FakeSocket)

    _FakeSocket.connect_ok = False
    assert service.request_show_window("srv") is False

    _FakeSocket.connect_ok = True
    _FakeSocket.bytes_written_ok = False
    assert service.request_show_window("srv") is False

    _FakeSocket.bytes_written_ok = True
    assert service.request_show_window("srv") is True


def test_setup_spell_server_raises_when_listen_fails(monkeypatch):
    _FakeServer.listen_sequence = [False, False]
    _FakeServer.listening_state = False
    _FakeServer.removed = []
    monkeypatch.setattr(service, "QLocalServer", _FakeServer)

    with pytest.raises(RuntimeError, match="failed to start local spell server"):
        service.setup_spell_server(object(), "srv")

    assert _FakeServer.removed == ["srv"]


def test_setup_spell_server_processes_connection_payloads(monkeypatch):
    _FakeServer.listen_sequence = [True]
    _FakeServer.listening_state = True
    _FakeServer.instances = []
    monkeypatch.setattr(service, "QLocalServer", _FakeServer)

    class _Controller:
        def __init__(self):
            self.calls = []

        def showWindow(self):
            self.calls.append("show")

        def setSpellText(self, text):
            self.calls.append(("text", text))

        def requestCheckForCurrentInput(self):
            self.calls.append("check")

    controller = _Controller()
    server = service.setup_spell_server(controller, "srv")
    assert server is _FakeServer.instances[-1]

    server.connections = [
        None,
        _FakeConnection("", ready=False),
        _FakeConnection("   ", ready=True),
        _FakeConnection(service.SHOW_WINDOW_COMMAND, ready=True),
        _FakeConnection("payload text", ready=True),
    ]

    server.newConnection.callback()
    assert controller.calls == ["show", ("text", "payload text"), "show", "check"]
