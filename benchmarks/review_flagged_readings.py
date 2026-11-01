"""Evidence audit of 17 flagged readings, without claiming auditory verification.

Replays saved ASR callbacks, preserves human-review fields, and creates context
audio for a person to check. This is diagnostic replay, not a new live trial.
"""
from dataclasses import asdict
import hashlib
import html
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher
import soundfile as sf

BATCH = ROOT / 'output/mps-expansion-2026-11-02'
LIB = ROOT / 'recordings/library'
# Conclusions concern provider/ASR/log evidence, not a human listening decision.
FINDINGS = {
    ('4a18f_EN-OL-RC-426_1', 'thick_legs'): ('low', 'timing_reference_gap',
        'Provider labels the anchor correct; live ASR reaches thick legs and medium.en locates legs. The small.en locator failure does not establish a bad trigger. Leave timing unscored.'),
    ('4a18f_EN-OL-RC-426_1', 'fish_and_seals'): ('low', 'plausible_context_variant',
        'The provider writes usually phonetically. Both reference models recover the full phrase and agree within 60 ms. The live trigger has the same ending; low confidence is a review flag, not proof of an incorrect scene.'),
    ('4a18f_EN-OL-RC-426_1', 'keep_away'): ('medium', 'endpoint_word_uncertain',
        'Provider and live ASR render the final word as use instead of us; neither timing locator accepts the printed anchor. Cannot decide pronunciation variant versus changed word without listening. No timing gold.'),
    ('4a18f_EN-OL-RC-426_2', 'clever_bears'): ('low', 'timing_reference_gap',
        'Provider substitutions are within the phrase; medium.en locates the expected clever ending and live ASR reaches it. One failed reference locator is not sufficient to reject the activation.'),
    ('4b25a_EN-OL-RC-426_2', 'hibernate'): ('low', 'plausible_context_variant',
        'The main discrepancy is beers versus bears. Both models retain hibernate through April and agree within 20 ms; the live transcript also contains the central phrase.'),
    ('4a35g_EN-OL-RC-426_1', 'fish_and_seals'): ('medium', 'endpoint_word_uncertain',
        'Provider labels seals correct, but live recognition ends fish and seas and neither acoustic locator supports the printed anchor. The sources disagree; do not infer that the child omitted seals or clear the trigger without listening.'),
    ('4a35g_EN-OL-RC-426_2', 'hibernate'): ('high', 'trigger_without_key_anchor_word',
        'Provider marks hibernate deleted. Both reference models and the live transcript also lack it, but the checkpoint fires after October to April before. This confirms a trigger without that word in the recognition evidence; whether it is acceptable depends on scene versus word-specific effect policy.'),
    ('4a35g_EN-OL-RC-426_2', 'clever_bears'): ('low', 'plausible_context_variant',
        'A very/well variation is inside the anchor; both models reach clever with endpoints 20 ms apart. The live transcript reaches the same ending. This looks consistent with tolerant scene tracking, subject to listening review.'),
    ('4a35g_EN-OL-RC-426_2', 'begging_paws'): ('medium', 'miss_with_unresolved_reading_variant',
        'This is the configured miss. Provider reports three substitutions, including the final word; live ASR has holing out their pile and neither timing model locates paws. Do not lower the global threshold or invent an endpoint to make this pass.'),
    ('5a28c_EN-OL-RC-538_1', 'fine_patterns'): ('low', 'inflection_variant',
        'Provider, both references, and live ASR use singular pattern rather than patterns. The word-ending mismatch flag is expected; this does not by itself imply a wrong scene.'),
    ('5b2b_EN-OL-RC-538_1', 'wing_colours'): ('low', 'plausible_context_variant',
        'The provider labels their/they differently; references vary the/ their while retaining wings and agree within 40 ms. The live transcript contains the intended descriptive phrase.'),
    ('5b2b_EN-OL-RC-538_1', 'small_scales'): ('medium', 'endpoint_word_uncertain',
        'Provider writes sales and live recognition says cells where print says scales. No two-model endpoint is justified. Context explains the match but does not establish correct pronunciation or correct word-specific effect behavior.'),
    ('5b2b_EN-OL-RC-538_1', 'fine_patterns'): ('low', 'inflection_variant',
        'Provider and all recognizers use pattern, with an extra article in the references. The same descriptive context is retained; keep it separate from the nearby scales/cells disagreement.'),
    ('5b2b_EN-OL-RC-538_2', 'escape_enemies'): ('high', 'trigger_without_endpoint_word',
        'Provider marks enemies deleted. The live transcript proceeds from escape from its directly to a bird or; the checkpoint then fires. This is a concrete effect-policy risk if this effect requires the endpoint, rather than passage progress.'),
    ('5b2b_EN-OL-RC-538_2', 'damaged_wing'): ('low', 'plausible_context_variant',
        'Provider and both reference models use bite instead of bit, while retaining wing; endpoints agree within 40 ms and live ASR matches that wording. The intended scene may be preserved despite the vowel/word variation.'),
    ('5a21k_EN-OL-RC-538_1', 'fine_patterns'): ('low', 'inflection_variant',
        'Provider and all recognizers use singular pattern; the two reference endpoints differ by 20 ms. Treat as an inflection-policy case, not a confirmed bad activation.'),
    ('5a21k_EN-OL-RC-538_2', 'damaged_wing'): ('high', 'reproducible_alignment_ranking_delay',
        'The first a bit of wings ASR update already has a qualifying endpoint candidate, but a slightly higher-scoring candidate stops one book word short. A later repetition finally wins. This is a reproduced alignment ranking issue, not merely GPU decoding time.'),
}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


class Probe(TimelyEvidenceMatcher):
    def _alignment_candidates(self, low, high):
        self.review_candidates = super()._alignment_candidates(low, high)
        return self.review_candidates


def main():
    output = BATCH / 'review/flagged-evidence-review'
    output.mkdir(exist_ok=True)
    manual_sheet = BATCH / 'review/manual_review.csv'
    manual_before = hashlib.sha256(manual_sheet.read_bytes()).hexdigest()
    protocol = read(BATCH / 'evaluation/protocol.json')
    for name, digest in protocol['source_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
    rows = []
    replayed = 0
    for job in read(BATCH / 'jobs.json')['recordings']:
        folder = LIB / job['path']
        manifest = read(folder / 'checkpoints.json')
        points = read(folder / 'expansion_checkpoint_review.json')['checkpoints']
        evidence = read(folder / 'checkpoint_evidence.json')
        events = [json.loads(s) for s in (BATCH / 'evaluation/live' / (job['audio_id'] + '.events.jsonl')).read_text(encoding='utf-8').splitlines()]
        origin = next(e['wall'] for e in events if e['kind'] == 'audio')
        triggers = [e for e in events if e['kind'] == 'tracker' and e['mode'] == 'timely' and e['triggered']]
        matcher = Probe(manifest)
        replay_triggers = []
        trace = []
        for event in events:
            if event['kind'] != 'segments':
                continue
            segments = event['segments']
            text = ' '.join(s['text'] for s in segments)
            update = matcher.process(text, segments)
            if update.triggered:
                replay_triggers.append(update.checkpoint_id)
            if job['audio_id'] == '5a21k_EN-OL-RC-538_2' and 'a bit of wings' in text:
                candidates = [c for c in getattr(matcher, 'review_candidates', []) if c.end == manifest['checkpoints'][-1]['word_end']]
                trace.append(dict(wall_seconds=event['wall'] - origin, text=text,
                    update=asdict(update), best_endpoint=asdict(max(candidates, key=lambda c: c.score)) if candidates else None))
        assert replay_triggers == [t['scene'] for t in triggers], job['audio_id']
        replayed += 1
        audio, rate = sf.read(folder / 'audio.wav', dtype='int16')
        for point in points:
            if not point['review_flags']:
                continue
            key = job['audio_id'], point['id']
            priority, category, finding = FINDINGS[key]
            cp = next(c for c in manifest['checkpoints'] if c['id'] == point['id'])
            trigger = next((t for t in triggers if t['scene'] == point['id']), None)
            segments = [e for e in events if e['kind'] == 'segments' and (trigger is None or e['wall'] <= trigger['wall'])]
            live_text = ' '.join(s['text'] for s in segments[-1]['segments'])
            matches = point['model_matches']
            if matches:
                start = max(0, min(m['start'] for m in matches.values()) - 2)
                end = max(m['end'] for m in matches.values()) + 2
                if trigger:
                    end = max(end, trigger['audio_end'] + 1)
                window_basis = 'Automatic anchor/context and trigger coverage; not human word alignment.'
            elif trigger:
                start, end = max(0, trigger['audio_end'] - 14), trigger['audio_end'] + 3
                window_basis = 'Trigger-centred context only; no acoustic endpoint inferred.'
            else:
                start, end = max(0, len(audio) / rate - 16), len(audio) / rate
                window_basis = 'End-of-recording context for an unlocated missed endpoint; not word aligned.'
            end = min(end, len(audio) / rate)
            clip = output / (job['audio_id'] + '.' + point['id'] + '.wav')
            sf.write(clip, audio[round(start * rate):round(end * rate)], rate, subtype='PCM_16')
            row = dict(audio_id=job['audio_id'], checkpoint=point['id'], priority=priority,
                category=category, finding=finding, review_type='assistant evidence audit, not auditory verification',
                manual_verification=False, original_flags=point['review_flags'],
                anchor=cp['checkpoint_text'], provider=evidence[point['id']], reference_matches=matches,
                live_text_at_trigger_or_final=live_text, triggered=point['triggered'],
                estimated_delay_seconds=point['estimated_delay_seconds'], clip=clip.name,
                clip_start_seconds=start, clip_end_seconds=end, window_basis=window_basis,
                trigger_wall_seconds=trigger['wall'] - origin if trigger else None)
            if trace and point['id'] == 'damaged_wing':
                first = trace[0]
                row['ranking_diagnostic'] = dict(first_asr=first,
                    observed_asr_to_trigger_seconds=trigger['wall'] - origin - first['wall_seconds'],
                    score_advantage_of_short_candidate=first['update']['score'] - first['best_endpoint']['score'],
                    replay_trace=trace, note='Saved-callback replay, not a fresh audio experiment or human-verified word delay.')
            rows.append(row)
    assert len(rows) == len(FINDINGS) == 17
    rows.sort(key=lambda r: ({'high': 0, 'medium': 1, 'low': 2}[r['priority']], r['audio_id'], r['checkpoint']))
    report = dict(date='2026-11-02', scope='17 flagged checkpoints; evidence audit only',
        human_listening_performed=False, human_review_fields_preserved=True,
        source_hashes_unchanged=True, replay_sequences_verified=replayed,
        counts={p: sum(r['priority'] == p for r in rows) for p in ('high', 'medium', 'low')}, cases=rows)
    (output / 'review.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    cards = []
    for row in rows:
        provider = ' | '.join(w['prompt'] + ' → ' + w['spoken'] + ' [' + w['label'] + ']' for w in row['provider'].get('words', []))
        cards.append('<article><h2>' + html.escape(row['priority'].upper() + ' — ' + row['audio_id'] + ' / ' + row['checkpoint']) +
            '</h2><p><b>' + html.escape(row['anchor']) + '</b></p><p>' + html.escape(row['finding']) +
            '</p><audio controls preload="none" src="' + row['clip'] + '"></audio><p>Full-recording window: ' +
            f'{row["clip_start_seconds"]:.2f}–{row["clip_end_seconds"]:.2f}s. ' + html.escape(row['window_basis']) +
            '</p><details><summary>Provider word labels</summary><p>' + html.escape(provider) +
            '</p></details><details><summary>Live ASR at trigger (or final ASR for the miss)</summary><p>' +
            html.escape(row['live_text_at_trigger_or_final']) + '</p></details></article>')
    (output / 'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Flagged reading evidence review</title>'
        '<style>body{max-width:950px;margin:35px auto;padding:0 20px;font:17px/1.6 system-ui}article{border-top:2px solid #ddd;margin-top:30px}audio{width:100%}summary{cursor:pointer}</style>'
        '<h1>17 flagged checkpoints</h1><p><b>Evidence review, not a human listening sign-off.</b> All original flags and human-review fields are preserved. '
        'These are context clips; some have no defensible word endpoint. Start with the three high-priority cases.</p>' + ''.join(cards), encoding='utf-8')
    assert hashlib.sha256(manual_sheet.read_bytes()).hexdigest() == manual_before
    print(json.dumps({k: report[k] for k in ('counts', 'replay_sequences_verified', 'human_listening_performed')}, indent=2))
    print('Review:', output / 'index.html')


if __name__ == '__main__':
    main()
