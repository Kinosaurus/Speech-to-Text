"""Isolated local latency sweep; one resident model, explicitly acknowledged profiles."""
import argparse
import hashlib
import json
from pathlib import Path
import threading
import time

from books_to_life.runtime.nemo_parakeet import NemoParakeetSession, hint_phrases, load_model

PROFILES={'baseline':(560,560),'short-chunk':(160,560),'balanced':(160,320),'fast':(160,160)}


class TimedSession(NemoParakeetSession):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.decode_seconds=0.;self.decode_count=0
    def _decode(self,*args,**kwargs):
        start=time.perf_counter()
        super()._decode(*args,**kwargs)
        self.decode_seconds+=time.perf_counter()-start;self.decode_count+=1


class Socket:
    def __init__(self,ws,options,session,profile):
        self.ws,self.options,self.session,self.profile=ws,options,session,profile
    def recv(self,timeout=None):return json.dumps(self.options)
    def __iter__(self):return iter(self.ws)
    def send(self,value):
        data=json.loads(value)
        if data.get('message')=='SERVER_READY':
            assert self.session.phrases==hint_phrases(self.options.get('hotwords'))
            data.update(benchmark_latency_profile=self.profile,
                        chunk_ms=self.session.context.chunk//16,right_ms=self.session.context.right//16,
                        boost=self.session.boost,
                        applied_hotwords_sha256=hashlib.sha256((self.options.get('hotwords') or '').encode()).hexdigest())
        if 'segments' in data:
            data['benchmark_server_timing']=dict(decode_seconds=self.session.decode_seconds,
                                                decode_count=self.session.decode_count)
        self.ws.send(json.dumps(data))


def main():
    from websockets.sync.server import serve
    from books_to_life.cli.run_nemo_server import handle_connection
    p=argparse.ArgumentParser();p.add_argument('--model-path',type=Path,required=True)
    p.add_argument('--port',type=int,default=9099);args=p.parse_args()
    model=load_model(args.model_path,560,560);lock=threading.Lock()
    def connection(ws):
        acquired=False
        try:
            options=json.loads(ws.recv(timeout=30));profile=options.pop('benchmark_latency_profile')
            chunk,right=PROFILES[profile]
            acquired=lock.acquire(blocking=False)
            if not acquired:raise ValueError('Latency trial already active')
            # Model's trained chunk axes include 2 and 7 encoder frames; right
            # context axes include 2, 4 and 7. Each frame is 80 ms.
            model.encoder.set_default_att_context_size([70,chunk//80,right//80])
            session=TimedSession(model,chunk,right,1.0)
            handle_connection(Socket(ws,options,session,profile),lambda:session,threading.Lock())
        except Exception as error:
            try:ws.send(json.dumps({'status':'ERROR','message':str(error)}))
            except Exception:pass
        finally:
            if acquired:lock.release()
    with serve(connection,'127.0.0.1',args.port,max_size=65536) as server:
        print('[READY] isolated latency server',args.port,flush=True);server.serve_forever()


if __name__=='__main__':main()
