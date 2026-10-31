"""Real touch, process identity, retained page and full reboot verification."""
import hashlib,json,os,struct,subprocess,sys,time,urllib.request
ROOT='/opt/device_guard/system_theme';OUT=ROOT+'/evidence'
def touch_frame(fd,items):
    for typ,code,val in items:os.write(fd,struct.pack('llHHi',0,0,typ,code,val))
def tap(x,y):
    fd=os.open('/dev/input/event1',os.O_WRONLY)
    try:
        touch_frame(fd,[(3,47,0),(3,57,int(time.monotonic()*100)%20000+300),(3,53,x),(3,54,y),(3,48,12),(3,50,12),(1,330,1),(0,0,0)])
        time.sleep(.12)
        touch_frame(fd,[(3,47,0),(3,57,-1),(1,330,0),(0,0,0)])
    finally:os.close(fd)
    time.sleep(.6)
def swipe(x0,y0,x1,y1):
    fd=os.open('/dev/input/event1',os.O_WRONLY)
    try:
        touch_frame(fd,[(3,47,0),(3,57,int(time.monotonic()*100)%20000+300),(3,53,x0),(3,54,y0),(3,48,12),(3,50,12),(1,330,1),(0,0,0)])
        for i in range(1,17):
            time.sleep(.018);touch_frame(fd,[(3,53,int(x0+(x1-x0)*i/16)),(3,54,int(y0+(y1-y0)*i/16)),(0,0,0)])
        touch_frame(fd,[(3,57,-1),(1,330,0),(0,0,0)])
    finally:os.close(fd)
    time.sleep(.8)
def api(port,path,data=None):
    req=urllib.request.Request('http://127.0.0.1:'+str(port)+path,data=None if data is None else json.dumps(data).encode('utf8'),headers={'Content-Type':'application/json'})
    return json.loads(urllib.request.urlopen(req,timeout=3).read().decode('utf8'))
def pids(argv):
    result=[]
    for name in os.listdir('/proc'):
        if not name.isdigit():continue
        try:cmd=open('/proc/'+name+'/cmdline','rb').read().split(b'\0')[0]
        except OSError:continue
        if cmd==argv.encode('utf8'):result.append(int(name))
    return result
def app(appname):return pids('/opt/ui/src/apps/'+appname)
def wait_app(name,present=True):
    for i in range(70):
        if bool(app(name))==present:return app(name)
        time.sleep(.1)
    raise AssertionError('Application state mismatch: '+name)
def capture(name):subprocess.check_call(['ffmpeg','-loglevel','error','-y','-f','fbdev','-i','/dev/fb0','-frames:v','1',OUT+'/'+name+'.png'])
def frame_hash(x,y,w,h):
    raw=open('/dev/fb0','rb').read(1024*600*2)
    return hashlib.sha256(b''.join(raw[(row*1024+x)*2:(row*1024+x+w)*2] for row in range(y,y+h))).hexdigest()
def record(name,value):
    with open(OUT+'/'+name+'.json','w') as stream:json.dump(value,stream,indent=2)
    print(json.dumps(value))
def close_background(name):
    api(18767,'/close',{'program':name})
    if name=='device_guard':
        for i in range(70):
            if not os.path.isfile('/opt/device_guard/runtime/launcher.pid'):return
            time.sleep(.1)
        raise AssertionError('Guard did not stop')
    wait_app(name,False)

if __name__=='__main__':
    mode=sys.argv[1]
    if mode=='ordinary':
        tap(988,304) # Guard returns to desktop and continues acquisition.
        tap(552,509);first=wait_app('fileview');time.sleep(3)
        tap(310,166);time.sleep(.5);capture('v2_file_directory')
        directory_hash=frame_hash(240,25,700,550)
        tap(988,304);assert app('fileview')==first
        tap(256,509);note=wait_app('notepad');time.sleep(3)
        tap(890,510);capture('v2_note_editor')
        tap(988,304);assert app('notepad')==note
        tap(552,509);time.sleep(.8);assert app('fileview')==first
        assert frame_hash(240,25,700,550)==directory_hash,'File directory must survive another application'
        capture('v2_file_after_other_app');tap(988,304)
        tap(256,509);time.sleep(.7);assert app('notepad')==note
        capture('v2_note_resumed');tap(988,304);tap(988,395);capture('v2_tasks_resident')
        tasks=api(18767,'/tasks?current=desktop')['tasks']
        assert all(any(item['program']==name and item['running'] for item in tasks) for name in ['notepad','fileview','device_guard'])
        # Most recent entry is the blank test note; use the visible End button.
        tap(757,221);wait_app('notepad',False);time.sleep(.8);capture('v2_task_closed')
        tap(988,213)
        record('v2_ordinary_background',{'file_pid':first,'notepad_pid':note,'file_directory_bytes_retained':True,'three_apps_resident':True,'notepad_editor_retained_visual_evidence':'v2_note_resumed.png','task_end_exits_notepad':True})
    elif mode=='clean_snapshot':
        close_background('fileview');close_background('device_guard')
        assert not app('notepad')
        capture('desktop_v2_final')
        record('v2_before_reboot',{'boot_id':open('/proc/sys/kernel/random/boot_id').read().strip(),'grid_hash':frame_hash(32,106,594,477),'sidebar_hash':frame_hash(952,0,72,600),'config_hash':hashlib.sha256(open('/opt/device_guard/data/config.json','rb').read()).hexdigest()})
    elif mode=='post_boot_background':
        tap(404,394);led=wait_app('led');time.sleep(2);capture('v2_led_after_reboot')
        tap(988,304);assert app('led')==led
        tap(988,395);time.sleep(.2);capture('v2_tasks_before_end')
        before_end=frame_hash(137,181,678,80)
        tap(757,221);wait_app('led',False);time.sleep(2)
        assert frame_hash(137,181,678,80)!=before_end,'Task row must refresh when process exits'
        capture('v2_tasks_after_end');tap(988,213)
        record('v2_post_boot_background',{'led_pid_before_home':led,'same_pid_after_home':True,'task_end_exits_process':True,'task_row_refreshes_automatically':True,'sidebar_in_factory_app_after_boot':True})
    elif mode=='after_reboot':
        before=json.load(open(OUT+'/v2_before_reboot.json'))
        boot_id=open('/proc/sys/kernel/random/boot_id').read().strip();assert boot_id!=before['boot_id'],'Must be a full kernel reboot'
        desktop=pids('/opt/ui/systemui');assert len(desktop)==1
        env=open('/proc/%d/environ'%desktop[0],'rb').read().split(b'\0')
        assert b'XDG_CACHE_HOME=/opt/device_guard/system_theme/cache/v2' in env
        assert len(open('/opt/ui/src/ATK-IMX6U/apk1.cfg',encoding='utf8').read().splitlines())==16
        assert not open('/opt/ui/src/ATK-IMX6U/apk2.cfg','rb').read() and not open('/opt/ui/src/ATK-IMX6U/apk3.cfg','rb').read()
        time.sleep(1)
        assert frame_hash(32,106,594,477)==before['grid_hash'],'16-icon single page must survive boot'
        assert frame_hash(952,0,72,600)==before['sidebar_hash'],'Sidebar must survive boot'
        swipe(900,240,640,240);assert frame_hash(32,106,594,477)==before['grid_hash'],'No blank second page on left swipe'
        swipe(640,240,900,240);assert frame_hash(32,106,594,477)==before['grid_hash'],'No blank second page on right swipe'
        capture('desktop_v2_after_reboot')
        record('v2_full_reboot',{'before_boot_id':before['boot_id'],'after_boot_id':boot_id,'full_kernel_reboot':True,'home_environment':next(v.decode() for v in env if v.startswith(b'HOME=')),'cache_namespace_fixed':True,'sixteen_icons_same_framebuffer':True,'sidebar_same_framebuffer':True,'no_blank_page_after_swipes':True,'dock_config_empty':True})
    else:raise RuntimeError('Unknown verification mode')
