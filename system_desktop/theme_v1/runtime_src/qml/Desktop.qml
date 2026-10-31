import QtQuick 2.12
import QtQuick.Window 2.12
import com.alientek.qmlcomponents 1.0
import "Api.js" as Api

Window{
    id:desktop
    width:Screen.desktopAvailableWidth;height:Screen.desktopAvailableHeight;visible:true;x:0;y:0;color:"#191218"
    property string pendingProgram:""
    property bool commandPolling:false
    property string launchMessage:""
    property string clockText:Qt.formatDateTime(new Date(),"hh:mm")
    property string dateText:Qt.formatDateTime(new Date(),"yyyy.MM.dd")
    function launchActivity(program){
        rootItem.enabled=false;desktop.launchMessage="";
        Api.request("/prepare",{program:program},function(data,ok){
            if(ok&&data.resumed){api.requestVisibilityChange(SystemUICommonApiServer.Hide);Api.request("/show",{program:program},null);}
            else if(ok&&data.allowed)api.launchApp(program);
            else{rootItem.enabled=true;desktop.launchMessage=data.error||"暂时无法打开应用";noticeTimer.restart();}
        });
    }
    function pollCommand(){
        if(commandPolling)return;commandPolling=true;
        Api.request("/command",null,function(data,ok){
            desktop.commandPolling=false;
            if(data.desktop)api.requestVisibilityChange(SystemUICommonApiServer.Show);
            if(ok&&data.program)desktop.pendingProgram=data.program;
            reconnect.interval=ok?20:700;reconnect.restart();
        });
    }
    SystemUICommonApiServer{
        id:api
        onRequestVisibilityChange:function(action){
            if(action===SystemUICommonApiServer.Hide){rootItem.enabled=false;desktop.x=Screen.desktopAvailableWidth;desktop.y=Screen.desktopAvailableHeight;desktop.hide();}
            if(action===SystemUICommonApiServer.Show){rootItem.enabled=true;desktop.x=0;desktop.y=0;desktop.show();api.currtentLauchAppName="";}
        }
        onCurrtentLauchAppNameChanged:if(api.currtentLauchAppName==="null")api.requestVisibilityChange(SystemUICommonApiServer.Show)
    }
    Timer{id:reconnect;interval:20;onTriggered:desktop.pollCommand()}
    Timer{interval:60;repeat:true;running:desktop.pendingProgram!=="";onTriggered:{
        if(desktop.visible&&rootItem.enabled&&api.currtentLauchAppName===""){
            var program=desktop.pendingProgram;desktop.pendingProgram="";desktop.launchActivity(program);
        }
    }}
    Timer{interval:1000;repeat:true;running:desktop.visible;onTriggered:{desktop.clockText=Qt.formatDateTime(new Date(),"hh:mm");desktop.dateText=Qt.formatDateTime(new Date(),"yyyy.MM.dd");}}
    Component.onCompleted:{desktop.pollCommand();console.log("THEME_DESKTOP_READY",Date.now());}
    ApkListModel{id:gridApps;Component.onCompleted:add("/opt/ui/src/"+hostName+"/apk1.cfg")}
    Timer{id:noticeTimer;interval:4500;onTriggered:desktop.launchMessage=""}

    Item{id:rootItem;anchors.fill:parent;anchors.rightMargin:72
        Image{anchors.fill:parent;source:"../assets/wallpaper.jpg";fillMode:Image.PreserveAspectCrop;sourceSize.width:952;sourceSize.height:600}
        Image{x:50;y:26;width:250;height:44;source:"../assets/desktop-title.png"}
        Text{x:56;y:76;text:"GUARD DESKTOP";font.pixelSize:10;font.letterSpacing:3;color:"#bda68a"}
        Rectangle{x:56;y:104;width:558;height:1;color:"#ad8153";opacity:.4}
        Text{x:745;y:24;width:171;horizontalAlignment:Text.AlignRight;text:desktop.clockText;font.pixelSize:30;font.letterSpacing:2;color:"#f1dabb";style:Text.Outline;styleColor:"#382029"}
        Text{x:736;y:69;width:180;horizontalAlignment:Text.AlignRight;text:desktop.dateText;font.pixelSize:12;font.letterSpacing:1;color:"#d1b395";style:Text.Outline;styleColor:"#382029"}
        GridView{x:34;y:119;width:592;height:464;interactive:false;clip:false;cellWidth:148;cellHeight:115;model:gridApps
            delegate:Item{width:148;height:115
                Image{x:32;y:3;width:84;height:84;source:apkIconPath;sourceSize.width:84;sourceSize.height:84;opacity:installed?1:.45}
                Text{x:5;y:91;width:138;horizontalAlignment:Text.AlignHCenter;text:apkName;font.pixelSize:15;font.bold:true;color:"#f2dabc";style:Text.Outline;styleColor:"#492c2b"}
                MouseArea{anchors.fill:parent;enabled:installed;onClicked:desktop.launchActivity(programName)}
            }
        }
        Rectangle{x:120;y:510;width:700;height:58;radius:7;color:"#35232b";border.color:"#b48b5e";visible:desktop.launchMessage!=="";z:100
            Text{anchors.centerIn:parent;text:desktop.launchMessage;font.pixelSize:17;color:"#f1dabb"}
        }
    }
    Nav{id:navigation;app:"desktop";enabled:rootItem.enabled;onBackRequested:{}
        onHomeRequested:api.requestVisibilityChange(SystemUICommonApiServer.Show)}
}
