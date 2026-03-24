import logging
import sys

from PySide6.QtNetwork import QLocalServer, QLocalSocket

logger = logging.getLogger(__name__)
SHOW_WINDOW_COMMAND = "__ecoacher_show_window__"


def read_spell_text(arguments: list[str]) -> str:
    logger.debug("Reading spell text from %s", "arguments" if arguments else "stdin")
    if arguments:
        return " ".join(arguments).strip()

    return sys.stdin.read().strip()


def send_spell_text(text: str, server_name: str) -> bool:
    logger.info("Sending spell text to running instance (%d chars)", len(text))
    socket = QLocalSocket()
    socket.connectToServer(server_name)
    if not socket.waitForConnected(1500):
        logger.info("No running instance available for spell delivery")
        return False

    socket.write(text.encode("utf-8"))
    if not socket.waitForBytesWritten(1500):
        logger.error("Failed to deliver spell text to running instance")
        print("failed to deliver text to ecoacher", file=sys.stderr)
        return False

    logger.info("Spell text delivered to running instance")
    socket.disconnectFromServer()
    return True


def request_show_window(server_name: str) -> bool:
    logger.info("Requesting running instance window focus/show")
    socket = QLocalSocket()
    socket.connectToServer(server_name)
    if not socket.waitForConnected(1000):
        logger.info("No running instance available for show request")
        return False

    socket.write(SHOW_WINDOW_COMMAND.encode("utf-8"))
    if not socket.waitForBytesWritten(1000):
        logger.warning("Failed to deliver show-window request")
        return False

    socket.disconnectFromServer()
    logger.info("Show-window request delivered")
    return True


def setup_spell_server(controller: object, server_name: str) -> QLocalServer:
    logger.info("Starting local spell IPC server (%s)", server_name)
    server = QLocalServer()

    if not server.listen(server_name):
        logger.warning("Spell IPC server name already in use; attempting cleanup")
        QLocalServer.removeServer(server_name)
        if not server.listen(server_name):
            logger.error("Failed to start local spell IPC server")
            raise RuntimeError("failed to start local spell server")

    if not server.isListening():
        logger.error("Spell IPC server is not listening after setup")
        raise RuntimeError("failed to start local spell server")

    def process_pending_connections() -> None:
        logger.debug("Processing incoming spell IPC connection(s)")
        while server.hasPendingConnections():
            connection = server.nextPendingConnection()
            if connection is None:
                logger.warning("Received null pending spell connection")
                continue

            if not connection.waitForReadyRead(1000):
                logger.warning("Spell IPC connection timed out waiting for payload")
                connection.disconnectFromServer()
                continue

            payload = bytes(connection.readAll()).decode("utf-8").strip()
            if not payload:
                logger.warning("Received empty spell payload")
            elif payload == SHOW_WINDOW_COMMAND:
                logger.info("Received show-window command")
                controller.showWindow()
            else:
                logger.info("Received spell payload (%d chars)", len(payload))
                controller.setSpellText(payload)
                controller.showWindow()
                controller.requestCheckForCurrentInput()

            connection.disconnectFromServer()

    server.newConnection.connect(process_pending_connections)
    logger.info("Local spell IPC server is ready")
    return server
