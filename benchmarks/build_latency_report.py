"""Export measured latency changes without hiding lost cues or reference limits."""
import csv
import hashlib
import json
from pathlib import Path
import statistics


def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))


def main():
    root=Path('output/latency-investigation-20261119');old=Path('output/product-comparison-20261119')
    provenance=read(root/'provenance.json')
    for name,digest in provenance['matcher_hashes'].items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest,'Matcher changed'
    human=read(root/'human/summary.json');off=read(root/'no-hints-02/summary.json')
    assert len(human)==9 and len(off)==10,'Incomplete regressions'
    gates=[]
    for mode,data in [('full-text',human),('off, unpaced quality only',off)]:
        baseline={d['case']:d for d in data if d['profile']=='baseline'}
        selected={d['case']:d for d in data if d['profile']=='short-chunk'}
        for case,b in baseline.items():
            n=selected[case];lost=sorted(set(b['hit_ids'])-set(n['hit_ids']))
            assert b['audio_sha256']==n['audio_sha256'],'Recording mismatch'
            gates.append(dict(hints=mode,case=case,baseline_hits=b['hit_ids'],selected_hits=n['hit_ids'],
                              lost=lost,duplicates_increased=n['duplicate_cues']>b['duplicate_cues']))
    assert not any(g['lost'] or g['duplicates_increased'] for g in gates),'Checkpoint regression'
    rows=[]
    for case,title,previous in [
        ('moon','The Moon',[Path('output/novel-cue-annotation-20261119-results')/t for t in ['pod-moon-trial-01','pod-moon-trial-02']]),
        ('lion','The Lion and the Mouse excerpt',[old/'pod-readmio-trial-02',old/'pod-readmio-trial-03'])]:
        current=[root/d/f'{case}-short-chunk-01' for d in ['short-chunk','confirmation']]
        scores=[read(p/'score.json') for p in current];before=[read(p/'score.json') for p in previous]
        ids=['opening','cat','mouse'] if case=='moon' else [e['id'] for e in before[0]['events']]
        def median(xs):return statistics.median(e['effect_delay_seconds'] for s in xs for e in s['events'] if e['hit'] and e['id'] in ids)
        for p,s in zip(current,scores):
            assert read(p/'result.json')['input_sha256']==read(previous[0]/'result.json')['input_sha256'],'Source mismatch'
            assert read(p/'result.json')['physical_endpoint_original_mute_restored']
            assert read(p/'result.json')['pre_source_digital_tone_verified']
            assert {e['id'] for e in s['events'] if e['hit']}>=set(ids)
        rows.append(dict(book=title,previous_common_target_median_seconds=median(before),
                         new_common_target_median_seconds=median(scores),
                         reduction_percent=100*(1-median(scores)/median(before)),
                         previous_all_configured_hits=f"{sum(s['checkpoints_hit'] for s in before)}/{sum(s['expected_checkpoints'] for s in before)}",
                         new_all_configured_hits=f"{sum(s['checkpoints_hit'] for s in scores)}/{sum(s['expected_checkpoints'] for s in scores)}",
                         replays_each=2,estimated_synthetic_wer_percent=100*scores[0]['estimated_synthetic_wer']['wer']))
    hr=[]
    for profile in ['baseline','short-chunk','fast']:
        xs=[x for x in human if x['profile']==profile]
        errors=sum(sum(x['wer'][k] for k in ['substitutions','deletions','insertions']) for x in xs)
        words=sum(x['wer']['reference_words'] for x in xs)
        hr.append(dict(profile=profile,hits=sum(x['hits'] for x in xs),configured=sum(x['expected'] for x in xs),
                       provisional_errors=errors,reference_words=words,estimated_wer_percent=100*errors/words))
    applied=read(root/'applied-settings.json') if (root/'applied-settings.json').exists() else None
    verification=read(root/'final-verification.json') if (root/'final-verification.json').exists() else None
    summary=dict(status='measured_and_applied' if applied else 'measured_not_yet_applied',
                 selected_profile='short-chunk',chunk_ms=160,right_ms=560,packet_samples=1280,
                 matcher_unchanged=True,synthetic_rows=rows,human_rows=hr,regression_gates=gates,
                 applied=applied,production_verification=verification,
                 metric='Digital sound onset minus estimated synthetic phrase end; latency compared on common targets',
                 caveats=['Only two synthetic clips and three existing human recordings; no general guarantee.',
                          'Human references are provisional ASR drafts; WER is estimated, not verified accuracy.',
                          'No-hints checks are accelerated quality-only: never use their wall clock for latency.',
                          'Three of seven configured human-recording targets fired under both settings; untriggered targets are not confirmed misses until the spoken phrases are verified.',
                          'Shorter chunks increase compute frequency; long sessions with live MapMap need a physical/headroom check.',
                          'Microphone acoustics, physical speaker and projector latency were not measured.'])
    (root/'results.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    with (root/'latency-canva.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader()
        w.writerows([{k:(f'{v:.2f}' if isinstance(v,float) else v) for k,v in r.items()} for r in rows])
    table='\n'.join(f"| {r['book']} | {r['previous_common_target_median_seconds']:.2f} s | {r['new_common_target_median_seconds']:.2f} s | {r['previous_all_configured_hits']} | {r['new_all_configured_hits']} |" for r in rows)
    human_table='\n'.join(f"| {r['profile']} | {r['hits']}/{r['configured']} | {r['estimated_wer_percent']:.1f}% ({r['provisional_errors']}/{r['reference_words']}) |" for r in hr)
    document=f'''# Reading Pod latency investigation - 19 November 2026

The selected profile uses 160 ms chunks, the original 560 ms future context,
and 80 ms microphone packets (1280 samples at 16 kHz). Threshold 82, stability 2,
coverage 0.8, shared matcher rules and boost 1.0 are unchanged.

## Actual local-sound results (estimated synthetic timings)

| Same source recording | Previous median | New median | Previous configured hits | New configured hits |
|---|---:|---:|---:|---:|
{table}

Two replays per setting per story. Latency uses only common targets so the newly
recovered dog cue does not make the median appear faster by changing the set.
All four configured poem targets fired in both new runs. The median across ALL
new poem events is about 1.05 seconds; the common-three median above is the fair
comparison with the original 1.80-second result. These are digital sound onsets,
not ASR word latency, acoustic speaker delay or projected first-frame timing.
Clean synthetic WER stayed 3/105 (2.9%) for the poem and 0/149 for the excerpt.

## Where the delay was

Saved baseline traces show about 1.07 seconds before the exact poem cue phrase
first appeared in a transcript, followed by about 0.78 seconds waiting for
eligible matcher evidence. Those are separate medians, not additive components
of one median. ASR used 560 ms future context and 560 ms chunk updates; packets
arrived every 256 ms. Transport queue waits were only a few milliseconds.
Matcher computation itself was at most about 12 ms in these trials; its larger
delay was waiting for another usable transcript, rather than CPU processing.
After subtracting sound-file lead-in, native sound output added about 71 ms.
Some excerpt sounds contain another 70-190 ms of intentional asset lead-in.

The selected profile emits smaller updates while retaining future context.
That makes usable evidence arrive sooner and recovered the poem's dog endpoint.
No similarity/coverage threshold was reduced and no timer fires unsupported cues.
The commercial apps expose no equivalent internal timings, so their precise
recognizer/tracker contribution cannot be inferred from their total sound delay.

## Existing human-recording regression

| Profile | Configured checkpoint hits | Estimated WER against provisional drafts |
|---|---:|---:|
{human_table}

The selected profile retained the same checkpoint IDs on every human recording,
with no additional duplicates. Three of seven configured targets fired under
both settings. The other four did not fire in either run; their phrases have
not been verified as spoken, so 3/7 is not a validated checkpoint-recall score. The estimated word
error increased by four edits across 150 reference words. This tradeoff is
retained explicitly: faster cues do not establish better transcription accuracy.
The human figures are estimated against existing drafts, not verbatim gold.

Hints-off regression also checked all five recordings with baseline and selected
profiles. All previously hit checkpoint IDs were retained, with no duplicate
increase. Those replays ran unpaced to check recognition/tracker quality only;
their wall-clock times are excluded from every latency table.

## Profiles rejected and measurement audit

160/160 ms chunk/right context was faster (roughly 0.4-0.5 seconds on clean
synthetic clips) but lost the human cat-story checkpoint and increased word error.
160/320 ms delayed one excerpt cue beyond six seconds; it failed the same
within-five-second detection rule used in the original product comparison.
Neither became the default.

An initial screening baseline scheduled the opening chime but its captured
output was absent. It remains archived as an output-path anomaly, not silently
converted to an ASR miss or hit. Confirmation runs independently verified a
quiet digital tone before source time zero, and captured all expected baseline
outputs except the already-missed dog. A failed Windows client import attempt
was also preserved and excluded. An initial accelerated transport attempt disconnected; its incomplete capture was excluded. Bounded no-op acknowledgements kept quality-only input from filling the socket. Tracker rescoring used native server audio positions, rather than the sender's queued-audio count; raw events and earlier counts are retained. This correction did not change the human hit result. Excerpt WER uses the canonical 149-word
normalized source, rather than a pre-existing mojibake benchmark-manifest draft;
the frozen hints and audio remained identical across profiles.

All timing runs used actual production SoundPlayer output and Windows
process-only loopback, with physical output muted then restored. A separate
two-second synthetic-silence warmup excluded one-time CUDA initialization;
the production server now also warms before reporting ready. No microphone was
opened and no sound was sent to MapMap in this investigation. Captures and
transcripts remain local; the phone was not used or changed.

## Application and remaining checks

Application status: {summary['status']}. See `output/latency-investigation-20261119/applied-settings.json`
for the actual server handshake and launch settings after deployment.
The final production-server smoke test captured all four poem sounds, with a
median of about 1.01 seconds across those four events. Speaker mute was restored.
The panel's own preflight verified SERVER_READY at 127.0.0.1:9097 with 160/560 ms
buffering. All 94 focused matcher, protocol, startup and server-management tests
passed; the CUDA-only decoder unit was skipped in Windows, while actual WSL CUDA
replays exercised decoding. See `final-verification.json` and `unit-checks.json`.
Shared defaults live in `books_to_life/runtime/nemo_defaults.py`; explicit
`--chunk-ms 560 --right-ms 560` restores legacy server buffering. The panel sends
NeMo microphone packets using that shared configuration; other models retain
their packet settings. Startup readiness now reports the actual chunk/context.

The 160 ms profile decodes about 3.5 times as often. Measured per-chunk decode
time was roughly 100 ms on this PC, so long book-length sessions with simultaneous
MapMap projection still need a sustained load/headroom check. Human live-mic
behavior, background speech, skips/repeats, physical speakers and projection
remain physical validation work. The tested subset cannot guarantee no future
misses or false cues on unseen speech.

Raw evidence is under `output/latency-investigation-20261119`: `screening-02`,
`short-chunk`, `confirmation`, `human`, `no-hints-02`, `baseline-breakdown.json`,
`stage-measurements.json`, `provenance.json`, `results.json`, and `latency-canva.csv`.
Original commercial-app comparison numbers remain unchanged in
[the product comparison](PRODUCT_COMPARISON.md); this is a subsequent Pod tuning experiment.
'''
    Path('benchmarks/LATENCY_INVESTIGATION.md').write_text(document,encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
