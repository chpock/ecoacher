pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: inputSection

    property var appController
    property bool textAreaActiveFocus: inputTextArea.activeFocus
    property var spellingSuggestions: []
    property int spellingCursorPosition: -1
    signal checkRequested()

    color: "#f4f6f8"

    function focusTextArea() {
        inputTextArea.forceActiveFocus()
    }

    GroupBox {
        anchors.fill: parent
        anchors.margins: 6
        title: "Input"

        ColumnLayout {
            anchors.fill: parent
            spacing: 8

            ScrollView {
                id: inputScrollView
                Layout.fillWidth: true
                Layout.fillHeight: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                ScrollBar.vertical: ScrollBar {
                    parent: inputScrollView
                    interactive: true

                    policy: (
                        inputTextArea.contentHeight
                        + inputTextArea.topPadding
                        + inputTextArea.bottomPadding
                    ) > inputScrollView.availableHeight
                        ? ScrollBar.AlwaysOn
                        : ScrollBar.AlwaysOff

                    readonly property int inset: 4

                    x: inputScrollView.width - width - inset
                    y: inputScrollView.topPadding + inset
                    height: inputScrollView.availableHeight - inset * 2

                    background: Rectangle {
                        implicitWidth: 8
                        radius: width / 2
                        color: "#00000000"
                    }

                    contentItem: Rectangle {
                        implicitWidth: 8
                        radius: width / 2
                        color: "#8c8c8c"
                        opacity: 0.95
                    }
                }

                TextArea {
                    id: inputTextArea
                    objectName: "inputTextArea"
                    wrapMode: TextArea.Wrap
                    selectByMouse: true
                    text: inputSection.appController ? inputSection.appController.spellText : ""

                    leftPadding: 8
                    topPadding: 8
                    bottomPadding: 8
                    rightPadding: 22

                    Keys.onPressed: function (event) {
                        if (event.key !== Qt.Key_Return && event.key !== Qt.Key_Enter) {
                            return
                        }

                        if ((event.modifiers & Qt.ShiftModifier) || (event.modifiers & Qt.ControlModifier)) {
                            inputTextArea.insert(inputTextArea.cursorPosition, "\n")
                        } else {
                            inputSection.checkRequested()
                        }

                        event.accepted = true
                    }

                    onTextChanged: {
                        if (inputSection.appController && inputSection.appController.spellText !== text) {
                            inputSection.appController.setSpellText(text)
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        acceptedButtons: Qt.RightButton
                        hoverEnabled: true
                        preventStealing: true
                        propagateComposedEvents: true
                        property bool hoverOnSpellingError: false
                        cursorShape: hoverOnSpellingError ? Qt.ArrowCursor : Qt.IBeamCursor

                        onPositionChanged: function(mouse) {
                            if (!inputSection.appController) {
                                hoverOnSpellingError = false
                                return
                            }

                            var cursorPos = inputTextArea.positionAt(mouse.x, mouse.y)
                            hoverOnSpellingError = inputSection.appController.hasSpellingSuggestionsAtPosition(cursorPos)
                        }

                        onExited: {
                            hoverOnSpellingError = false
                        }

                        onPressed: function(mouse) {
                            if (mouse.button !== Qt.RightButton || !inputSection.appController) {
                                mouse.accepted = false
                                return
                            }

                            inputSection.spellingCursorPosition = inputTextArea.positionAt(mouse.x, mouse.y)
                            inputSection.spellingSuggestions = inputSection.appController.spellingSuggestionsAtPosition(
                                inputSection.spellingCursorPosition
                            )

                            if (!inputSection.spellingSuggestions || inputSection.spellingSuggestions.length === 0) {
                                mouse.accepted = false
                                return
                            }

                            var popupParent = spellingMenu.parent
                            var popupPos = inputTextArea.mapToItem(popupParent, mouse.x, mouse.y)

                            var lineHeight = 0
                            if (inputTextArea.cursorRectangle) {
                                lineHeight = inputTextArea.cursorRectangle.height
                            }
                            if (!lineHeight || lineHeight <= 0) {
                                lineHeight = inputTextArea.font.pixelSize > 0
                                    ? Math.round(inputTextArea.font.pixelSize * 1.35)
                                    : 18
                            }

                            spellingMenu.popup(popupPos.x, popupPos.y + lineHeight)
                            mouse.accepted = true
                        }
                    }
                }

                Menu {
                    id: spellingMenu
                    parent: Overlay.overlay

                    Repeater {
                        model: inputSection.spellingSuggestions

                        delegate: MenuItem {
                            required property var modelData
                            text: modelData
                            onTriggered: {
                                if (inputSection.appController && inputSection.spellingCursorPosition >= 0) {
                                    inputSection.appController.replaceSpellingAtPosition(
                                        inputSection.spellingCursorPosition,
                                        modelData
                                    )
                                }
                            }
                        }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true

                RowLayout {
                    spacing: 8

                    Button {
                        text: "Clear"
                        onClicked: {
                            inputSection.appController.clearSpellText()
                            inputTextArea.forceActiveFocus()
                        }
                    }

                    Button {
                        text: "Paste from clipboard"
                        onClicked: {
                            inputSection.appController.pasteFromClipboard()
                            inputTextArea.forceActiveFocus()
                        }
                    }
                }

                Item {
                    Layout.fillWidth: true
                }

                Button {
                    text: "Check"
                    onClicked: inputSection.checkRequested()
                }
            }
        }
    }
}
