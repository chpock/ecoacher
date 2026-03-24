import logging

from ecoacher.logging import setup as logging_setup


class _DummyContext:
    def __init__(self, file_name: str = "", line: int = 0) -> None:
        self.file = file_name
        self.line = line


def test_should_use_color_respects_no_color(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("CLICOLOR_FORCE", "1")
    assert logging_setup._should_use_color() is False


def test_should_use_color_respects_force(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("CLICOLOR_FORCE", "1")
    assert logging_setup._should_use_color() is True


def test_should_use_color_respects_dumb_term(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("CLICOLOR_FORCE", "0")
    monkeypatch.setenv("TERM", "dumb")
    assert logging_setup._should_use_color() is False


def test_should_use_color_uses_tty(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("CLICOLOR_FORCE", "0")
    monkeypatch.setenv("TERM", "xterm")
    monkeypatch.setattr(logging_setup.sys.stdout, "isatty", lambda: True)
    assert logging_setup._should_use_color() is True


def test_qt_message_handler_routes_levels(caplog):
    caplog.set_level(logging.DEBUG, logger="qt")
    context = _DummyContext("file.qml", 42)

    logging_setup._qt_message_handler(logging_setup.QtMsgType.QtDebugMsg, context, "debug")
    logging_setup._qt_message_handler(logging_setup.QtMsgType.QtInfoMsg, context, "info")
    logging_setup._qt_message_handler(logging_setup.QtMsgType.QtWarningMsg, context, "warn")
    logging_setup._qt_message_handler(logging_setup.QtMsgType.QtCriticalMsg, context, "error")
    logging_setup._qt_message_handler(logging_setup.QtMsgType.QtFatalMsg, context, "fatal")

    messages = [record.getMessage() for record in caplog.records]
    assert any("debug (file.qml:42)" in message for message in messages)
    assert any("info (file.qml:42)" in message for message in messages)
    assert any("warn (file.qml:42)" in message for message in messages)
    assert any("error (file.qml:42)" in message for message in messages)
    assert any("fatal (file.qml:42)" in message for message in messages)


def test_install_qt_logging_bridge_calls_installer(monkeypatch):
    called = {"handler": None}

    def fake_install(handler):
        called["handler"] = handler

    monkeypatch.setattr(logging_setup, "qInstallMessageHandler", fake_install)
    logging_setup._install_qt_logging_bridge()
    assert called["handler"] is logging_setup._qt_message_handler


def test_configure_logging_color(monkeypatch):
    monkeypatch.setenv("ECOACHER_LOG_LEVEL", "debug")
    monkeypatch.setattr(logging_setup, "_should_use_color", lambda: True)
    installed = {"called": False}
    monkeypatch.setattr(logging_setup, "_install_qt_logging_bridge", lambda: installed.update(called=True))

    logging_setup.configure_logging()
    root = logging.getLogger()
    assert root.level == logging.DEBUG
    assert len(root.handlers) == 1
    assert installed["called"] is True


def test_configure_logging_plain_invalid_level(monkeypatch):
    monkeypatch.setenv("ECOACHER_LOG_LEVEL", "not_a_level")
    monkeypatch.setattr(logging_setup, "_should_use_color", lambda: False)
    monkeypatch.setattr(logging_setup, "_install_qt_logging_bridge", lambda: None)

    logging_setup.configure_logging()
    root = logging.getLogger()
    assert root.level == logging.INFO
