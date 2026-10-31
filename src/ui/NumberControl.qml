import QtQuick 2.6
Rectangle {
    id: control
    property string label: ""
    property real value: 0
    property real step: 1
    property real minimum: 0
    property real maximum: 100
    property int decimals: 0
    signal edited(real newValue)
    width: 368; height: 92; color: "#261e22"; border.color: "#514033"
    Text { x: 16; y: 9; text: control.label; font.pixelSize: 16; color: "#c3b09a" }
    Text { x: 16; y: 36; text: Number(control.value).toFixed(control.decimals); font.pixelSize: 26; color: "#f4e2c9" }
    ActionButton { x: 228; y: 31; width: 58; height: 48; label: "−"; onClicked: control.edited(Math.max(control.minimum, control.value-control.step)) }
    ActionButton { x: 296; y: 31; width: 58; height: 48; label: "+"; onClicked: control.edited(Math.min(control.maximum, control.value+control.step)) }
}
