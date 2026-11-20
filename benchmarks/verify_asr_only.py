"""Audit completed ASR-only trials against frozen inputs and raw delivery logs."""
import argparse
import json
from pathlib import Path
import wave

from benchmarks.asr_only import PROTOCOL, atomic_json, sha256


def verify_trial(output, profile, case, dataset):
    path = output / f'{profile}--{case["id"]}.json'
    result = json.loads(path.read_text(encoding='utf-8'))
    if result.get('status') != 'ok':
        raise ValueError('Trial did not complete: ' + str(result.get('error')))
    if result.get('protocol') != PROTOCOL or result.get('profile') != profile or result.get('case') != case['id']:
        raise ValueError('Trial identity/protocol differs.')
    if result.get('tracker') is not False or result.get('hints') is not False or not result.get('no_tracker_modules_imported'):
        raise ValueError('Tracker/hint isolation failed.')
    if result.get('audio_sha256') != case['audio_sha256'] or sha256(case['audio']) != case['audio_sha256']:
        raise ValueError('Audio hash differs.')
    if sha256(case['reference_path']) != case['reference_sha256']:
        raise ValueError('Reference file hash differs.')
    if result.get('packet_samples') != dataset['packet_samples'] or result.get('tail_seconds') != dataset['tail_seconds']:
        raise ValueError('Delivery configuration differs.')
    with wave.open(case['audio']) as wav:
        expected = wav.getnframes() + round(dataset['tail_seconds'] * 16000)
    events = [json.loads(line) for line in path.with_suffix('.events.jsonl').read_text(encoding='utf-8').splitlines()]
    packets = [e for e in events if e['kind'] == 'audio']
    cursor = 0
    max_lag = 0
    for packet in packets:
        count = packet['sample_count']
        if packet['sample_start'] != cursor or not 0 < count <= dataset['packet_samples']:
            raise ValueError('Audio samples skipped, duplicated or reordered.')
        cursor += count
        if packet['wall_seconds'] < cursor / 16000 - .002:
            raise ValueError('Input was accelerated ahead of its 1x availability time.')
        max_lag = max(max_lag, packet['feed_lateness_seconds'])
    if cursor != expected or result['delivery']['samples_sent'] != expected:
        raise ValueError('Incomplete audio delivery.')
    eof = [e for e in events if e['kind'] == 'end_of_audio']
    if len(eof) != 1 or eof[0]['samples'] != expected:
        raise ValueError('Missing or inconsistent EOF.')
    transcripts = [e for e in events if e['kind'] == 'transcript']
    if not transcripts or not transcripts[-1].get('final'):
        raise ValueError('Missing final collected transcript.')
    if transcripts[-1]['text'] != result['metrics']['final_text']:
        raise ValueError('Scored transcript differs from raw final snapshot.')
    if any(e.get('discarded_unprocessed_seconds', 0) > .001 for e in events if e['kind'] == 'decoder_buffer_trim'):
        raise ValueError('Recognizer dropped unprocessed audio.')
    if case['reference_kind'] != 'verified_spoken' and result['metrics']['spoken_wer'] is not None:
        raise ValueError('Unverified text was scored as verified spoken WER.')
    queued = {}
    if result.get('audio_delivery_mode') == 'queued':
        queued = verify_queue(events, expected, complete=True)
        for key in ('samples_captured', 'max_capture_lateness_seconds', 'max_queue_wait_seconds',
                    'max_queued_audio_seconds'):
            if result['delivery'].get(key) != queued[key]:
                raise ValueError('Queue delivery summary differs from the packet log: ' + key)
    return {'profile': profile, 'case': case['id'], 'samples': expected,
            'text_updates': len(transcripts), 'max_feed_lateness_seconds': max_lag,
            'no_tracker': True, 'same_audio': True, 'complete_delivery': True, **queued}


def verify_queue(events, expected, *, complete):
    captured = submitted = 0
    capture_eof = submission_eof = False
    pending = {}
    max_capture_lag = max_backlog = max_wait = 0
    for event in events:
        kind = event['kind']
        if kind == 'capture':
            offset, count = event['sample_start'], event['sample_count']
            if capture_eof or offset != captured or count <= 0 or captured + count > expected:
                raise ValueError('Capture skipped, duplicated or reordered audio.')
            captured += count
            when = event['wall_seconds']
            if when < captured / 16000 - .002:
                raise ValueError('Capture ran ahead of its real-time clock.')
            if event['pending_audio_seconds'] != (captured - submitted) / 16000:
                raise ValueError('Incorrect pending audio count.')
            pending[offset] = (count, when)
            max_capture_lag = max(max_capture_lag, event['capture_lateness_seconds'])
            max_backlog = max(max_backlog, event['pending_audio_seconds'])
        elif kind == 'audio':
            offset, count = event['sample_start'], event['sample_count']
            original = pending.pop(offset, None)
            if submission_eof or offset != submitted or original is None or original[0] != count:
                raise ValueError('Recognition received a missing, duplicated or out-of-order packet.')
            if event['queue_wait_seconds'] < 0 or event['wall_seconds'] < original[1]:
                raise ValueError('Recognition received a packet before capture.')
            submitted += count
            max_wait = max(max_wait, event['queue_wait_seconds'])
        elif kind == 'end_of_capture':
            if capture_eof or captured != expected or event['samples'] != captured:
                raise ValueError('Capture ended with inconsistent sample count.')
            capture_eof = True
        elif kind == 'end_of_audio':
            if submission_eof or not capture_eof or pending or submitted != expected or event['samples'] != submitted:
                raise ValueError('Recognition finalized before the capture queue drained.')
            submission_eof = True
    if complete and not submission_eof:
        raise ValueError('Incomplete queued audio delivery.')
    return {'samples_captured': captured, 'samples_submitted': submitted,
            'capture_complete': capture_eof, 'submission_complete': submission_eof,
            'max_capture_lateness_seconds': max_capture_lag, 'max_queued_audio_seconds': max_backlog,
            'max_queue_wait_seconds': max_wait}


def verify_recorded_failure(output, profile, case):
    path = output / f'{profile}--{case["id"]}.json'
    result = json.loads(path.read_text(encoding='utf-8'))
    # A killed/timed-out worker cannot write its final metadata. The frozen
    # parent's failure record and nonempty raw events retain that distinction.
    error = result.get('error', '')
    if set(result) == {'status', 'error'} and result.get('status') == 'failed' and (
            error == 'Worker exceeded trial timeout; see log.' or error.startswith('Worker exit ')):
        if sha256(case['audio']) != case['audio_sha256']:
            raise ValueError('Parent-recorded failure audio hash differs.')
        if not path.with_suffix('.log').is_file():
            raise ValueError('Missing parent-recorded failure log.')
        events = [json.loads(line) for line in path.with_suffix('.events.jsonl').read_text(encoding='utf-8').splitlines()]
        if not any(e.get('kind') == 'audio' for e in events):
            raise ValueError('Parent-recorded failure has no input-delivery evidence.')
        return {'profile': profile, 'case': case['id'], 'error': error,
                'worker_shutdown_unavailable': True,
                'isolation_evidence': 'frozen source import guard; final worker assertion unavailable'}
    if (result.get('status') != 'failed' or not result.get('error')
            or result.get('protocol') != PROTOCOL or result.get('profile') != profile
            or result.get('case') != case['id'] or result.get('audio_sha256') != case['audio_sha256']
            or result.get('tracker') is not False or result.get('hints') is not False
            or not result.get('no_tracker_modules_imported')):
        raise ValueError('Failure is missing its identity, reason or isolation evidence.')
    if sha256(case['audio']) != case['audio_sha256']:
        raise ValueError('Failure audio hash differs.')
    for suffix in ('.log', '.events.jsonl'):
        if not path.with_suffix(suffix).is_file():
            raise ValueError('Missing retained failure artifact: ' + suffix)
    return {'profile': profile, 'case': case['id'], 'error': result['error']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    dataset = json.loads((output / 'dataset.json').read_text(encoding='utf-8'))
    config = json.loads((output / 'run.json').read_text(encoding='utf-8'))
    root = Path(__file__).resolve().parents[1]
    for name, digest in config['source_sha256'].items():
        snapshot = output / 'source' / name
        source = snapshot if snapshot.is_file() else root / name
        if sha256(source) != digest:
            raise ValueError('Benchmark source differs from the frozen run: ' + name)
    results, recorded_failures, failures = [], [], []
    for profile in config['profiles']:
        for case in dataset['cases']:
            try:
                path = output / f'{profile}--{case["id"]}.json'
                trial = json.loads(path.read_text(encoding='utf-8'))
                queued = config.get('delivery') == 'queued'
                if trial.get('status') == 'failed':
                    failure = verify_recorded_failure(output, profile, case)
                    if queued:
                        with wave.open(case['audio']) as source:
                            expected = source.getnframes() + round(dataset['tail_seconds'] * 16000)
                        events = [json.loads(line) for line in path.with_suffix('.events.jsonl').read_text(encoding='utf-8').splitlines()]
                        failure.update(verify_queue(events, expected, complete=False))
                    recorded_failures.append(failure)
                else:
                    if queued and trial.get('audio_delivery_mode') != 'queued':
                        raise ValueError('Queued run is missing its delivery mode.')
                    results.append(verify_trial(output, profile, case, dataset))
            except (OSError, ValueError, KeyError) as error:
                failures.append({'profile': profile, 'case': case['id'], 'error': str(error)})
    report = {'passed': not failures, 'verified_trials': len(results),
              'expected_trials': len(config['profiles']) * len(dataset['cases']),
              'results': results, 'recorded_failed_trials': recorded_failures, 'failures': failures,
              'scope': 'Audit integrity; passed does not imply every recognition trial succeeded.'}
    atomic_json(output / 'verification.json', report)
    print(json.dumps({'passed': report['passed'], 'verified_trials': len(results),
                      'recorded_failed_trials': len(recorded_failures), 'failures': failures}), flush=True)
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
