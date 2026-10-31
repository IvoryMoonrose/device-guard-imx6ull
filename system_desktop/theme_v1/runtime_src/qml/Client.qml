import QtQuick 2.12
import QtQuick.Window 2.12
import com.alientek.qmlcomponents 1.0
import "qrc:/" as Original
import "Api.js" as Api

Item {
    id: client
    property string programmerName
    anchors.fill: parent
    property real scaleFactor: client.width/1024
    property real contentScale: (client.width-72)/client.width
    property bool commandPolling:false
    function pollCommand(){
        if(commandPolling)return;commandPolling=true;
        Api.request("/appcommand?program="+programmerName,null,function(data,ok){
            client.commandPolling=false;
            if(data.command==="close"){client.beforeHome(appMainBody,0);Qt.quit();return;}
            reconnect.interval=ok?20:1000;reconnect.restart();
        });
    }
    Timer{id:reconnect;interval:20;onTriggered:client.pollCommand()}
    Component.onCompleted:client.pollCommand()
    function beforeHome(object,depth){
        if(!object||depth>18)return;
        if(typeof object.themeBeforeHome==="function"){object.themeBeforeHome();return;}
        var children=object.data||object.children||[];
        for(var i=0;i<children.length;i++)beforeHome(children[i],depth+1);
    }
    function goHome(){
        Qt.inputMethod.hide();
        window.x=Screen.desktopAvailableWidth;window.y=Screen.desktopAvailableHeight;
        appMainBody.visible=false;window.hide();
        systemUICommonApiClient.askSystemUItohideOrShow(SystemUICommonApiClient.Show);
    }
    function backInside(object,depth){
        if(!object||depth>18||object.visible===false)return false;
        if(typeof object.themeBack==="function"&&object.themeBack())return true;
        if(object.opened===true&&typeof object.close==="function"){object.close();return true;}
        var children=object.data||object.children||[];
        for(var i=children.length-1;i>=0;i--)if(backInside(children[i],depth+1))return true;
        return false;
    }
    SystemUICommonApiClient{
        id: systemUICommonApiClient
        appName: programmerName
        onActionCommand:{
            if(cmd===SystemUICommonApiClient.Show){
                systemUICommonApiClient.askSystemUItohideOrShow(SystemUICommonApiClient.Hide);
                window.x=0;window.y=0;appMainBody.visible=true;window.show();
                Api.request("/activity",{program:programmerName},null);
            }
            if(cmd===SystemUICommonApiClient.Quit){client.beforeHome(appMainBody,0);Qt.quit();}
        }
    }
    Rectangle{anchors.fill:parent;color:"#171216"}
    Item{width:client.width;height:client.height;scale:client.contentScale;transformOrigin:Item.TopLeft;y:(client.height-client.height*client.contentScale)/2
        Original.AppMainBody{id:appMainBody;anchors.fill:parent;visible:true}
    }
    Nav{app:client.programmerName;onHomeRequested:client.goHome();onBackRequested:{if(Qt.inputMethod.visible)Qt.inputMethod.hide();else if(!client.backInside(appMainBody,0))client.goHome();}}
}
