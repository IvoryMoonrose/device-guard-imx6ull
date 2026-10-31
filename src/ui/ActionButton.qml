import QtQuick 2.6
Item {
    id: control
    property string label: ""
    property string tone: "normal"
    property string icon: ""
    signal clicked()
    implicitWidth:150;implicitHeight:48
    Image{anchors.fill:parent;source:"../assets/hud/button-"+(!control.enabled?"disabled":control.tone)+".png";opacity:area.pressed?.7:1}
    Image{x:16;anchors.verticalCenter:parent.verticalCenter;width:28;height:28;source:control.icon?"../assets/hud/"+control.icon+".png":"";visible:control.icon!=="";opacity:control.enabled?1:.45}
    Text{x:control.icon?47:8;y:0;width:parent.width-(control.icon?55:16);height:parent.height;horizontalAlignment:Text.AlignHCenter;verticalAlignment:Text.AlignVCenter;text:control.label;elide:Text.ElideRight;font.pixelSize:control.width>200?18:16;font.bold:control.tone==="primary"||control.tone==="danger";color:!control.enabled?"#8f8172":control.tone==="primary"||control.tone==="danger"?"#fff0db":"#e5ccb0"}
    MouseArea{id:area;anchors.fill:parent;enabled:control.enabled;onClicked:control.clicked()}
}
