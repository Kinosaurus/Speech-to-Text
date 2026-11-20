"""Render the local aggregate-only HTML slides in a hidden muted Edge session."""
import argparse
import base64
import json
from pathlib import Path
import subprocess
import time
from urllib.request import Request, urlopen

import websocket


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('html',type=Path)
    args=parser.parse_args();source=args.html.resolve();directory=source.parent
    edge=next(path for path in (Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'),Path('C:/Program Files/Microsoft/Edge/Application/msedge.exe')) if path.is_file())
    process=subprocess.Popen([str(edge),'--headless=new','--disable-extensions','--mute-audio','--no-first-run',
                              '--disable-background-networking','--disable-sync','--remote-debugging-address=127.0.0.1',
                              '--remote-debugging-port=9226','--remote-allow-origins=http://localhost:9226',
                              '--user-data-dir='+str(directory/'slide-browser-profile'),'about:blank'],
                             stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    ws=None
    try:
        deadline=time.monotonic()+20
        while True:
            try:
                with urlopen(Request('http://127.0.0.1:9226/json/new?'+source.as_uri(),method='PUT'),timeout=2) as response:
                    target=json.load(response)
                break
            except OSError:
                if time.monotonic()>deadline:raise
                time.sleep(.2)
        ws=websocket.create_connection(target['webSocketDebuggerUrl'],origin='http://localhost:9226',timeout=15)
        sequence=0
        def cdp(method,params=None):
            nonlocal sequence
            sequence+=1;ident=sequence;ws.send(json.dumps({'id':ident,'method':method,'params':params or {}}))
            while True:
                message=json.loads(ws.recv())
                if message.get('id')==ident:
                    if 'error' in message:raise RuntimeError(message['error'])
                    return message['result']
        def evaluate(expression):
            result=cdp('Runtime.evaluate',{'expression':expression,'returnByValue':True,'awaitPromise':True})
            if result.get('exceptionDetails'):raise RuntimeError(result['exceptionDetails'])
            return result.get('result',{}).get('value')
        cdp('Emulation.setDeviceMetricsOverride',{'width':1920,'height':1080,'deviceScaleFactor':1,'mobile':False})
        deadline=time.monotonic()+15
        while not evaluate("document.querySelectorAll('.page').length>0 && document.readyState==='complete'"):
            if time.monotonic()>deadline:raise TimeoutError('Local slide HTML did not load.')
            time.sleep(.2)
        evaluate('document.fonts.ready.then(()=>true)')
        checks=evaluate("""Array.from(document.querySelectorAll('.page')).map((p,i)=>{const r=p.getBoundingClientRect();return {page:i+1,x:r.x+scrollX,y:r.y+scrollY,width:r.width,height:r.height,overflowY:p.scrollHeight>p.clientHeight,overflowX:p.scrollWidth>p.clientWidth,lastContentBottom:Math.max(...Array.from(p.children).filter(e=>!e.classList.contains('pageNum')).map(e=>e.getBoundingClientRect().bottom-r.top))};})""")
        for check in checks:
            if check['overflowX'] or check['overflowY'] or check['lastContentBottom']>1030:
                raise ValueError('Slide content overflows: '+str(check))
            capture=cdp('Page.captureScreenshot',{'format':'png','captureBeyondViewport':True,
                        'clip':{key:check[key] for key in ('x','y','width','height')}|{'scale':1}})
            (directory/f'canva-table-slide-{check["page"]}.png').write_bytes(base64.b64decode(capture['data']))
        (directory/'slide-layout-verification.json').write_text(json.dumps({'pages':checks,'silent_headless_browser':True},indent=2)+'\n')
        print(json.dumps(checks),flush=True)
    finally:
        if ws:
            try:ws.send(json.dumps({'id':9999,'method':'Browser.close'}))
            except Exception:pass
            ws.close()
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:process.terminate()


if __name__=='__main__':main()
