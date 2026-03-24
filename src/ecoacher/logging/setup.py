import logging
import os
import sys
from typing import Any

import colorlog
from PySide6.QtCore import QtMsgType, qInstallMessageHandler

from ..config.constants import DEFAULT_LOG_LEVEL


qt_logger = logging.getLogger("qt")


def _should_use_color() -> bool:
    if os.environ.get("NO_COLOR") is not None:
        return False

    if os.environ.get("CLICOLOR_FORCE", "0") not in ("0", ""):
        return True

    if os.environ.get("TERM", "").lower() == "dumb":
        return False

    return sys.stdout.isatty()


def _qt_message_handler(msg_type: QtMsgType, context: Any, message: str) -> None:
    location = ""
    file_name = getattr(context, "file", "")
    line = getattr(context, "line", 0)
    if file_name:
        location = f" ({file_name}:{line})"

    if msg_type == QtMsgType.QtDebugMsg:
        qt_logger.debug("%s%s", message, location)
    elif msg_type == QtMsgType.QtInfoMsg:
        qt_logger.info("%s%s", message, location)
    elif msg_type == QtMsgType.QtWarningMsg:
        qt_logger.warning("%s%s", message, location)
    elif msg_type == QtMsgType.QtCriticalMsg:
        qt_logger.error("%s%s", message, location)
    else:
        qt_logger.critical("%s%s", message, location)


def _install_qt_logging_bridge() -> None:
    qInstallMessageHandler(_qt_message_handler)


def configure_logging() -> None:
    log_level_name = os.environ.get("ECOACHER_LOG_LEVEL", DEFAULT_LOG_LEVEL).upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    if _should_use_color():
        formatter: logging.Formatter = colorlog.ColoredFormatter(
            fmt="%(asctime)s %(log_color)s%(levelname)-8s%(reset)s [%(name)s] %(message)s",
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "bold_red",
            },
        )
    else:
        formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(log_level)
    root_logger.addHandler(handler)

    _install_qt_logging_bridge()
