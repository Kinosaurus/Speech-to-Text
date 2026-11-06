"""Report all frozen challenge outcomes, including failures and raw ASR context."""
import argparse
import csv
import html
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from benchmarks.run_mps_heldout import read,write,check_frozen,digest
from benchmarks.run_false_trigger_challenges import verify,KINDS
from benchmarks.pod_pronunciation_review import annotate,reviewed_cases
from books_to_life.matching.checkpoint_matcher import normalize_text


def metrics(rows,policy,label):
    positives=[r for r in rows if r['expected']]; negatives=[r for r in rows if not r['expected']]
    emits=lambda row:'target' in row['policies'][policy][label]['emitted']
    return dict(cases=len(rows),script_positive_cases=len(positives),script_negative_cases=len(negatives),
        positive_emissions=sum(emits(r) for r in positives),missed_positive_cases=sum(not emits(r) for r in positives),
        false_triggers=sum(emits(r) for r in negatives),negative_cases_without_trigger=sum(not emits(r) for r in negatives))


def enrich(output,rows,jobs):
    for row in rows:
        job=jobs[row['id']]
        events=[json.loads(s) for s in (output/'streams'/(row['id']+'.events.jsonl')).read_text(encoding='utf-8').splitlines()]
        latest=''; context={}
        for event in events:
            if event['kind']=='segments': latest=' '.join(s['text'] for s in event['segments'])
            if (event['kind']=='tracker' and event['mode']=='timely' and event['scene']=='target' and event['triggered']):
                context[event['book']]=latest
        for policy in ('default','required'):
            text=context.get(policy)
            row['policies'][policy]['asr_at_target_trigger']=text
            expected_wrong=job['expected_spoken_anchor'] if row['category']=='close_wrong_word' else None
            row['policies'][policy]['scripted_wrong_phrase_present_at_trigger']=bool(text and expected_wrong
                and ' '+normalize_text(expected_wrong)+' ' in ' '+normalize_text(text)+' ')
        row['audio_seconds']=next(r['audio_seconds'] for r in read(output/'audio-inventory.json') if r['id']==row['id'])


def review(output,rows,jobs):
    dest=output/'review';dest.mkdir(exist_ok=True); cards=[];sheet=[]
    accepted=reviewed_cases()
    ordered=sorted(rows,key=lambda r:(not r['policies']['default']['false_trigger'],
        not any(r['policies'][p]['missed_target'] for p in ('default','required')),r['id']))
    for row in ordered:
        job=jobs[row['id']];state=row['policies']['default'];other=row['policies']['required']
        if not any(row['policies'][p]['false_trigger'] or row['policies'][p]['missed_target'] for p in ('default','required')):
            continue
        esc=lambda value:html.escape(str(value))
        label=accepted.get(row['id'])
        if label and digest(Path(job['audio']))!=label['audio_sha256']:
            label=None
        acceptance=('<p><b>User accepted: should count for the pod (3 November).</b> '
            +esc(label['hearing_note'])+'</p>') if label else '<p>Awaiting user listening review.</p>'
        cards.append('<article><h2>'+esc(row['id'])+'</h2><p><b>Book anchor:</b> '+esc(row['anchor'])+'</p>'
            '<p><b>Requested synthetic speech:</b> '+esc(row['script'])+'</p>'
            '<audio controls preload="none" src="../inputs/'+esc(row['id'])+'/audio.wav"></audio>'
            +acceptance+'<p>Original strict-literal expectation: '+esc(row['expected'])+'. Default target emitted: '+esc(state['target_emitted'])
            +'. Required-word observer emitted: '+esc(other['target_emitted'])+'.</p>'
            '<details><summary>Recognition and automated diagnosis</summary><p>Default trigger ASR: '
            +esc(state['asr_at_target_trigger'])+'</p><p>Final ASR: '+esc(row['final_asr'])+'</p></details></article>')
        sheet.append(dict(id=row['id'],category=row['category'],book_anchor=row['anchor'],script=row['script'],
            script_expected_emit=row['expected'],default_emitted=state['target_emitted'],required_observer_emitted=other['target_emitted'],
            asr_at_default_trigger=state['asr_at_target_trigger'] or '',final_asr=row['final_asr'],
            audio=str(Path(job['audio']).resolve()),human_heard=(label['human_heard_word'] or '') if label else '',
            human_should_emit=label['user_should_emit'] if label else '',reviewer='user' if label else '',
            notes=('User accepts this contextual variant for the pod. '+label['hearing_note']+
                ' Original strict-literal expectation retained separately.') if label else ''))
    if sheet:
        path=dest/'manual_review.csv'
        if not path.exists():
            with path.open('w',encoding='utf-8',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=list(sheet[0]));writer.writeheader();writer.writerows(sheet)
    (dest/'index.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><title>Pronunciation acceptance review</title>'
        '<style>body{max-width:950px;margin:35px auto;padding:0 22px;font:17px/1.6 system-ui;color:#203040}'
        'article{border-top:2px solid #ccd5df;padding:22px 0}audio{width:100%}summary{cursor:pointer}</style>'
        '<h1>Pronunciation acceptance review</h1><p>Synthetic adult Microsoft Zira speech. '
        'Scripts are synthesis requests, not independent human transcriptions. All 45 trials are retained. '
        'These cases were originally flagged under strict literal-word expectations. '
        'Later user acceptance is shown separately and does not change the original trials. '
        'Unreviewed cases retain blank human labels.</p>'
        '<p>'+str(len(sheet))+' originally flagged cases. <a href="manual_review.csv">Review CSV</a></p>'+''.join(cards)+'</html>',encoding='utf-8')
    return len(sheet)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    output=parser.parse_args().output.resolve();done=read(output/'completed.json');protocol=check_frozen(output,model_hash=True)
    jobs={j['id']:j for j in verify(output,audio=True)};rows=read(output/'results.json')['cases']
    assert len(rows)==done['fresh_streams']==45
    assert [r['id'] for r in rows]==protocol['ordered_recordings']
    assert all(r['delivery_audit_pass'] and r['app_observer_replay_agreement'] for r in rows)
    assert not any(r['policies'][p]['duplicate_target_emissions'] for r in rows for p in ('default','required'))
    enrich(output,rows,jobs)
    totals={p:{label:metrics(rows,p,label) for label in ('before','after')} for p in ('default','required')}
    groups={kind:{p:metrics([r for r in rows if r['category']==kind],p,'after') for p in ('default','required')} for kind in KINDS}
    failures=[dict(id=r['id'],category=r['category'],anchor=r['anchor'],spoken_target_word=r['spoken_target_word'],
        default_asr_at_trigger=r['policies']['default']['asr_at_target_trigger'],
        scripted_wrong_phrase_present_at_default_trigger=r['policies']['default']['scripted_wrong_phrase_present_at_trigger'],
        emitted_before='target' in r['policies']['default']['before']['emitted'],
        required_observer_emitted=r['policies']['required']['target_emitted'])
        for r in rows if r['policies']['default']['false_trigger']]
    prior=read(output/'text-diagnostics.json')
    text_metrics={p:{label:dict(
        false_triggers=sum(not r['expected'] and 'target' in r[p][label]['emitted'] for r in prior['cases']),
        missed_positive_cases=sum(r['expected'] and 'target' not in r[p][label]['emitted'] for r in prior['cases']))
        for label in ('before','after')} for p in ('default','required')}
    diff=subprocess.run(['git','diff','--check'],cwd=ROOT,capture_output=True,text=True);assert diff.returncode==0,diff.stdout+diff.stderr
    count=review(output,rows,jobs)
    report=dict(date='2026-11-02',scope='Frozen full-stream synthetic adult false-trigger challenges',
        execution=dict(fresh_streams=45,anchors=5,categories=9,manifest_policies_per_callback=2,
            audio_seconds=sum(r['audio_seconds'] for r in rows),trials_per_case=1,all_trials_retained=True,
            all_audio_delivered=True,all_partial_before_eof=True,all_stream_done=True,
            all_app_observer_replay_agreement=True,duplicate_target_emissions=0),
        source=protocol['source'],expected_policy=protocol['expected_policy'],
        server_environment=read(Path(protocol['runtime_reference']).parent/'server-environment.json'),
        pre_audio_setup_failures=[read(ROOT/'output/false-trigger-challenges-2026-11-02/ABORTED.json')],
        configuration=protocol['configuration'],model=protocol['model'],lexicon=protocol['lexicon'],
        totals=totals,by_category=groups,false_triggers_default=failures,
        matcher_only_text_diagnostics=dict(kind=prior['kind'],cases=45,totals=text_metrics),
        integrity=dict(no_asr_or_matcher_tuning=True,runtime_matches_frozen_heldout_batch=True,
            scripts_manifests_and_audio_unchanged=True,source_sha256=protocol['source_sha256'],
            baseline_sha256=protocol['baseline_sha256'],all_checks_passed=True,diff_check_passed=True),
        listening_review=dict(flagged_cases=count,human_labels_blank=True,
            path=(output/'review/index.html').relative_to(ROOT).as_posix()),
        limits=protocol['limits']+[
            'Challenge counts are designed counterexamples, not population precision/recall or child-reading accuracy.',
            'Both manifest policies share each stream. The required-word observer was predeclared; production manifests were not tightened.',
            'The previous matcher is replayed on identical current ASR callbacks; this is not an ASR-model comparison.',
            'Final ASR can differ from the trigger snapshot. Trigger context is recorded separately.',
            'Required-word checks can reject valid ASR substitutions and cannot prevent false triggers when ASR itself substitutes the expected word.'],
        cases=rows,artifacts=output.relative_to(ROOT).as_posix())
    annotate(report)
    write(output/'summary.json',report)
    write(ROOT/'benchmarks/results/false-trigger-challenges-2026-11-02.json',report)
    print(json.dumps({k:report[k] for k in ('execution','totals','false_triggers_default','listening_review')},indent=2))


if __name__=='__main__':main()
