"""Loopback-only, silent-by-default transcript/word-boundary review service."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from threading import RLock
from urllib.parse import urlsplit

from benchmarks.asr_only import atomic_json, sha256 as file_sha256
from benchmarks.asr_reference import approval_status, compare_delivery_runs, comparison, digest, estimated_comparison, validate


class ReviewProject:
    def __init__(self, directory):
        self.directory = directory.resolve()
        self.metadata = json.loads((directory / 'project.json').read_text(encoding='utf-8'))
        self.run = Path(self.metadata['run'])
        self.lock = RLock()
        self.cases = tuple(self.metadata['cases'])
        self.identities = {}
        for case in self.cases:
            annotation = self.load(case)
            if file_sha256(annotation['audio']) != annotation['audio_sha256']:
                raise ValueError('Audio hash changed: ' + case)
            self.identities[case] = {key: annotation[key] for key in
                                     ('schema', 'case', 'audio', 'audio_sha256', 'duration_seconds', 'scope',
                                      'draft_source', 'draft_model_sha256')}

    def path(self, case):
        if case not in self.cases:
            raise ValueError('Unknown recording.')
        return self.directory / f'{case}.annotation.json'

    def load(self, case):
        data = self.path(case).read_bytes()
        annotation = json.loads(data)
        return annotation

    def payload(self, case):
        with self.lock:
            path = self.path(case)
            annotation = self.load(case)
            return {'annotation': annotation, 'revision': sha256(path.read_bytes()).hexdigest(),
                    'verification': approval_status(annotation)}

    def save(self, case, body):
        with self.lock:
            path = self.path(case)
            original = path.read_bytes()
            if body.get('revision') != sha256(original).hexdigest():
                raise ValueError('This draft changed in another window. Reload before saving.')
            existing = json.loads(original)
            annotation = deepcopy(existing)
            # Only editable word rows and review declarations come from the UI.
            annotation['words'] = body['words']
            action = body.get('action', 'draft')
            if action not in ('draft', 'approve_text', 'approve_timing'):
                raise ValueError('Unknown review action.')
            validate(annotation)
            review = annotation.setdefault('review', {})
            review['all_speech_checked'] = body.get('all_speech_checked') is True
            review['timing_uncertainty_seconds'] = body.get('timing_uncertainty_seconds')
            review['notes'] = str(body.get('notes', ''))[:10000]
            if action != 'draft':
                reviewer = str(body.get('reviewer', '')).strip()
                if not reviewer or len(reviewer) > 100:
                    raise ValueError('Name the person who reviewed the audio.')
                if not review['all_speech_checked']:
                    raise ValueError('Confirm the whole recording was checked for omitted speech, prompts and repetitions.')
                validate(annotation, strict_text=True, strict_timing=action == 'approve_timing')
                now = datetime.now(timezone.utc).isoformat()
                if action == 'approve_text':
                    review['text_approval'] = {'reviewer': reviewer, 'at': now, 'digest': digest(annotation)}
                else:
                    if not approval_status(annotation)['text_verified']:
                        raise ValueError('Approve the corrected transcript before approving timing.')
                    uncertainty = review.get('timing_uncertainty_seconds')
                    if isinstance(uncertainty, bool) or not isinstance(uncertainty, (int, float)) or not 0 < uncertainty <= 1:
                        raise ValueError('Declare the estimated boundary uncertainty, e.g. 0.10 seconds.')
                    review['timing_approval'] = {'reviewer': reviewer, 'at': now, 'digest': digest(annotation, timing=True)}
            if not approval_status(annotation)['text_verified']:
                review.pop('text_approval', None)
                review.pop('timing_approval', None)
            elif not approval_status(annotation)['timing_verified']:
                review.pop('timing_approval', None)
            annotation['status'] = ('reviewed_text_and_timing' if approval_status(annotation)['timing_verified'] else
                                    'reviewed_text' if approval_status(annotation)['text_verified'] else 'draft_not_verified')
            for key, value in self.identities[case].items():
                if annotation[key] != value:
                    raise ValueError('Recording identity cannot be edited.')
            if file_sha256(annotation['audio']) != annotation['audio_sha256']:
                raise ValueError('Recording changed; approval refused.')
            backup = path.with_name(f'{case}.before-{sha256(original).hexdigest()[:16]}.json')
            if not backup.exists():
                backup.write_bytes(original)
            atomic_json(path, annotation)
            return self.payload(case)

    def table(self):
        with self.lock:
            annotations = {case: self.load(case) for case in self.cases}
            for annotation in annotations.values():
                if file_sha256(annotation['audio']) != annotation['audio_sha256']:
                    raise ValueError('Recording changed since annotation.')
            result = comparison(self.run, annotations)
            atomic_json(self.directory / 'reviewed-comparison.json', result)
            columns = ['profile', 'complete_streams', 'verified_wer_percent',
                       'full_corpus_verified_wer_percent',
                       'stable_word_delay_median_seconds', 'stable_word_delay_p95_seconds',
                       'timed_correct_words', 'eligible_reference_words',
                       'common_correct_word_count', 'common_correct_word_delay_median_seconds', 'status']
            import csv
            with (self.directory / 'reviewed-comparison.csv').open('w', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=columns)
                writer.writeheader()
                writer.writerows({key: row[key] for key in columns} for row in result['rows'])
            lines = ['# Reviewed ASR comparison', '',
                     'Unreviewed ASR drafts never populate the actual WER/word-latency columns.', '',
                     '| Configuration | Complete files | Verified WER | Stable word delay, median | Timed words | Status |',
                     '|---|---:|---:|---:|---:|---|']
            for row in result['rows']:
                wer = 'pending' if row['verified_wer_percent'] is None else f'{row["verified_wer_percent"]:.2f}%'
                delay = 'pending' if row['stable_word_delay_median_seconds'] is None else f'{row["stable_word_delay_median_seconds"]:.3f} s'
                coverage = 'pending' if row['eligible_reference_words'] is None else f'{row["timed_correct_words"]}/{row["eligible_reference_words"]}'
                lines.append(f'| {row["profile"]} | {row["complete_streams"]}/{row["attempted_streams"]} | {wer} | {delay} | {coverage} | {row["status"]} |')
            lines += ['', 'Shared completed recordings: ' + ', '.join(result['shared_recordings']), '',
                      result['accuracy_formula'], result['latency_formula'], result['latency_alignment'],
                      'P95 requires at least 20 measured words. Missing/ambiguous words have no invented delay.',
                      'Common-correct-word latency compares the same word IDs across all configurations; inspect CSV/JSON.',
                      result['selection_note']]
            (self.directory / 'reviewed-comparison.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
            return result

    def book_comparison(self):
        """Read the frozen book-informed trial without rerunning ASR or cue output."""
        directory = self.metadata.get('book_comparison_run')
        if not directory:
            return {'available': False}
        with self.lock:
            directory = Path(directory)
            dataset = json.loads((directory / 'dataset.json').read_text(encoding='utf-8'))
            result = json.loads((directory / 'comparison.json').read_text(encoding='utf-8'))
            for case in dataset['cases']:
                if case['audio_sha256'] != self.identities[case['id']]['audio_sha256']:
                    raise ValueError('Book comparison uses a different recording: ' + case['id'])
            result.update(available=True, human_verified=False,
                          reference_scope='Frozen unverified Whisper Small drafts from this book-informed run.',
                          conditions={'keen-book': 'Full printed passage in an oral-reading graph',
                                      'nemo-full-book': 'Every printed word in bounded boosted phrases; boost 1.0',
                                      'nemo-hints': 'Fixed checkpoint phrase hints; no full-passage graph'})
            return result

    def all_models(self):
        if not self.book_comparison().get('available'):
            return {'available': False}
        path = Path(self.metadata['book_comparison_run']) / 'all-models.json'
        if not path.is_file():
            return {'available': False}
        return {**json.loads(path.read_text(encoding='utf-8')), 'available': True}

    def boost_sweep(self):
        directory = self.metadata.get('boost_sweep_run')
        if not directory:
            return {'available': False}
        directory = Path(directory)
        dataset = json.loads((directory / 'dataset.json').read_text(encoding='utf-8'))
        for case in dataset['cases']:
            if case['audio_sha256'] != self.identities[case['id']]['audio_sha256']:
                raise ValueError('Boost sweep uses a different recording: ' + case['id'])
        result = directory / 'boost-comparison.json'
        if not result.is_file():
            progress = directory / 'progress.json'
            return {'available': True, 'running': True, 'progress': json.loads(progress.read_text()) if progress.exists() else {}}
        return {**json.loads(result.read_text(encoding='utf-8')), 'available': True, 'running': False}

    def estimated_table(self):
        with self.lock:
            annotations = {case: self.load(case) for case in self.cases}
            for annotation in annotations.values():
                if file_sha256(annotation['audio']) != annotation['audio_sha256']:
                    raise ValueError('Recording changed since annotation.')
            result = estimated_comparison(self.run, annotations)
            previous = self.metadata.get('previous_delivery_run')
            if previous:
                result['delivery_comparison'] = compare_delivery_runs(
                    estimated_comparison(Path(previous), annotations), result)
            atomic_json(self.directory / 'estimated-comparison.json', result)
            import csv
            with (self.directory / 'estimated-comparison.csv').open('w', newline='', encoding='utf-8') as file:
                columns = [key for key in result['rows'][0] if key != 'delivery_by_case']
                writer = csv.DictWriter(file, fieldnames=columns, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(result['rows'])
            labels = {'whisper-tiny-cuda': 'Whisper Tiny / CUDA', 'whisper-base-cuda': 'Whisper Base / CUDA',
                      'nemo-cuda': 'Parakeet NeMo / CUDA', 'parakeet-vulkan': 'Native Parakeet / Vulkan',
                      'moonshine-vulkan': 'Moonshine / Vulkan', 'moonshine-cpu': 'Official Moonshine / CPU'}
            lines = ['# ESTIMATED ASR accuracy and recognition latency', '', result['label'], '',
                     'Reference: the separate local offline Whisper Small English drafts. No human review is implied.',
                     f'Run `{result["run"]}` with {result["delivery_mode"]} audio delivery.',
                     'Comparison recordings: ' + (', '.join(result['shared_recordings']) or 'unavailable') +
                     ' (' + result['common_recording_scope'] + ').', '',
                     '| Configuration | Complete files | Est. WER ↓ | Est. same-word median ↓ | Est. same-word P95 | Timed correct words |',
                     '|---|---:|---:|---:|---:|---:|']
            def seconds(value):
                return 'unavailable' if value is None else f'{value:.2f} s'
            for row in result['rows']:
                wer = 'unavailable' if row['estimated_wer_percent'] is None else f'{row["estimated_wer_percent"]:.1f}%'
                lines.append(f'| {labels.get(row["profile"], row["profile"])} | {row["complete_streams"]}/{row["attempted_streams"]} | {wer} | '
                             f'{seconds(row["estimated_common_word_delay_median_seconds"])} | {seconds(row["estimated_common_word_delay_p95_seconds"])} | '
                             f'{row["timed_correct_words"]}/{row["eligible_reference_words"]} |')
            common = max(row['common_correct_word_count'] for row in result['rows'])
            lines += ['', f'Timing medians/P95 above compare the same {common} correctly and unambiguously aligned word IDs for each configuration with a score.',
                      'The coverage column counts each model’s own usable correct words; unmatched words have no invented latency.', '',
                      '## How the estimated comparison works', '', result['accuracy_formula'], result['latency_formula'],
                      result['latency_alignment'], '', 'No tracker or fuzzy matching is involved. Signed delays are preserved; P95 requires at least 20 observations.',
                      'These are estimates against automatic word endings; decimal display does not establish timing precision.', '',
                      '## Estimated per-recording word error', '',
                      '| Configuration | ' + ' | '.join(self.cases) + ' | All three files |',
                      '|---|' + '---:|' * (len(self.cases) + 1)]
            for row in result['rows']:
                scores = result['case_scores'][row['profile']]
                cells = [f'{100 * scores[case]["score"]["wer"]:.1f}%' if 'score' in scores[case] else 'incomplete' for case in self.cases]
                full = row['full_corpus_estimated_wer_percent']
                lines.append('| ' + labels.get(row['profile'], row['profile']) + ' | ' + ' | '.join(cells) +
                             ' | ' + (f'{full:.1f}%' if full is not None else 'incomplete') + ' |')
            lines += ['', '## Estimated median stable delay by recording', '',
                      'Each cell uses the words timed for that model and recording. Use the main table for timing on identical words.', '',
                      '| Configuration | ' + ' | '.join(self.cases) + ' |',
                      '|---|' + '---:|' * len(self.cases)]
            for row in result['rows']:
                scores = result['case_scores'][row['profile']]
                cells = [seconds(scores[case]['estimated_stable_word_delay_median_seconds'])
                         + f' ({scores[case]["timed_correct_words"]} words)' if 'score' in scores[case] else 'incomplete'
                         for case in self.cases]
                lines.append('| ' + labels.get(row['profile'], row['profile']) + ' | ' + ' | '.join(cells) + ' |')
            if result['delivery_mode'] == 'queued':
                lines += ['', '## Queue results', '',
                          'The file replay makes audio available in 256 ms packets on its own clock. The recognizer takes packets in order.',
                          'The maxima cover all three attempts per profile, including unfinished trials. Pending audio excludes the packet already handed to the recognizer.', '',
                          '| Configuration | Worst capture lateness | Peak pending audio | Longest packet queue wait |',
                          '|---|---:|---:|---:|']
                def capture_ms(value):
                    return 'unavailable' if value is None else f'{value * 1000:.1f} ms'
                for row in result['rows']:
                    lines.append(f'| {labels.get(row["profile"], row["profile"])} | '
                                 f'{capture_ms(row["max_capture_lateness_seconds"])} | '
                                 f'{seconds(row["max_queued_audio_seconds"])} | {seconds(row["max_queue_wait_seconds"])} |')
                lines += ['', 'Queue time measures the wait before input submission. Decoder or transport buffering after submission can add further delay.']
            if previous:
                compared = result['delivery_comparison']
                lines += ['', '## Original delivery versus queued delivery', '',
                          f'Shared recordings are {", ".join(compared["shared_recordings"]) or "unavailable"}. '
                          f'Timing uses the same {compared["common_words"]} words across the {compared["profile_count"]} included configurations and both runs.', '',
                          '| Configuration | Est. WER original → queued | Est. median delay original → queued |',
                          '|---|---:|---:|']
                def percent(value):
                    return 'unavailable' if value is None else f'{value:.1f}%'
                for row in compared['rows']:
                    lines.append(f'| {labels.get(row["profile"], row["profile"])} | '
                                 f'{percent(row["before_wer_percent"])} → {percent(row["after_wer_percent"])} | '
                                 f'{seconds(row["before_median_seconds"])} → {seconds(row["after_median_seconds"])} |')
                lines += ['', 'These single runs were performed at different times. System load and normal run-to-run variation can affect the differences.']
            lines += ['', '## Limits', '', *['- ' + note for note in result['limitations']], '',
                      'The independently reviewed table remains separate. Draft annotations, approvals and original benchmark results are unchanged.',
                      'JSON contains the fixed reference text/timing digests, source model identity, edit counts and per-word arrival ledger.']
            (self.directory / 'estimated-comparison.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
            return result


class Handler(BaseHTTPRequestHandler):
    project = None

    def allowed(self):
        return (self.client_address[0] == '127.0.0.1' and
                self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}')

    def send(self, data, content_type='application/json', status=200):
        if not isinstance(data, bytes):
            data = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; media-src 'self'")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self.allowed():
            self.send_error(403)
            return
        try:
            path = urlsplit(self.path).path
            if path == '/':
                return self.send(Path(__file__).with_name('asr_reference_review.html').read_bytes(), 'text/html; charset=utf-8')
            if path == '/api/project':
                return self.send({'cases': list(self.project.cases), 'run': str(self.project.run), 'audio_autoplay': False})
            if path == '/api/table':
                return self.send(self.project.table())
            if path == '/api/estimated-table':
                return self.send(self.project.estimated_table())
            if path == '/api/book-comparison':
                return self.send(self.project.book_comparison())
            if path == '/api/all-models':
                return self.send(self.project.all_models())
            if path == '/api/boost-sweep':
                return self.send(self.project.boost_sweep())
            match = re.fullmatch(r'/(api/case|api/waveform|audio)/([a-z0-9_]+)', path)
            if not match:
                self.send_error(404)
                return
            kind, case = match.groups()
            annotation = self.project.load(case)
            if kind == 'api/case':
                return self.send(self.project.payload(case))
            if kind == 'api/waveform':
                return self.send((self.project.directory / f'{case}.waveform.json').read_bytes())
            audio = Path(annotation['audio'])
            size = audio.stat().st_size
            start, end, status = 0, size-1, 200
            requested = self.headers.get('Range')
            if requested:
                byte_range = re.fullmatch(r'bytes=(\d+)-(\d*)', requested)
                if not byte_range:
                    self.send_error(416)
                    return
                start = int(byte_range[1])
                end = min(int(byte_range[2]) if byte_range[2] else size-1, size-1)
                if not 0 <= start <= end < size:
                    self.send_error(416)
                    return
                status = 206
            self.send_response(status)
            self.send_header('Content-Type', 'audio/wav')
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Content-Length', str(end-start+1))
            if status == 206:
                self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
            self.end_headers()
            with audio.open('rb') as file:
                file.seek(start)
                remaining = end-start+1
                while remaining:
                    data = file.read(min(65536, remaining))
                    if not data:
                        break
                    self.wfile.write(data)
                    remaining -= len(data)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except (KeyError, ValueError, OSError) as error:
            self.send({'error': str(error)}, status=400)

    def do_POST(self):
        if (not self.allowed() or self.headers.get('Origin') not in
                (None, f'http://127.0.0.1:{self.server.server_port}')):
            self.send_error(403)
            return
        try:
            if self.headers.get_content_type() != 'application/json':
                raise ValueError('Use application/json.')
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 2_000_000:
                raise ValueError('Invalid request length.')
            match = re.fullmatch(r'/api/case/([a-z0-9_]+)', urlsplit(self.path).path)
            if not match:
                self.send_error(404)
                return
            body = json.loads(self.rfile.read(length))
            self.send(self.project.save(match[1], body))
        except (KeyError, TypeError, ValueError, OSError) as error:
            self.send({'error': str(error)}, status=400)

    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8766)
    args = parser.parse_args()
    Handler.project = ReviewProject(args.project)
    Handler.project.table()
    Handler.project.estimated_table()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'Local reference review: http://127.0.0.1:{args.port} (sound off; no autoplay)', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
