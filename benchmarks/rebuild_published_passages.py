"""Rebuild Kites, Billy and Tom checkpoint ranges from published passage text."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import wave

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from checkpoint_matcher import normalize_text
from alignment_matcher import AlignmentMatcher

LIB=ROOT/'recordings/library'
OUT=ROOT/'output/published-passages-2026-10-30'
JOBS=[('making-kites','7028'),('billy-visits-grandpa','6027'),('tom-s-secret-study','7015')]
REPLACEMENTS={'dinosaur_kite':'Joe cut a dinosaur kite.'}

def main():
    OUT.mkdir(exist_ok=True)
    rows=[]
    for story,reader in JOBS:
        folder=LIB/'stories'/story/'readers'/reader
        history=folder/'history/before-published-rebuild-2026-10-30'
        history.mkdir(parents=True,exist_ok=True)
        for name in ['checkpoints.json','expected.json','text_status.json','README.md']:
            archived=history/('README.original.txt' if name=='README.md' else name)
            if (folder/name).exists() and not archived.exists():
                shutil.copyfile(folder/name,archived)
        old=json.loads((history/'checkpoints.json').read_text(encoding='utf-8'))
        passage=(folder/'published_passage.txt').read_text(encoding='utf-8').strip()
        (folder/'passage.txt').write_text(passage+'\n',encoding='utf-8')
        words=normalize_text(passage).split()
        old['pages'][0]['text']=passage
        changes=[]
        for cp in old['checkpoints']:
            before=dict(cp)
            cp['checkpoint_text']=REPLACEMENTS.get(cp['id'],cp['checkpoint_text'])
            anchor=normalize_text(cp['checkpoint_text']).split()
            hits=[i for i in range(len(words)-len(anchor)+1) if words[i:i+len(anchor)]==anchor]
            assert len(hits)==1,(story,cp['id'],hits)
            cp['word_start']=hits[0]
            cp['word_end']=hits[0]+len(anchor)
            changes.append(dict(id=cp['id'],previous_text=before['checkpoint_text'],new_text=cp['checkpoint_text'],old_range=[before['word_start'],before['word_end']],new_range=[cp['word_start'],cp['word_end']]))
        old['provenance'].update(reference_status='independently published passage version; exact OCSC stimulus-card edition unverified',
            published_source='passage_source.json',previous_manifest='history/before-published-rebuild-2026-10-30/checkpoints.json',
            timing='Pending fresh audio-derived endpoint estimates; older corpus timing archived',rebuilt_date='2026-10-30')
        AlignmentMatcher(old)
        (folder/'checkpoints.json').write_text(json.dumps(old,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (folder/'expected.json').write_text(json.dumps(dict(expected={},unread=[],timing='Pending fresh acoustic estimates',verified=False),indent=2)+'\n')
        (folder/'text_status.json').write_text(json.dumps(dict(kind='published_passage_version',file='passage.txt',
            note='Independently published text used by current checkpoint manifest. Exact recording-card edition unverified; reference.txt retains the older transcript-derived reference. See passage_source.json.'),indent=2)+'\n')
        with wave.open(str(folder/'audio.wav')) as wav:duration=wav.getnframes()/wav.getframerate()
        row=dict(audio_id=story+'-'+reader,path=folder.relative_to(LIB).as_posix(),audio_sha256=hashlib.sha256((folder/'audio.wav').read_bytes()).hexdigest(),
                 manifest_sha256=hashlib.sha256((folder/'checkpoints.json').read_bytes()).hexdigest(),duration_seconds=duration,age_years=None,grade=None,changes=changes)
        rows.append(row)
        (folder/'passage_rebuild.json').write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(story,reader,duration,changes,flush=True)
    (OUT/'jobs.json').write_text(json.dumps(dict(recordings=rows),indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
