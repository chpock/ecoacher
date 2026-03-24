import QtQuick

ReadOnlyTextSection {
    id: explanationsSection

    property var appController

    color: "#e8edf2"

    sectionTitle: "Explanations"
    sectionText: explanationsSection.appController ? explanationsSection.appController.explanationText : ""
}
