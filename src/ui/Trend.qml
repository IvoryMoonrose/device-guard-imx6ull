import QtQuick 2.6
Canvas {
    id: chart
    property var points: []
    property string metric: "angle"
    property real threshold: 15
    property color lineColor: "#efd0a3"
    property bool compact: false
    onPointsChanged: requestPaint()
    onThresholdChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onPaint: {
        var ctx = getContext("2d"); ctx.clearRect(0, 0, width, height);
        var left=compact?0:32, top=compact?3:12, right=compact?2:12, bottom=compact?2:24, w=width-left-right, h=height-top-bottom;
        var maximum=Math.max(20, threshold*1.5);
        for(var i=0;i<points.length;i++) maximum=Math.max(maximum, Number(points[i][metric])*1.15);
        ctx.font="12px sans-serif"; ctx.fillStyle="#ac9a84"; ctx.lineWidth=1;
        for(var k=0;k<4;k++) {
            if(compact&&k>0&&k<3)continue;
            var yy=top+h*k/3; ctx.strokeStyle="#554237"; ctx.beginPath();ctx.moveTo(left,yy);ctx.lineTo(left+w,yy);ctx.stroke();
            if(!compact)ctx.fillText((maximum*(1-k/3)).toFixed(0), 2, yy+4);
        }
        var limitY=top+h*(1-threshold/maximum);ctx.strokeStyle=compact?"#8c6c4c":"#d4a164";ctx.beginPath();
        if(compact){for(var dash=0;dash<w;dash+=9){ctx.moveTo(left+dash,limitY);ctx.lineTo(left+Math.min(w,dash+3),limitY);}}
        else{ctx.moveTo(left,limitY);ctx.lineTo(left+w,limitY);}ctx.stroke();
        if(points.length>1) {
            ctx.strokeStyle=lineColor;ctx.lineWidth=2.4;ctx.beginPath();
            for(var n=0;n<points.length;n++) {
                var x=left+w*n/(points.length-1), y=top+h*(1-Number(points[n][metric])/maximum);
                if(n===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);
            }
            ctx.stroke();
        }
        if(!compact){ctx.fillStyle="#ac9a84";ctx.fillText("时间 →",width-70,height-3);}
    }
}
