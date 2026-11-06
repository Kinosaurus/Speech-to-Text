"""Preselect unseen MPS speakers, freeze the matcher, and run untuned app streams.

Raw provider audio, passages, transcripts, logs and review clips remain under
ignored output/. A completed batch is never resampled by recognition outcome.
"""
import argparse
from collections import defaultdict
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path, PurePosixPath
import random
import re
import subprocess
import sys
import urllib.request
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks.import_mps_samples import ANCHORS as GRADE3
from benchmarks.prepare_mps_expansion import ANCHORS as EXPANSION, provider_anchor_evidence
from books_to_life.matching.checkpoint_matcher import normalize_text
from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher
import books_to_life.matching.effect_permission as permission_module
import cmudict

REVISION = '6b4a075b9f7db047f70e3c6abef8a843ba369594'
METADATA_HASH = 'd43d1c9b2cb1f2fd6177eecea4ff501595413a04ddb2050c037d87e90883b6b0'
SEED = 2026110203
DEFAULT_OUTPUT = ROOT / 'output/mps-heldout-2026-11-02'
DEFAULT_METADATA = ROOT / 'output/listening-review-2026-11-02/source/data.json'
DEFAULT_BASELINE = ROOT / 'output/listening-review-2026-11-02/regression/baseline/source-snapshot'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def digest(path):
    checksum = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            checksum.update(block)
    return checksum.hexdigest()


def source_files():
    return sorted(set((ROOT / 'books_to_life').rglob('*.py')) | {
        Path(__file__).resolve(), ROOT / 'benchmarks/live_tracker_probe.py',
        ROOT / 'benchmarks/observer_manifests.py', ROOT / 'benchmarks/import_mps_samples.py',
        ROOT / 'benchmarks/prepare_mps_expansion.py', ROOT / 'benchmarks/pilot_effect_policy.json',
        *list((ROOT / 'requirements').glob('*.txt'))})


def exclusions():
    # Bulk metadata lists everyone, so it is never evidence of prior use.
    paths = list((ROOT / 'benchmarks/results').glob('*.json'))
    paths += [p for p in (ROOT / 'output').rglob('*.json')
              if p.name != 'data.json' and 'source-snapshot' not in p.parts]
    used, evidence = set(), {}
    pattern = r'\b([345][a-z]\d+[a-z])_EN-OL-RC-\d+_[12]\b'
    for path in paths:
        found = set(re.findall(pattern, path.read_text(encoding='utf-8')))
        if found:
            used.update(found)
            evidence[path.relative_to(ROOT).as_posix()] = sorted(found)
    return used, evidence


def prepare(output, metadata, baseline):
    if digest(metadata) != METADATA_HASH:
        raise ValueError('Metadata does not match the fixed provider revision.')
    rows = read(metadata)
    excluded, evidence = exclusions()
    groups = defaultdict(list)
    for row in rows:
        groups[row['metaData']['speakerID']].append(row)
    rng = random.Random(SEED)
    selected = []
    strata = []
    for grade in ('3', '4', '5'):
        for gender in ('Female', 'Male'):
            pool = sorted(s for s, pair in groups.items() if s not in excluded
                and len(pair) == 2 and {r['metaData']['paragraphID'] for r in pair} == {'1', '2'}
                and all(r['metaData']['grade'] == grade and r['metaData']['gender'] == gender for r in pair))
            speakers = rng.sample(pool, 2)
            strata.append(dict(grade=grade, gender=gender, eligible_speakers=len(pool), selected=speakers))
            for speaker in speakers:
                selected.extend(sorted(groups[speaker], key=lambda row: row['audioID']))
    rng.shuffle(selected)
    speakers = {r['metaData']['speakerID'] for r in selected}
    assert len(selected) == 24 and len(speakers) == 12 and speakers.isdisjoint(excluded)
    output.mkdir(parents=True, exist_ok=False)
    snapshot = output / 'source-snapshot'
    hashes = {}
    for path in source_files():
        name = path.relative_to(ROOT).as_posix()
        target = snapshot / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
        hashes[name] = digest(path)
    baseline_hashes = {}
    for name in ('effect_permission.py', 'timely_matcher.py'):
        path = baseline / 'books_to_life/matching' / name
        target = output / 'baseline-snapshot' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
        baseline_hashes[name] = digest(path)
    # All other matcher parents must be identical for the paired comparison.
    for path in (baseline / 'books_to_life/matching').glob('*.py'):
        if path.name not in baseline_hashes:
            assert path.read_bytes() == (ROOT / 'books_to_life/matching' / path.name).read_bytes()
    model = ROOT / 'model-cache/parakeet-nemo/parakeet-unified-en-0.6b.nemo'
    model_stat = model.stat()
    protocol = dict(date='2026-11-02', seed=SEED, provider_revision=REVISION,
        metadata_sha256=METADATA_HASH, excluded_speakers=sorted(excluded), exclusion_evidence=evidence,
        speakers=sorted(speakers), strata=strata, ordered_recordings=[r['audioID'] for r in selected],
        selection_rule='Two paired-paragraph speakers per grade/gender stratum, sorted pools and fixed RNG seed; shuffle all 24 recordings once. No selection by duration, transcript quality, miscues, audio or ASR outcome.',
        configuration=dict(model='parakeet-nemo', matching='split', hints=False, hotwords=None,
            chunk_ms=560, right_ms=560, left_ms=5600, packet_samples=4096,
            threshold=82, stability=2, min_coverage=.8, device='RTX 4060 Laptop GPU / WSL NeMo'),
        runs_per_recording=1, timeout_rule='ceil(audio_seconds * 1.5) + 180 seconds',
        warmup='No separate inference warmup; first reading includes first-inference effects.',
        no_matcher_or_hint_tuning=True, source_sha256=hashes, baseline_sha256=baseline_hashes,
        lexicon=dict(package='cmudict', version=importlib.metadata.version('cmudict'),
            data_sha256=hashlib.sha256(cmudict.dict_string().encode('utf-8')).hexdigest()),
        model=dict(path=model.relative_to(ROOT).as_posix(), bytes=model_stat.st_size,
            mtime_ns=model_stat.st_mtime_ns, sha256=digest(model)),
        note='Speaker-disjoint test on familiar six MPS paragraph texts; not held-out books, Singapore voices, or human-verified timing.')
    # Persist selection and source hashes before inspecting labels or audio.
    write(output / 'protocol.json', protocol)
    write(output / 'selected.json', selected)
    jobs = []
    policy = read(ROOT / 'benchmarks/pilot_effect_policy.json')
    for row in selected:
        ident, meta = row['audioID'], row['metaData']
        relative = PurePosixPath(row['audioPath'])
        assert not relative.is_absolute() and '..' not in relative.parts and relative.suffix == '.wav'
        folder = output / 'inputs' / ident
        folder.mkdir(parents=True)
        grade, paragraph = meta['grade'], meta['paragraphID']
        anchors = GRADE3[paragraph] if grade == '3' else EXPANSION[grade, paragraph]
        text = row['promptText']
        words = normalize_text(text).split()
        book = 'heldout-' + ident
        checkpoints = []
        for position, (name, anchor_text) in enumerate(anchors, 1):
            anchor = normalize_text(anchor_text).split()
            hits = [i for i in range(len(words)-len(anchor)+1) if words[i:i+len(anchor)] == anchor]
            assert len(hits) == 1
            cp = dict(id=name, book_id=book, checkpoint_position=position, page=1,
                checkpoint_text=anchor_text, word_start=hits[0], word_end=hits[0]+len(anchor),
                effect_policy=policy['default_effect_policy'], effect=dict(effect_id=name))
            for rule in policy['rules']:
                if normalize_text(rule['checkpoint_text']) == normalize_text(anchor_text):
                    for field in ('effect_cue', 'required_words'):
                        if field in rule:
                            cp[field] = rule[field]
            checkpoints.append(cp)
        manifest = dict(book_id=book, title=book, threshold=82, stability=2, min_coverage=.8,
            pages=[dict(page=1, text=text)], checkpoints=checkpoints)
        TimelyEvidenceMatcher(manifest)
        path = folder / 'checkpoints.json'
        write(path, manifest)
        jobs.append(dict(id=ident, speaker=meta['speakerID'], grade=grade, gender=meta['gender'],
            audio_path=row['audioPath'], audio=str(folder / 'audio.wav'), manifest=str(path),
            manifest_sha256=digest(path)))
    write(output / 'jobs.json', jobs)
    print(json.dumps(dict(recordings=24, speakers=12, checkpoints=72, excluded_speakers=sorted(excluded),
        selected_speakers=sorted(speakers), frozen_before_download=True), indent=2), flush=True)


def check_frozen(output, model_hash=False):
    protocol = read(output / 'protocol.json')
    for name, checksum in protocol['source_sha256'].items():
        if digest(ROOT / name) != checksum:
            raise RuntimeError(f'Frozen source changed: {name}')
    for name, checksum in protocol['baseline_sha256'].items():
        assert digest(output/'baseline-snapshot'/name) == checksum
    for job in read(output / 'jobs.json'):
        assert digest(Path(job['manifest'])) == job['manifest_sha256']
    assert importlib.metadata.version('cmudict') == protocol['lexicon']['version']
    assert hashlib.sha256(cmudict.dict_string().encode('utf-8')).hexdigest() == protocol['lexicon']['data_sha256']
    model = ROOT / protocol['model']['path']
    stat = model.stat()
    assert stat.st_size == protocol['model']['bytes'] and stat.st_mtime_ns == protocol['model']['mtime_ns']
    if model_hash:
        assert digest(model) == protocol['model']['sha256']
    return protocol


def download(output):
    protocol = check_frozen(output)
    jobs = read(output / 'jobs.json')
    for job in jobs:
        path = Path(job['audio'])
        if path.exists():
            raise FileExistsError('Refusing to replace a selected source recording.')
        url = f'https://raw.githubusercontent.com/DAP-Lab/mps_dataset/{protocol["provider_revision"]}/{job["audio_path"]}'
        request = urllib.request.Request(url, headers={'User-Agent': 'BooksToLife-frozen-heldout-evaluation'})
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read(20*1024*1024+1)
        if len(data) > 20*1024*1024:
            raise ValueError('Unexpectedly large provider WAV')
        with path.open('xb') as handle:
            handle.write(data)
        with wave.open(str(path)) as wav:
            assert wav.getframerate() == 16000 and wav.getnchannels() == 1 and wav.getsampwidth() == 2
            job['audio_seconds'] = wav.getnframes()/16000
        job['audio_sha256'] = digest(path)
        print('DOWNLOADED', job['id'], round(job['audio_seconds'], 2), flush=True)
    write(output / 'downloaded-jobs.json', jobs)
    check_frozen(output)
    print('Downloaded', len(jobs), 'fixed recordings;', round(sum(j['audio_seconds'] for j in jobs)/60, 2), 'minutes.', flush=True)


def old_tracker(output):
    def load(name, filename):
        spec = importlib.util.spec_from_file_location(name, output / 'baseline-snapshot' / filename)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    effect = load('_heldout_old_permission', 'effect_permission.py')
    if (output / 'baseline-snapshot' / 'phonetic_endpoint.py').exists():
        # A phonetic-rule comparison must not accidentally use the new helper
        # in its old permission module. Legacy two-file snapshots stay valid.
        effect.phonetic_endpoint_match = load('_heldout_old_phonetic', 'phonetic_endpoint.py').phonetic_endpoint_match
    timely = load('_heldout_old_timely', 'timely_matcher.py')
    timely.EffectPermission = effect.EffectPermission
    return timely.TimelyEvidenceMatcher


def audit_and_score(output, job, Old):
    stem = output / 'streams' / job['id']
    events = [json.loads(s) for s in stem.with_suffix('.events.jsonl').read_text(encoding='utf-8').splitlines()]
    packets = [e for e in events if e['kind']=='audio']
    segments = [e for e in events if e['kind']=='segments']
    count = 0
    for packet in packets:
        assert packet['sample_start'] == count
        count += packet['sample_count']
    with wave.open(job['audio']) as wav:
        assert count == wav.getnframes() and wav.getframerate() == 16000
    assert segments and segments[0]['wall'] < packets[-1]['wall']
    assert segments[-1]['segments'][-1]['completed']
    assert abs(segments[-1]['segments'][-1]['end']-count/16000) < .001
    assert any(e['kind']=='status' and e.get('message')=='STREAM_DONE' for e in events)
    assert not any(e['kind']=='status' and e.get('status')=='ERROR' for e in events)
    manifest = read(Path(job['manifest']))
    calls = []
    original = permission_module.phonetic_endpoint_match
    def trace(reference, heard):
        matched = original(reference, heard)
        calls.append(dict(reference=reference, heard=heard, matched=matched))
        return matched
    permission_module.phonetic_endpoint_match = trace
    ledgers, decisions = {}, {}
    try:
        for label, Tracker in [('before', Old), ('after', TimelyEvidenceMatcher)]:
            tracker = Tracker(manifest)
            rows, skipped = [], set()
            for event in segments:
                seg = event['segments']; start = len(calls)
                update = tracker.process(' '.join(s['text'] for s in seg), seg)
                skipped.update(update.skipped_checkpoint_ids)
                for ident in getattr(update, 'additional_suppressed_checkpoint_ids', ()):
                    rows.append(dict(checkpoint=ident, emitted=False, suppressed=True,
                        audio_end=seg[-1]['end'], callback_seconds=event['wall']-packets[0]['wall'],
                        buffer=list(tracker._buffer), phonetic_calls=[]))
                if update.triggered or update.effect_suppressed:
                    rows.append(dict(checkpoint=update.checkpoint_id, emitted=update.triggered,
                        suppressed=update.effect_suppressed, audio_end=seg[-1]['end'],
                        callback_seconds=event['wall']-packets[0]['wall'], buffer=list(tracker._buffer),
                        phonetic_calls=calls[start:]))
            emitted = [r['checkpoint'] for r in rows if r['emitted']]
            suppressed = [r['checkpoint'] for r in rows if r['suppressed']]
            assert len(set(emitted)) == len(emitted) and len(set(suppressed)) == len(suppressed)
            ledgers[label] = dict(emitted=emitted, suppressed=suppressed, skipped=sorted(skipped),
                unreached=sorted({c['id'] for c in manifest['checkpoints']}-set(emitted)-set(suppressed)-skipped))
            decisions[label] = rows
    finally:
        permission_module.phonetic_endpoint_match = original
    observed = [e for e in events if e['kind']=='tracker' and e['mode']=='timely']
    assert [e['scene'] for e in observed if e['triggered']] == ledgers['after']['emitted']
    assert [e['scene'] for e in observed if e.get('suppressed')] == ledgers['after']['suppressed']
    log = stem.with_suffix('.log').read_text(encoding='utf-8')
    assert re.findall(r'^\[TRIGGER\] (\S+):', log, re.M) == ledgers['after']['emitted']
    assert re.findall(r'^\[SUPPRESSED\] (\S+):', log, re.M) == ledgers['after']['suppressed']
    source = next(r for r in read(output / 'selected.json') if r['audioID']==job['id'])
    points = []
    for cp in manifest['checkpoints']:
        evidence = provider_anchor_evidence(source, cp['word_start'], cp['word_end'])
        flags = []
        words = evidence.get('words', [])
        endpoint_deleted = bool(words and words[-1]['label'].lower()=='d')
        required_deleted = any(w['prompt'] in cp.get('required_words', []) and w['label'].lower()=='d' for w in words)
        emitted = cp['id'] in ledgers['after']['emitted']
        if emitted and (endpoint_deleted or required_deleted): flags.append('Emitted despite provider-deleted endpoint/essential word; listening needed')
        if not emitted and evidence.get('substitutions')==0 and evidence.get('deletions')==0: flags.append('No effect on provider-correct anchor; listening needed')
        if evidence.get('substitutions') or evidence.get('deletions'): flags.append('Provider reports anchor substitutions/deletions; pronunciation acceptance unresolved')
        points.append(dict(id=cp['id'], emitted=emitted, suppressed=cp['id'] in ledgers['after']['suppressed'],
            provider_evidence=evidence, provider_endpoint_deleted=endpoint_deleted,
            provider_required_word_deleted=required_deleted, review_flags=flags, human_verified=False))
    write(stem.with_suffix('.decisions.json'), decisions)
    return dict(recording=job['id'], speaker=job['speaker'], grade=job['grade'], gender=job['gender'],
        audio_seconds=job['audio_seconds'], audio_sha256=job['audio_sha256'], manifest_sha256=job['manifest_sha256'],
        configured=3, before=ledgers['before'], after=ledgers['after'], checkpoints=points,
        added_emissions=sorted(set(ledgers['after']['emitted'])-set(ledgers['before']['emitted'])),
        removed_emissions=sorted(set(ledgers['before']['emitted'])-set(ledgers['after']['emitted'])),
        phonetic_calls=calls, samples_delivered=count, partial_before_eof=True, stream_done=True,
        delivery_audit_pass=True, app_observer_agreement=True)


def run(output):
    protocol = check_frozen(output, model_hash=True)
    jobs = read(output / 'downloaded-jobs.json')
    assert [j['id'] for j in jobs] == protocol['ordered_recordings']
    streams = output / 'streams'
    streams.mkdir(exist_ok=False)
    Old = old_tracker(output)
    results = []
    for index, job in enumerate(jobs, 1):
        check_frozen(output)
        assert digest(Path(job['audio'])) == job['audio_sha256']
        stem = streams / job['id']
        command = [sys.executable, '-X', 'utf8', '-u', 'benchmarks/live_tracker_probe.py',
            '--model', 'parakeet-nemo', '--port', '9097', '--server', '127.0.0.1',
            '--matching_mode', 'split', '--no_book_context', '--files', job['audio'],
            '--mute_audio_playback', '--checkpoints', job['manifest'], '--transcript_file', str(stem.with_suffix('.srt'))]
        print('START', index, '/', len(jobs), job['id'], flush=True)
        with stem.with_suffix('.log').open('w', encoding='utf-8') as log:
            subprocess.run(command, cwd=ROOT, env=dict(os.environ, PYTHONUTF8='1'),
                stdout=log, stderr=subprocess.STDOUT, timeout=math.ceil(job['audio_seconds']*1.5)+180, check=True)
        check_frozen(output)
        result = audit_and_score(output, job, Old)
        results.append(result)
        write(output / 'results.json', dict(recordings=results))
        print('DONE', index, 'before/after', len(result['before']['emitted']), len(result['after']['emitted']),
            'added', result['added_emissions'], 'removed', result['removed_emissions'], flush=True)
    check_frozen(output, model_hash=True)
    write(output / 'completed.json', dict(streams=24, speakers=12, configured_checkpoints=72,
        source_unchanged=True, model_unchanged=True, manifests_unchanged=True, all_selected_trials_retained=True))
    print('COMPLETE all 24 selected streams; matcher unchanged.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=('prepare', 'download', 'run'), required=True)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--metadata', type=Path, default=DEFAULT_METADATA)
    parser.add_argument('--baseline-snapshot', type=Path, default=DEFAULT_BASELINE)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'output'):
        parser.error('Raw results must remain under ignored output/.')
    if args.stage == 'prepare': prepare(output, args.metadata.resolve(), args.baseline_snapshot.resolve())
    elif args.stage == 'download': download(output)
    else: run(output)


if __name__ == '__main__':
    main()
