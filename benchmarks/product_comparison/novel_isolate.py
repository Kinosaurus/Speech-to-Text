"""Quiet, causal prefix controls for Novel Effect, using the authorized A54.

All PCM comes from the saved local synthetic master. The virtual input is armed
before app navigation; replay starts only after native route verification and
with phone networking off. No app-private files or physical mic data are read.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
import wave
import xml.etree.ElementTree as ET

import numpy as np
from scipy.signal import resample_poly

from benchmarks.product_comparison.score import timed_words, anchor_interval

REPO = Path(__file__).resolve().parents[2]
ADB = Path(r'C:\Users\heart\AppData\Local\Android\Sdk\platform-tools\adb.exe')
SERIAL = 'R5CW60FRZVW'
PACKAGE = 'com.noveleffect.book'
DEX = '/data/local/tmp/reading-pod-novel-isolation.dex'


class Phone:
    def __init__(self, root):
        self.root = root
        self.owned = {DEX}
    def run(self, *args, check=True, timeout=25):
        command=[str(ADB), '-s', SERIAL, *map(str,args)]
        for attempt in range(8):
            result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',
                                  errors='replace',timeout=timeout)
            transient=any(s in result.stderr.lower() for s in ['device offline','device not found','no devices','closed','device \''])
            # Never repeat a potentially completed tap/text/key action.
            if result.returncode and transient and 'input' not in args and attempt<7:
                time.sleep(.5);continue
            if check:result.check_returncode()
            return result.stdout.strip()
    def dump(self, case, stage):
        name = f'reading-pod-isolate-{case}-{stage}.xml'
        remote = '/data/local/tmp/'+name
        self.owned.add(remote)
        local = self.root/case/name
        for attempt in range(3):
            self.run('shell','rm','-f',remote)
            self.run('shell','uiautomator','dump',remote,check=False)
            result=subprocess.run([str(ADB),'-s',SERIAL,'pull',remote,str(local)],
                                  capture_output=True,text=True,timeout=20)
            if result.returncode==0:
                return list(ET.parse(local).iter('node'))
            time.sleep(.5)
        raise RuntimeError('UI did not settle for a fresh, readable snapshot')
    def wait(self, case, stage, *, ident=None, text=None):
        # Network restoration after an offline replay can leave the splash
        # screen visible longer than ordinary in-app navigation.
        for attempt in range(20 if stage=='home' else 6):
            nodes = self.dump(case,stage)
            candidates = ([n for n in nodes if n.get('resource-id','').endswith('/'+ident)]
                          if ident else [n for n in nodes if n.get('text')==text])
            if candidates:
                return candidates[0]
            packages = {n.get('package') for n in nodes if n.get('package')}
            if packages and PACKAGE not in packages:
                raise RuntimeError('Target app no longer foreground; stopped UI navigation')
            time.sleep(.3)
        raise RuntimeError(f'Missing expected control: {ident or text}')
    def tap(self, node):
        if node.get('package') != PACKAGE:
            raise RuntimeError('Refusing a control outside the selected app')
        x1,y1,x2,y2 = map(int,re.findall(r'\d+',node.get('bounds')))
        self.run('shell','input','tap',(x1+x2)//2,(y1+y2)//2)
    def open_poem(self, case):
        self.run('shell','am','start','-n',PACKAGE+'/.ui.activities.MainActivity')
        self.tap(self.wait(case,'home',ident='myLibraryNavigation'))
        self.tap(self.wait(case,'library',ident='cl_my_library_downloads'))
        self.tap(self.wait(case,'downloads',text='The Moon'))
        self.wait(case,'edition',text='Robert Louis Stevenson')
        # Only cached content is used; there is no purchase/download flow here.
        self.wait(case,'downloaded',text='Downloaded')
        self.tap(self.wait(case,'detail',text='PRINT'))


def prepare(root,full_replays=0):
    old = REPO/'output/product-comparison-20261119'
    master = old/'synthetic/moon-normal.wav'
    with wave.open(str(master)) as w:
        if (w.getframerate(),w.getnchannels(),w.getsampwidth())!=(16000,1,2):
            raise ValueError('Unexpected synthetic master format')
        source = np.frombuffer(w.readframes(w.getnframes()),dtype='<i2')
    words = timed_words(old/'synthetic/moon-normal')
    anchors = [('opening','The moon has a face'),('clock','the clock in the hall'),('cat','The squalling cat'),
               ('mouse','the squeaking mouse'),('dog','The howling dog')]
    cases = []
    for ident,anchor in ([] if full_replays else anchors):
        start,end = anchor_interval(words,anchor)
        for kind,cut in [('before',start),('after',end)]:
            case = ident+'-'+kind
            folder = root/case
            folder.mkdir(parents=True,exist_ok=True)
            # Preserve the master prefix byte-for-byte, then add eight seconds
            # of silence for decoding and any delayed cue. No new prosody.
            samples = np.concatenate([source[:round(cut*16000)],np.zeros(8*16000,dtype='<i2')])
            wav = folder/'input.wav'
            if not wav.exists():
                with wave.open(str(wav),'wb') as w:
                    w.setparams((1,2,16000,0,'NONE','not compressed'));w.writeframes(samples.tobytes())
            stereo = np.repeat(np.clip(np.rint(resample_poly(samples.astype(float),3,1)),-32768,32767).astype('<i2')[:,None],2,axis=1)
            pcm = folder/'input.48k-stereo.pcm'
            if not pcm.exists():stereo.tofile(pcm)
            cases.append(dict(id=case,phrase=anchor,kind=kind,cut_seconds=cut,
                              expected_phrase_start_seconds=start,expected_phrase_end_seconds=end,
                              source_seconds=len(samples)/16000,
                              pcm_sha256=hashlib.sha256(pcm.read_bytes()).hexdigest()))
    if full_replays:
        import shutil
        stereo=np.repeat(np.clip(np.rint(resample_poly(source.astype(float),3,1)),-32768,32767).astype('<i2')[:,None],2,axis=1)
        for i in range(full_replays):
            case=f'full-{i+1:02d}';folder=root/case;folder.mkdir(parents=True,exist_ok=True)
            wav=folder/'input.wav';pcm=folder/'input.48k-stereo.pcm'
            if not wav.exists():shutil.copyfile(master,wav)
            if not pcm.exists():stereo.tofile(pcm)
            cases.append(dict(id=case,kind='full_validation',phrase='complete synthetic poem',
                              source_seconds=len(source)/16000,pcm_sha256=hashlib.sha256(pcm.read_bytes()).hexdigest(),
                              master_wav_sha256=hashlib.sha256(wav.read_bytes()).hexdigest()))
    plan = dict(protocol='full-validation-replays-v1' if full_replays else 'causal-prefix-controls-v1',source_master=str(master.resolve()),
                source_sha256=hashlib.sha256(master.read_bytes()).hexdigest(),
                pad_seconds=0 if full_replays else 8,cases=cases,
                interpretation='Before/after controls identify phrase-associated output changes; semantic sound names are not assumed.')
    file = root/'plan.json'
    if file.exists() and json.loads(file.read_text())!=plan:
        raise ValueError('Existing plan differs; choose a fresh directory')
    file.write_text(json.dumps(plan,indent=2)+'\n',encoding='utf-8')
    return plan


def trial(phone, case):
    ident=case['id']; folder=phone.root/ident
    result_file=folder/'result.json'
    if result_file.exists():
        if json.loads(result_file.read_text()).get('status')=='ok':
            print('REUSE',ident,flush=True);return
        raise ValueError('Preserve failed attempt and choose a fresh case directory')
    prefix='/data/local/tmp/reading-pod-isolate-'+ident
    pcm=prefix+'.input.pcm';control=prefix+'.control'
    for suffix in ['.input.pcm','.jsonl','.output.pcm','.control.start','.control.stop']:
        phone.owned.add(prefix+suffix)
    phone.run('push',folder/'input.48k-stereo.pcm',pcm)
    actual=phone.run('shell','sha256sum',pcm).split()[0]
    if actual!=case['pcm_sha256']:raise ValueError('Phone PCM hash mismatch')
    phone.run('shell','cmd','media_session','volume','--stream','3','--set','0')
    cmd=[str(ADB),'-s',SERIAL,'shell','env','CLASSPATH='+DEX,'app_process','/system/bin',
         'QuietAudioSession','hold',PACKAGE,pcm,prefix,control]
    log=(folder/'console.log').open('w',encoding='utf-8')
    process=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,text=True)
    status=dict(case=case,status='failed',phone_pcm_sha256=actual)
    try:
        for _ in range(50):
            log.flush()
            if 'SESSION_READY' in (folder/'console.log').read_text(encoding='utf-8'):
                break
            if process.poll() is not None:raise RuntimeError('Audio route did not arm')
            time.sleep(.1)
        else:raise TimeoutError('Audio route readiness timeout')
        print('ARMED',ident,flush=True)
        phone.run('shell','svc','data','disable')
        phone.open_poem(ident)
        for _ in range(10):
            inspection=phone.run('shell','env','CLASSPATH='+DEX,'app_process','/system/bin',
                                 'QuietAudioSession','inspect',PACKAGE)
            objects=[json.loads(line) for line in inspection.splitlines() if line.startswith('{')]
            recs=[obj for obj in objects if 'recording_uid' in obj]
            if recs and all(r['device_type']==25 and not r['silenced'] for r in recs):break
            if process.poll() is not None:raise RuntimeError('Virtual route session ended')
            time.sleep(.3)
        else:raise RuntimeError('No verified unsilenced virtual microphone')
        (folder/'route.txt').write_text(inspection,encoding='utf-8')
        phone.run('shell','svc','data','disable')
        if phone.run('shell','settings','get','global','wifi_on')!='0':
            raise RuntimeError('Wi-Fi unexpectedly enabled; do not feed speech')
        phone.run('shell','touch',control+'.start')
        print('REPLAY',ident,'seconds',case['source_seconds'],flush=True)
        code=process.wait(timeout=case['source_seconds']+30)
        console=(folder/'console.log').read_text(encoding='utf-8')
        if code!=0 or 'REPLAY_COMPLETE' not in console or 'SESSION_RELEASED' not in console:
            raise RuntimeError('Incomplete quiet replay: '+console[-500:])
        for suffix,filename in [('.jsonl','clocks.jsonl'),('.output.pcm','output.pcm')]:
            phone.run('pull',prefix+suffix,folder/filename)
        status.update(status='ok',exit_code=code,virtual_route_verified=True,
                      wifi_off_during_replay=True,cellular_off_during_replay=True)
        print('CAPTURED',ident,flush=True)
    except Exception as e:
        status['error']=repr(e);raise
    finally:
        errors=[]
        try:phone.run('shell','am','force-stop',PACKAGE)
        except Exception as error:errors.append(repr(error))
        if process.poll() is None:
            try:phone.run('shell','touch',control+'.stop')
            except Exception as error:errors.append(repr(error))
            try:process.wait(timeout=15)
            except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=5)
        log.close()
        if phone.original['mobile_data']=='1':
            try:phone.run('shell','svc','data','enable')
            except Exception as error:errors.append(repr(error))
        status['cleanup_errors']=errors
        result_file.write_text(json.dumps(status,indent=2)+'\n',encoding='utf-8')


def trial_detached(phone,case):
    """Device-owned cleanup survives loss of the host's USB shell channel."""
    ident=case['id'];folder=phone.root/ident;result_file=folder/'result.json'
    if result_file.exists():
        if json.loads(result_file.read_text()).get('status')=='ok':return
        raise ValueError('Preserve failed case; choose a fresh root')
    tag=hashlib.sha256(str(phone.root.resolve()).encode()).hexdigest()[:8]
    prefix='/data/local/tmp/reading-pod-isolate-'+tag+'-'+ident
    pcm=prefix+'.input.pcm';control=prefix+'.control'
    for suffix in ['.input.pcm','.jsonl','.output.pcm','.control.start','.control.stop',
                   '.session.sh','.console.log','.launcher.log','.exit','.restored']:
        phone.owned.add(prefix+suffix)
    original=phone.original
    if not (str(original['media_volume']).isdigit() and str(original['stay_on']).isdigit()
            and original['mobile_data'] in ['0','1'] and original['wifi_on'] in ['0','1']):raise ValueError('Invalid restoration snapshot')
    script='''#!/system/bin/sh
cleanup() {
  am force-stop com.noveleffect.book
  cmd media_session volume --stream 3 --set VOLUME
  settings put global stay_on_while_plugged_in STAY
  svc data DATA
  svc wifi WIFI
  echo done > PREFIX.restored
}
trap cleanup EXIT HUP INT TERM
export CLASSPATH=DEX
app_process /system/bin QuietAudioSession hold com.noveleffect.book PREFIX.input.pcm PREFIX PREFIX.control > PREFIX.console.log 2>&1
status=$?
echo "$status" > PREFIX.exit
exit "$status"
'''.replace('VOLUME',str(original['media_volume'])).replace('STAY',original['stay_on']).replace('DATA','enable' if original['mobile_data']=='1' else 'disable').replace('WIFI','enable' if original['wifi_on']=='1' else 'disable').replace('PREFIX',prefix).replace('DEX',DEX)
    local_script=folder/'session.sh';local_script.write_text(script,encoding='utf-8',newline='\n')
    phone.run('push',folder/'input.48k-stereo.pcm',pcm)
    actual=phone.run('shell','sha256sum',pcm).split()[0]
    if actual!=case['pcm_sha256']:raise ValueError('PCM changed during transfer')
    phone.run('push',local_script,prefix+'.session.sh')
    phone.run('shell','cmd','media_session','volume','--stream','3','--set','0')
    phone.run('shell','svc','power','stayon','usb')
    # All shell tokens are generated constants, a hex tag, or fixed case IDs.
    phone.run('shell','nohup /system/bin/sh '+prefix+'.session.sh > '+prefix+'.launcher.log 2>&1 < /dev/null &')
    status=dict(case=case,status='failed',phone_pcm_sha256=actual,detached=True,
                autonomous_phone_cleanup=True,remote_prefix=prefix)
    done=False
    try:
        for _ in range(30):
            console=phone.run('shell','cat',prefix+'.console.log',check=False)
            if 'SESSION_READY' in console:break
            time.sleep(.2)
        else:raise RuntimeError('Detached route did not arm: '+console[-400:])
        print('ARMED',ident,'detached',flush=True)
        phone.open_poem(ident)
        for _ in range(10):
            inspection=phone.run('shell','env','CLASSPATH='+DEX,'app_process','/system/bin','QuietAudioSession','inspect',PACKAGE)
            recs=[json.loads(l) for l in inspection.splitlines() if l.startswith('{') and 'recording_uid' in l]
            if recs and all(r['device_type']==25 and not r['silenced'] for r in recs):break
            time.sleep(.3)
        else:raise RuntimeError('No unsilenced virtual input')
        (folder/'route.txt').write_text(inspection,encoding='utf-8')
        phone.run('shell','svc','data','disable')
        phone.run('shell','svc','wifi','disable')
        if phone.run('shell','settings','get','global','wifi_on')!='0':raise RuntimeError('Wi-Fi is on')
        phone.run('shell','touch',control+'.start')
        print('REPLAY',ident,case['source_seconds'],flush=True)
        deadline=time.monotonic()+case['source_seconds']+35
        while time.monotonic()<deadline:
            code=phone.run('shell','test -f '+prefix+'.restored && cat '+prefix+'.exit',check=False)
            if code.strip() in ['0','2']:done=True;break
            time.sleep(.5)
        if not done or code.strip()!='0':raise RuntimeError('Detached replay did not complete')
        for suffix,name in [('.jsonl','clocks.jsonl'),('.output.pcm','output.pcm'),('.console.log','console.log')]:
            phone.run('pull',prefix+suffix,folder/name)
        if 'REPLAY_COMPLETE' not in (folder/'console.log').read_text():raise RuntimeError('Missing completion evidence')
        status.update(status='ok',virtual_route_verified=True,cellular_off_during_replay=True,
                      wifi_off_during_replay=True,exit_code=0)
        print('CAPTURED',ident,flush=True)
    except Exception as error:status['error']=repr(error);raise
    finally:
        if not done:
            try:
                phone.run('shell','am','force-stop',PACKAGE)
                phone.run('shell','touch',control+'.stop')
                time.sleep(.5)
            except Exception as error:status['host_cleanup_error']=repr(error)
        result_file.write_text(json.dumps(status,indent=2)+'\n',encoding='utf-8')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--only',nargs='*');parser.add_argument('--prepare-only',action='store_true')
    parser.add_argument('--full-replays',type=int,choices=range(6),default=0)
    args=parser.parse_args();args.root.mkdir(parents=True,exist_ok=True)
    plan=prepare(args.root,args.full_replays)
    if args.prepare_only:print(json.dumps(plan,indent=2));return
    phone=Phone(args.root)
    volume=phone.run('shell','cmd','media_session','volume','--stream','3','--get')
    match=re.search(r'volume is (\d+)',volume)
    if not match:raise ValueError('Cannot preserve phone volume')
    original=dict(media_volume=int(match[1]),
                  mobile_data=phone.run('shell','settings','get','global','mobile_data'),
                  wifi_on=phone.run('shell','settings','get','global','wifi_on'),
                  stay_on=phone.run('shell','settings','get','global','stay_on_while_plugged_in'))
    phone.original=original
    (args.root/'phone-original.json').write_text(json.dumps(original,indent=2),encoding='utf-8')
    if original['wifi_on'] not in ['0','1']:raise RuntimeError('Unknown Wi-Fi state; cannot preserve it')
    try:
        phone.run('shell','rm','-f',DEX)
        phone.run('push',REPO/'output/product-comparison-20261119/android-probe/dex/classes.dex',DEX)
        phone.run('shell','chmod','0444',DEX)
        phone.run('shell','svc','power','stayon','usb')
        for case in plan['cases']:
            if args.only and case['id'] not in args.only:continue
            trial_detached(phone,case)
    finally:
        errors=[]
        actions=[('shell','am','force-stop',PACKAGE)]
        actions += [('shell','rm','-f',remote) for remote in sorted(phone.owned)]
        actions += [('shell','cmd','media_session','volume','--stream','3','--set',original['media_volume']),
                    ('shell','settings','put','global','stay_on_while_plugged_in',original['stay_on'])]
        if original['mobile_data']=='1':actions.append(('shell','svc','data','enable'))
        actions.append(('shell','svc','wifi','enable' if original['wifi_on']=='1' else 'disable'))
        for action in actions:
            try:phone.run(*action)
            except Exception as error:errors.append(dict(action=list(action),error=repr(error)))
        restored=dict(status='cleanup_pending' if errors else 'restored',original=original,
                      errors=errors,temporary_files_removed=not errors)
        if not errors:
            restored.update(media_volume=phone.run('shell','cmd','media_session','volume','--stream','3','--get'),
                            stay_on=phone.run('shell','settings','get','global','stay_on_while_plugged_in'),
                            mobile_data=phone.run('shell','settings','get','global','mobile_data'))
        else:
            (args.root/'cleanup-pending.json').write_text(json.dumps(restored,indent=2),encoding='utf-8')
        (args.root/'phone-restored.json').write_text(json.dumps(restored,indent=2),encoding='utf-8')
        print('PHONE_CLEANUP_PENDING' if errors else 'PHONE_RESTORED',flush=True)


if __name__=='__main__':main()
