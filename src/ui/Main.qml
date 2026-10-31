import QtQuick 2.12
import QtQuick.Window 2.12
import "NavApi.js" as Api

Rectangle{
    id: frame
    width:1024;height:600;color:"#171216"
    property bool commandPolling:false
    property bool backgrounded:false
    function leave(){
        Qt.inputMethod.hide();frame.backgrounded=true;
        if(frame.Window.window)frame.Window.window.hide();
        Api.request("/background",{program:"device_guard"},function(data,ok){
            if(!ok){frame.backgrounded=false;if(frame.Window.window)frame.Window.window.show();}
        });
    }
    function closeGuard(){
        if(frame.Window.window)frame.Window.window.hide();
        Api.request("/background",{program:"device_guard"},function(){
            guard.call("/api/shutdown",{},function(){Qt.quit();});
        });
    }
    function pollCommand(){
        if(commandPolling)return;commandPolling=true;
        Api.request("/appcommand?program=device_guard",null,function(data,ok){
            frame.commandPolling=false;
            if(data.command==="close"){guard.shutdown();return;}
            if(data.command==="show")resumeTimer.restart();
            reconnect.interval=ok?20:1000;reconnect.restart();
        });
    }
    Timer{id:reconnect;interval:20;onTriggered:frame.pollCommand()}
    Timer{id:resumeTimer;interval:120;onTriggered:{
        frame.backgrounded=false;
        if(frame.Window.window){frame.Window.window.x=0;frame.Window.window.y=0;frame.Window.window.show();}
        guard.poll();
    }}
    Component.onCompleted:frame.pollCommand()
    GuardContent{
        id:guard
        foreground:!frame.backgrounded
        onCloseRequested:frame.closeGuard()
        width:1024;height:600
        scale:952/1024
        transformOrigin:Item.TopLeft
        y:(600-600*scale)/2
    }
    SystemNav{
        app:"device_guard"
        assetRoot:"../assets/hud"
        onHomeRequested:frame.leave()
        onBackRequested:{if(guard.page!==0)guard.navigate(0);else frame.leave();}
    }
}
