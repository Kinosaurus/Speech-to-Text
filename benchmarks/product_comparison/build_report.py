"""Export the local matched-content synthetic pilot, with explicit scope."""
import csv
import hashlib
import html
import json
from pathlib import Path
import statistics


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def aggregate(name,book,trials,ids,scope):
    scores=[read(t/'score.json') for t in trials]
    events=[[e for e in s['events'] if e['id'] in ids] for s in scores]
    if any({e['id'] for e in es}!=set(ids) for es in events):
        raise ValueError('Expected targets missing from score file')
    delays=[e['effect_delay_seconds'] for es in events for e in es if e['hit']]
    row=dict(system=name,book=book,targets_per_replay=len(ids),
             median_effect_latency_seconds=statistics.median(delays) if delays else None,
             checkpoints_hit=sum(e['hit'] for es in events for e in es),
             expected_checkpoints=len(ids)*len(trials),replays=len(trials),status=scope)
    detail=dict(trials=[str(t) for t in trials],target_ids=ids,
                per_trial_medians=[statistics.median([e['effect_delay_seconds'] for e in es if e['hit']])
                                   if any(e['hit'] for e in es) else None for es in events],
                events=events,largest_observed_delay_seconds=max(delays) if delays else None,
                earliest_observed_delay_seconds=min(delays) if delays else None)
    return row,detail


def build(root):
    work=Path('output/novel-cue-annotation-20261119-results')
    freeze_path=work/'annotation-freeze.json';freeze=read(freeze_path)
    for name,digest in freeze['files'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:
            raise ValueError('Frozen annotation changed')
    annotations=read(work/'annotations.json')
    ids=[a['id'] for a in annotations['annotations'] if a['status']=='causally_verified']
    novel_trials=[Path('output/novel-cue-annotation-20261119-validation/full-01'),
                  Path('output/novel-cue-annotation-20261119-validation-repeat/full-01')]
    expected_freeze=hashlib.sha256(freeze_path.read_bytes()).hexdigest()
    if any(read(t/'score.json')['freeze_sha256']!=expected_freeze for t in novel_trials):
        raise ValueError('Evaluation scores use a different detector')
    pod_moon=[work/'pod-moon-trial-01',work/'pod-moon-trial-02']
    lion_ids=[e['id'] for e in read(root/'readmio-trial-01/score.json')['events']]
    plans=[('Reading Pod (NeMo + shared matcher)','The Lion and the Mouse — 147-word excerpt',
            [root/'pod-readmio-trial-02',root/'pod-readmio-trial-03'],lion_ids,'estimated synthetic pilot; four matched targets'),
           ('Readmio 2.7.2','The Lion and the Mouse — 147-word excerpt',
            [root/'readmio-trial-01',root/'readmio-trial-02'],lion_ids,'estimated synthetic pilot; first run calibrated detector'),
           ('Reading Pod (NeMo + shared matcher)','The Moon — Robert Louis Stevenson',pod_moon,ids,
            'estimated synthetic pilot; three independently verified common targets'),
           ('Novel Effect 4.2.9','The Moon — Robert Louis Stevenson',novel_trials,ids,
            'estimated synthetic pilot; frozen waveform detector; three targets, not complete vendor cue set')]
    rows=[];details={}
    for name,book,trials,targets,scope in plans:
        row,detail=aggregate(name,book,trials,targets,scope)
        rows.append(row);details[name+' / '+book]=detail
    diagnostic,diag_detail=aggregate('Reading Pod (NeMo + shared matcher)','The Moon',pod_moon,
                                    ['opening','cat','mouse','dog'],'four configured candidates; dog missed twice')
    restoration_path=root/'phone-restoration-final.json'
    restored=read(restoration_path) if restoration_path.exists() else {'status':'verification_pending'}
    if restored['status']!='restored':
        raise ValueError('Verify device cleanup before publishing the completed report')
    summary=dict(status='two_matched_synthetic_pairs_scored',
                 scope='Two book-specific paired pilots; not a three-way same-book ranking or human-reader accuracy test',
                 rows=rows,details=details,metric='captured digital sound/component onset minus estimated highlighted phrase ending',
                 source_voice='Microsoft David Desktop, rate 0',
                 recordings=[dict(book='The Moon',seconds=45.09,words=105,
                                  sha256=hashlib.sha256((root/'synthetic/moon-normal.wav').read_bytes()).hexdigest()),
                             dict(book='The Lion and the Mouse excerpt',seconds=57.925,words=147,
                                  sha256=hashlib.sha256((root/'synthetic/readmio-lion-normal.wav').read_bytes()).hexdigest())],
                 novel_annotation_manifest=str(work/'annotations.json'),annotation_freeze=str(freeze_path),
                 novel_automatically_verified_responses=ids,
                 pod_moon_all_four_candidates=dict(row=diagnostic,details=diag_detail),
                 phone_cleanup_pending=restored['status']!='restored',phone_restoration=str(restoration_path),
                 caveats=[
                     'Each pair uses two replays of one identical synthetic recording, not independent readers.',
                     'The Moon common set has three verified responses. Dog is unverified in Novel Effect, not a vendor miss; the separate Pod four-target result remains 6/8.',
                     'Targets were selected through calibration; Pod Moon runs predate the final common-subset selection. This is exploratory, not a preregistered comparison.',
                     'Novel Effect waveform definitions were frozen before evaluation audio was inspected; the first validation capture already existed at freeze time.',
                     'Component onsets are estimated by waveform alignment: 10 ms opening frames and 80 ms cat/mouse windows. They are not semantic labels verified by listening.',
                     'Readmio first replay calibrated its asset detector; the second used the same detector.',
                     'Median includes hits only. Readmio repeat included a 2.72-second late event.',
                     'A54 app hardware differs from Windows/WSL CUDA NeMo. This does not isolate ASR engine speed.',
                     'Digital loopback excludes physical speaker/projector delay and acoustic microphone conditions.',
                     'SAPI synthetic phrase endings are estimates; this is effect timing, not ASR word latency.',
                     'WER unavailable for commercial apps because no usable transcript is exposed; no WER inferred from hits.',
                     'Human recordings, noise, accents, repeats/skips, false positives and complete vendor cue coverage remain untested.'])
    (root/'comparison.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    with (root/'comparison-canva.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=rows[0].keys());writer.writeheader()
        writer.writerows([{**r,'median_effect_latency_seconds':f"{r['median_effect_latency_seconds']:.2f}"} for r in rows])
    table=''.join('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in
                    [r['book'],r['system'],r['targets_per_replay'],f"{r['median_effect_latency_seconds']:.2f} s",
                     f"{r['checkpoints_hit']} / {r['expected_checkpoints']}",r['replays']])+'</tr>' for r in rows)
    evidence=''.join('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in
                       [a['id'],a['phrase'],f"{a['calibration_match_ncc']:.3f}",f"{a['negative_control_ncc']:.3f}",
                        a['onset_method']])+'</tr>' for a in annotations['annotations'] if a['status']=='causally_verified')
    caveats=''.join('<li>'+html.escape(c)+'</li>' for c in summary['caveats'])
    document='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Reading Pod — estimated synthetic product pilot</title><style>
body{font:17px/1.5 system-ui;color:#17353a;background:#f5f5ed;margin:0;padding:28px}main{max-width:1150px;margin:auto}
section{background:white;border:1px solid #d8dfd2;border-radius:12px;padding:22px;margin:20px 0}
table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:10px;border-bottom:1px solid #ddd}
audio{display:block;width:100%;margin:12px 0}.scroll{overflow:auto}li{margin:8px 0}</style><main>
<h1>Product comparison · estimated synthetic pilot</h1>
<p>Two matched book-specific comparisons. Each pair received the same recording twice at 1×. No audio plays until clicked.</p>
<section class="scroll"><table><tr><th>Book</th><th>System</th><th>Targets per run</th><th>Median effect delay</th><th>Hits</th><th>Replays</th></tr>'''+table+'''</table>
<p>8/8 = four targets × two runs. 6/6 = three targets × two runs. These are selected observable responses, not proof that all of a product’s cues fired.</p>
<p>Delay = captured digital sound onset minus estimated phrase end. Negative values mean early starts. This measures the whole response pipeline, rather than ASR word latency.</p>
<p><b>Retained diagnostic:</b> Reading Pod’s original four-candidate Moon test was 6/8 at 1.80 s: the dog checkpoint missed twice. The matched Moon table excludes dog from both systems because its Novel Effect response could not be independently established.</p>
<a href="comparison-canva.csv">CSV table for Canva</a> · <a href="comparison.json">Full measurements and evidence</a></section>
<section><h2>Automatic Novel Effect annotations</h2>
<p>Before/after phrase-prefix controls isolated three repeatable changes, then fixed waveform templates were tested on two separate complete readings. The startup chime is excluded. The clock phrase overlaps the opening response and is not double-counted. Dog remains unverified. Names identify associated phrases; they do not claim that an animal sound was confirmed by listening.</p>
<div class="scroll"><table><tr><th>Target</th><th>Phrase</th><th>Calibration correlation</th><th>Negative control</th><th>Onset method</th></tr>'''+evidence+'''</table></div>
<p>The frozen detector threshold is 0.55. Full calibration capture and prefix controls were separate from the two scored evaluation captures. Local evidence and annotation hashes are linked from the JSON summary.</p></section>
<section><h2>What the numbers can support</h2><ul>'''+caveats+'''</ul>
<p>Production shared matcher: threshold 82, stability 2, coverage 0.8. NeMo used full-text hints and managed default boost. Existing local marker sounds were used for the Pod poem, rather than recreating vendor sound design. No matcher rules changed for this comparison.</p>
<p>Pod synthetic WER: 0/149 normalized words in the Readmio excerpt; 3/105 (2.9%) in each Moon run. Vendor WER is unavailable. The 147-word excerpt has 149 words after normalization.</p>
<p>Phone media/connectivity/stay-awake settings were restored and temporary benchmark files removed after verification. Both scored app replays used verified virtual input with networking disabled. Existing human recordings were never supplied; all local transcripts/captures remain on this PC. Later vendor telemetry was not audited.</p></section>
<section><h2>Optional local listening</h2><p>These controls stay silent until you press Play. No manual annotations are needed to reproduce the reported scores.</p>
<b>Source: The Moon</b><audio controls preload="metadata" src="synthetic/moon-normal.wav"></audio>
<b>Original Novel Effect calibration output</b><audio controls preload="metadata" src="novel-trial-01/aligned-output.wav"></audio>
<p>This calibration clip includes two seconds before source time zero; it is not one of the two scored evaluation runs.</p></section></main></html>'''
    (root/'review.html').write_text(document,encoding='utf-8')
    print(json.dumps(rows,indent=2))
    return summary


if __name__=='__main__':build(Path('output/product-comparison-20261119'))
