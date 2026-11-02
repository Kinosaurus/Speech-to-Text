"""Frozen synthetic adult-speech challenges; never child-reading accuracy data.

Expected outcomes describe literal authored words. Close-word substitutions
deliberately test a limitation of pronunciation-tolerant text matching.
"""
import argparse
import hashlib
import html
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks.run_mps_heldout import read, write, digest, check_frozen, source_files, old_tracker
from benchmarks.run_pending_regression import replay
from books_to_life.matching.checkpoint_matcher import normalize_text
from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher

DEST = ROOT / 'output/false-trigger-challenges-2026-11-02'
REFERENCE = ROOT / 'output/mps-heldout-phonetic-2026-11-02'
BEFORE = ROOT / 'output/phonetic-feature-regression-2026-11-02/baseline-snapshot'
MARKER = 'we walked along a quiet path beside the trees'
FINISH = 'after that we returned safely to the little house'
# Fixed before synthesis/ASR. No selection from recognition outcomes.
PAIRS = [('coat', 'she carried the winter coat', 'goat', 'stone'),
         ('fan', 'he switched on the fan', 'van', 'lamp'),
         ('seal', 'we spotted a playful seal', 'zeal', 'bird'),
         ('pen', 'the child held a red pen', 'pin', 'book'),
         ('sink', 'he carefully cleaned the white sink', 'zinc', 'chair')]
KINDS = ('correct', 'omitted', 'close_wrong_word', 'distant_wrong_word',
         'quoted_prompt', 'negated_prompt', 'prefix_then_unrelated', 'skipped', 'reread')


def manifest(name, anchor, required=False):
    text = MARKER + ' then ' + anchor + ' ' + FINISH
    result = dict(book_id=name, threshold=82, stability=2, min_coverage=.8,
                  pages=[dict(page=1, text=text)], checkpoints=[])
    words = text.split()
    for position, (ident, phrase) in enumerate((('start', MARKER), ('target', anchor), ('finish', FINISH)), 1):
        tokens = phrase.split(); hits = [i for i in range(len(words)-len(tokens)+1) if words[i:i+len(tokens)] == tokens]
        assert len(hits) == 1
        cp = dict(id=ident, book_id=name, checkpoint_position=position, checkpoint_text=phrase,
                  word_start=hits[0], word_end=hits[0]+len(tokens), effect_policy='one_shot', effect={'effect_id': ident})
        if required and ident == 'target': cp['required_words'] = [tokens[-1]]
        result['checkpoints'].append(cp)
    TimelyEvidenceMatcher(result)
    return result


def prepare(output):
    output.mkdir(parents=True, exist_ok=False)
    reference = check_frozen(REFERENCE)
    jobs = []
    for endpoint, anchor, close, distant in PAIRS:
        prefix = anchor.rsplit(' ', 1)[0]
        for kind in KINDS:
            ident = endpoint + '-' + kind; folder = output / 'inputs' / ident; folder.mkdir(parents=True)
            actual = close if kind == 'close_wrong_word' else distant if kind == 'distant_wrong_word' else endpoint
            lead = 'please repeat ' if kind == 'quoted_prompt' else 'do not say ' if kind == 'negated_prompt' else ''
            if kind == 'skipped': middle = ''
            elif kind == 'omitted': middle = 'then ' + prefix
            elif kind == 'prefix_then_unrelated': middle = 'then ' + prefix + ' the television remote has disappeared again'
            else: middle = 'then ' + lead + prefix + ' ' + actual
            if kind == 'reread': middle += '. ' + anchor
            spoken = MARKER + '. ' + (middle + '. ' if middle else '') + FINISH + '.'
            # Matched artificial pauses make endpoint acquisition testable for
            # both correct and wrong words, without changing runtime buffering.
            escaped = html.escape(middle)
            if middle:
                escaped = escaped.replace(html.escape(prefix), html.escape(prefix)+'<break time="600ms"/>')
            ssml = ('<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">'
                    '<s>'+MARKER+'.</s><break time="400ms"/>'
                    + ('<s>'+escaped+'.</s><break time="400ms"/>' if middle else '')
                    + '<s>'+FINISH+'.</s></speak>')
            (folder / 'speech.ssml').write_text(ssml, encoding='utf-8')
            paths = {}
            for policy in ('default', 'required'):
                path = folder / (policy + '.json'); write(path, manifest(ident, anchor, policy == 'required'))
                paths[policy] = str(path)
            jobs.append(dict(id=ident, endpoint=endpoint, anchor=anchor, spoken_target_word=actual,
                category=kind, expected_target_emit=kind in ('correct', 'reread'), expected_target_max_emissions=1,
                script=spoken, expected_spoken_anchor=lead+prefix+' '+actual if kind not in ('omitted','skipped','prefix_then_unrelated') else None,
                ssml=str(folder/'speech.ssml'), ssml_sha256=digest(folder/'speech.ssml'),
                audio=str(folder/'audio.wav'), manifest=paths['default'],
                manifest_sha256=digest(Path(paths['default'])), observer_manifests=paths,
                observer_manifest_sha256={k:digest(Path(v)) for k,v in paths.items()}))
    assert len(jobs) == 45
    write(output/'jobs.json', jobs)
    hashes = {}
    files = set(source_files()) | {Path(__file__).resolve(), ROOT/'benchmarks/synthesize_challenges.ps1'}
    for path in sorted(files):
        name = path.relative_to(ROOT).as_posix(); data = path.read_bytes()
        target = output/'source-snapshot'/name; target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(data); hashes[name] = hashlib.sha256(data).hexdigest()
        if name.startswith('books_to_life/'):
            assert hashes[name] == reference['source_sha256'][name]
    baseline = {}
    for path in BEFORE.glob('*.py'):
        target = output/'baseline-snapshot'/path.name; target.parent.mkdir(exist_ok=True)
        shutil.copyfile(path,target); baseline[path.name] = digest(target)
    write(output/'protocol.json', dict(date='2026-11-02', scope='Synthetic adult false-trigger challenge',
        configuration=reference['configuration'], model=reference['model'], lexicon=reference['lexicon'],
        source_sha256=hashes, baseline_sha256=baseline, ordered_recordings=[j['id'] for j in jobs],
        source='Windows offline Microsoft Zira Desktop, adult female en-US, rate 0, volume 100; 16 kHz mono PCM16.',
        design=dict(anchors=5, categories=list(KINDS), fresh_streams=45, trials_per_case=1,
                    policies=['default','required'], required_policy_is_observer_only=True),
        runtime_reference=str(REFERENCE/'protocol.json'), no_asr_or_matcher_tuning=True,
        frozen_before_synthesis=True, artificial_prefix_pause_ms=600, artificial_sentence_pause_ms=400,
        baseline='Previous matcher before the phonetic-feature/progress change; same current ASR callbacks.',
        expected_policy='Literal endpoint semantics: actual wrong words, omissions, prompts and skipped anchors should not emit. Correct and reread cases should emit once. Pronunciation-tolerant acceptance can conflict with this strict wrong-word requirement.',
        limits=['Synthetic adult speech and constructed pauses, not children or real room audio.',
                'A scripted synthesis request is not an independent human transcript; review failures with the audio and saved ASR.',
                'The required-word observer is a predeclared policy comparison, not a production-manifest change or a guarantee against close spelling.']))
    check_frozen(output, model_hash=True)
    print('FROZEN 45 synthetic cases, two predeclared manifest policies, unchanged ASR/matcher.', flush=True)


def verify(output, audio=False):
    check_frozen(output)
    jobs = read(output/'jobs.json')
    for job in jobs:
        assert digest(Path(job['ssml'])) == job['ssml_sha256']
        for policy,path in job['observer_manifests'].items():
            assert digest(Path(path)) == job['observer_manifest_sha256'][policy]
    if audio:
        frozen = read(output/'audio-inventory.json')
        assert [r['id'] for r in frozen] == [j['id'] for j in jobs]
        for row in frozen: assert digest(Path(row['audio'])) == row['audio_sha256']
    return jobs


def preflight(output):
    jobs=verify(output); Old=old_tracker(output); rows=[]
    for job in jobs:
        words=normalize_text(job['script']).split(); events=[]
        for stop in range(2,len(words)+2,2):
            text=' '.join(words[:stop]); end=min(stop,len(words))*.28
            events.append(dict(kind='segments',segments=[dict(start=0,end=end,text=text,completed=False)]))
        events.append(dict(kind='segments',segments=[dict(start=0,end=len(words)*.28,text=' '.join(words),completed=True)]))
        result=dict(id=job['id'],category=job['category'],expected=job['expected_target_emit'])
        for policy,path in job['observer_manifests'].items():
            result[policy]={label:replay(Tracker,read(Path(path)),events) for label,Tracker in (('before',Old),('after',TimelyEvidenceMatcher))}
        rows.append(result)
    write(output/'text-diagnostics.json',dict(kind='Constructed word-by-word text snapshots, not ASR/audio trials',cases=rows))
    for policy in ('default','required'):
        for label in ('before','after'):
            false=[r['id'] for r in rows if not r['expected'] and 'target' in r[policy][label]['emitted']]
            missed=[r['id'] for r in rows if r['expected'] and 'target' not in r[policy][label]['emitted']]
            print('TEXT',policy,label,'false',false,'missed',missed,flush=True)


def inventory(output):
    jobs=verify(output); rows=[]
    for job in jobs:
        path=Path(job['audio'])
        with wave.open(str(path)) as wav:
            assert wav.getframerate()==16000 and wav.getnchannels()==1 and wav.getsampwidth()==2
            rows.append(dict(id=job['id'],audio=str(path),audio_sha256=digest(path),samples=wav.getnframes(),audio_seconds=wav.getnframes()/16000))
    write(output/'audio-inventory.json',rows)
    print('SYNTHESIZED',len(rows),'files;',round(sum(r['audio_seconds'] for r in rows),2),'seconds.',flush=True)


def audit(output,job,Old):
    stem=output/'streams'/job['id']; events=[json.loads(s) for s in stem.with_suffix('.events.jsonl').read_text(encoding='utf-8').splitlines()]
    packets=[e for e in events if e['kind']=='audio']; segments=[e for e in events if e['kind']=='segments']; count=0
    for packet in packets: assert packet['sample_start']==count; count+=packet['sample_count']
    with wave.open(job['audio']) as wav: assert count==wav.getnframes()
    assert segments and segments[0]['wall']<packets[-1]['wall']
    assert segments[-1]['segments'][-1]['completed']
    assert abs(segments[-1]['segments'][-1]['end']-count/16000)<.001
    assert any(e['kind']=='status' and e.get('message')=='STREAM_DONE' for e in events)
    assert not any(e['kind']=='status' and e.get('status')=='ERROR' for e in events)
    result=dict(id=job['id'],category=job['category'],expected=job['expected_target_emit'],
        script=job['script'],anchor=job['anchor'],spoken_target_word=job['spoken_target_word'],
        audio_sha256=digest(Path(job['audio'])),samples_delivered=count,delivery_audit_pass=True,
        final_asr=' '.join(s['text'] for s in segments[-1]['segments']),policies={})
    final=' '+normalize_text(result['final_asr'])+' '
    result['expected_spoken_anchor_in_final_asr']=bool(job['expected_spoken_anchor'] and ' '+normalize_text(job['expected_spoken_anchor'])+' ' in final)
    for policy,path in job['observer_manifests'].items():
        cfg=read(Path(path)); before=replay(Old,cfg,segments); after=replay(TimelyEvidenceMatcher,cfg,segments)
        observed=[e for e in events if e['kind']=='tracker' and e['mode']=='timely' and e['book']==policy]
        assert [e['scene'] for e in observed if e['triggered']]==after['emitted']
        assert [e['scene'] for e in observed if e.get('suppressed')]==after['suppressed']
        emitted='target' in after['emitted']; expected=job['expected_target_emit']
        result['policies'][policy]=dict(before=before,after=after,target_emitted=emitted,
            false_trigger=emitted and not expected,missed_target=expected and not emitted,
            target_trigger_audio_end=next((e['audio_end'] for e in observed if e['scene']=='target' and e['triggered']),None),
            duplicate_target_emissions=max(0,sum(e['scene']=='target' and e['triggered'] for e in observed)-1))
    log=stem.with_suffix('.log').read_text(encoding='utf-8')
    assert re.findall(r'^\[TRIGGER\] (\S+):',log,re.M)==result['policies']['default']['after']['emitted']
    assert re.findall(r'^\[SUPPRESSED\] (\S+):',log,re.M)==result['policies']['default']['after']['suppressed']
    result['app_observer_replay_agreement']=True
    return result


def run(output):
    jobs=verify(output,audio=True); Old=old_tracker(output)
    inventory_by_id={r['id']:r for r in read(output/'audio-inventory.json')}
    (output/'streams').mkdir(exist_ok=False); rows=[]
    for i,job in enumerate(jobs,1):
        verify(output); assert digest(Path(job['audio']))==inventory_by_id[job['id']]['audio_sha256']
        stem=output/'streams'/job['id']; print('START',i,'/',len(jobs),job['id'],flush=True)
        command=[sys.executable,'-X','utf8','-u','benchmarks/live_tracker_probe.py','--model','parakeet-nemo',
            '--server','127.0.0.1','--port','9097','--matching_mode','split','--no_book_context','--files',job['audio'],
            '--mute_audio_playback','--checkpoints',job['manifest'],'--transcript_file',str(stem.with_suffix('.srt'))]
        env=dict(os.environ,PYTHONUTF8='1',TRACKER_COMPARE_MANIFESTS=json.dumps(job['observer_manifests']))
        with stem.with_suffix('.log').open('w',encoding='utf-8') as handle:
            subprocess.run(command,cwd=ROOT,env=env,stdout=handle,stderr=subprocess.STDOUT,
                           timeout=math.ceil(inventory_by_id[job['id']]['audio_seconds']*1.5)+180,check=True)
        verify(output); row=audit(output,job,Old); rows.append(row); write(output/'results.json',dict(cases=rows))
        print('DONE',i,'default/required target:',row['policies']['default']['target_emitted'],row['policies']['required']['target_emitted'],flush=True)
    verify(output,audio=True); check_frozen(output,model_hash=True)
    write(output/'completed.json',dict(fresh_streams=45,all_trials_retained=True,one_trial_per_case=True,
        source_model_manifest_audio_hashes_unchanged=True,all_delivery_and_replay_audits_pass=True))
    print('COMPLETE 45 frozen synthetic adult-speech challenges. Failures are retained as results.',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--stage',choices=('prepare','preflight','inventory','run'),required=True)
    parser.add_argument('--output',type=Path,default=DEST);args=parser.parse_args();output=args.output.resolve()
    if not output.is_relative_to(ROOT/'output'):parser.error('Raw artifacts must stay under output/.')
    {'prepare':prepare,'preflight':preflight,'inventory':inventory,'run':run}[args.stage](output)
