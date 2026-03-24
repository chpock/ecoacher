import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ReadOnlyTextSection {
    id: correctedSection

    property var appController

    color: "#eef1f4"

    sectionTitle: "Corrected"
    sectionText: correctedSection.appController ? correctedSection.appController.correctedDiffHtml : ""
    selectAllOnFocus: true

    Item {
        Layout.fillWidth: true
    }

    Button {
        text: "Copy to clipboard"
        onClicked: {
            if (correctedSection.appController) {
                correctedSection.appController.copyCorrectedTextToClipboard()
            }
        }
    }
}
