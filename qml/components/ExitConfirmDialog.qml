import QtQuick
import QtQuick.Controls

Dialog {
    id: exitConfirmDialog

    property var appController
    property var confirmButton: null
    property var cancelButton: null

    title: "Confirm Exit"
    width: 340
    modal: true
    focus: true
    parent: Overlay.overlay
    x: Math.round((parent.width - width) / 2)
    y: Math.round((parent.height - height) / 2)

    contentItem: Label {
        text: "Exit application?"
        wrapMode: Text.WordWrap
        padding: 12
    }

    footer: DialogButtonBox {
        id: exitConfirmButtons
        standardButtons: Dialog.Ok | Dialog.Cancel
        onAccepted: {
            if (exitConfirmDialog.appController) {
                exitConfirmDialog.appController.quitApplication()
            }
            exitConfirmDialog.close()
        }
        onRejected: {
            exitConfirmDialog.close()
        }

        Component.onCompleted: {
            exitConfirmDialog.confirmButton = standardButton(Dialog.Ok)
            exitConfirmDialog.cancelButton = standardButton(Dialog.Cancel)
            if (exitConfirmDialog.confirmButton) {
                exitConfirmDialog.confirmButton.focusPolicy = Qt.StrongFocus
                exitConfirmDialog.confirmButton.activeFocusOnTab = true
                exitConfirmDialog.confirmButton.highlighted = Qt.binding(function () {
                    return exitConfirmDialog.confirmButton.activeFocus
                })
            }
            if (exitConfirmDialog.cancelButton) {
                exitConfirmDialog.cancelButton.focusPolicy = Qt.StrongFocus
                exitConfirmDialog.cancelButton.activeFocusOnTab = true
                exitConfirmDialog.cancelButton.highlighted = Qt.binding(function () {
                    return exitConfirmDialog.cancelButton.activeFocus
                })
            }
        }
    }

    function focusConfirmButton() {
        if (confirmButton) {
            confirmButton.forceActiveFocus()
        }
    }

    function focusCancelButton() {
        if (cancelButton) {
            cancelButton.forceActiveFocus()
        }
    }

    function toggleDialogButtonFocus() {
        if (confirmButton && confirmButton.activeFocus) {
            focusCancelButton()
            return
        }

        focusConfirmButton()
    }

    Shortcut {
        sequences: ["Left"]
        context: Qt.WindowShortcut
        enabled: exitConfirmDialog.visible
        onActivated: exitConfirmDialog.focusCancelButton()
    }

    Shortcut {
        sequences: ["Right"]
        context: Qt.WindowShortcut
        enabled: exitConfirmDialog.visible
        onActivated: exitConfirmDialog.focusConfirmButton()
    }

    Shortcut {
        sequences: ["Tab", "Shift+Tab"]
        context: Qt.WindowShortcut
        enabled: exitConfirmDialog.visible
        onActivated: exitConfirmDialog.toggleDialogButtonFocus()
    }

    onOpened: {
        focusConfirmButton()
    }
}
