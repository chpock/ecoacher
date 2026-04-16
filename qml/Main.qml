import QtQuick
import QtQuick.Controls

import "components"

ApplicationWindow {
    id: rootWindow

    width: Math.max(900, Math.round(Screen.width * 0.55))
    height: Math.max(680, Math.round(Screen.height * 0.7))
    minimumWidth: 760
    minimumHeight: 560
    visible: true
    title: appProfile === "dev" ? "English Coacher [DEV]" : "English Coacher"
    flags: Qt.Window | Qt.WindowStaysOnTopHint
    property var appController
    property string appProfile: "normal"

    onClosing: function (close) {
        close.accepted = rootWindow.appController.handleCloseRequest()
    }

    onVisibleChanged: {
        if (visible) {
            inputSection.activateTextArea()
        }
    }

    onActiveChanged: {
        if (active) {
            inputSection.activateTextArea()
        }
    }

    Component.onCompleted: {
        inputSection.activateTextArea()
    }

    Shortcut {
        sequences: [StandardKey.Cancel]
        onActivated: {
            if (rootWindow.appController) {
                rootWindow.appController.hideWindow()
            }
        }
    }

    Shortcut {
        sequences: ["Ctrl+Q"]
        onActivated: exitConfirmDialog.open()
    }

    Shortcut {
        sequences: ["Ctrl+Down"]
        context: Qt.WindowShortcut
        onActivated: rootWindow.focusNextTextArea()
    }

    Shortcut {
        sequences: ["Ctrl+Up"]
        context: Qt.WindowShortcut
        onActivated: rootWindow.focusPreviousTextArea()
    }

    function focusNextTextArea() {
        if (inputSection.textAreaActiveFocus) {
            correctedSection.focusTextArea()
            return
        }

        if (correctedSection.textAreaActiveFocus) {
            explanationsSection.focusTextArea()
            return
        }

        inputSection.focusTextArea()
    }

    function focusPreviousTextArea() {
        if (inputSection.textAreaActiveFocus) {
            explanationsSection.focusTextArea()
            return
        }

        if (correctedSection.textAreaActiveFocus) {
            inputSection.focusTextArea()
            return
        }

        if (explanationsSection.textAreaActiveFocus) {
            correctedSection.focusTextArea()
            return
        }

        explanationsSection.focusTextArea()
    }

    ExitConfirmDialog {
        id: exitConfirmDialog
        appController: rootWindow.appController
    }

    footer: StatusFooter {
        appController: rootWindow.appController
        onExitRequested: {
            if (rootWindow.appController) {
                rootWindow.appController.quitApplication()
            }
        }
    }

    Column {
        anchors.fill: parent
        spacing: 0

        InputSection {
            id: inputSection
            width: parent.width
            height: parent.height * 0.25
            appController: rootWindow.appController
            onCheckRequested: {
                if (rootWindow.appController) {
                    rootWindow.appController.runCheck()
                }
            }
        }

        CorrectedSection {
            id: correctedSection
            width: parent.width
            height: parent.height * 0.25
            appController: rootWindow.appController
        }

        ExplanationsSection {
            id: explanationsSection
            width: parent.width
            height: parent.height * 0.5
            appController: rootWindow.appController
        }
    }
}
