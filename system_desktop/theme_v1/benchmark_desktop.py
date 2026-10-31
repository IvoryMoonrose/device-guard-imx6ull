"""Record desktop first framebuffer and settled resident memory, twice."""
import argparse,json,os,signal,subprocess,time

def desktop():
    matches=[]
    for name in os.listdir('/proc'):
        if not name.isdigit():continue
        try:args=open('/proc/'+name+'/cmdline','rb').read().split(b'\0')
        except OSError:continue
        if args[0]==b'/opt/ui/systemui':matches.append(int(name))
    assert len(matches)==1,matches
    return matches[0]
def frame():
    with open('/dev/fb0','rb',buffering=0) as stream:data=stream.read(1024*600*2)
    return [data[(y*1024+x)*2:(y*1024+x)*2+2] for y in range(80,500,32) for x in range(30,950,32)]
parser=argparse.ArgumentParser();parser.add_argument('--label',required=True);args=parser.parse_args()
out='/opt/device_guard/system_theme/evidence';os.makedirs(out,exist_ok=True)
results=[]
for run in range(2):
    pid=desktop();env=os.environ.copy()
    for item in open('/proc/%d/environ'%pid,'rb').read().split(b'\0'):
        if b'=' not in item:continue
        key,value=item.split(b'=',1);key=key.decode('utf8','replace')
        if key.startswith(('QT_','TSLIB_','QML')) or key in ['DISPLAY','LD_LIBRARY_PATH','XDG_RUNTIME_DIR']:env[key]=value.decode('utf8','replace')
    os.kill(pid,signal.SIGTERM)
    for unused in range(60):
        try:
            if '\nState:\tZ' in '\n'+open('/proc/%d/status'%pid).read():break
        except OSError:break
        time.sleep(.05)
    else:raise AssertionError('Desktop did not exit')
    with open('/dev/fb0','r+b',buffering=0) as stream:stream.write(b'\0'*(1024*600*2))
    log=open(out+'/'+args.label+'-start.log','a')
    begin=time.monotonic()
    process=subprocess.Popen(['/opt/ui/systemui'],cwd='/opt/ui',env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    elapsed=None
    for unused in range(400):
        assert process.poll() is None,'Desktop exited'
        pixels=frame()
        if sum(p!=b'\0\0' for p in pixels)>len(pixels)*.75:elapsed=round(time.monotonic()-begin,3);break
        time.sleep(.015)
    assert elapsed is not None
    time.sleep(1)
    status=open('/proc/%d/status'%process.pid).read();rss=int(next(s for s in status.splitlines() if s.startswith('VmRSS:')).split()[1])
    results.append({'run':run+1,'first_frame_s':elapsed,'desktop_rss_kb':rss,'pid':process.pid})
    log.close()
with open(out+'/'+args.label+'.json','w') as stream:json.dump(results,stream,indent=2)
print(json.dumps(results))
