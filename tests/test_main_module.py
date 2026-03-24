import importlib
import importlib.util
from argparse import Namespace
from pathlib import Path

from ecoacher import main as app_main


class _FakeSignal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)


class _FakeTimer:
    def __init__(self):
        self.timeout = _FakeSignal()
        self.started_with = None

    def start(self, value):
        self.started_with = value


class _FakeRootWindow:
    def __init__(self):
        self.properties = {}

    def setProperty(self, key, value):
        self.properties[key] = value


class _FakeEngine:
    root_objects = [None]

    def __init__(self):
        self.loaded = None

    def load(self, url):
        self.loaded = url

    def rootObjects(self):
        return self.root_objects


class _FakeApp:
    set_names = []
    desktop_names = []

    @classmethod
    def setApplicationName(cls, name):
        cls.set_names.append(name)

    @classmethod
    def setDesktopFileName(cls, name):
        cls.desktop_names.append(name)

    def __init__(self, argv):
        self.argv = argv
        self.quit_on_last_window_closed = None
        self.exec_result = 7

    def setQuitOnLastWindowClosed(self, value):
        self.quit_on_last_window_closed = value

    def exec(self):
        return self.exec_result


class _FakeController:
    def __init__(self, app, tray_available, app_id):
        self.app = app
        self.tray_available = tray_available
        self.app_id = app_id
        self.calls = []

    def requestShutdown(self):
        self.calls.append("shutdown")

    def setSpellText(self, text):
        self.calls.append(("spell", text))

    def requestCheckForCurrentInput(self):
        self.calls.append("auto-check")

    def set_window(self, window):
        self.calls.append(("window", window))

    def ensureOpencodeStopped(self):
        self.calls.append("stop-opencode")


def _patch_runtime(
    monkeypatch,
    cli: Namespace,
    root_objects,
    spell_result: str | None = "text",
    show_running: bool = False,
):
    _FakeEngine.root_objects = root_objects

    monkeypatch.setattr(app_main, "_parse_cli_args", lambda _argv: cli)
    monkeypatch.setattr(app_main, "configure_logging", lambda: None)
    monkeypatch.setattr(app_main, "QApplication", _FakeApp)
    monkeypatch.setattr(app_main, "QSystemTrayIcon", type("T", (), {"isSystemTrayAvailable": staticmethod(lambda: True)}))
    monkeypatch.setattr(app_main, "QTimer", _FakeTimer)
    monkeypatch.setattr(app_main, "QQmlApplicationEngine", _FakeEngine)
    monkeypatch.setattr(app_main, "AppController", _FakeController)
    monkeypatch.setattr(app_main, "request_show_window", lambda _name: show_running)
    monkeypatch.setattr(app_main, "_run_spell_command", lambda _args, _server: spell_result)
    monkeypatch.setattr(app_main, "setup_spell_server", lambda _controller, _name: object())
    monkeypatch.setattr(app_main.signal, "signal", lambda *_args: None)


def test_parse_cli_args_profile_from_env(monkeypatch):
    monkeypatch.setenv("ECOACHER_PROFILE", "dev")
    cli = app_main._parse_cli_args(["spell", "a"])
    assert cli.profile == "dev"
    assert cli.command == "spell"
    assert cli.text == ["a"]


def test_parse_cli_args_invalid_env_falls_back(monkeypatch):
    monkeypatch.setenv("ECOACHER_PROFILE", "invalid")
    cli = app_main._parse_cli_args([])
    assert cli.profile == "normal"
    assert cli.command is None


def test_run_spell_command_paths(monkeypatch, capsys):
    monkeypatch.setattr(app_main, "read_spell_text", lambda _args: "")
    assert app_main._run_spell_command([], "srv") is None
    assert "spell text is empty" in capsys.readouterr().err

    monkeypatch.setattr(app_main, "read_spell_text", lambda _args: "payload")
    monkeypatch.setattr(app_main, "send_spell_text", lambda *_args: True)
    assert app_main._run_spell_command([], "srv") == ""

    monkeypatch.setattr(app_main, "send_spell_text", lambda *_args: False)
    assert app_main._run_spell_command([], "srv") == "payload"


def test_main_spell_command_error_returns_1(monkeypatch):
    cli = Namespace(profile="normal", command="spell", text=["x"])
    _patch_runtime(monkeypatch, cli, [_FakeRootWindow()], spell_result=None)
    assert app_main.main() == 1


def test_main_spell_command_short_circuit_returns_0(monkeypatch):
    cli = Namespace(profile="normal", command="spell", text=["x"])
    _patch_runtime(monkeypatch, cli, [_FakeRootWindow()], spell_result="")
    assert app_main.main() == 0


def test_main_existing_instance_returns_0(monkeypatch):
    cli = Namespace(profile="normal", command=None, text=[])
    _patch_runtime(monkeypatch, cli, [_FakeRootWindow()], show_running=True)
    assert app_main.main() == 0


def test_main_qml_load_failure_returns_1(monkeypatch):
    cli = Namespace(profile="dev", command=None, text=[])
    _patch_runtime(monkeypatch, cli, [])
    assert app_main.main() == 1


def test_main_success_path_sets_window_and_returns_exec_code(monkeypatch):
    cli = Namespace(profile="dev", command="spell", text=["x"])
    root = _FakeRootWindow()
    _patch_runtime(monkeypatch, cli, [root], spell_result="boot text")

    exit_code = app_main.main()
    assert exit_code == 7
    assert _FakeApp.set_names[-1] == "ecoacher-dev"
    assert _FakeApp.desktop_names[-1] == "ecoacher-dev"
    assert root.properties["appProfile"] == "dev"


def test_root_launcher_adds_src_to_syspath():
    launcher_path = Path(__file__).resolve().parents[1] / "main.py"
    spec = importlib.util.spec_from_file_location("ecoacher_root_main", launcher_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert str(module.SRC_PATH) in module.sys.path
