import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    property string sectionTitle: ""
    property string sectionText: ""
    property bool selectAllOnFocus: false
    property bool textAreaActiveFocus: sectionTextArea.activeFocus
    default property alias footerContent: footerRow.data

    function focusTextArea() {
        sectionTextArea.forceActiveFocus()
    }

    GroupBox {
        anchors.fill: parent
        anchors.margins: 6
        title: root.sectionTitle

        ColumnLayout {
            anchors.fill: parent
            spacing: 8

            ScrollView {
                id: sectionScrollView
                Layout.fillWidth: true
                Layout.fillHeight: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                ScrollBar.vertical: ScrollBar {
                    parent: sectionScrollView
                    interactive: true

                    policy: (
                        sectionTextArea.contentHeight
                        + sectionTextArea.topPadding
                        + sectionTextArea.bottomPadding
                    ) > sectionScrollView.availableHeight
                        ? ScrollBar.AlwaysOn
                        : ScrollBar.AlwaysOff

                    readonly property int inset: 4

                    x: sectionScrollView.width - width - inset
                    y: sectionScrollView.topPadding + inset
                    height: sectionScrollView.availableHeight - inset * 2

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
                    id: sectionTextArea
                    wrapMode: TextArea.Wrap
                    selectByMouse: true
                    textFormat: TextEdit.RichText
                    text: root.sectionText
                    readOnly: true

                    onActiveFocusChanged: {
                        if (activeFocus && root.selectAllOnFocus) {
                            sectionTextArea.selectAll()
                        }
                    }

                    leftPadding: 8
                    topPadding: 8
                    bottomPadding: 8
                    rightPadding: 22
                }
            }

            RowLayout {
                id: footerRow
                Layout.fillWidth: true
                visible: footerRow.children.length > 0
            }
        }
    }
}
