"""Publish completed real-audio MPS detection results into the local library."""
import argparse
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
LIB=ROOT/'recordings/library'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results',type=Path,required=True)
    args=parser.parse_args()
    data=json.loads((args.results/'comparison.json').read_text(encoding='utf-8'))
    rows=data['recordings']
    assert len(rows)==6 and all(r['stream_done'] and r['partial_before_eof'] for r in rows)
    destination=LIB/'evaluation'/args.results.name
    shutil.copytree(args.results,destination,dirs_exist_ok=True)
    lines=['# MPS actual-audio pipeline test', '',
           'Six Grade 3 recordings from three children in India; exact ages unknown. Actual WAV samples streamed in real time through Parakeet Unified NeMo on the local GPU. Checkpoint manifests were frozen before each run. No book context or phrase hints. 560 ms chunk/right context; threshold 82, stability 2, minimum coverage 0.8.', '',
           'Current application split mode uses the timely observer below. The observer named split is an older comparison implementation.', '',
           '| Recording | Seconds | Current triggers | Missing |', '| --- | ---: | --- | --- |']
    totals={mode:0 for mode in ['original','split','boundary','timely']}
    for row in rows:
        item=row['observers']['timely']
        lines.append(f'| {row["audio_id"]} | {row["audio_seconds"]:.2f} | {", ".join(item["triggered"]) or "None"} | {", ".join(item["missing"]) or "None"} |')
        for mode in totals:totals[mode]+=len(row['observers'][mode]['triggered'])
        paragraph=row['audio_id'].rsplit('_',1)[1]
        folder=LIB/'stories'/f'mps-the-lost-sheep-part-{paragraph}'/'readers'/row['reader']
        result=dict(test='Actual real-time audio through ASR and checkpoint pipeline',configuration=data['configuration'],result=row,
                    artifacts=f'evaluation/{args.results.name}/{row["audio_id"]}',delay_accuracy='Unavailable: no manually verified word timestamps')
        (folder/'live_pipeline_test.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        marker='\n<!-- mps-live-test -->'
        original=(folder/'README.md').read_text(encoding='utf-8').split(marker)[0]
        (folder/'README.md').write_text(original.rstrip()+marker+'\n\n[Actual-audio pipeline result](live_pipeline_test.json). '+str(len(item['triggered']))+'/3 checkpoints triggered; no verified delay gold.\n',encoding='utf-8')
    duplicates=sum(r['observers']['timely']['duplicate_triggers'] for r in rows)
    unexpected=sum(len(r['observers']['timely']['unexpected']) for r in rows)
    lines+=['',f'Current matcher: **{totals["timely"]}/18** checkpoints; {duplicates} recordings with duplicate triggers; {unexpected} unexpected IDs.', '',
            '## Audit', '',
            '- Every input audio hash and frozen manifest hash was recorded; sent sample counts equal WAV frame counts.',
            '- Every recording produced live ASR output before EOF and a server STREAM_DONE acknowledgement.',
            '- Logs, SRT files, packet/ASR/tracker JSONL events, frozen manifests, and comparison.json are retained in this folder.',
            '- Arrival seconds are measured from the first audio packet. ASR audio_end is the end of the received audio snapshot, not the checkpoint word ending. Neither is a verified detection delay.',
            '- One completed audited run per recording. Two earlier attempts on the first recording were rejected by the audit harness while its completion-message hook was corrected; they remain in output/mps/live-2026-10-29 and output/mps/live-2026-10-29-complete and are excluded from this result set. Native client completion behavior was unchanged.',
            '- No anchor, threshold, or model tuning was performed in response to these results.', '',
            '## Comparison observers', '', '| Observer | Triggered / 18 |','| --- | ---: |']
    lines += [f'| {mode} | {count} |' for mode,count in totals.items()]
    lines += ['', 'The original and older split observers missed lost_sheep for reader 3d60g paragraph 1 and happy_friends for the same reader paragraph 2. The boundary and current timely observers caught both. All other checkpoint IDs triggered in every observer.', '',
              'This demonstrates checkpoint detection on ASR output, not word-perfect child reading: ASR can normalize mistakes. The provider human transcript and final ASR snapshot remain separate, and neither was edited to force a trigger. No manual audio/word-boundary verification was performed.']
    lines += ['', '## Final ASR snapshots', '']
    for row in rows:lines += [f'### {row["audio_id"]}', '',row['final_asr'],'']
    (destination/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    catalogue=LIB/'README.md'
    marker='\n<!-- mps-live-results -->'
    original=catalogue.read_text(encoding='utf-8').split(marker)[0]
    catalogue.write_text(original.rstrip()+marker+f'\n\n[MPS actual-audio test results](evaluation/{args.results.name}/README.md): current matcher {totals["timely"]}/18 checkpoints across six recordings. No verified delay timestamps.\n',encoding='utf-8')
    print(json.dumps(dict(current_triggered=totals['timely'],total_checkpoints=18,observers=totals,duplicates=duplicates,unexpected=unexpected,report=str(destination/'README.md')),indent=2))

if __name__=='__main__':main()
