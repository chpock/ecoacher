import html
import logging
import os
import re
from typing import Any

from PySide6.QtCore import QObject, Property, QProcess, QTimer, Signal, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QStyle, QSystemTrayIcon

from ..config.constants import OPENCODE_PING_ENABLED, OPENCODE_PING_INTERVAL_MS
from ..opencode.client import OpencodeClient
from ..opencode.request import CheckWorker
from ..spellcheck.manager import SpellCheckManager
from ..text.diff import build_word_diff_html



logger = logging.getLogger(__name__)


class AppController(QObject):
    spellTextChanged = Signal()
    correctedTextChanged = Signal()
    correctedDiffHtmlChanged = Signal()
    summaryRuChanged = Signal()
    correctionsChanged = Signal()
    explanationTextChanged = Signal()
    opencodeStatusChanged = Signal()
    requestStatusChanged = Signal()
    requestInFlightChanged = Signal()

    def __init__(self, app: QApplication, tray_available: bool, app_id: str) -> None:
        super().__init__()
        logger.info("Initializing AppController (tray_available=%s, app_id=%s)", tray_available, app_id)
        self._app = app
        self._app_id = app_id
        self._tray_available = tray_available
        self._window: Any = None
        self._tray_icon = None
        self._tray_menu = None
        self._toggle_visibility_action = None
        self._quit_action = None
        self._window_hidden = False
        self._spell_text = ""
        self._submitted_spell_text = ""
        self._corrected_text = ""
        self._corrected_diff_html = ""
        self._summary_ru = ""
        self._corrections_text = ""
        self._explanation_text = ""
        self._request_status = ""
        self._request_in_flight = False
        self._opencode_process = QProcess(self)
        self._opencode_process.setProgram("opencode")
        self._opencode_process.setArguments(["serve"])
        self._opencode_kill_timer = QTimer(self)
        self._opencode_kill_timer.setSingleShot(True)
        self._opencode_ping_timer = QTimer(self)
        self._opencode_ping_timer.setInterval(OPENCODE_PING_INTERVAL_MS)
        self._is_shutting_down = False
        self._opencode_status = "not ready"
        self._opencode_server_url: str | None = None
        self._opencode_client: OpencodeClient | None = None
        self._opencode_stdout_buffer = ""
        self._check_worker: CheckWorker | None = None
        self._pending_check = False
        self._spell_check_manager: SpellCheckManager | None = None

        self._opencode_process.started.connect(self._on_opencode_started)
        self._opencode_process.errorOccurred.connect(self._on_opencode_error)
        self._opencode_process.finished.connect(self._on_opencode_finished)
        self._opencode_process.readyReadStandardOutput.connect(self._on_opencode_stdout)
        self._opencode_process.readyReadStandardError.connect(self._on_opencode_stderr)
        self._opencode_kill_timer.timeout.connect(self._kill_opencode)
        self._opencode_ping_timer.timeout.connect(self._on_ping_timer_tick)
        if OPENCODE_PING_ENABLED:
            self._opencode_ping_timer.start()

        if self._tray_available:
            self._setup_tray_icon()

    @Property(bool, constant=True)
    def trayAvailable(self) -> bool:
        logger.debug("Reading tray availability: %s", self._tray_available)
        return self._tray_available

    @Property(str, notify=spellTextChanged)
    def spellText(self) -> str:
        logger.debug("Reading spell text (%d chars)", len(self._spell_text))
        return self._spell_text

    @Property(str, notify=correctedTextChanged)
    def correctedText(self) -> str:
        logger.debug("Reading corrected text (%d chars)", len(self._corrected_text))
        return self._corrected_text

    @Property(str, notify=correctedDiffHtmlChanged)
    def correctedDiffHtml(self) -> str:
        logger.debug("Reading corrected diff HTML (%d chars)", len(self._corrected_diff_html))
        return self._corrected_diff_html

    @Property(str, notify=explanationTextChanged)
    def explanationText(self) -> str:
        logger.debug("Reading explanation text (%d chars)", len(self._explanation_text))
        return self._explanation_text

    @Property(str, notify=summaryRuChanged)
    def summaryRu(self) -> str:
        logger.debug("Reading summary_ru text (%d chars)", len(self._summary_ru))
        return self._summary_ru

    @Property(str, notify=correctionsChanged)
    def correctionsText(self) -> str:
        logger.debug("Reading corrections text (%d chars)", len(self._corrections_text))
        return self._corrections_text

    @Property(str, notify=opencodeStatusChanged)
    def opencodeStatus(self) -> str:
        logger.debug("Reading opencode status: %s", self._opencode_status)
        return self._opencode_status

    @Property(str, notify=requestStatusChanged)
    def requestStatus(self) -> str:
        logger.debug("Reading request status: %s", self._request_status)
        return self._request_status

    @Property(bool, notify=requestInFlightChanged)
    def requestInFlight(self) -> bool:
        logger.debug("Reading request in-flight: %s", self._request_in_flight)
        return self._request_in_flight

    @Slot(str)
    def setSpellText(self, text: str) -> None:
        if text == self._spell_text:
            return

        self._spell_text = text
        self.spellTextChanged.emit()
        self._rebuild_corrected_diff_html()

    @Slot()
    def clearSpellText(self) -> None:
        logger.info("Clearing spell text")
        self.setSpellText("")

    @Slot()
    def pasteFromClipboard(self) -> None:
        logger.info("Pasting spell text from clipboard")
        clipboard = QApplication.clipboard()
        self.setSpellText(clipboard.text())

    @Slot(str)
    def setCorrectedText(self, text: str) -> None:
        if text == self._corrected_text:
            return

        logger.info("Updating corrected text (%d chars)", len(text))
        self._corrected_text = text
        self.correctedTextChanged.emit()
        self._rebuild_corrected_diff_html()

    @Slot()
    def copyCorrectedTextToClipboard(self) -> None:
        clipboard = QApplication.clipboard()
        clipboard.setText(self._corrected_text)
        logger.info("Copied corrected text to clipboard (%d chars)", len(self._corrected_text))

    @Slot(int, result="QVariantList")
    def spellingSuggestionsAtPosition(self, position: int) -> list[str]:
        if self._spell_check_manager is None:
            return []

        return self._spell_check_manager.get_suggestions_at(position)

    @Slot(int, result=bool)
    def hasSpellingSuggestionsAtPosition(self, position: int) -> bool:
        if self._spell_check_manager is None:
            return False

        return self._spell_check_manager.has_suggestions_at(position)

    @Slot(int, str)
    def replaceSpellingAtPosition(self, position: int, replacement: str) -> None:
        if self._spell_check_manager is None:
            return

        self._spell_check_manager.apply_replacement_at(position, replacement)

    @Slot(str)
    def setExplanationText(self, text: str) -> None:
        if text == self._explanation_text:
            return

        logger.info("Updating explanation text (%d chars)", len(text))
        self._explanation_text = text
        self.explanationTextChanged.emit()

    @Slot(str)
    def setSummaryRu(self, text: str) -> None:
        if text == self._summary_ru:
            return

        logger.info("Updating summary_ru text (%d chars)", len(text))
        self._summary_ru = text
        self.summaryRuChanged.emit()

    @Slot(str)
    def setCorrectionsText(self, text: str) -> None:
        if text == self._corrections_text:
            return

        logger.info("Updating corrections text (%d chars)", len(text))
        self._corrections_text = text
        self.correctionsChanged.emit()

    @Slot()
    def runCheck(self) -> None:
        logger.info("Check requested")
        self._pending_check = False
        input_text = self._spell_text.strip()
        if not input_text:
            logger.warning("Cannot run check: input text is empty")
            return

        if self._opencode_status != "ready":
            logger.warning("Cannot run check: opencode status is %s", self._opencode_status)
            self._set_request_status("opencode not ready")
            return

        if self._opencode_client is None:
            logger.warning("Cannot run check: opencode client is not initialized")
            self._set_request_status("opencode not ready")
            return

        if self._check_worker is not None and self._check_worker.isRunning():
            logger.warning("Check already running; ignoring new request")
            self._set_request_status("request already running")
            return

        self._set_request_status("create session")
        self._submitted_spell_text = input_text
        self.setCorrectedText("")
        self.setSummaryRu("")
        self.setCorrectionsText("")
        self.setExplanationText("")

        logger.info("Starting SDK check worker")
        self._set_request_in_flight(True)
        self._check_worker = CheckWorker(self._opencode_client, input_text)
        self._check_worker.statusChanged.connect(self._on_check_status_changed)
        self._check_worker.success.connect(self._on_check_success)
        self._check_worker.failed.connect(self._on_check_failed)
        self._check_worker.finished.connect(self._on_check_worker_finished)
        self._check_worker.start()

    @Slot()
    def requestCheckForCurrentInput(self) -> None:
        input_text = self._spell_text.strip()
        if not input_text:
            logger.debug("Skipping auto-check request: input text is empty")
            self._pending_check = False
            return

        if self._check_worker is not None and self._check_worker.isRunning():
            logger.info("Check is running; queueing check for current input")
            self._pending_check = True
            return

        if self._opencode_status == "ready":
            logger.info("Auto-check request accepted; running check")
            self._pending_check = False
            self.runCheck()
            return

        logger.info("Auto-check request queued until opencode is ready")
        self._pending_check = True

    def set_window(self, window: Any) -> None:
        logger.info("Binding root window to controller")
        self._window = window
        self._spell_check_manager = SpellCheckManager(window)
        self._window_hidden = not bool(self._window.isVisible())
        self._refresh_toggle_action_text()
        QTimer.singleShot(0, self.startOpencodeServer)

    @Slot(result=bool)
    def handleCloseRequest(self) -> bool:
        logger.info("Received window close request")
        if self._tray_available and self._window is not None:
            logger.info("Tray available; hiding window instead of closing")
            self.hideWindow()
            return False

        logger.info("Tray unavailable; initiating application shutdown")
        self.requestShutdown()
        return False

    @Slot()
    def showWindow(self) -> None:
        if self._window is None:
            logger.warning("Cannot show window: root window is not bound")
            return

        logger.info("Showing application window")
        self._window.show()
        self._window.raise_()
        self._window.requestActivate()
        self._window_hidden = False
        self._refresh_toggle_action_text()

    @Slot()
    def hideWindow(self) -> None:
        if self._window is None:
            logger.warning("Cannot hide window: root window is not bound")
            return

        logger.info("Hiding application window")
        self._window.hide()
        self._window_hidden = True
        self._refresh_toggle_action_text()

    @Slot()
    def toggleWindowVisibility(self) -> None:
        if self._window is None:
            logger.warning("Cannot toggle window visibility: root window is not bound")
            return

        logger.debug("Toggling window visibility (hidden=%s)", self._window_hidden)
        if self._window_hidden:
            self.showWindow()
        else:
            self.hideWindow()

    @Slot()
    def quitApplication(self) -> None:
        logger.info("Exit action selected from tray menu")
        self.requestShutdown()

    @Slot()
    def requestShutdown(self) -> None:
        if self._is_shutting_down:
            logger.debug("Shutdown already in progress; ignoring duplicate request")
            return

        logger.info("Application shutdown requested")
        self._is_shutting_down = True
        self._opencode_ping_timer.stop()
        if self._spell_check_manager is not None:
            self._spell_check_manager.close()
            self._spell_check_manager = None
        if self._tray_icon is not None:
            logger.debug("Hiding tray icon")
            self._tray_icon.hide()

        if self._check_worker is not None and self._check_worker.isRunning():
            logger.info("Waiting for active SDK check worker to finish")
            self._check_worker.wait(5000)
            self._set_request_in_flight(False)

        if self._opencode_process.state() == QProcess.ProcessState.NotRunning:
            logger.info("Opencode process not running; quitting application now")
            self._app.quit()
            return

        logger.info("Terminating opencode process before app exit")
        self._opencode_kill_timer.start(3000)
        self._opencode_process.terminate()

    @Slot()
    def startOpencodeServer(self) -> None:
        if self._is_shutting_down:
            logger.debug("Skipping opencode start during shutdown")
            return

        if self._opencode_process.state() != QProcess.ProcessState.NotRunning:
            logger.debug("Opencode already running or starting; skipping start")
            return

        logger.info("Starting opencode server process")
        self._opencode_stdout_buffer = ""
        self._opencode_server_url = None
        if self._opencode_client is not None:
            self._opencode_client.close()
            self._opencode_client = None
        self._set_opencode_status("launching")
        self._opencode_process.start()

    def _setup_tray_icon(self) -> None:
        logger.info("Setting up system tray icon and menu")
        icon = self._app.style().standardIcon(QStyle.SP_ComputerIcon)
        self._tray_icon = QSystemTrayIcon(icon, self)
        self._tray_icon.setToolTip(self._app_id)

        self._tray_menu = QMenu()
        self._toggle_visibility_action = QAction("Show", self._tray_menu)
        self._toggle_visibility_action.triggered.connect(self.toggleWindowVisibility)
        self._quit_action = QAction("Exit", self._tray_menu)
        self._quit_action.triggered.connect(self.quitApplication)
        self._tray_menu.aboutToShow.connect(self._update_tray_menu_labels)
        self._tray_menu.addAction(self._toggle_visibility_action)
        self._tray_menu.addAction(self._quit_action)

        self._tray_icon.setContextMenu(self._tray_menu)
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.show()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        logger.debug("Tray icon activated (reason=%s)", reason)
        if reason == QSystemTrayIcon.Trigger:
            self.toggleWindowVisibility()

    def _update_tray_menu_labels(self) -> None:
        logger.debug("Updating tray menu labels")
        self._refresh_toggle_action_text()

    def _refresh_toggle_action_text(self) -> None:
        if self._toggle_visibility_action is None:
            logger.debug("Tray toggle action not available yet")
            return

        if self._window_hidden:
            self._toggle_visibility_action.setText("Show")
        else:
            self._toggle_visibility_action.setText("Hide")

    def _set_opencode_status(self, status: str) -> None:
        if self._opencode_status == status:
            logger.debug("Opencode status unchanged: %s", status)
            return

        logger.info("Opencode status changed: %s -> %s", self._opencode_status, status)
        self._opencode_status = status
        self.opencodeStatusChanged.emit()

        if status == "ready" and self._pending_check:
            logger.info("Opencode ready with pending check request")
            QTimer.singleShot(0, self.requestCheckForCurrentInput)

    def _set_request_status(self, status: str) -> None:
        if self._request_status == status:
            return

        logger.info("Request status changed: %s -> %s", self._request_status, status)
        self._request_status = status
        self.requestStatusChanged.emit()

    def _set_request_in_flight(self, in_flight: bool) -> None:
        if self._request_in_flight == in_flight:
            return

        logger.info("Request in-flight changed: %s -> %s", self._request_in_flight, in_flight)
        self._request_in_flight = in_flight
        self.requestInFlightChanged.emit()

    def _rebuild_corrected_diff_html(self) -> None:
        rendered = build_word_diff_html(self._submitted_spell_text, self._corrected_text)
        if rendered == self._corrected_diff_html:
            return

        self._corrected_diff_html = rendered
        self.correctedDiffHtmlChanged.emit()

    def _maybe_set_opencode_endpoint(self, line: str) -> None:
        plain_line = re.sub(r"\x1b\[[0-9;]*m", "", line).strip()
        match = re.search(r"listening on (https?://\S+)", plain_line, flags=re.IGNORECASE)
        if match is None:
            return

        endpoint = match.group(1).rstrip(".,)")
        if endpoint == self._opencode_server_url and self._opencode_client is not None:
            return

        logger.info("Detected opencode endpoint: %s", endpoint)
        self._opencode_server_url = endpoint
        if self._opencode_client is not None:
            self._opencode_client.close()

        self._opencode_client = OpencodeClient(
            base_url=endpoint,
            directory=os.getcwd(),
        )
        self._set_opencode_status("ready")

    def _kill_opencode(self) -> None:
        if self._opencode_process.state() != QProcess.ProcessState.NotRunning:
            logger.warning("Opencode terminate timeout reached; killing process")
            self._opencode_process.kill()

    def ensureOpencodeStopped(self) -> None:
        self._opencode_ping_timer.stop()
        if self._spell_check_manager is not None:
            self._spell_check_manager.close()
            self._spell_check_manager = None

        if self._check_worker is not None and self._check_worker.isRunning():
            logger.info("Final cleanup: waiting for check worker")
            self._check_worker.wait(5000)
            self._set_request_in_flight(False)

        if self._opencode_client is not None:
            logger.debug("Closing opencode SDK client")
            self._opencode_client.close()
            self._opencode_client = None

        if self._opencode_process.state() == QProcess.ProcessState.NotRunning:
            logger.debug("Opencode already stopped during final cleanup")
            return

        logger.info("Final cleanup: terminating opencode process")
        self._opencode_process.terminate()
        if self._opencode_process.waitForFinished(3000):
            logger.info("Opencode process terminated cleanly during final cleanup")
            return

        logger.warning("Force-killing opencode process during final cleanup")
        self._opencode_process.kill()
        self._opencode_process.waitForFinished(2000)

    def _on_opencode_started(self) -> None:
        logger.info("Opencode process started")
        self._set_opencode_status("launching")

    def _on_opencode_error(self, _error: QProcess.ProcessError) -> None:
        if self._is_shutting_down:
            logger.info("Opencode process stopped during shutdown")
        else:
            logger.error("Opencode process error occurred")
        self._opencode_server_url = None
        if self._opencode_client is not None:
            self._opencode_client.close()
            self._opencode_client = None
        self._set_opencode_status("not ready")
        if self._is_shutting_down:
            logger.info("Shutdown in progress after opencode error; quitting app")
            self._app.quit()

    def _on_opencode_finished(
        self,
        _exit_code: int,
        _exit_status: QProcess.ExitStatus,
    ) -> None:
        logger.info("Opencode process finished (exit_code=%s, exit_status=%s)", _exit_code, _exit_status)
        self._opencode_kill_timer.stop()
        self._opencode_server_url = None
        if self._opencode_client is not None:
            self._opencode_client.close()
            self._opencode_client = None
        self._set_opencode_status("not ready")
        if self._is_shutting_down:
            logger.info("Shutdown in progress and opencode finished; quitting app")
            self._app.quit()

    @Slot(str)
    def _on_check_status_changed(self, status: str) -> None:
        logger.info("Check worker status: %s", status)
        self._set_request_status(status)

    @Slot(str, str, str)
    def _on_check_success(self, corrected_phrase: str, summary_ru: str, corrections_text: str) -> None:
        logger.info("Check worker returned structured result")
        self.setCorrectedText(corrected_phrase)
        self.setSummaryRu(summary_ru)
        self.setCorrectionsText(corrections_text)

        explanation_parts: list[str] = []
        if summary_ru:
            explanation_parts.append(f"<b>Summary</b><br>{html.escape(summary_ru)}")
        if corrections_text:
            explanation_parts.append(corrections_text)

        self.setExplanationText("<br><br>".join(explanation_parts))
        self._set_request_status("")

    @Slot(str)
    def _on_check_failed(self, error_message: str) -> None:
        logger.error("Check worker failed: %s", error_message)
        self._set_request_status("request failed")

    @Slot()
    def _on_check_worker_finished(self) -> None:
        logger.info("Check worker finished")
        self._set_request_in_flight(False)
        self._check_worker = None
        if self._pending_check:
            logger.info("Running queued check after worker completion")
            QTimer.singleShot(0, self.requestCheckForCurrentInput)

    def _on_opencode_stdout(self) -> None:
        payload = bytes(self._opencode_process.readAllStandardOutput()).decode("utf-8", errors="replace")
        self._opencode_stdout_buffer += payload
        while "\n" in self._opencode_stdout_buffer:
            line, self._opencode_stdout_buffer = self._opencode_stdout_buffer.split("\n", 1)
            line = line.strip()
            if not line:
                continue

            logger.info("[opencode stdout] %s", line)
            self._maybe_set_opencode_endpoint(line)

    def _on_opencode_stderr(self) -> None:
        payload = bytes(self._opencode_process.readAllStandardError()).decode("utf-8", errors="replace")
        for line in payload.splitlines():
            logger.warning("[opencode stderr] %s", line)
            self._maybe_set_opencode_endpoint(line)

    def _on_ping_timer_tick(self) -> None:
        if self._is_shutting_down:
            return

        if self._request_in_flight or self._pending_check:
            logger.debug("Skipping opencode ping: request is active or queued")
            return

        if self._check_worker is not None and self._check_worker.isRunning():
            logger.debug("Skipping opencode ping: check worker is running")
            return

        if self._opencode_status != "ready" or self._opencode_client is None:
            logger.debug("Skipping opencode ping: server is not ready")
            return

        logger.debug("Pinging opencode server")
        if self._opencode_client.ping():
            logger.debug("Opencode ping succeeded")
            return

        logger.warning("Opencode ping failed; marking server as not ready")
        self._opencode_server_url = None
        self._opencode_client.close()
        self._opencode_client = None
        self._set_opencode_status("not ready")
