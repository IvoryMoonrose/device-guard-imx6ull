.pragma library
function request(path,payload,done) {
    var xhr=new XMLHttpRequest();
    xhr.open(payload===null?"GET":"POST","http://127.0.0.1:18767"+path);
    if(payload!==null)xhr.setRequestHeader("Content-Type","application/json");
    xhr.onreadystatechange=function(){if(xhr.readyState===XMLHttpRequest.DONE){
        var data={};try{data=JSON.parse(xhr.responseText);}catch(error){}
        if(done)done(data,xhr.status===200);
    }};
    xhr.send(payload===null?"":JSON.stringify(payload));
}
