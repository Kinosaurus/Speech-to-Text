"""Read-only diagnosis of saved MPS recognition/progress, with unchanged streams.

The observer returns every production result unchanged and verifies every update
against a separate vanilla tracker. Text probes are diagnostics, not audio trials.
"""
import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
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
FROZEN = ROOT / 'output/mps-frozen-streaming-2026-11-06'
PRIOR = ROOT / 'output/internal-phonetic-regression-2026-11-03'
DEST = ROOT / 'output/mps-progress-investigation-2026-11-06'
# Import the actual frozen implementation, including all matcher bases.
sys.path.insert(0, str(FROZEN / 'source-snapshot'))
from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher
from books_to_life.matching.effect_permission import EffectPermission, ordered_support
from books_to_life.matching.checkpoint_matcher import normalize_text
from benchmarks.prepare_mps_expansion import provider_anchor_evidence
import books_to_life.matching.timely_matcher as implementation


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def verify(output, audio=False):
    p = read(output / 'protocol.json')
    assert digest(Path(__file__)) == p['diagnostic_helper_sha256']
    for name, checksum in p['frozen_sources'].items():
        assert digest(ROOT / name) == checksum, name
        assert digest(FROZEN / 'source-snapshot' / name) == checksum, name
    for name, checksum in p['input_sha256'].items():
        assert digest(ROOT / name) == checksum, name
    for j in read(output / 'jobs.json'):
        assert digest(Path(j['manifest'])) == j['manifest_sha256'], j['id']
        assert digest(Path(j['events'])) == j['events_sha256'], j['id']
        if audio and j.get('audio'):
            assert digest(Path(j['audio'])) == j['audio_sha256'], j['id']
    model = ROOT / p['model']['path']
    assert model.stat().st_size == p['model']['bytes']
    assert model.stat().st_mtime_ns == p['model']['mtime_ns']
    if audio:
        assert digest(model) == p['model']['sha256']
    assert Path(implementation.__file__).resolve().is_relative_to(FROZEN / 'source-snapshot/books_to_life')
    return p


def prepare(output):
    assert not output.exists()
    frozen = read(FROZEN / 'protocol.json')
    for name, sha in frozen['source_sha256'].items():
        assert digest(ROOT / name) == sha, name
    historical = read(PRIOR / 'replay-jobs.json')
    old_outcomes = {r['id']: r['outcomes'] for r in read(PRIOR / 'saved-after.json')['cases']}
    new_outcomes = {r['recording']: r['after'] for r in read(FROZEN / 'results.json')['recordings']}
    originals = {}
    for path in sorted((ROOT / 'output').rglob('downloaded-jobs.json')):
        for j in read(path):
            originals.setdefault(j['id'], j)
    jobs = []
    for j in historical:
        if j['group'] != 'saved_mps':
            continue
        ident = j['id'].removeprefix('reading-')
        original = originals[ident]
        jobs.append(dict(id=ident, group='historical_saved_callbacks', manifest=j['manifest'],
            manifest_sha256=j['manifest_sha256'], events=j['events'], events_sha256=j['events_sha256'],
            expected=old_outcomes[j['id']], audio=original['audio'], audio_sha256=original['audio_sha256'],
            audio_seconds=original['audio_seconds']))
    for j in read(FROZEN / 'downloaded-jobs.json'):
        events = FROZEN / 'streams' / (j['id'] + '.events.jsonl')
        jobs.append(dict(id=j['id'], group='latest_frozen_streams', manifest=j['manifest'],
            manifest_sha256=j['manifest_sha256'], events=str(events), events_sha256=digest(events),
            expected=new_outcomes[j['id']], audio=j['audio'], audio_sha256=j['audio_sha256'],
            audio_seconds=j['audio_seconds']))
    assert len(jobs) == 147 and len({j['id'] for j in jobs}) == 147
    # Outcome-informed diagnostic cases, never a new accuracy/holdout sample.
    reruns = [
        ('3b4c_EN-OL-RC-234_1', 'User-transcribed miss with multiple ASR substitutions'),
        ('3a21c_EN-OL-RC-234_1', 'Other latest miss, uncertain internal nouns'),
        ('3d20g_EN-OL-RC-234_1', 'Latest clean positive comparison'),
        ('3b55f_EN-OL-RC-234_1', 'Latest positive despite an imperfect final ASR tail'),
        ('3b20g_EN-OL-RC-234_1', 'Historical stream ending after the first clause'),
        ('3b24c_EN-OL-RC-234_1', 'Historical incorrect final endpoint'),
        ('3a5b_EN-OL-RC-234_1', 'Historical positive with the same shorter subject wording heard by the user'),
    ]
    output.mkdir(parents=True)
    write(output / 'jobs.json', jobs)
    write(output / 'reruns.json', [dict(next(j for j in jobs if j['id'] == ident), selection_reason=reason)
        for ident, reason in reruns])
    inputs = [FROZEN / 'protocol.json', FROZEN / 'results.json', FROZEN / 'downloaded-jobs.json',
        PRIOR / 'replay-jobs.json', PRIOR / 'saved-after.json',
        ROOT / 'benchmarks/results/mps-listening-review-2026-11-06.json',
        ROOT / 'output/listening-review-2026-11-02/source/data.json',
        output / 'jobs.json', output / 'reruns.json']
    shutil.copyfile(__file__, output / 'diagnostic-helper.py')
    write(output / 'protocol.json', dict(date='2026-11-06', scope=__doc__,
        frozen_sources=frozen['source_sha256'], model=frozen['model'], configuration=frozen['configuration'],
        lexicon=frozen['lexicon'], diagnostic_helper_sha256=digest(__file__),
        input_sha256={p.relative_to(ROOT).as_posix(): digest(p) for p in inputs},
        saved_readings=147, focus_rule='All checkpoints with id lost_sheep in all 147 original MPS readings; no exclusions by outcome.',
        comparison_rule='All 441 checkpoints in these same recordings; observe acquisition, raw candidates, score filtering, selection, confirmation and permission.',
        fresh_diagnostic_streams=7, rerun_selection_informed_by_saved_outcomes=True,
        new_holdout_accuracy_claim=False, no_production_or_manifest_changes=True,
        fresh_inputs='Original full WAVs, unchanged manifests, fixed order, one stream per selected case; no crop, padding, boosting, or resampling.',
        historical_limit='Historical callbacks include earlier streaming implementations. Replaying them with the frozen matcher does not make them current-ASR trials.',
        hypothesis='Distinguish damaged recognition/coverage from score/recovery, confirmation, endpoint policy and genuinely omitted content. Do not assume every non-emission should trigger.'))
    verify(output, audio=True)
    print('FROZEN diagnosis: 147 saved recordings, all lost-sheep cases, 7 unchanged full-audio reruns.', flush=True)


def state(m):
    return dict(position=m.tracked_word_position, index=m.current_index, misses=m._misses,
        confirmations=m.confirmations, pending_scene=m._pending_scene,
        buffer=list(m._buffer), completed=m.completed,
        emitted=sorted(m.triggered_checkpoint_ids), suppressed=sorted(m.suppressed_checkpoint_ids))


class Observed(TimelyEvidenceMatcher):
    """Observe method inputs/outputs; never change production return values."""
    def _alignment_candidates(self, low, high):
        result = super()._alignment_candidates(low, high)
        self.trace['window'] = [low, high]
        self.trace['raw_candidates'] = [asdict(s) for s in result]
        return result

    def _threshold(self, scene, recovering):
        result = super()._threshold(scene, recovering)
        self.trace.setdefault('threshold_calls', []).append(dict(scene=scene,
            recovering=recovering, value=result, phase=self.trace.get('phase', 'candidate_filter')))
        return result

    def _select_candidate(self, candidates):
        self.trace['phase'] = 'selection'
        self.trace['eligible_candidates'] = [asdict(s) for s in candidates]
        result = super()._select_candidate(candidates)
        self.trace['selected_candidate'] = asdict(result) if result else None
        return result

    def _confirm_candidate(self, scene, best):
        self.trace['phase'] = 'confirmation'
        before = self.confirmations
        result = super()._confirm_candidate(scene, best)
        self.trace['confirmation'] = dict(scene=scene, before=before, after=result)
        return result

    def _reject_candidate(self, ambiguous):
        self.trace['rejected'] = dict(ambiguous=ambiguous)
        return super()._reject_candidate(ambiguous)


def contains(words, phrase):
    return any(words[i:i + len(phrase)] == phrase for i in range(len(words) - len(phrase) + 1))


def trace_case(output, job, events_path=None, label='saved'):
    manifest = read(job['manifest'])
    normal, observed = TimelyEvidenceMatcher(manifest), Observed(manifest)
    events = [json.loads(s) for s in Path(events_path or job['events']).read_text(encoding='utf-8').splitlines()]
    rows = []; emitted = []; suppressed = []; skipped = set()
    all_points = [dict(id=cp['id'], raw_crossings=0, eligible_crossings=0, selected_crossings=0,
        max_crossing_confirmations=0, max_exact_endpoint_raw_score=None,
        ever_locally_acquired=False, ever_permission_ordinary=False, ever_permission_with_local_aids=False,
        exact_first_clause_observed=False, first_clause_words=len(normalize_text(re.split(r'[.!?]', cp['checkpoint_text'])[0]).split()))
        for cp in manifest['checkpoints']]
    for n, event in enumerate(e for e in events if e['kind'] == 'segments'):
        segments = event['segments']; text = ' '.join(s['text'] for s in segments)
        observed.trace = dict(callback=n, audio_end=segments[-1]['end'], before=state(observed))
        wanted = normal.process(text, segments)
        update = observed.process(text, segments)
        assert asdict(wanted) == asdict(update), (job['id'], n, 'observer altered an update')
        assert state(normal) == state(observed), (job['id'], n, 'observer altered state')
        trace = observed.trace
        trace.update(after=state(observed), update=asdict(update))
        raw = trace.get('raw_candidates', [])
        eligible = trace.get('eligible_candidates', [])
        selected = trace.get('selected_candidate')
        permission = {}
        for i, (cp, (start, end), point) in enumerate(zip(manifest['checkpoints'], observed.checkpoint_ranges, all_points)):
            before = trace['before']
            acquired = before['index'] == i and before['position'] > 0 and before['position'] >= start
            point['ever_locally_acquired'] |= acquired
            point['raw_crossings'] += any(observed._scene(s['end']) == i for s in raw)
            point['eligible_crossings'] += any(observed._scene(s['end']) == i for s in eligible)
            chosen = selected is not None and observed._scene(selected['end']) == i
            point['selected_crossings'] += chosen
            if chosen and trace.get('confirmation'):
                point['max_crossing_confirmations'] = max(point['max_crossing_confirmations'], trace['confirmation']['after'])
            scores = [s['score'] for s in raw if s['end'] == end]
            if scores:
                point['max_exact_endpoint_raw_score'] = max(scores + [point['max_exact_endpoint_raw_score'] or 0])
            guard = observed._effect_permissions[cp['id']]
            plain = guard.permits(observed._buffer)[0]
            aided = guard.permits(observed._buffer, allow_phonetic_endpoint=True,
                allow_word_boundaries=True, allow_phonetic_internal=True)[0]
            point['ever_permission_ordinary'] |= plain
            point['ever_permission_with_local_aids'] |= aided
            first = normalize_text(re.split(r'[.!?]', cp['checkpoint_text'])[0]).split()
            point['exact_first_clause_observed'] |= contains(observed._buffer, first)
            permission[cp['id']] = dict(ordinary=plain, with_local_aids=aided, acquired=acquired,
                ordinary_ordered_support=len(ordered_support(guard.anchor, observed._buffer[-(len(guard.anchor)+8):])),
                required_support=math.ceil(len(guard.anchor) * guard.coverage), reference_start=start, reference_end=end)
        trace['permission_diagnostics'] = permission
        rows.append(trace)
        if update.triggered:
            emitted.append(update.checkpoint_id)
        if update.effect_suppressed:
            suppressed.append(update.checkpoint_id)
        suppressed.extend(update.additional_suppressed_checkpoint_ids)
        skipped.update(update.skipped_checkpoint_ids)
    ledger = dict(emitted=emitted, suppressed=suppressed, skipped=sorted(skipped),
        unreached=sorted({c['id'] for c in manifest['checkpoints']} - set(emitted) - set(suppressed) - skipped))
    if label == 'saved':
        assert ledger == job['expected'], (job['id'], ledger, job['expected'])
    assert len(emitted) == len(set(emitted)) and not (set(emitted) & set(suppressed))
    assert observed._pending_effect is None
    for cp, point in zip(manifest['checkpoints'], all_points):
        point['outcome'] = next(k for k, ids in ledger.items() if cp['id'] in ids)
        if point['outcome'] in ('emitted', 'suppressed', 'skipped'):
            point['observed_stage'] = point['outcome']
        elif not point['raw_crossings']:
            point['observed_stage'] = 'no_raw_crossing_alignment'
        elif not point['eligible_crossings']:
            point['observed_stage'] = 'all_crossing_alignments_filtered'
        elif not point['selected_crossings']:
            point['observed_stage'] = 'crossing_alignment_not_selected'
        else:
            point['observed_stage'] = 'crossing_selected_without_confirmed_progress'
    path = output / 'traces' / (label + '-' + job['id'] + '.json')
    path.parent.mkdir(exist_ok=True)
    write(path, rows)
    callbacks = [e for e in events if e['kind'] == 'segments']
    return dict(id=job['id'], group=job['group'], label=label, outcomes=ledger, checkpoints=all_points,
        callbacks=len(rows), every_observer_update_identical=True, final_position=observed.tracked_word_position,
        final_asr=' '.join(s['text'] for s in callbacks[-1]['segments']),
        final_buffer=observed._buffer, trace=str(path.relative_to(ROOT)),
        audio_seconds=job['audio_seconds'], audio_sha256=job['audio_sha256'])


def replay_saved(output):
    verify(output)
    rows = []
    for n, job in enumerate(read(output / 'jobs.json'), 1):
        rows.append(trace_case(output, job))
        if n % 10 == 0:
            write(output / 'saved-results.json', dict(cases=rows))
            print('TRACED', n, '/147; every observed update agrees with the vanilla tracker.', flush=True)
    write(output / 'saved-results.json', dict(cases=rows))
    verify(output)
    print('SAVED COMPLETE 147 exact-ledger replays.', flush=True)


def fresh(output):
    verify(output, audio=True)
    (output / 'streams').mkdir(exist_ok=False)
    rows = []
    for n, job in enumerate(read(output / 'reruns.json'), 1):
        verify(output)
        stem = output / 'streams' / job['id']
        print('START', n, '/7', job['id'], flush=True)
        cmd = [str(ROOT / '.venv/Scripts/python.exe'), '-X', 'utf8', '-u', 'benchmarks/live_tracker_probe.py',
            '--model', 'parakeet-nemo', '--server', '127.0.0.1', '--port', '9097',
            '--matching_mode', 'split', '--no_book_context', '--files', job['audio'],
            '--mute_audio_playback', '--checkpoints', job['manifest'], '--transcript_file', str(stem.with_suffix('.srt'))]
        env = dict(os.environ, PYTHONUTF8='1'); env.pop('TRACKER_COMPARE_MANIFESTS', None)
        with stem.with_suffix('.log').open('x', encoding='utf-8') as log:
            subprocess.run(cmd, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                check=True, timeout=math.ceil(job['audio_seconds'] * 1.5) + 180)
        events_path = stem.with_suffix('.events.jsonl')
        events = [json.loads(s) for s in events_path.read_text(encoding='utf-8').splitlines()]
        packets = [e for e in events if e['kind'] == 'audio']; samples = 0
        for p in packets:
            assert p['sample_start'] == samples; samples += p['sample_count']
        with wave.open(job['audio']) as source:
            assert samples == source.getnframes() and source.getframerate() == 16000
        callbacks = [e for e in events if e['kind'] == 'segments']
        assert callbacks[-1]['segments'][-1]['completed']
        assert abs(callbacks[-1]['segments'][-1]['end'] - job['audio_seconds']) < .001
        assert any(e['wall'] < packets[-1]['wall'] and not e['segments'][-1]['completed'] for e in callbacks)
        assert any(e['kind'] == 'status' and e.get('message') == 'STREAM_DONE' for e in events)
        assert not any(e['kind'] == 'status' and e.get('status') == 'ERROR' for e in events)
        assert not any(e['kind'] == 'book_context_sent' for e in events)
        assert packets[-1]['wall'] - packets[0]['wall'] >= job['audio_seconds'] - 1
        row = trace_case(output, job, events_path, 'fresh')
        observed = [e for e in events if e['kind'] == 'tracker' and e['mode'] == 'timely']
        assert [e['scene'] for e in observed if e['triggered']] == row['outcomes']['emitted']
        assert [e['scene'] for e in observed if e.get('suppressed')] == row['outcomes']['suppressed']
        log = stem.with_suffix('.log').read_text(encoding='utf-8')
        assert re.findall(r'^\[TRIGGER\] (\S+):', log, re.M) == row['outcomes']['emitted']
        assert re.findall(r'^\[SUPPRESSED\] (\S+):', log, re.M) == row['outcomes']['suppressed']
        previous = [json.loads(s) for s in Path(job['events']).read_text(encoding='utf-8').splitlines()]
        row['asr_callback_sequence_identical'] = [e['segments'] for e in callbacks] == [e['segments'] for e in previous if e['kind'] == 'segments']
        row['previous_outcomes'] = job['expected']
        row['all_streaming_audits_pass'] = True
        rows.append(row); write(output / 'fresh-results.json', dict(cases=rows))
        print('DONE', n, job['id'], row['outcomes'], 'same ASR:', row['asr_callback_sequence_identical'], flush=True)
    verify(output, audio=True)
    write(output / 'completed.json', dict(fresh_streams=7, unchanged_original_inputs=True,
        no_asr_matcher_or_manifest_changes=True, all_audits_pass=True, all_trials_retained=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=('prepare', 'replay', 'fresh', 'verify'), required=True)
    parser.add_argument('--output', type=Path, default=DEST)
    args = parser.parse_args(); output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'output'):
        parser.error('Raw diagnostics belong in output/.')
    if args.stage == 'verify':
        verify(output, audio=True); print('Diagnostic inputs and frozen runtime verified.', flush=True)
    else:
        {'prepare': prepare, 'replay': replay_saved, 'fresh': fresh}[args.stage](output)
