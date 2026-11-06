"""Freeze and verify separate authored effect cues and bounded acquisition."""
import argparse
from copy import deepcopy
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import wave
import cmudict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks.run_mps_heldout import read, write, digest as file_digest, source_files
from benchmarks.run_pending_regression import replay
from benchmarks.run_shared_reading import audit
from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher
from books_to_life.matching.checkpoint_matcher import normalize_text

DEST = ROOT / 'output/effect-cue-regression-v4-2026-11-06'
PRIOR = ROOT / 'output/internal-phonetic-regression-2026-11-03'
LATEST = ROOT / 'output/mps-frozen-streaming-2026-11-06'
DIAG = ROOT / 'output/mps-progress-investigation-2026-11-06'
NEGATIVES = {'omitted', 'negated_prompt', 'distant_wrong_word', 'prefix_then_unrelated', 'skipped'}


def digest(path):
    return file_digest(Path(path))


def authored(cfg):
    result = deepcopy(cfg)
    for cp in result['checkpoints']:
        for rule in read(ROOT / 'benchmarks/pilot_effect_policy.json')['rules']:
            if normalize_text(cp['checkpoint_text']) == normalize_text(rule['checkpoint_text']):
                for field in ('effect_cue', 'required_words'):
                    if field in rule:
                        cp[field] = deepcopy(rule[field])
    return result


def prepare(output):
    assert (output / 'baseline.json').exists() and not (output / 'protocol.json').exists()
    baseline = read(output / 'baseline.json')
    old = {r['id']: r['outcomes'] for r in read(PRIOR / 'saved-after.json')['cases']}
    inputs = []
    for j in read(PRIOR / 'replay-jobs.json'):
        inputs.append(dict(j, expected_before=old[j['id']]))
    sources = [
        (PRIOR, read(PRIOR / 'jobs.json'), {r['id']: r['outcomes'] for r in read(PRIOR / 'results.json')['cases']}, 'internal-'),
        (LATEST, read(LATEST / 'downloaded-jobs.json'), {r['recording']: r['after'] for r in read(LATEST / 'results.json')['recordings']}, 'latest-'),
        (DIAG, read(DIAG / 'reruns.json'), {r['id']: r['outcomes'] for r in read(DIAG / 'fresh-results.json')['cases']}, 'diagnostic-'),
    ]
    for directory, jobs, outcomes, prefix in sources:
        for j in jobs:
            events = directory / 'streams' / (j['id'] + '.events.jsonl')
            inputs.append(dict(id=prefix+j['id'], group=prefix.rstrip('-'), manifest=j['manifest'],
                events=str(events), events_sha256=digest(events), expected_before=outcomes[j['id']],
                category=j.get('category', 'original')))
    assert len(inputs) == 383
    legacy = []; cued = []
    for source in inputs:
        j = dict(source); path = output / 'replay-inputs' / j['id'] / 'checkpoints.json'
        path.parent.mkdir(parents=True); shutil.copyfile(j['manifest'], path)
        j.update(manifest=str(path), manifest_sha256=digest(path))
        legacy.append(j)
        cfg = read(path); revised = authored(cfg)
        if any('effect_cue' in c for c in revised['checkpoints']):
            cj = dict(j, id='cued-' + j['id'], group='authored_cue')
            cp = output / 'replay-inputs' / cj['id'] / 'checkpoints.json'; cp.parent.mkdir(parents=True)
            write(cp, revised); cj.update(manifest=str(cp), manifest_sha256=digest(cp), legacy_id=j['id'])
            cued.append(cj)
    write(output / 'legacy-jobs.json', legacy); write(output / 'cued-jobs.json', cued)
    jobs = []
    def add(ident, audio, cfg, events=None, **extra):
        path = output / 'inputs' / ident / 'checkpoints.json'; path.parent.mkdir(parents=True)
        write(path, cfg); TimelyEvidenceMatcher(cfg)
        jobs.append(dict(id=ident, audio=str(audio), manifest=str(path), manifest_sha256=digest(path),
            baseline_events=str(events) if events else None, **extra))
    for j in read(PRIOR / 'jobs.json'):
        add('legacy-' + j['id'], Path(j['audio']), read(Path(j['manifest'])),
            PRIOR / 'streams' / (j['id'] + '.events.jsonl'), category='legacy',
            target=j['target'], expected_target_emit=j['expected_target_emit'],
            asserted_checkpoint=j.get('asserted_checkpoint'),
            expected_before=next(r['outcomes'] for r in read(PRIOR / 'results.json')['cases'] if r['id'] == j['id']),
            unrelated=j['group'] == 'unrelated')
    for j in read(DIAG / 'reruns.json'):
        add('cue-' + j['id'], Path(j['audio']), authored(read(Path(j['manifest']))),
            DIAG / 'streams' / (j['id'] + '.events.jsonl'), category='authored_cue',
            target='lost_sheep', expected_target_emit=True, unrelated=False)
    # Include the policy's known ASR-essential-word limitation and the optional
    # opening-word regression found in preflight; do not hide either outcome.
    j = next(j for j in read(PRIOR/'jobs.json') if j['id']=='reading-3a8b_EN-OL-RC-234_1')
    add('cue-essential-asr-limitation', Path(j['audio']), authored(read(Path(j['manifest']))),
        PRIOR/'streams'/(j['id']+'.events.jsonl'), category='authored_cue_asr_limitation',
        target='lost_sheep', expected_target_emit=True, guard_expected_target_emit=False,
        unrelated=False, known_human_accepted=True)
    j = next(j for j in read(DIAG/'jobs.json') if j['id']=='3a4c_EN-OL-RC-234_1')
    add('cue-optional-prefix', Path(j['audio']), authored(read(Path(j['manifest']))),
        Path(j['events']), category='authored_cue',target='lost_sheep',expected_target_emit=True,
        require_identical_asr=False,unrelated=False)
    synthesis = []
    intro = 'We walked across the old bridge.'
    finish = 'We closed the book and went home.'
    for n, (cue, essential) in enumerate((('One sheep was lost.', 'lost'),
            ('A small rabbit jumped.', 'jumped'), ('The red balloon popped.', 'popped'),
            ('The heavy door opened.', 'opened'))):
        tail = 'The little child watched from the gate.'
        book = 'cue-synthetic-' + str(n)
        cfg = dict(book_id=book, threshold=82, stability=2, min_coverage=.8,
            pages=[dict(page=1, text=' '.join((intro, cue, tail, finish)))], checkpoints=[
                dict(id='start', book_id=book, checkpoint_position=1, checkpoint_text=intro, effect={}),
                dict(id='event', book_id=book, checkpoint_position=2, checkpoint_text=cue+' '+tail,
                    effect_cue=cue, required_words=[essential], effect={}),
                dict(id='finish', book_id=book, checkpoint_position=3, checkpoint_text=finish, effect={})])
        for omitted in (False, True):
            ident = book + ('-essential_omitted' if omitted else '-positive')
            audio = output / 'inputs' / ident / 'audio.wav'
            spoken = (' '.join(w for w in cue.rstrip('.').split() if w.lower() != essential) + '.') if omitted else cue
            add(ident, audio, cfg, category='essential_omitted' if omitted else 'controlled_positive',
                target='event', expected_target_emit=not omitted, unrelated=False)
            synthesis.append(dict(id=ident, audio=str(audio), voice='Microsoft Zira Desktop' if n % 2 == 0 else 'Microsoft David Desktop',
                text=' '.join((intro, spoken, tail, finish))))
    assert len(jobs) == 42
    write(output / 'jobs.json', jobs); write(output / 'synthesis-jobs.json', synthesis)
    files = set(source_files()) | set((ROOT / 'tests').glob('*.py')) | {
        Path(__file__).resolve(), ROOT / 'benchmarks/run_pending_regression.py',
        ROOT / 'benchmarks/run_shared_reading.py', ROOT / 'benchmarks/replay_policy_batch.py',
        ROOT / 'benchmarks/synthesize_shared_reading.ps1'}
    hashes = {}
    for path in sorted(files):
        name = path.relative_to(ROOT).as_posix(); dest = output / 'source-snapshot' / name
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(path, dest); hashes[name] = digest(path)
    changed = [name for name, sha in hashes.items() if name.startswith('books_to_life/') and baseline['source_sha256'].get(name) != sha]
    assert changed == ['books_to_life/matching/effect_permission.py', 'books_to_life/matching/timely_matcher.py'], changed
    write(output / 'protocol.json', dict(date='2026-11-06', scope=__doc__, source_sha256=hashes,
        baseline_sha256=baseline['source_sha256'], model=baseline['model'], configuration=baseline['configuration'], lexicon=baseline['lexicon'],
        fixed_json_sha256={name:digest(output/name) for name in ('jobs.json', 'legacy-jobs.json', 'cued-jobs.json', 'synthesis-jobs.json')},
        legacy_comparisons=len(legacy), cued_comparisons=len(cued), fresh_streams=42,
        changed_runtime_files=changed, ordered_recordings=[j['id'] for j in jobs],
        asr_and_numeric_thresholds_unchanged=True, source_audio_unchanged=True,
        policy='effect_cue is authored book data, not an ASR replacement. Required words belong to the cue and retain spelling support >=85. Full checkpoint text stays book context.',
        bounded_acquisition='Next nearby unread cue only; at least the configured minimum words of unique book context, one observed internal nonessential pronunciation variant between exact neighbours, exact cue/context endpoints, and unchanged scoring/ambiguity/confirmation.',
        synthetic_rule='Four fixed action cues, two installed synthetic voices, positive versus omitted essential word. Original speech scripts frozen before synthesis/ASR; no audio edits.',
        legacy_labels_unchanged=True,
        authored_label_difference='A missing following descriptive sentence is not a missing essential cue word. Original full-anchor endpoint-deletion labels remain in legacy tests; new cue policy is assessed separately.',
        inspected_regressions_not_new_holdout=True, one_fresh_trial_per_input=True))
    verify(output, model=True)
    print('FROZEN', len(legacy), 'legacy /', len(cued), 'authored comparisons; 42 fixed streams.', flush=True)


def verify(output, model=False, audio=False):
    p = read(output / 'protocol.json')
    for n, sha in p['source_sha256'].items():
        assert digest(ROOT / n) == sha, n
        assert digest(output / 'source-snapshot' / n) == sha, n
    for n, sha in p['baseline_sha256'].items():
        assert digest(output / 'baseline-snapshot' / n) == sha, n
    for n, sha in p['fixed_json_sha256'].items():
        assert digest(output / n) == sha, n
    for j in read(output / 'jobs.json') + read(output / 'legacy-jobs.json') + read(output / 'cued-jobs.json'):
        assert digest(j['manifest']) == j['manifest_sha256'], j['id']
        if j.get('events'):
            assert digest(j['events']) == j['events_sha256'], j['id']
    assert importlib.metadata.version('cmudict') == p['lexicon']['version']
    assert hashlib.sha256(cmudict.dict_string().encode('utf-8')).hexdigest() == p['lexicon']['data_sha256']
    path = ROOT / p['model']['path']
    assert path.stat().st_size == p['model']['bytes'] and path.stat().st_mtime_ns == p['model']['mtime_ns']
    if model:
        assert digest(path) == p['model']['sha256']
    if audio:
        for r in read(output / 'audio-inventory.json'):
            assert digest(r['audio']) == r['audio_sha256'], r['id']
    return p


def preflight(output):
    verify(output)
    for cohort in ('legacy', 'cued'):
        for version in ('before', 'after'):
            cmd = [sys.executable, '-X', 'utf8', '-u', 'benchmarks/replay_policy_batch.py',
                '--jobs', str(output/(cohort+'-jobs.json')), '--output', str(output/(cohort+'-'+version+'.json'))]
            if version == 'before':
                cmd += ['--snapshot', str(output/'baseline-snapshot')]
            subprocess.run(cmd, cwd=ROOT, check=True)
    old = {r['id']:r['outcomes'] for r in read(output/'legacy-before.json')['cases']}
    new = {r['id']:r['outcomes'] for r in read(output/'legacy-after.json')['cases']}
    for j in read(output/'legacy-jobs.json'):
        assert old[j['id']] == j['expected_before'], j['id']
        assert set(old[j['id']]['emitted']).issubset(new[j['id']]['emitted']), (j['id'], old[j['id']], new[j['id']])
        if 'unrelated' in j['group']:
            assert not new[j['id']]['emitted'], j['id']
        if 'challenge' in j['group'] and j.get('category') in NEGATIVES:
            assert 'target' not in new[j['id']]['emitted'], j['id']
    # Every unchanged fresh input is replayed before spending another stream.
    expectations = []
    for j in read(output/'jobs.json'):
        if not j['baseline_events']:
            continue
        events = [json.loads(s) for s in Path(j['baseline_events']).read_text(encoding='utf-8').splitlines()]
        result = replay(TimelyEvidenceMatcher, read(Path(j['manifest'])), events)
        if 'guard_expected_target_emit' in j:
            assert (j['target'] in result['emitted']) == j['guard_expected_target_emit'], (j['id'], result)
        else:
            assert (j['target'] in result['emitted']) == j['expected_target_emit'], (j['id'], result)
        if j.get('asserted_checkpoint'):
            assert j['asserted_checkpoint'] in result['emitted'], (j['id'], result)
        if j.get('expected_before'):
            assert set(j['expected_before']['emitted']).issubset(result['emitted']), (j['id'], result)
        expectations.append(dict(id=j['id'], outcomes=result))
    write(output/'preflight.json', dict(all_legacy_old_ledgers_reproduced=True,
        no_legacy_emitted_effects_removed=True, fresh_replay_expectations=expectations,
        legacy_changes=[dict(id=j['id'],before=old[j['id']],after=new[j['id']])
            for j in read(output/'legacy-jobs.json') if old[j['id']] != new[j['id']]]))
    print('PREFLIGHT PASS: original ledgers reproduced; legacy emissions preserved; cue targets recovered.', flush=True)


def inventory(output):
    verify(output)
    result = []
    for j in read(output/'jobs.json'):
        with wave.open(j['audio']) as src:
            assert src.getframerate() == 16000 and src.getnchannels() == 1 and src.getsampwidth() == 2
            result.append(dict(id=j['id'],audio=j['audio'],audio_sha256=digest(j['audio']),
                samples=src.getnframes(),audio_seconds=src.getnframes()/16000,spans=[]))
    write(output/'audio-inventory.json', result)
    verify(output, audio=True)
    print('AUDIO INVENTORY', len(result), 'streams;', round(sum(r['audio_seconds'] for r in result),2), 'seconds.', flush=True)


def run(output):
    verify(output, model=True, audio=True); assert read(output/'preflight.json')['no_legacy_emitted_effects_removed']
    infos = {r['id']:r for r in read(output/'audio-inventory.json')}; rows=[]
    (output/'streams').mkdir(exist_ok=False)
    for n,j in enumerate(read(output/'jobs.json'),1):
        verify(output); stem=output/'streams'/j['id']; print('START', n, '/42', j['id'], flush=True)
        cmd=[sys.executable,'-X','utf8','-u','benchmarks/live_tracker_probe.py','--model','parakeet-nemo',
            '--server','127.0.0.1','--port','9097','--matching_mode','split','--no_book_context',
            '--files',j['audio'],'--mute_audio_playback','--checkpoints',j['manifest'],'--transcript_file',str(stem.with_suffix('.srt'))]
        env=dict(os.environ,PYTHONUTF8='1');env.pop('TRACKER_COMPARE_MANIFESTS',None)
        with stem.with_suffix('.log').open('x',encoding='utf-8') as log:
            subprocess.run(cmd,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,
                timeout=math.ceil(infos[j['id']]['audio_seconds']*1.5)+180)
        compatible=dict(j,group=j['category'],source_id=None)
        row=audit(output,compatible,infos[j['id']])
        events=[json.loads(s) for s in stem.with_suffix('.events.jsonl').read_text(encoding='utf-8').splitlines()]
        packets=[e for e in events if e['kind']=='audio']
        assert row['partial_before_eof'],j['id']
        assert packets[-1]['wall']-packets[0]['wall'] >= infos[j['id']]['audio_seconds']-1,j['id']
        if j['baseline_events']:
            signature=lambda path:[json.loads(s)['segments'] for s in Path(path).read_text(encoding='utf-8').splitlines() if json.loads(s)['kind']=='segments']
            row['asr_callbacks_identical']=signature(stem.with_suffix('.events.jsonl'))==signature(j['baseline_events'])
            if j.get('require_identical_asr',True):
                assert row['asr_callbacks_identical'],j['id']
        else:
            row['asr_callbacks_identical']=None
        rows.append(row);write(output/'results.json',dict(cases=rows))
        if 'guard_expected_target_emit' in j:
            row['guard_expected_target_emit']=j['guard_expected_target_emit']
            row['guard_expectation_met']=row['target_emitted']==j['guard_expected_target_emit']
        if j.get('asserted_checkpoint'):
            assert j['asserted_checkpoint'] in row['outcomes']['emitted'], j['id']
        if j.get('expected_before'):
            assert set(j['expected_before']['emitted']).issubset(row['outcomes']['emitted']), j['id']
        print('DONE',n,j['id'],row['outcomes'],flush=True)
    verify(output,model=True,audio=True)
    write(output/'completed.json',dict(fresh_streams=42,all_transport_and_integrity_assertions_pass=True,
        semantic_misses_retained=True,
        asr_and_numeric_thresholds_unchanged=True,all_trials_retained=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=('prepare','preflight','inventory','run','verify'),required=True)
    parser.add_argument('--output',type=Path,default=DEST);args=parser.parse_args();output=args.output.resolve()
    if not output.is_relative_to(ROOT/'output'):
        parser.error('Raw artifacts belong in output/.')
    if args.stage=='verify':
        verify(output,model=True,audio=True);print('Frozen sources, ASR, model, thresholds, manifests and audio verified.',flush=True)
    else:
        globals()[args.stage](output)
