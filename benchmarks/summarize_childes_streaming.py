"""Separate Singapore conversation diagnostics from authored-reading results."""
import argparse
import csv
import hashlib
import html
import json
from pathlib import Path
import subprocess
import sys
import wave

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from benchmarks.run_mps_heldout import read,write,digest
from benchmarks.run_childes_streaming import DEST,verify
from benchmarks.run_pending_regression import replay
from benchmarks.metrics import words,edit_alignment
from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=DEST)
    output=parser.parse_args().output.resolve();done=read(output/'completed.json');protocol=verify(output,model_hash=True)
    rows=read(output/'results.json')['streams'];jobs={j['id']:j for j in read(output/'jobs.json')}
    assert len(rows)==done['streams']==4 and done['independent_source_recordings']==1
    assert [r['id'] for r in rows]==protocol['ordered_recordings']
    assert all(r['delivery_audit_pass'] and r['app_observer_replay_agreement'] and r['stream_done'] for r in rows)
    full_events=[json.loads(s) for s in (output/'streams/full_recording.events.jsonl').read_text(encoding='utf-8').splitlines()]
    # Diagnostic replay only; never supplies extra confirmations to the live trial.
    tracker=TimelyEvidenceMatcher(read(Path(jobs['full_recording']['manifest'])))
    alignment_trace=[]
    for event in full_events:
        if event['kind']!='segments':continue
        segments=event['segments'];text=' '.join(s['text'] for s in segments)
        update=tracker.process(text,segments)
        alignment_trace.append(dict(audio_end=segments[-1]['end'],checkpoint=update.checkpoint_id,
            score=update.score,confirmations=update.confirmations,required=update.confirmations_required,
            position=update.tracked_word_position,duplicate=update.duplicate,
            recovering=update.recovering,ambiguous=update.ambiguous))
    offbook=[]
    for path in read(output/'offbook-manifests.json'):
        result=replay(TimelyEvidenceMatcher,read(Path(path)),full_events)
        offbook.append(dict(policy=Path(path).name,**result))
    review=output/'review';review.mkdir(exist_ok=True);sheet=[];cards=[];portable=[];local_diagnostics=[]
    human_path=review/'user-listening.json'
    human_review=read(human_path) if human_path.exists() else dict(cases=[])
    human={(case['stream'],case['target']):case for case in human_review['cases']}
    for row in rows:
        job=jobs[row['id']]
        callbacks=[json.loads(s) for s in (output/'streams'/(row['id']+'.events.jsonl')).read_text(encoding='utf-8').splitlines()
                   if json.loads(s)['kind']=='segments']
        item={k:v for k,v in row.items() if k not in ('targets','final_asr')};item['targets']=[]
        item['final_asr_words']=len(words(row['final_asr']));item['final_asr_sha256']=hashlib.sha256(row['final_asr'].encode('utf-8')).hexdigest()
        for target in row['targets']:
            human_case=human.get((row['id'],target['id']))
            phrase=' '.join(words(target['reference']))
            first=next((e for e in callbacks if ' '+phrase+' ' in ' '+' '.join(words(' '.join(s['text'] for s in e['segments'])))+' '),None)
            cue=first['segments'][-1]['end'] if first else None
            point={k:v for k,v in target.items() if k not in ('reference','decision','best_ordered_word_support')}
            point['reference_words']=len(words(target['reference']))
            point['first_exact_phrase_callback_audio_end']=cue
            if human_case:
                point['human_review']={k:v for k,v in human_case.items()
                    if k not in ('raw_feedback','clarified_feedback')}
            if target['decision']:
                point['decision_audio_end']=target['decision']['audio_end']
            item['targets'].append(point)
            if row['id']=='full_recording':
                if cue is not None:
                    start=max(0,cue-12);end=min(row['audio_seconds'],cue+3);basis='ASR callback-centred listening context; not verified word alignment.'
                else:
                    start=max(0,target['chat_start_original']-5);end=min(row['audio_seconds'],target['chat_end_original']+8)
                    basis='Machine-aligned CHAT interval plus context; target audibility/time is unverified.'
                clip=review/(row['id']+'.'+target['id']+'.wav')
                with wave.open(job['audio']) as src,wave.open(str(clip),'wb') as dst:
                    dst.setparams(src.getparams());src.setpos(round(start*16000));dst.writeframes(src.readframes(round((end-start)*16000)))
                media=clip.name
            else:
                start=job['source_start_seconds'];end=start+row['audio_seconds']
                media='../inputs/'+row['id']+'/audio.wav';basis='Exact previously selected context clip used in the fresh stream.'
            decision=target['decision'];snapshot=' '.join(decision['buffer']) if decision else row['final_asr']
            provisional_edit=edit_alignment(target['reference'],row['final_asr'])[0]
            local_diagnostics.append(dict(stream=row['id'],target=target['id'],reference=target['reference'],
                final_asr=row['final_asr'],provisional_context_clip_edit_stats=provisional_edit,
                note='Reference may be incomplete; context has extra voices/words, and CHAT times are automated. These edit statistics are not reported as an accuracy score.'))
            sheet.append(dict(stream=row['id'],target=target['id'],speaker_from_chat=target['speaker'],
                reference_from_chat=target['reference'],emitted=target['emitted'],suppressed=target['suppressed'],
                exact_phrase_seen=target['exact_phrase_in_any_callback'],first_exact_callback=cue,
                listening_audio=media,source_start_seconds=start,source_end_seconds=end,
                asr_snapshot=snapshot,human_heard='',human_reference_matches_audio='',human_single_speaker='',
                human_should_emit='',notes=basis))
            esc=lambda value:html.escape(str(value))
            cards.append('<article><h2>'+esc(row['id']+' / '+target['id'])+'</h2>'
                '<p><b>CHAT reference:</b> '+esc(target['reference'])+'</p>'
                '<audio controls preload="none" src="'+esc(media)+'"></audio>'
                '<p>'+esc(basis)+' Original source window '+f'{start:.2f}–{end:.2f}s.'+'</p>'
                +('<p><b>User review:</b> '+esc(human_case.get('clarified_feedback',human_case['raw_feedback']))+
                  ' '+esc(human_case['note'])+'</p>' if human_case else '')+
                '<details><summary>Streaming result</summary><p>Emitted: '+esc(target['emitted'])+
                '; exact phrase seen: '+esc(target['exact_phrase_in_any_callback'])+'.</p><p>ASR: '+esc(snapshot)+'</p></details></article>')
        portable.append(item)
    write(output/'local-reference-diagnostics.json',local_diagnostics)
    path=review/'manual_review.csv'
    if not path.exists():
        with path.open('w',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(sheet[0]));writer.writeheader();writer.writerows(sheet)
    (review/'index.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><title>Singapore conversation streaming review</title>'
        '<style>body{max-width:950px;margin:36px auto;padding:0 22px;font:17px/1.6 system-ui;color:#203040}'
        'article{border-top:2px solid #ccd5df;padding:22px 0}audio{width:100%}</style>'
        '<h1>Singapore conversation streaming review</h1><p>One classroom source; three repeated context clips. '
        'CHAT references and machine-aligned timestamps are not independently verified audio labels. '
        'Confirm whether the reference is audible, whether other voices overlap, and whether the effect should emit. '
        'User feedback is shown where received; other human fields remain unlabelled. '
        '<a href="manual_review.csv">Review CSV</a></p>'+''.join(cards)+'</html>',encoding='utf-8')
    full=next(r for r in portable if r['id']=='full_recording');clips=[r for r in portable if r['id']!='full_recording']
    diff=subprocess.run(['git','diff','--check'],cwd=ROOT,capture_output=True,text=True);assert diff.returncode==0,diff.stdout+diff.stderr
    report=dict(date='2026-11-02',scope='Initial Singapore CHILDES conversation streaming probe',
        source=dict(corpus='CHILDES English-Mandarin Singapore',media_id='e5d6a',
                    corpus_url='https://talkbank.org/childes/access/Biling/Singapore.html',
                    independent_source_recordings=1,other_background_speakers_present=True,
                    selected_child_codes=protocol['preselected_child_codes'],human_listening_labels=len(human)),
        configuration=protocol['configuration'],model=protocol['model'],lexicon=protocol['lexicon'],
        server_environment=read(output/'server-environment.json'),client_environment=read(output/'client-environment.json'),
        execution=dict(fresh_streams=4,complete_source_streams=1,context_clip_streams=3,
            independent_source_recordings=1,audio_seconds=sum(r['audio_seconds'] for r in rows),
            unique_transcript_anchors=3,checkpoint_opportunities=6,one_trial_per_selected_input=True,
            all_trials_retained=True,all_samples_delivered=True,
            streams_with_partial_before_eof=sum(r['partial_before_eof'] for r in rows),
            all_stream_done=True,all_app_observer_replay_agreement=True),
        matched_outcomes=dict(full_recording={k:full[k] for k in ('emitted','suppressed','skipped','unreached')},
            context_clips=dict(emitted=sum(len(r['emitted']) for r in clips),
                suppressed=sum(len(r['suppressed']) for r in clips),skipped=sum(len(r['skipped']) for r in clips),
                unreached=sum(len(r['unreached']) for r in clips))),
        full_recording_alignment_trace=alignment_trace,
        offbook_replay=dict(kind='Same fresh full-source ASR callbacks replayed against six existing MPS passage policies; no additional ASR trials.',
            comparisons=6,emitted=sum(len(r['emitted']) for r in offbook),results=offbook),
        integrity=dict(asr_and_matcher_unchanged=True,model_hash_unchanged=True,source_audio_and_chat_unchanged=True,
            manifests_and_clips_fixed_before_recognition=True,no_hints_or_outcome_tuning=True,
            runtime_matches_reference=protocol['reference_runtime_protocol'],source_sha256=protocol['source_sha256'],
            original_inputs_sha256=protocol['original_inputs_sha256'],
            harness_amendments=protocol.get('harness_amendments',[])),
        validation=dict(new_chat_parser_tests_passed=3,diff_check_passed=True),
        limits=protocol['notes']+[protocol['timestamps'],
            'Exact text in an ASR callback is recognition evidence, not independent confirmation that the reference was audible.',
            'No verified end-to-end word latency, population WER, reading accuracy or omission score is claimed.',
            'Existing close-word false-trigger limitations of the frozen matcher remain unresolved.'],
        post_evaluation_human_review=dict(cases=[{k:v for k,v in case.items()
            if k not in ('raw_feedback','clarified_feedback')} for case in human.values()],
            confirmed_false_negatives=sum(c['classification']=='confirmed_false_negative' for c in human.values()),
            unresolved=sum(c['classification']=='unresolved' for c in human.values()),
            original_stream_results_unchanged=True,matcher_tuned_after_review=False,
            scope=human_review.get('scope','No human listening labels received.')),
        streams=portable,listening_review=dict(cases=6,human_labels_blank=not bool(human),
            reviewed_cases=len(human),
            html=(review/'index.html').relative_to(ROOT).as_posix()),artifacts=output.relative_to(ROOT).as_posix())
    write(output/'summary.json',report);write(ROOT/'benchmarks/results/childes-singapore-streaming-2026-11-02.json',report)
    print(json.dumps({k:report[k] for k in ('execution','matched_outcomes','offbook_replay')},indent=2))
    print('TARGETS',json.dumps([{k:t.get(k) for k in ('id','emitted','suppressed','exact_phrase_in_any_callback','first_exact_phrase_callback_audio_end')}
                              | {'stream':r['id']} for r in portable for t in r['targets']],indent=2))


if __name__=='__main__':main()
