"""Compare nine saved no-hint streams with eighteen fresh hinted streams."""
import hashlib
import json
from pathlib import Path
import shutil
import statistics
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from benchmarks.annotate_mps_timing import boundary_wall

LIB=ROOT/'recordings/library'
OUT=ROOT/'output/hint-comparison-2026-10-30'
DEST=LIB/'evaluation/hint-comparison-2026-10-30'
CONDITIONS=['none','moving','whole']

def load(path):return json.loads(path.read_text(encoding='utf-8'))
def write(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def fmt(value):return '—' if value is None else f'{value:+.3f}s'

def main():
    protocol=load(OUT/'protocol.json')
    jobs=protocol['jobs']
    assert len(jobs)==9
    DEST.mkdir(parents=True,exist_ok=True)
    shutil.copytree(OUT,DEST,dirs_exist_ok=True)
    all_rows=[]
    records=[]
    final_text=[]
    for job in jobs:
        folder=LIB/job['path']
        assert hashlib.sha256((folder/'audio.wav').read_bytes()).hexdigest()==job['audio_sha256']
        assert hashlib.sha256((folder/'checkpoints.json').read_bytes()).hexdigest()==job['manifest_sha256']
        endpoints={r['id']:r for r in load(LIB/job['timing'])['checkpoints'] if r['audio_id']==job['id']}
        ids=[c['id'] for c in load(folder/'checkpoints.json')['checkpoints']]
        assert set(ids)==set(endpoints)
        observed={}
        for condition in CONDITIONS:
            if condition=='none':
                base=LIB/job['baseline_folder']
                events_path=base/(job['id']+'.events.jsonl')
                comparison=load(base/'comparison.json')
                base_result=next(r for r in comparison['recordings'] if r['audio_id']==job['id'])
                assert base_result['audio_sha256']==job['audio_sha256'] and base_result['manifest_sha256']==job['manifest_sha256']
                text=base_result['final_asr']
                source=job['baseline_folder']
                hints=None
            else:
                base=OUT/condition/job['id']
                result=load(base/'result.json')
                assert result['audio_sha256']==job['audio_sha256'] and result['manifest_sha256']==job['manifest_sha256']
                assert result['stream_done'] and result['live_before_eof']
                assert result['duplicates']==0 and not result['unexpected']
                events_path=base/'transcript.events.jsonl'
                text=result['final_asr']
                source=(DEST/condition/job['id']).relative_to(LIB).as_posix()
                hints=result['initial_hint_config']
            events=[json.loads(s) for s in events_path.read_text(encoding='utf-8').splitlines()]
            packets=[e for e in events if e['kind']=='audio']
            triggers=[e for e in events if e['kind']=='tracker' and e['mode']=='timely' and e['triggered']]
            assert len({t['scene'] for t in triggers})==len(triggers)
            sent=[e for e in events if e['kind']=='book_context_sent']
            distinct=sorted({e['hints']['hotwords'] for e in sent if e['hints'].get('hotwords')})
            captured=[]
            for ident in ids:
                endpoint=endpoints[ident]
                trigger=next((t for t in triggers if t['scene']==ident),None)
                end=endpoint['estimated_end_seconds']
                delay=trigger['wall']-boundary_wall(packets,end,16000) if trigger else None
                sensitivity=[trigger['wall']-boundary_wall(packets,e,16000) for e in endpoint['model_endpoint_range_seconds']] if trigger else []
                captured.append(dict(checkpoint=ident,triggered=trigger is not None,estimated_delay_seconds=delay,
                    estimated_endpoint_seconds=end,delay_model_range_seconds=[min(sensitivity),max(sensitivity)] if sensitivity else None,
                    endpoint_review_flags=endpoint['review_flags'],skipped=trigger['skipped'] if trigger else [],manual_verification=False))
            observed[condition]=dict(checkpoints=captured,caught=sum(r['triggered'] for r in captured),
                missing=[r['checkpoint'] for r in captured if not r['triggered']],
                median_delay_seconds=statistics.median([r['estimated_delay_seconds'] for r in captured if r['triggered']]) if any(r['triggered'] for r in captured) else None,
                distinct_live_hotword_sets=len(distinct),hint_updates_sent=len(sent),hint_config=hints,source=source,final_asr=text)
            final_text.append((job['id'],condition,text))
        for position,ident in enumerate(ids):
            row=dict(id=job['id'],checkpoint=ident,conditions={c:observed[c]['checkpoints'][position] for c in CONDITIONS})
            for c in ['moving','whole']:
                old,new=row['conditions']['none'],row['conditions'][c]
                row['conditions'][c]['change_from_no_hints_seconds']=(new['estimated_delay_seconds']-old['estimated_delay_seconds'] if old['triggered'] and new['triggered'] else None)
            all_rows.append(row)
        record=dict(id=job['id'],path=job['path'],conditions=observed)
        records.append(record)
        write(folder/'hint_comparison.json',dict(protocol='evaluation/hint-comparison-2026-10-30/protocol.json',result=record))
        marker='\n<!-- hints-comparison -->'
        original=(folder/'README.md').read_text(encoding='utf-8').split(marker)[0]
        (folder/'README.md').write_text(original.rstrip()+marker+'\n\n[Moving/whole-passage versus no-hints comparison](hint_comparison.json). Actual audio; acoustic delay estimates remain provisional.\n',encoding='utf-8')
    summary={}
    for condition in CONDITIONS:
        rows=[r['conditions'][condition] for r in all_rows]
        delays=[r['estimated_delay_seconds'] for r in rows if r['triggered']]
        summary[condition]=dict(caught=len(delays),configured=len(rows),median_delay_seconds=statistics.median(delays),
            minimum_delay_seconds=min(delays),maximum_delay_seconds=max(delays),negative_estimates=sum(d<0 for d in delays),
            more_than_one_second_early_estimates=sum(d < -1 for d in delays))
        if condition!='none':
            pairs=[r for r in all_rows if r['conditions']['none']['triggered'] and r['conditions'][condition]['triggered']]
            changes=[r['conditions'][condition]['change_from_no_hints_seconds'] for r in pairs]
            summary[condition].update(shared_with_baseline=len(changes),median_paired_delay_change=statistics.median(changes),
                earlier_by_over_50ms=sum(d<-.05 for d in changes),later_by_over_50ms=sum(d>.05 for d in changes),within_50ms=sum(abs(d)<=.05 for d in changes),
                newly_caught=[(r['id'],r['checkpoint']) for r in all_rows if not r['conditions']['none']['triggered'] and r['conditions'][condition]['triggered']],
                lost=[(r['id'],r['checkpoint']) for r in all_rows if r['conditions']['none']['triggered'] and not r['conditions'][condition]['triggered']])
    write(DEST/'scored.json',dict(summary=summary,recordings=records,checkpoints=all_rows))
    lines=['# Moving hints and whole-passage phrases: real-audio comparison', '',
        '30 October 2026. Nine recordings; eighteen new paced audio streams. Saved no-hints streams are the baseline. Same audio hashes, frozen checkpoint manifests, matcher/settings, Parakeet model and boost=1.0. No threshold or anchor tuning during evaluation.', '',
        'Moving uses the existing application BookContext defaults: next checkpoint plus two lookahead; phrases change with confirmed progress. Whole uses fixed chunks covering both MPS story paragraphs, or the full published Kites/Billy/Tom text, packed to <=16 words, <=32 phrases and <=200 characters per phrase. NeMo consumes phrase hotwords, not the full-passage prompt field.', '',
        'Timing uses the same previously estimated small/medium Whisper endpoints, mapped onto each run\'s actual packet-send clock. These are automatic acoustic estimates, not listening-verified gold. Model-dependent word attempts and uncertain source editions remain flagged. Model spread is not a confidence interval.', '',
        '**Outcome:** No hints remains the strongest configuration in this comparison. Moving hints recovered no misses and made one Billy checkpoint substantially later. Whole-passage phrases lost Tom\'s first checkpoint and produced a clearly concerning early comic-books activation, as well as longer delays. Counts are fired IDs, not validated correct activations.', '',
        '| Condition | Triggered IDs | Median estimated delay | Delay range |', '| --- | ---: | ---: | --- |']
    for c,s in summary.items():lines.append(f'| {c} | {s["caught"]}/27 | {s["median_delay_seconds"]:.3f}s | {s["minimum_delay_seconds"]:.3f} to {s["maximum_delay_seconds"]:.3f}s |')
    lines+=['', '## Material regressions', '',
        '- Billy seven_years_old: no hints +1.833s; moving +6.083s; whole +13.656s. Final cookies_and_chess remains missed in all three conditions.',
        '- Kites see_kites: no hints +0.650s; whole +5.384s. Whole-hinted recognition contains repeated earlier phrases.',
        '- Tom whole: secret_place was skipped and comic_books_and_toys fired at 11.571s wall time from the first packet, after only 11.264s of source audio had arrived. Its acoustically estimated spoken endpoint is 30.160s; drift-corrected estimate is -19.843s. This is an early-activation warning, not a latency improvement.',
        '- The Tom trigger snapshot was: Tom and his family lived in a busy city. There was always something to see and hear. Sometimes Tom wanted a secret place tom decided to call his. The actual comic-books anchor is absent. The hinted ASR supplied later-story wording and the matcher advanced to the later scene. This exposes a failure of the combined hinted recognition and catch-up policy; it does not establish which component alone caused the failure.',
        '- The tiny negative MPS riverside estimates (about 16–22ms) are within the scale of unverified word timing and should not be equated with the Tom regression.']
    lines+=['','## Per recording','', '| Recording | No hints | Moving | Whole passage |', '| --- | --- | --- | --- |']
    for r in records:
        cells=[f'{r["conditions"][c]["caught"]}/3; median {fmt(r["conditions"][c]["median_delay_seconds"])}' for c in CONDITIONS]
        lines.append(f'| {r["id"]} | '+' | '.join(cells)+' |')
    lines+=['','## Paired changes on checkpoints detected in both conditions','',
        'Negative change means earlier than no hints. Misses are excluded from paired medians and are listed separately; comparing overall medians alone can hide that change in the detected set.', '',
        '| Hint condition | Shared checkpoints | Median paired change | Earlier >50 ms | Within 50 ms | Later >50 ms |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for c in ['moving','whole']:
        s=summary[c]
        lines.append(f'| {c} | {s["shared_with_baseline"]} | {fmt(s["median_paired_delay_change"])} | {s["earlier_by_over_50ms"]} | {s["within_50ms"]} | {s["later_by_over_50ms"]} |')
        lines+=[]
    lines+=['','## Newly caught and lost checkpoints','']
    for c in ['moving','whole']:
        s=summary[c]
        lines.append(f'- {c}: newly caught {s["newly_caught"]}; lost {s["lost"]}.')
    lines+=['','## All checkpoint delays','', '| Recording | Checkpoint | No hints | Moving | Whole |', '| --- | --- | ---: | ---: | ---: |']
    for r in all_rows:
        cells=[fmt(r['conditions'][c]['estimated_delay_seconds']) if r['conditions'][c]['triggered'] else 'Missed' for c in CONDITIONS]
        lines.append(f'| {r["id"]} | {r["checkpoint"]} | '+' | '.join(cells)+' |')
    lines+=['','## Interpretation limits','',
        '- Single run per recording/condition, with no fresh no-hints replication; small differences can be runtime variation. Baseline MPS runs are from 29 October, other baseline runs from 30 October.',
        '- Runs were ordered moving first, then whole, without counterbalancing. This is an exploratory comparison rather than a repeated statistical experiment.',
        '- Moving uses the existing checkpoint-phrase formatting: commas delimit NeMo phrases, so commas inside an anchor split it into shorter hints, and automatic phrases are bounded to 16 words/100 characters. Whole phrases remove punctuation and pack the full source into <=16-word chunks. This compares two concrete hint policies, not context amount in isolation.',
        '- Nine recordings are only six distinct readers and a few texts; the two MPS paragraphs per child are correlated.',
        '- Positive reading samples only: this does not measure wrong activations during unrelated speech, adult prompting, negated phrases or skipped text.',
        '- A hinted recognizer can normalize or infer expected words. A recovered checkpoint does not prove that a child pronounced the word correctly. Billy\'s final chess/cheat/cheap attempt remains a specific listening-review case.',
        '- Full Tom text includes a published ending not read in this clip; it has no configured checkpoint here, so this trial cannot test false triggers on that ending.',
        '- Negative delay estimates are preserved. They may indicate early activation or endpoint-estimation error, and need listening review.',
        '- Every fresh stream delivered all samples, produced live recognition before EOF, received STREAM_DONE, and had application triggers identical to the timely observer. No duplicate triggers or unexpected IDs were allowed by the audit.', '',
        'protocol.json preserves source/baseline paths and hashes. Per-condition folders contain the exact hint files/configuration, frozen manifests, audio-packet and ASR event logs, SRT and application logs. scored.json contains all calculations. Source audio remains in the library reader folders.', '',
        '## Final ASR snapshots','']
    for ident,condition,text in final_text:lines += [f'### {ident}: {condition}','',text,'']
    (DEST/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    path=LIB/'README.md'
    marker='\n<!-- nine-recording-hint-comparison -->'
    original=path.read_text(encoding='utf-8').split(marker)[0]
    path.write_text(original.rstrip()+marker+'\n\n[Moving hints and whole-passage phrases versus no hints: nine-recording live comparison](evaluation/hint-comparison-2026-10-30/README.md).\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
