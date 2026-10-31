import QtQuick 2.12
import "Api.js" as Api

Item {
    id: nav
    anchors.fill: parent
    z: 1000
    property string app: "desktop"
    property string assetRoot: "../assets"
    property bool tasksOpen: false
    property bool busy: false
    property string message: ""
    property var tasks: []
    property string closingProgram:""
    signal backRequested()
    signal homeRequested()
    function back(){if(tasksOpen)tasksOpen=false;else backRequested();}
    function openTasks(){
        tasksOpen=!tasksOpen;if(!tasksOpen)return;
        refreshTasks();
    }
    function refreshTasks(){
        busy=true;message="";
        Api.request("/tasks?current="+app,null,function(data,ok){
            nav.busy=false;nav.tasks=ok?data.tasks:[];
            if(!ok)nav.message="任务服务正在连接，请稍后重试";
            if(ok&&nav.closingProgram!==""){
                var stillRunning=false;
                for(var i=0;i<nav.tasks.length;i++)if(nav.tasks[i].program===nav.closingProgram&&nav.tasks[i].running)stillRunning=true;
                if(stillRunning)refreshTimer.restart();else nav.closingProgram="";
            }
        });
    }
    function choose(program){
        if(program===app){tasksOpen=false;return;}
        busy=true;
        Api.request("/activate",{program:program},function(data,ok){
            nav.busy=false;
            if(ok){nav.tasksOpen=false;nav.homeRequested();}
            else nav.message=data.error||"暂时无法切换，请重新选择";
        });
    }
    function closeTask(program){
        busy=true;closingProgram=program;
        Api.request("/close",{program:program},function(data,ok){
            nav.busy=false;
            if(ok)refreshTimer.restart();else nav.message=data.error||"暂时无法结束应用";
        });
    }
    Timer{id:refreshTimer;interval:700;onTriggered:nav.refreshTasks()}
    Component.onCompleted: if(app!=="desktop")Api.request("/activity",{program:app},null)

    Rectangle{anchors.right:parent.right;width:72;height:parent.height;color:"#1a1219"}
    Rectangle{x:parent.width-72;width:1;height:parent.height;color:"#72563f";opacity:.65}
    Image{x:parent.width-57;y:32;width:42;height:42;source:nav.assetRoot+"/crest.png"}
    Rectangle{x:parent.width-54;y:99;width:36;height:1;color:"#b18c62";opacity:.45}
    Repeater{model:[{name:"返回",file:"back"},{name:"主页",file:"home"},{name:"任务",file:"tasks"}]
        Item{x:nav.width-72;y:174+index*91;width:72;height:78
            Rectangle{x:8;y:0;width:56;height:73;radius:10;color:area.pressed?"#52322f":"transparent";border.color:area.pressed?"#aa8055":"transparent"}
            Image{x:22;y:10;width:28;height:28;source:nav.assetRoot+"/nav-"+modelData.file+".png"}
            Text{y:45;width:72;horizontalAlignment:Text.AlignHCenter;text:modelData.name;font.pixelSize:12;color:"#dec49f"}
            MouseArea{id:area;anchors.fill:parent;onClicked:{if(index===0)nav.back();else if(index===1){nav.tasksOpen=false;nav.homeRequested();}else nav.openTasks();}}
        }
    }
    Text{x:nav.width-72;y:552;width:72;horizontalAlignment:Text.AlignHCenter;text:"GUARD";font.pixelSize:8;font.letterSpacing:1;color:"#937b62"}

    Loader{anchors.fill:parent;active:nav.tasksOpen;sourceComponent:taskPane}
    Component{id:taskPane
        Item{
            Rectangle{width:nav.width-72;height:nav.height;color:"#171015";opacity:.87}
            MouseArea{width:nav.width-72;height:nav.height;onClicked:nav.tasksOpen=false}
            Rectangle{x:112;y:70;width:728;height:460;color:"#23181f";border.color:"#846346";radius:8
                MouseArea{anchors.fill:parent}
                Text{x:28;y:20;text:"应用任务";font.pixelSize:25;color:"#f4dfbd"}
                Text{x:28;y:61;text:"切换已打开的应用，或重新打开最近使用的应用";font.pixelSize:14;color:"#bca58b"}
                Text{x:660;y:18;width:44;height:44;text:"×";horizontalAlignment:Text.AlignHCenter;font.pixelSize:30;color:"#d5b58f";MouseArea{anchors.fill:parent;onClicked:nav.tasksOpen=false}}
                Rectangle{x:28;y:94;width:672;height:1;color:"#694d3b"}
                ListView{x:25;y:111;width:678;height:322;clip:true;spacing:7;model:nav.tasks
                    delegate:Rectangle{width:678;height:80;radius:5;color:modelData.current?"#49302d":"#2d2026";border.color:modelData.current?"#97704b":"#49342c"
                        Image{x:14;y:10;width:60;height:60;source:modelData.icon;sourceSize.width:84;sourceSize.height:84}
                        Text{x:94;y:13;text:modelData.label;font.pixelSize:21;color:"#f3dec2"}
                        Text{x:94;y:45;text:modelData.current?"当前应用":modelData.running?"后台驻留 · 点击恢复":"最近使用 · 点击打开";font.pixelSize:13;color:modelData.current?"#d8b386":"#ae9982"}
                        Text{x:623;y:20;visible:!closeButton.visible;text:modelData.current?"●":"›";font.pixelSize:26;color:"#c09a6e"}
                        MouseArea{anchors.fill:parent;enabled:!nav.busy;onClicked:nav.choose(modelData.program)}
                        Rectangle{id:closeButton;x:580;y:18;width:80;height:44;radius:5;color:closeArea.pressed?"#604037":"#3b292c";border.color:"#79553e";visible:nav.app==="desktop"&&modelData.running&&!modelData.current
                            Text{anchors.centerIn:parent;text:nav.closingProgram===modelData.program?"结束中":"结束";font.pixelSize:15;color:"#dec49f"}
                            MouseArea{id:closeArea;anchors.fill:parent;enabled:!nav.busy&&nav.closingProgram!==modelData.program;onClicked:nav.closeTask(modelData.program)}
                        }
                    }
                }
                Text{x:28;y:205;width:672;horizontalAlignment:Text.AlignHCenter;visible:nav.busy||nav.message!==""||nav.tasks.length===0;text:nav.busy?"正在读取任务…":nav.message!==""?nav.message:"还没有最近使用的应用";font.pixelSize:18;color:"#d3b995"}
            }
        }
    }
}
