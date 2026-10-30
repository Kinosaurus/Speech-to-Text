"""No-prompt acoustic word estimates for locally indexed library recordings."""
import argparse
import json
import os
from pathlib import Path
import sys

import soundfile as sf
from faster_whisper import WhisperModel

ROOT=Path(__file__).resolve().parents[1]
LIB=ROOT/'recordings/library'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jobs',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    dlls=Path(sys.prefix)/'Lib/site-packages/torch/lib'
    if os.name=='nt' and dlls.is_dir():
        directory=os.add_dll_directory(str(dlls))
        os.environ['PATH']=str(dlls)+os.pathsep+os.environ['PATH']
    jobs=json.loads(args.jobs.read_text(encoding='utf-8'))['recordings']
    for name in ['small.en','medium.en']:
        print('LOAD',name,flush=True)
        model=WhisperModel(name,device='cuda',compute_type='float16',local_files_only=True)
        for recording in jobs:
            target=args.output/(recording['audio_id']+'.'+name+'.json')
            if target.exists():
                data=json.loads(target.read_text(encoding='utf-8'))
                assert data['audio_sha256']==recording['audio_sha256']
                continue
            audio,rate=sf.read(LIB/recording['path']/'audio.wav',dtype='float32')
            assert rate==16000 and audio.ndim==1
            segments,info=model.transcribe(audio,language='en',beam_size=5,word_timestamps=True,
                vad_filter=False,condition_on_previous_text=False,temperature=0)
            words=[]
            text=[]
            for segment in segments:
                text.append(segment.text)
                for word in segment.words or []:
                    words.append(dict(word=word.word,start=word.start,end=word.end,probability=word.probability))
            data=dict(audio_id=recording['audio_id'],audio_sha256=recording['audio_sha256'],model=name,
                engine='faster-whisper',device='cuda',compute_type='float16',initial_prompt=None,hotwords=None,
                vad_filter=False,manual_verification=False,text=' '.join(text),words=words)
            target.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print('DONE',recording['audio_id'],name,data['text'],flush=True)
        del model

if __name__=='__main__':main()
