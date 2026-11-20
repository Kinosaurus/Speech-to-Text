"""Local, tracker-free ASR scoring, dataset freezing and sequential orchestration."""
import argparse
import csv
import hashlib
import importlib.abc
import json
import os
from pathlib import Path
from queue import Queue
import statistics
import subprocess
import sys
import threading
import time
import wave

from benchmarks.metrics import edit_alignment, words

PROTOCOL = 'asr-only-streaming-v1'
PROFILES = ('nemo-cuda', 'whisper-tiny-cpu', 'whisper-base-cpu', 'whisper-tiny-cuda', 'whisper-base-cuda',
            'parakeet-vulkan', 'moonshine-vulkan', 'moonshine-cpu')


class NoTrackerImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(('books_to_life.matching', 'books_to_life.context')):
            raise ImportError('ASR-only benchmark forbids tracker/context imports: ' + fullname)


def enforce_no_tracker():
    forbidden = [name for name in sys.modules if name.startswith(
        ('books_to_life.matching', 'books_to_life.context'))]
    if forbidden:
        raise RuntimeError('Tracker/context modules already imported: ' + repr(forbidden))
    sys.meta_path.insert(0, NoTrackerImports())


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_json(path, data):
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def phrase_present(text, phrase):
    haystack, needle = words(text), words(phrase)
    return bool(needle) and any(haystack[i:i + len(needle)] == needle
                               for i in range(len(haystack) - len(needle) + 1))


def score_updates(events, case):
    updates = [e for e in events if e['kind'] == 'transcript']
    text = updates[-1]['text'] if updates else ''
    score, _ = edit_alignment(case['reference'], text)
    revisions = sum(not words(b['text'])[:len(words(a['text']))] == words(a['text'])
                    for a, b in zip(updates, updates[1:]))
    timing = []
    for mark in case.get('timing_marks', []):
        matches = [i for i, e in enumerate(updates) if phrase_present(e['text'], mark['phrase'])]
        first = updates[matches[0]]['wall_seconds'] if matches else None
        # A transient correct hypothesis can be revised away. Report first and
        # persistent availability separately; neither is a checkpoint decision.
        persistent = None
        if updates and phrase_present(text, mark['phrase']):
            last_absent = max((i for i, e in enumerate(updates)
                               if not phrase_present(e['text'], mark['phrase'])), default=-1)
            persistent = updates[last_absent + 1]['wall_seconds']
        timing.append({**mark, 'first_available_seconds': first,
                       'first_delay_seconds': first - mark['end_seconds'] if first is not None else None,
                       'persistent_available_seconds': persistent,
                       'persistent_delay_seconds': persistent - mark['end_seconds'] if persistent is not None else None,
                       'present_in_final': phrase_present(text, mark['phrase'])})
    first_text = next((e['wall_seconds'] for e in updates if words(e['text'])), None)
    return {'final_text': text, 'reference_kind': case['reference_kind'],
            'reference_score': score, 'spoken_wer': score['wer'] if case['reference_kind'] == 'verified_spoken' else None,
            'passage_wer': score['wer'] if case['reference_kind'] == 'supplied_passage' else None,
            'first_text_seconds_from_audio_start': first_text,
            'text_updates': len(updates), 'non_append_revisions': revisions,
            'timing_marks': timing}


class ASRRecorder:
    def __init__(self, path, delivery='inline'):
        self.file = Path(path).open('w', encoding='utf-8')
        self.events = []
        self.lock = threading.RLock()
        self.origin = None
        self.sent_samples = 0
        self.error = None
        self.last_text = None
        self.delivery = delivery
        self.capture_stop = threading.Event()
        self.capture_thread = None

    def begin(self):
        self.origin = time.perf_counter()

    def emit(self, kind, **data):
        with self.lock:
            if self.origin is None:
                return
            event = {'kind': kind, 'wall_seconds': time.perf_counter() - self.origin, **data}
            self.events.append(event)
            self.file.write(json.dumps(event, ensure_ascii=False) + '\n')
            self.file.flush()

    def receive(self, text, *, segments=None, final=False):
        with self.lock:
            if self.origin is None:
                return
            if text == self.last_text and not final:
                return
            self.last_text = text
            self.emit('transcript', text=text, final=final, segments=segments,
                      delivered_audio_seconds=self.sent_samples / 16000)

    def chunks(self, pcm, packet_samples=4096, tail_seconds=1.5):
        import numpy as np
        stream = np.concatenate((pcm, np.zeros(round(tail_seconds * 16000), dtype=np.float32)))
        self.begin()
        if self.delivery == 'queued':
            yield from self.queued_chunks(stream, packet_samples)
            return
        for offset in range(0, len(stream), packet_samples):
            end = min(offset + packet_samples, len(stream))
            due = self.origin + end / 16000
            if due > time.perf_counter():
                time.sleep(due - time.perf_counter())
            self.sent_samples = end
            self.emit('audio', sample_start=offset, sample_count=end - offset,
                      feed_lateness_seconds=max(0, time.perf_counter() - due))
            yield stream[offset:end]
        self.emit('end_of_audio', samples=self.sent_samples)

    def queued_chunks(self, stream, packet_samples):
        # This is a finite file replay. The FIFO can hold at most the input file
        # plus its silence tail, and each item is a view into the same sample array.
        packets = Queue()
        capture_error = None

        def capture():
            nonlocal capture_error
            try:
                for offset in range(0, len(stream), packet_samples):
                    end = min(offset + packet_samples, len(stream))
                    due = self.origin + end / 16000
                    if self.capture_stop.wait(max(0, due - time.perf_counter())):
                        return
                    with self.lock:
                        available = time.perf_counter()
                        self.emit('capture', sample_start=offset, sample_count=end - offset,
                                  capture_lateness_seconds=max(0, available - due),
                                  pending_audio_seconds=(end - self.sent_samples) / 16000)
                        packets.put((offset, end, available))
                self.emit('end_of_capture', samples=len(stream))
            except Exception as error:
                capture_error = error
            finally:
                packets.put(None)

        self.capture_thread = threading.Thread(target=capture, name='paced-audio-source', daemon=True)
        self.capture_thread.start()
        while (packet := packets.get()) is not None:
            offset, end, available = packet
            with self.lock:
                now = time.perf_counter()
                self.sent_samples = end
                self.emit('audio', sample_start=offset, sample_count=end - offset,
                          feed_lateness_seconds=max(0, now - self.origin - end / 16000),
                          queue_wait_seconds=now - available)
            # The calling worker submits this packet or hands it to the backend.
            # Only the consumer advances sent_samples, even during a long decode.
            yield stream[offset:end]
        if capture_error is not None:
            raise capture_error
        self.emit('end_of_audio', samples=self.sent_samples)

    def close(self):
        self.capture_stop.set()
        if self.capture_thread is not None:
            self.capture_thread.join()
        self.file.close()


def freeze_dataset(root, output):
    cases = []
    # The working checkout is output/<name>; historical results live in the
    # enclosing repository's output/benchmarks, not beside source modules.
    historical = root.parent / 'benchmarks'
    timing = {'tea': [('tea', 'pot of tea', 20), ('stove', 'stove', 54), ('house', 'house', 77)],
              'fat_cat': [('hat', 'cat in a hat', 53)]}
    for name in ('tea', 'fat_cat', 'little_mermaid'):
        folder = root / f'recordings/library/stories/{name}/readers/{name}'
        audio = folder / 'audio.wav'
        with wave.open(str(audio)) as wav:
            if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth(), wav.getcomptype()) != (16000, 1, 2, 'NONE'):
                raise ValueError('Expected 16 kHz mono PCM16 WAV: ' + str(audio))
            duration = wav.getnframes() / 16000
        reference_path = folder / 'passage.txt'
        reference = reference_path.read_text(encoding='utf-8-sig').strip()
        marks = []
        annotation = historical / ('tea-streaming' if name == 'tea' else 'fat-cat-streaming') / 'manual-checkpoint-annotations.json'
        if name in timing and annotation.is_file():
            metadata = json.loads(annotation.read_text())
            if metadata['audio_sha256'] != sha256(audio):
                raise ValueError('Listening mark audio hash differs: ' + name)
            marks = [{'id': ident, 'phrase': phrase, 'end_seconds': end, 'precision_seconds': 1,
                      'source': metadata['source']} for ident, phrase, end in timing[name]]
        cases.append({'id': name, 'audio': str(audio.resolve()), 'audio_sha256': sha256(audio),
                      'duration_seconds': duration, 'reference_path': str(reference_path.resolve()),
                      'reference_sha256': sha256(reference_path), 'reference': reference,
                      'reference_kind': 'supplied_passage', 'timing_marks': marks})
    dataset = {'protocol': PROTOCOL, 'hints': False, 'tracker': False, 'packet_samples': 4096,
               'tail_seconds': 1.5, 'cases': cases,
               'limitations': ['Printed passage references are not verified verbatim spoken transcripts.',
                              'Timing marks are whole-second listening estimates; not millisecond ground truth.',
                              'No microphone, speakers, projector or checkpoint matcher is used.']}
    atomic_json(output / 'dataset.json', dataset)
    return dataset


def report(output, dataset, profiles):
    rows, details = [], []
    for profile in profiles:
        trials = []
        failures = []
        for case in dataset['cases']:
            path = output / f'{profile}--{case["id"]}.json'
            if path.is_file():
                result = json.loads(path.read_text(encoding='utf-8'))
                if result.get('status') == 'ok':
                    trials.append(result)
                else:
                    failures.append({'case': case['id'], 'error': result.get('error')})
            else:
                failures.append({'case': case['id'], 'error': 'Not completed'})
        counts = [t['metrics']['reference_score'] for t in trials if t['metrics']['reference_kind'] == 'supplied_passage']
        total_words = sum(c['reference_words'] for c in counts)
        edits = sum(c[k] for c in counts for k in ('substitutions', 'deletions', 'insertions'))
        spoken = [t['metrics']['reference_score'] for t in trials if t['metrics']['reference_kind'] == 'verified_spoken']
        spoken_words = sum(c['reference_words'] for c in spoken)
        spoken_edits = sum(c[k] for c in spoken for k in ('substitutions', 'deletions', 'insertions'))
        first = [t['metrics']['first_text_seconds_from_audio_start'] for t in trials
                 if t['metrics']['first_text_seconds_from_audio_start'] is not None]
        delays = [m['first_delay_seconds'] for t in trials for m in t['metrics']['timing_marks']
                  if m['first_delay_seconds'] is not None]
        row = {'profile': profile, 'completed': len(trials), 'total': len(dataset['cases']),
               'passage_wer_percent': edits / total_words * 100 if total_words else None,
               'spoken_wer_percent': spoken_edits / spoken_words * 100 if spoken_words else None,
               'median_first_text_seconds': statistics.median(first) if first else None,
               'median_approx_word_delay_seconds': statistics.median(delays) if delays else None,
               'timing_phrases_available': len(delays),
               'timing_phrases_total': sum(len(c.get('timing_marks', [])) for c in dataset['cases']),
               'max_feed_lateness_seconds': max((t['delivery']['max_feed_lateness_seconds'] for t in trials), default=None),
               'failures': failures}
        rows.append(row)
        details.extend(trials)
    atomic_json(output / 'comparison.json', {'protocol': PROTOCOL, 'rows': rows, 'trials': details})
    with (output / 'comparison.csv').open('w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=[k for k in rows[0] if k != 'failures'])
        writer.writeheader()
        writer.writerows({k: v for k, v in row.items() if k != 'failures'} for row in rows)
    lines = ['# ASR-only comparison', '',
             'No tracker, book hints, checkpoint decisions or physical playback. Audio is streamed at 1x.', '',
             '**Passage WER is deviation from the printed passage. It includes reading mistakes and is not verified ASR WER.**',
             'Missing or failed trials remain visible. Partial profiles must not be ranked against complete profiles.', '',
             '| Profile | Completed | Passage WER | Verified spoken WER | First text, median | Approx. word delay, median | Timed phrases | Max feed lag |',
             '|---|---:|---:|---:|---:|---:|---:|---:|']
    def value(number, suffix='s'):
        return 'unavailable' if number is None else f'{number:.2f}{suffix}'
    for row in rows:
        lines.append(f'| {row["profile"]} | {row["completed"]}/{row["total"]} | '
                     f'{value(row["passage_wer_percent"], "%")} | {value(row["spoken_wer_percent"], "%")} | {value(row["median_first_text_seconds"])} | '
                     f'{value(row["median_approx_word_delay_seconds"])} | '
                     f'{row["timing_phrases_available"]}/{row["timing_phrases_total"]} | {value(row["max_feed_lateness_seconds"])} |')
    lines += ['', 'First text is timed from recording start, including initial silence, not from speech onset.',
              'Word delay uses post-run exact normalized phrase presence, not tracker decisions. Negative means earlier than the supplied mark.',
              'Marks have whole-second precision. First availability can be transient; persistent availability and final retention are in JSON.',
              'Absent phrases have no delay. Delay medians cover available phrases only and must be read with coverage.',
              'Paced stream duration is not an inference real-time factor. Startup, EOF drain, revisions and delivery are reported separately.',
              'GPU/CPU, precision, buffering and backend differ and are recorded per trial. One trial per recording/profile; development data.',
              'GPU memory snapshots include other applications and are not model-only allocation measurements.',
              'NeMo reuses the already loaded server. Its handshake is not a cold model-load measurement.', '']
    for row in rows:
        for failure in row['failures']:
            lines.append(f'- {row["profile"]} / {failure["case"]}: {failure["error"]}')
    (output / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--python', type=Path, default=Path(sys.executable))
    parser.add_argument('--profiles', nargs='+', choices=PROFILES, default=[p for p in PROFILES if not p.startswith('whisper-') or p.endswith('-cpu')])
    parser.add_argument('--nemo-url', default='ws://127.0.0.1:9097')
    parser.add_argument('--delivery', choices=('inline', 'queued'), default='inline')
    parser.add_argument('--dataset', type=Path, help='Reuse a frozen dataset from an earlier run.')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--summarize-only', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    dataset_path = output / 'dataset.json'
    if dataset_path.exists():
        if not args.resume and not args.summarize_only:
            parser.error('Use a fresh output directory, or --resume for an interrupted run.')
        dataset = json.loads(dataset_path.read_text(encoding='utf-8'))
    elif args.dataset:
        dataset = json.loads(args.dataset.read_text(encoding='utf-8'))
        atomic_json(dataset_path, dataset)
    else:
        dataset = freeze_dataset(root, output)
    for case in dataset['cases']:
        if sha256(case['audio']) != case['audio_sha256'] or sha256(case['reference_path']) != case['reference_sha256']:
            raise ValueError('Frozen input changed: ' + case['id'])
    source_hashes = {name: sha256(root / name) for name in
                     ('benchmarks/asr_only.py', 'benchmarks/asr_only_worker.py', 'benchmarks/metrics.py')}
    metadata_path = output / 'run.json'
    metadata = {'protocol': PROTOCOL, 'source_sha256': source_hashes, 'profiles': args.profiles,
                'python': str(args.python.resolve()), 'cache': str(args.cache.resolve()), 'nemo_url': args.nemo_url}
    if args.delivery != 'inline':
        metadata['delivery'] = args.delivery
    if metadata_path.exists() and json.loads(metadata_path.read_text()) != metadata:
        raise ValueError('Run configuration/source changed; use a fresh output directory.')
    atomic_json(metadata_path, metadata)
    for name in source_hashes:
        target = output / 'source' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((root / name).read_bytes())
    if not args.summarize_only:
        env = dict(os.environ, HF_HUB_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1', PYTHONUTF8='1')
        for profile in args.profiles:
            for case in dataset['cases']:
                result_path = output / f'{profile}--{case["id"]}.json'
                if args.resume and result_path.is_file():
                    continue  # Failed trials are retained too; use a new run for retries.
                print(f'START {profile} {case["id"]}', flush=True)
                atomic_json(output / 'progress.json', {'profile': profile, 'case': case['id'], 'state': 'running'})
                command = [str(args.python), '-X', 'utf8', '-u', '-m', 'benchmarks.asr_only_worker',
                           '--profile', profile, '--dataset', str(dataset_path), '--case', case['id'],
                           '--cache', str(args.cache.resolve()), '--output', str(result_path), '--nemo-url', args.nemo_url,
                           '--delivery', args.delivery]
                with result_path.with_suffix('.log').open('w', encoding='utf-8') as log:
                    try:
                        result = subprocess.run(command, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT,
                                                timeout=case['duration_seconds'] * 3 + 120,
                                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                        if result.returncode and not result_path.exists():
                            atomic_json(result_path, {'status': 'failed', 'error': f'Worker exit {result.returncode}; see log.'})
                    except subprocess.TimeoutExpired:
                        atomic_json(result_path, {'status': 'failed', 'error': 'Worker exceeded trial timeout; see log.'})
                rows = report(output, dataset, args.profiles)
                state = json.loads(result_path.read_text())['status']
                print(f'{state.upper()} {profile} {case["id"]}', flush=True)
    rows = report(output, dataset, args.profiles)
    atomic_json(output / 'progress.json', {'state': 'complete', 'rows': rows})
    print(output / 'report.md', flush=True)


if __name__ == '__main__':
    main()
