import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Frame {
    id: footerRoot

    property var appController
    signal exitRequested()

    width: parent.width

    RowLayout {
        anchors.fill: parent
        spacing: 8

        Item {
            id: statusContainer
            Layout.fillWidth: true
            Layout.fillHeight: true

            Row {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                spacing: 8

                Label {
                    text: "Opencode: "
                        + (footerRoot.appController ? footerRoot.appController.opencodeStatus : "not ready")
                        + (footerRoot.appController && footerRoot.appController.requestStatus
                            ? " | " + footerRoot.appController.requestStatus
                            : "")
                }

                BusyIndicator {
                    width: Math.max(18, statusContainer.height - 4)
                    height: width
                    property bool inProgress: footerRoot.appController
                        ? footerRoot.appController.requestInFlight
                        : false
                    running: inProgress
                    visible: true
                    opacity: inProgress ? 1.0 : 0.0
                }
            }
        }

        Button {
            text: "Exit"
            onClicked: footerRoot.exitRequested()
        }
    }
}
