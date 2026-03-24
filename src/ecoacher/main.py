import argparse
import logging
import os
from pathlib import Path
import signal
import sys

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from ecoacher.config.constants import (
    DEFAULT_PROFILE,
    SUPPORTED_PROFILES,
    app_id_for_profile,
    spell_server_name_for_profile,
)
from ecoacher.app.controller import AppController
from ecoacher.ipc.service import (
    read_spell_text,
    request_show_window,
    send_spell_text,
    setup_spell_server,
)
from ecoacher.logging.setup import configure_logging


logger = logging.getLogger("ecoacher.main")


def _parse_cli_args(argv: list[str]) -> argparse.Namespace:
    env_profile = os.environ.get("ECOACHER_PROFILE", DEFAULT_PROFILE)
    if env_profile not in SUPPORTED_PROFILES:
        env_profile = DEFAULT_PROFILE

    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--profile", choices=SUPPORTED_PROFILES, default=env_profile)
    subparsers = parser.add_subparsers(dest="command")

    spell_parser = subparsers.add_parser("spell")
    spell_parser.add_argument("text", nargs="*")

    return parser.parse_args(argv)


def _run_spell_command(arguments: list[str], spell_server_name: str) -> str | None:
    logger.info("Running spell command")
    text = read_spell_text(arguments)
    if not text:
        logger.error("Spell command received empty text")
        print("spell text is empty", file=sys.stderr)
        return None

    if send_spell_text(text, spell_server_name):
        logger.info("Spell command completed by updating running instance")
        return ""

    logger.info("No running instance; spell command will bootstrap app")
    return text


def main() -> int:
    cli = _parse_cli_args(sys.argv[1:])
    profile = cli.profile
    app_id = app_id_for_profile(profile)
    spell_server_name = spell_server_name_for_profile(profile)

    configure_logging()
    logger.info("Starting ecoacher application (profile=%s)", profile)

    initial_spell_text = ""
    if cli.command == "spell":
        spell_result = _run_spell_command(cli.text, spell_server_name)
        if spell_result is None:
            logger.error("Spell command failed")
            return 1

        if spell_result == "":
            logger.info("Spell command completed; exiting CLI helper")
            return 0

        initial_spell_text = spell_result
        logger.info("Spell command bootstrapping GUI with initial text")
    elif request_show_window(spell_server_name):
        logger.info("Another instance is running; focusing existing window and exiting")
        return 0

    QApplication.setApplicationName(app_id)
    QApplication.setDesktopFileName(app_id)
    app = QApplication([sys.argv[0]])

    tray_available = QSystemTrayIcon.isSystemTrayAvailable()
    logger.info("System tray availability: %s", tray_available)
    app.setQuitOnLastWindowClosed(not tray_available)

    sigint_timer = QTimer()
    sigint_timer.timeout.connect(lambda: None)
    sigint_timer.start(200)

    engine = QQmlApplicationEngine()
    controller = AppController(app, tray_available, app_id)
    signal.signal(signal.SIGINT, lambda *_: controller.requestShutdown())

    if initial_spell_text:
        controller.setSpellText(initial_spell_text)
        controller.requestCheckForCurrentInput()

    _spell_server = setup_spell_server(controller, spell_server_name)

    qml_path = Path(__file__).resolve().parents[2] / "qml" / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(qml_path)))
    logger.info("Loaded QML from %s", qml_path)

    if not engine.rootObjects():
        logger.error("No root QML objects loaded; exiting with failure")
        return 1

    root_window = engine.rootObjects()[0]
    root_window.setProperty("appController", controller)
    root_window.setProperty("appProfile", profile)
    controller.set_window(root_window)

    logger.info("Entering Qt event loop")
    exit_code = app.exec()
    logger.info("Qt event loop finished with exit code %s", exit_code)
    controller.ensureOpencodeStopped()
    logger.info("Application shutdown complete")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
