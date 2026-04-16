from ecoacher.app import controller as app_controller


class _FakeSignal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)

    def emit(self, *args, **kwargs):
        for callback in list(self.callbacks):
            callback(*args, **kwargs)


class _FakeProcess:
    class ProcessState:
        NotRunning = 0
        Running = 1

    ProcessError = int
    ExitStatus = int

    def __init__(self, *_args, **_kwargs):
        self.started = _FakeSignal()
        self.errorOccurred = _FakeSignal()
        self.finished = _FakeSignal()
        self.readyReadStandardOutput = _FakeSignal()
        self.readyReadStandardError = _FakeSignal()
        self._state = self.ProcessState.NotRunning
        self.stdout_payload = b""
        self.stderr_payload = b""
        self.started_program = None
        self.arguments = None
        self.terminated = False
        self.killed = False

    def setProgram(self, program):
        self.started_program = program

    def setArguments(self, args):
        self.arguments = args

    def state(self):
        return self._state

    def start(self):
        self._state = self.ProcessState.Running

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True

    def waitForFinished(self, timeout):
        return timeout >= 3000

    def readAllStandardOutput(self):
        payload = self.stdout_payload
        self.stdout_payload = b""
        return payload

    def readAllStandardError(self):
        payload = self.stderr_payload
        self.stderr_payload = b""
        return payload


class _FakeTimer:
    def __init__(self, *_args, **_kwargs):
        self.timeout = _FakeSignal()
        self.started = None
        self.stopped = False

    def setSingleShot(self, _value):
        pass

    def setInterval(self, _value):
        pass

    def start(self, value=None):
        self.started = value

    def stop(self):
        self.stopped = True

    @staticmethod
    def singleShot(_ms, callback):
        callback()


class _FakeClipboard:
    def __init__(self):
        self._text = ""

    def text(self):
        return self._text

    def setText(self, text):
        self._text = text


class _FakeApp:
    def __init__(self):
        self.quit_called = False

    def quit(self):
        self.quit_called = True


class _FakeWorker:
    def __init__(self, _client, _text):
        self.statusChanged = _FakeSignal()
        self.success = _FakeSignal()
        self.failed = _FakeSignal()
        self.finished = _FakeSignal()
        self.started = False
        self.running = False

    def start(self):
        self.started = True
        self.running = True

    def isRunning(self):
        return self.running

    def wait(self, _timeout):
        self.running = False


class _FakeClient:
    def __init__(self, base_url=None, directory=None):
        self.base_url = base_url
        self.directory = directory
        self.closed = False
        self.ping_result = True

    def close(self):
        self.closed = True

    def ping(self):
        return self.ping_result


def _make_controller(monkeypatch, qapp):
    clipboard = _FakeClipboard()
    monkeypatch.setattr(app_controller, "QProcess", _FakeProcess)
    monkeypatch.setattr(app_controller, "QTimer", _FakeTimer)
    monkeypatch.setattr(app_controller, "CheckWorker", _FakeWorker)
    monkeypatch.setattr(app_controller, "OpencodeClient", _FakeClient)
    monkeypatch.setattr(app_controller.QApplication, "clipboard", staticmethod(lambda: clipboard))
    monkeypatch.setattr(app_controller, "build_word_diff_html", lambda a, b: f"<{a}|{b}>")

    app = _FakeApp()
    controller = app_controller.AppController(app, tray_available=False, app_id="ecoacher")
    return controller, app, clipboard


def test_text_properties_and_clipboard_actions(monkeypatch, qapp):
    controller, _app, clipboard = _make_controller(monkeypatch, qapp)
    controller.setSpellText("input")
    assert controller.spellText == "input"
    assert controller.correctedDiffHtml == "<|>"

    controller._submitted_spell_text = "input"
    controller._rebuild_corrected_diff_html()
    assert controller.correctedDiffHtml == "<input|>"

    controller.setCorrectedText("fixed")
    assert controller.correctedText == "fixed"
    assert controller.correctedDiffHtml == "<input|fixed>"

    controller.copyCorrectedTextToClipboard()
    assert clipboard.text() == "fixed"

    clipboard.setText("from clip")
    controller.pasteFromClipboard()
    assert controller.spellText == "from clip"

    controller.clearSpellText()
    assert controller.spellText == ""


def test_run_check_guards_and_start(monkeypatch, qapp):
    controller, _app, _clipboard = _make_controller(monkeypatch, qapp)
    controller.runCheck()
    assert controller.requestStatus == ""

    controller.setSpellText("hello")
    controller.runCheck()
    assert controller.requestStatus == "opencode not ready"

    controller._set_opencode_status("ready")
    controller._opencode_client = _FakeClient()
    controller.runCheck()
    assert controller.requestInFlight is True
    assert controller._check_worker is not None
    assert controller._check_worker.started is True


def test_request_check_queueing_and_ready_path(monkeypatch, qapp):
    controller, _app, _clipboard = _make_controller(monkeypatch, qapp)
    controller.requestCheckForCurrentInput()
    assert controller._pending_check is False

    controller.setSpellText("text")
    controller._set_opencode_status("launching")
    controller.requestCheckForCurrentInput()
    assert controller._pending_check is True

    controller._opencode_client = _FakeClient()
    controller._set_opencode_status("ready")
    assert controller._pending_check is False


def test_endpoint_detection_and_ping_handling(monkeypatch, qapp):
    controller, _app, _clipboard = _make_controller(monkeypatch, qapp)
    controller._maybe_set_opencode_endpoint("\x1b[32mopencode server listening on http://127.0.0.1:8080\x1b[0m")
    assert controller.opencodeStatus == "ready"
    assert controller._opencode_server_url == "http://127.0.0.1:8080"

    controller._on_ping_timer_tick()
    assert controller.opencodeStatus == "ready"

    controller._opencode_client.ping_result = False
    controller._on_ping_timer_tick()
    assert controller.opencodeStatus == "not ready"
    assert controller._opencode_client is None


def test_worker_callbacks_and_shutdown(monkeypatch, qapp):
    controller, app, _clipboard = _make_controller(monkeypatch, qapp)
    controller._on_check_success("correct", "понято как <x>", "sum <x>", "corr")
    assert controller.correctedText == "correct"
    assert controller.understoodMeaningRu == "понято как <x>"
    assert "Summary" in controller.explanationText
    assert "sum &lt;x&gt;" in controller.explanationText
    assert "Understood meaning" in controller.explanationText
    assert "понято как &lt;x&gt;" in controller.explanationText
    assert controller.requestStatus == ""

    controller._on_check_failed("err")
    assert controller.requestStatus == "request failed"

    controller._opencode_process._state = _FakeProcess.ProcessState.NotRunning
    controller.requestShutdown()
    assert app.quit_called is True


def test_check_success_omits_understood_meaning_block_when_empty(monkeypatch, qapp):
    controller, _app, _clipboard = _make_controller(monkeypatch, qapp)
    controller._on_check_success("correct", "", "sum", "corr")

    assert "Summary" in controller.explanationText
    assert "Understood meaning" not in controller.explanationText


def test_stdout_stderr_handlers_process_lines(monkeypatch, qapp):
    controller, _app, _clipboard = _make_controller(monkeypatch, qapp)
    controller._opencode_process.stdout_payload = b"line one\nlistening on http://127.0.0.1:9000\n"
    controller._on_opencode_stdout()
    assert controller._opencode_server_url == "http://127.0.0.1:9000"

    controller._opencode_process.stderr_payload = b"warning\nlistening on http://127.0.0.1:9001\n"
    controller._on_opencode_stderr()
    assert controller._opencode_server_url == "http://127.0.0.1:9001"
