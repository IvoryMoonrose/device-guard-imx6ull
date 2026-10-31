"""Run labelled replay against the real target Python, HTTP and SQLite stack."""
import json
import os
import subprocess
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = '/opt/device_guard'
URL = 'http://127.0.0.1:18766'
DATA = BASE+'/integration_data'
results=[]
process=None
log=open(BASE+'/runtime/integration.log','w')
def api(path='/api/state', payload=None):
    request=Request(URL+path,data=None if payload is None else json.dumps(payload).encode('utf8'),headers={'Content-Type':'application/json'})
    raw=urlopen(request,timeout=4).read()
    return raw if path.endswith('.csv') else json.loads(raw.decode('utf8'))
def start():
    global process
    process=subprocess.Popen(['python3',BASE+'/run.py','--port','18766','--replay','--no-indicators','--data',DATA],stdout=log,stderr=subprocess.STDOUT)
    for unused in range(40):
        try:return api()
        except Exception:time.sleep(0.1)
    raise RuntimeError('Backend unavailable')
def check(name, condition, detail=None):
    results.append({'name':name,'passed':bool(condition),'detail':detail})
    if not condition:raise AssertionError(name)
def rejected(path,payload):
    try:api(path,payload);return False
    except HTTPError as exc:return exc.code==400
try:
    s=start()
    check('replay source and indicators disabled',s['source']=='replay' and not s['outputs'])
    check('arming before calibration rejected',rejected('/api/action',{'action':'arm'}))
    check('invalid settings rejected',rejected('/api/config',{'tilt_deg':0}))
    api('/api/action',{'action':'calibrate'});time.sleep(2.3)
    check('static calibration accepted',api()['calibrated'])
    api('/api/action',{'action':'arm'});time.sleep(5.3)
    check('arming countdown completes',api()['state']=='ARMED')
    api('/api/replay',{'scenario':'tap'});time.sleep(1.5)
    check('short tap does not alarm',api()['state']=='ARMED')
    api('/api/replay',{'scenario':'tilt'});time.sleep(2.3)
    s=api(); key=s['active_event']
    check('sustained tilt latches alarm',s['state']=='ALARM',s['angle'])
    api('/api/action',{'action':'mute'})
    check('mute retains alarm',api()['state']=='ALARM' and api()['muted'])
    # A record is finalized three seconds after its trigger, not three seconds
    # after the replay starts. Wait for the entire post-trigger window.
    time.sleep(3.3)
    event=api('/api/event?id='+str(key))
    check('event includes pre and post samples',len(event['samples'])>=20,len(event['samples']))
    api('/api/action',{'action':'disarm'})
    check('disarm acknowledges event',bool(api('/api/event?id='+str(key))['acknowledged']))
    api('/api/replay',{'scenario':'static'})
    api('/api/config',{'tilt_deg':22,'sound_enabled':False})
    check('CSV exports labelled source', '回放测试' in api('/api/export.csv').decode('utf8'))
    exported=api('/api/export',{})
    check('CSV file created',os.path.isfile(DATA+'/exports/'+exported['filename']))
    api('/api/replay',{'scenario':'fault'});time.sleep(0.6)
    check('data loss enters fault',api()['state']=='FAULT')
    api('/api/replay',{'scenario':'static'});time.sleep(2.4)
    s=api()
    check('recovery does not rearm',s['state']=='DISARMED' and not s['calibrated'])
    before=api('/api/events')
    api('/api/shutdown',{});process.wait(timeout=6)
    s=start(); after=api('/api/events')
    check('restart retains events and settings',len(before)==len(after) and s['config']['tilt_deg']==22 and not s['config']['sound_enabled'])
    fault=next(e for e in after if e['kind']=='sensor_fault')
    check('historical event can be acknowledged after restart',bool(api('/api/acknowledge',{'id':fault['id']})['acknowledged']))
    check('replay records never become hardware',all(e['source']=='replay' for e in after))
finally:
    if process and process.poll() is None:
        process.terminate();process.wait(timeout=6)
    log.close()
    with open(BASE+'/evidence/integration_check.json','w',encoding='utf8') as stream:json.dump(results,stream,ensure_ascii=False,indent=2)
print(json.dumps(results,ensure_ascii=True))
