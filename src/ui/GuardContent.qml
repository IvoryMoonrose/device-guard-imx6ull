import QtQuick 2.6

Rectangle {
    id: root
    width: 1024; height: 600; color: "#151015"
    property int page: 0
    property bool foreground: true
    property var s: ({state:"DISARMED",state_text:"正在连接",message:"正在连接本地监测服务…",sensor_ok:false,calibrated:false,source:"hardware",source_text:"实机采集",angle:0,motion:0,gyro:0,countdown:0,cal_progress:0,muted:false,history:[],config:{tilt_deg:15,motion_g:0.18,gyro_dps:25,tilt_hold_ms:1200,motion_hold_ms:800,arming_seconds:5,sound_enabled:false},time_text:"",event_count:0,sample_count:0,error_count:0})
    property var draft: ({})
    property var events: []
    property var selected: null
    property int selectedId: -1
    property string toast: ""
    property bool connected: false
    property bool polling: false
    property bool announced: false
    property int tick: 0
    property color ink: "#f4e2c9"
    property color mutedInk: "#b6a591"
    property color stateColor: s.state==="ALARM"?"#ff947e":s.state==="FAULT"?"#f3c37d":s.state==="ARMED"?"#b9ceb0":"#dfbf95"
    property string timeText: s.time_text ? s.time_text.substr(11,5) : "--:--"
    property string dateText: s.time_text ? s.time_text.substr(0,10).replace(/-/g," / ") : "连接中"
    function call(path,payload,callback) {
        var xhr=new XMLHttpRequest(); xhr.open(payload===null?"GET":"POST","http://127.0.0.1:18765"+path);
        xhr.setRequestHeader("Content-Type","application/json");
        xhr.onreadystatechange=function(){if(xhr.readyState===XMLHttpRequest.DONE){
            var data={};try{data=JSON.parse(xhr.responseText);}catch(error){}
            if(xhr.status>=200&&xhr.status<300){if(callback)callback(data);}
            else if(payload!==null)root.notify(data.error||"操作未完成，请检查设备状态");
            if(path==="/api/state"){root.polling=false;root.connected=xhr.status===200;}
        }};
        xhr.send(payload===null?"":JSON.stringify(payload));
    }
    function poll(){
        if(!polling){polling=true;call("/api/state",null,function(data){root.s=data;});}
        tick++;
        if(page===1&&tick%8===0){refreshEvents();if(selectedId>0)loadEvent(selectedId);}
    }
    function action(name){call("/api/action",{action:name},function(data){root.s=data;});}
    function notify(message){toast=message;toastTimer.restart();}
    function navigate(index){page=index;if(index===1)refreshEvents();if(index===2)draft=JSON.parse(JSON.stringify(s.config));}
    function refreshEvents(){call("/api/events",null,function(data){root.events=data;});}
    function loadEvent(id){selectedId=id;call("/api/event?id="+id,null,function(data){root.selected=data;});}
    function edit(key,value){var copy=JSON.parse(JSON.stringify(draft));copy[key]=value;draft=copy;}
    signal closeRequested()
    function shutdown(){closeRequested();}
    Component.onCompleted: { console.log("GUARD_QML_CREATED",Date.now()); poll(); }
    Timer{interval:250;repeat:true;running:root.foreground;onTriggered:{root.poll();if(root.connected&&!root.announced){root.announced=true;console.log("GUARD_UI_READY",Date.now());}}}
    Timer{id:toastTimer;interval:3000;onTriggered:root.toast=""}

    Image{id:wallpaper;anchors.fill:parent;source:"../assets/hud/background.jpg";cache:true}
    Rectangle{x:94;y:94;width:790;height:488;color:"#151116";opacity:.94;visible:root.page!==0}
    Rectangle{x:75;y:26;width:1;height:548;color:"#dbc6a6";opacity:.16}
    Image{x:22;y:25;width:32;height:32;source:"../assets/hud/shield.png"}
    Rectangle{x:25;y:73;width:28;height:1;color:"#c99f71";opacity:.45}
    Repeater{model:[{label:"监测",icon:"monitor"},{label:"记录",icon:"record"},{label:"参数",icon:"tune"},{label:"说明",icon:"info"}]
        Item{x:0;y:128+index*87;width:74;height:64
            Rectangle{x:11;width:54;height:62;color:"#efd2a3";opacity:root.page===index?.055:0}
            Rectangle{width:3;height:56;color:"#ecc99b";visible:root.page===index}
            Image{x:23;y:3;width:30;height:30;source:"../assets/hud/"+modelData.icon+".png";opacity:root.page===index?1:.6}
            Text{x:0;y:39;width:74;horizontalAlignment:Text.AlignHCenter;text:modelData.label;font.pixelSize:12;color:root.page===index?"#f1dbb8":"#a69b8b"}
            MouseArea{anchors.fill:parent;onClicked:root.navigate(index)}
        }
    }
    Item{x:8;y:520;width:60;height:65
        Image{x:15;y:15;width:30;height:30;source:"../assets/hud/power.png";opacity:.8}
        MouseArea{anchors.fill:parent;onClicked:root.shutdown()}
    }
    Image{x:100;y:16;width:250;height:40;source:"../assets/hud/title.png"}
    Text{x:106;y:57;text:"DEVICE GUARD";font.pixelSize:9;font.letterSpacing:3.8;color:"#bca88d"}
    Rectangle{x:104;y:86;width:444;height:1;color:"#cfb694";opacity:.23}
    Rectangle{x:104;y:86;width:33;height:1;color:"#ddbc8d"}
    Text{x:360;y:30;width:188;horizontalAlignment:Text.AlignRight;text:["实时监测","异常事件与追溯","监测参数","设备与操作说明"][root.page];font.pixelSize:13;color:"#d7c5ad"}
    Rectangle{x:477;y:60;width:5;height:5;radius:3;color:root.connected?"#a8b39a":"#d3a677"}
    Text{x:485;y:53;width:63;horizontalAlignment:Text.AlignRight;text:root.connected?root.s.source_text:"连接中";font.pixelSize:11;color:"#b4ac9b"}
    Text{x:800;y:10;width:188;horizontalAlignment:Text.AlignRight;text:root.timeText;font.pixelSize:25;font.letterSpacing:2;color:"#f7e6d0"}
    Text{x:790;y:50;width:198;horizontalAlignment:Text.AlignRight;text:root.dateText;font.pixelSize:11;font.letterSpacing:1;color:"#c9b3a0"}

    Item{visible:root.page===0;anchors.fill:parent
        Rectangle{x:112;y:115;width:424;height:1;color:"#c8ab86";opacity:.19}
        Repeater{model:["建立参考","倒计时布防","持续监测"]
            Item{x:108+index*166;y:104;width:150;height:24
                property bool reached: index===0 || (index===1&&root.s.calibrated) || (index===2&&(root.s.state==="ARMED"||root.s.state==="ALARM"))
                Rectangle{x:1;y:8;width:6;height:6;rotation:45;color:parent.reached?"#e3bb8e":"#65534b"}
                Text{x:19;y:0;text:modelData;font.pixelSize:12;color:parent.reached?"#e6c399":"#887e73"}
            }
        }
        Image{x:112;y:128;width:264;height:264;source:"../assets/hud/ring.png"}
        Rectangle{x:125;y:141;width:238;height:238;radius:119;color:"transparent";border.width:root.s.state==="ALARM"?2:1;border.color:root.stateColor;opacity:root.s.state==="ALARM"?.7:.07}
        Text{x:118;y:196;width:252;horizontalAlignment:Text.AlignHCenter;text:root.s.state==="DISARMED"?"STANDBY":root.s.state==="CALIBRATING"?"CALIBRATING":root.s.state==="ARMING"?"ARMING":root.s.state==="ARMED"?"GUARDING":root.s.state==="ALARM"?"ALERT":"SENSOR FAULT";font.pixelSize:10;font.letterSpacing:3;color:root.stateColor}
        Image{x:94;y:215;width:300;height:65;source:"../assets/hud/state-"+root.s.state+".png"}
        Rectangle{x:212;y:282;width:64;height:1;color:root.stateColor;opacity:.45}
        Text{x:128;y:298;width:232;height:40;horizontalAlignment:Text.AlignHCenter;wrapMode:Text.WordWrap;text:!root.connected?"正在连接本地服务…":root.s.state==="CALIBRATING"?"校准进度 "+Math.round(root.s.cal_progress*100)+"%":root.s.state==="ARMING"?root.s.countdown+" 秒后开始监测":root.s.state==="ALARM"?"异常已记录，请确认":root.s.state==="FAULT"?"请检查六轴传感器":root.s.calibrated?"静止参考已建立":"请先建立静止参考";font.pixelSize:13;color:"#c1ad96"}
        Repeater{model:3;Rectangle{x:229+index*13;y:332;width:4;height:4;radius:2;color:index===0||(index===1&&root.s.calibrated)||(index===2&&(root.s.state==="ARMED"||root.s.state==="ALARM"))?"#d8b789":"#706055"}}
        Repeater{model:3
            Item{x:404;y:150+index*90;width:140;height:86
                Text{text:["相对倾斜","动态加速度","旋转强度"][index];font.pixelSize:13;color:"#bcae9d"}
                Text{x:-1;y:16;text:!root.connected?"—":index===0?Number(root.s.angle).toFixed(1):index===1?Number(root.s.motion).toFixed(3):Number(root.s.gyro).toFixed(1);font.pixelSize:32;color:"#f9eddd"}
                Text{x:107;y:35;width:31;horizontalAlignment:Text.AlignRight;text:["°","g","°/s"][index];font.pixelSize:13;color:"#cab596"}
                Text{x:120;y:0;width:18;horizontalAlignment:Text.AlignRight;text:"0"+(index+1);font.pixelSize:10;color:"#8d8074"}
                Rectangle{y:67;width:137;height:1;color:"#e4c9a1";opacity:.25}
                Rectangle{y:66;width:Math.max(4,Math.min(137,137*(index===0?root.s.angle/root.s.config.tilt_deg:index===1?root.s.motion/root.s.config.motion_g:root.s.gyro/root.s.config.gyro_dps)));height:2;color:root.stateColor}
                Text{y:71;text:"触发阈值  "+(index===0?root.s.config.tilt_deg+"°":index===1?root.s.config.motion_g+" g":root.s.config.gyro_dps+" °/s");font.pixelSize:11;color:"#a99a89"}
            }
        }
        ActionButton{x:114;y:423;width:256;height:54;icon:"target";tone:root.s.state==="ALARM"?"danger":"primary";label:root.s.state==="DISARMED"?"静止校准":root.s.state==="CALIBRATING"?"校准 "+Math.round(root.s.cal_progress*100)+"%":"撤防 / 确认";enabled:root.connected&&(root.s.state!=="DISARMED"||root.s.sensor_ok)&&root.s.state!=="CALIBRATING";onClicked:root.action(root.s.state==="DISARMED"?"calibrate":"disarm")}
        ActionButton{x:384;y:423;width:160;height:54;label:root.s.state==="DISARMED"?"开始布防":root.s.state==="CALIBRATING"?"取消校准":(root.s.state==="ALARM"||root.s.state==="FAULT")?(!root.s.config.sound_enabled?"声音已关闭":root.s.muted?"已消音":"消音"):"查看记录";enabled:root.connected&&(root.s.state==="DISARMED"?root.s.calibrated&&root.s.sensor_ok:(root.s.state==="ALARM"||root.s.state==="FAULT")?root.s.config.sound_enabled&&!root.s.muted:true);onClicked:{if(root.s.state==="DISARMED")root.action("arm");else if(root.s.state==="CALIBRATING")root.action("disarm");else if(root.s.state==="ALARM"||root.s.state==="FAULT")root.action("mute");else root.navigate(1);}}
        Text{x:115;y:486;width:429;height:24;elide:Text.ElideRight;text:root.connected?root.s.message:"正在启动监测服务，请稍候…";font.pixelSize:12;color:root.s.state==="ALARM"?root.stateColor:"#b1a18d"}
        Text{x:113;y:515;text:"姿态轨迹";font.pixelSize:13;color:"#cdb99b"}
        Text{x:420;y:517;width:124;horizontalAlignment:Text.AlignRight;text:"最近 30 秒";font.pixelSize:11;color:"#a3927e"}
        Trend{x:114;y:541;width:430;height:33;points:root.s.history;threshold:root.s.config.tilt_deg;lineColor:root.stateColor;compact:true}
        Rectangle{x:696;y:519;width:290;height:1;color:"#edcfac";opacity:.28}
        Rectangle{x:696;y:519;width:34;height:1;color:"#edd0a4"}
        Text{x:696;y:526;width:290;elide:Text.ElideRight;text:!root.connected?"正在连接监测服务":root.s.storage_error?"事件记录保存异常":root.s.state==="ALARM"?"检测到异常，请确认":root.s.state==="ARMED"?"设备守护中":root.s.sensor_ok?"监测终端已就绪":"六轴传感器异常";font.pixelSize:16;color:root.stateColor}
        Rectangle{x:697;y:562;width:6;height:6;radius:3;color:root.s.sensor_ok?"#a9bf9c":"#dd9b77"}
        Text{x:712;y:554;text:root.s.sensor_ok?"六轴在线":"等待六轴";font.pixelSize:12;color:"#d9c4aa"}
        Image{x:797;y:550;width:22;height:22;source:"../assets/hud/bell.png";visible:!root.s.config.sound_enabled||root.s.muted}
        Text{x:822;y:554;text:!root.s.config.sound_enabled?"声音关闭":root.s.muted?"已消音":"声音开启";font.pixelSize:12;color:"#d9c4aa"}
        Text{x:914;y:554;width:72;horizontalAlignment:Text.AlignRight;text:root.s.event_count+" 条事件";font.pixelSize:12;color:"#d9c4aa"}
    }

    Loader{x:104;y:105;width:760;height:470;active:root.page!==0;sourceComponent:root.page===1?eventsPage:root.page===2?settingsPage:guidePage}
    Component{id:eventsPage
        Item{
            Text{y:1;text:"事件档案";font.pixelSize:20;color:root.ink}
            Text{x:205;y:9;text:"实机与回放来源分别标记";font.pixelSize:12;color:root.mutedInk}
            ListView{x:0;y:43;width:351;height:352;clip:true;model:root.events;spacing:5
                delegate:Rectangle{width:351;height:77;color:root.selectedId===modelData.id?"#49352e":"#261e22";border.color:root.selectedId===modelData.id?"#a17d58":"#42332c"
                    Text{x:12;y:8;text:"#"+modelData.id+"  "+modelData.kind_text;font.pixelSize:18;color:root.ink}
                    Text{x:12;y:43;text:modelData.time_text;font.pixelSize:13;color:root.mutedInk}
                    Text{x:264;y:13;text:modelData.source_text;font.pixelSize:12;color:modelData.source==="hardware"?"#b9ceb0":"#cab4dc"}
                    Text{x:278;y:44;text:modelData.acknowledged?"已确认":"待确认";font.pixelSize:12;color:modelData.acknowledged?"#a39482":"#e9b18a"}
                    MouseArea{anchors.fill:parent;onClicked:root.loadEvent(modelData.id)}
                }
            }
            Text{x:45;y:190;visible:root.events.length===0;text:"暂无异常事件";font.pixelSize:19;color:root.mutedInk}
            ActionButton{x:0;y:414;width:351;height:48;label:"导出全部记录为 CSV";onClicked:root.call("/api/export",{},function(data){root.notify("已保存："+data.filename);})}
            Rectangle{x:375;y:0;width:1;height:462;color:"#816950";opacity:.4}
            Text{x:398;y:1;width:215;text:root.selected?"事件 #"+root.selected.id:"触发详情";font.pixelSize:20;color:root.ink}
            ActionButton{x:628;y:0;width:132;height:41;label:root.selected&&root.selected.acknowledged?"已确认":"确认记录";enabled:root.selected!==null&&!root.selected.acknowledged;onClicked:root.call("/api/acknowledge",{id:root.selectedId},function(data){root.selected=data;root.refreshEvents();})}
            Text{x:398;y:58;width:352;height:67;wrapMode:Text.WordWrap;text:root.selected?root.selected.reason:"点击左侧记录，查看触发原因和前后数据。";font.pixelSize:17;color:root.ink}
            Text{x:398;y:135;width:352;text:root.selected?"来源："+root.selected.source_text+"\n倾斜："+Number(root.selected.angle).toFixed(1)+"°\n动态加速度："+Number(root.selected.motion).toFixed(3)+" g\n旋转强度："+Number(root.selected.gyro).toFixed(1)+" °/s":"";font.pixelSize:16;lineHeight:1.5;color:root.mutedInk}
            Text{x:398;y:286;text:"触发前后 · 倾斜曲线";font.pixelSize:14;color:root.mutedInk;visible:root.selected!==null}
            Trend{x:395;y:318;width:365;height:138;points:root.selected?root.selected.samples:[];threshold:root.s.config.tilt_deg;visible:root.selected!==null}
        }
    }
    Component{id:settingsPage
        Item{
            Grid{columns:2;columnSpacing:24;rowSpacing:12
                NumberControl{label:"倾斜阈值（°）";value:root.draft.tilt_deg||15;minimum:5;maximum:60;onEdited:root.edit("tilt_deg",newValue)}
                NumberControl{label:"倾斜持续时间（毫秒）";value:root.draft.tilt_hold_ms||1200;step:100;minimum:300;maximum:5000;onEdited:root.edit("tilt_hold_ms",newValue)}
                NumberControl{label:"动态加速度阈值（g）";value:root.draft.motion_g||.18;step:.02;minimum:.08;maximum:1.5;decimals:2;onEdited:root.edit("motion_g",newValue)}
                NumberControl{label:"旋转强度阈值（°/s）";value:root.draft.gyro_dps||25;step:5;minimum:10;maximum:180;onEdited:root.edit("gyro_dps",newValue)}
                NumberControl{label:"搬动持续时间（毫秒）";value:root.draft.motion_hold_ms||800;step:100;minimum:300;maximum:5000;onEdited:root.edit("motion_hold_ms",newValue)}
                NumberControl{label:"布防倒计时（秒）";value:root.draft.arming_seconds||5;minimum:3;maximum:30;onEdited:root.edit("arming_seconds",newValue)}
            }
            ActionButton{x:0;y:326;width:240;label:root.draft.sound_enabled?"报警声音：开启":"报警声音：关闭";onClicked:root.edit("sound_enabled",!root.draft.sound_enabled)}
            Text{x:264;y:342;text:"修改前请先撤防";font.pixelSize:16;color:root.mutedInk}
            ActionButton{x:0;y:410;width:240;height:54;label:"保存监测参数";tone:"primary";enabled:root.connected&&root.s.state==="DISARMED";onClicked:root.call("/api/config",root.draft,function(data){root.s=data;root.notify("参数已保存，重启后保留");})}
            Text{x:264;y:424;width:490;text:"连续超阈值才报警，短暂碰动不累计。";font.pixelSize:15;color:root.mutedInk}
        }
    }
    Component{id:guidePage
        Item{
            Text{y:0;text:"设备防搬动与异常事件记录终端";font.pixelSize:23;color:root.ink}
            Text{y:57;width:755;text:"01   放稳设备，点击静止校准，等待参考建立。\n02   开始布防，倒计时结束后持续监测。\n03   持续倾斜或搬动触发报警，并保存前后数据。\n04   消音保留报警；撤防用于结束监测、确认事件。\n05   事件页可查看原因与曲线，并导出 CSV。";font.pixelSize:19;lineHeight:1.9;color:"#d2bea4"}
            Rectangle{y:289;width:755;height:1;color:"#816950";opacity:.45}
            Text{y:308;text:"i.MX6ULL  /  ICM20608 六轴  /  SQLite 本地记录";font.pixelSize:17;color:"#c5b38f"}
            Text{y:343;text:"当前来源："+root.s.source_text+"   ·   有效采样 "+root.s.sample_count+" 次   ·   HUD 2.0";font.pixelSize:14;color:root.mutedInk}
            Row{x:0;y:380;spacing:8;visible:root.s.source==="replay"
                Repeater{model:[{text:"静止",name:"static"},{text:"短碰",name:"tap"},{text:"倾斜",name:"tilt"},{text:"搬动",name:"motion"},{text:"断流",name:"fault"}]
                    ActionButton{width:112;height:44;label:modelData.text;onClicked:root.call("/api/replay",{scenario:modelData.name},function(data){root.s=data;})}
                }
            }
            ActionButton{x:528;y:416;width:232;height:48;label:"退出到原桌面";onClicked:root.shutdown()}
        }
    }
    Rectangle{x:310;y:4;width:450;height:28;color:"#33252b";border.color:"#947453";visible:root.toast!=="";z:100
        Text{anchors.centerIn:parent;width:430;text:root.toast;horizontalAlignment:Text.AlignHCenter;elide:Text.ElideMiddle;font.pixelSize:14;color:"#f5dfbc"}
    }
}
