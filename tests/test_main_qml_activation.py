from pathlib import Path

from PySide6.QtCore import QObject, QUrl
from PySide6.QtQml import QQmlApplicationEngine


def _drain_events(qapp, cycles: int = 20) -> None:
    for _ in range(cycles):
        qapp.processEvents()


def test_input_text_area_selected_and_focused_when_window_is_activated(qapp) -> None:
    engine = QQmlApplicationEngine()
    qml_path = Path(__file__).resolve().parents[1] / "qml" / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(qml_path)))

    roots = engine.rootObjects()
    assert roots, "Main window should be created from qml/Main.qml"
    root_window = roots[0]

    input_text_area = root_window.findChild(QObject, "inputTextArea")
    assert input_text_area is not None

    sample_text = "Spell me please"
    input_text_area.setProperty("text", sample_text)
    _drain_events(qapp)

    input_text_area.select(0, 0)
    input_text_area.setProperty("cursorPosition", 0)
    _drain_events(qapp)

    assert input_text_area.property("selectionStart") == 0
    assert input_text_area.property("selectionEnd") == 0
    assert input_text_area.property("cursorPosition") == 0

    root_window.hide()
    _drain_events(qapp)
    root_window.show()
    _drain_events(qapp)

    assert input_text_area.property("activeFocus") is True
    assert input_text_area.property("selectionStart") == 0
    assert input_text_area.property("selectionEnd") == len(sample_text)
    assert input_text_area.property("cursorPosition") == len(sample_text)
