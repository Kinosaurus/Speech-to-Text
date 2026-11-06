"""Attach explicit user acceptance without changing frozen trial measurements."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
REVIEW=ROOT/'benchmarks/results/pronunciation-acceptance-review-2026-11-03.json'


def reviewed_cases():
    if not REVIEW.exists():return {}
    return {case['id']:case for case in json.loads(REVIEW.read_text(encoding='utf-8'))['cases']}


def annotate(report):
    cases=reviewed_cases()
    if not cases:return report
    report['post_evaluation_pronunciation_review']=dict(
        date='2026-11-03',reviewer='user',review=REVIEW.relative_to(ROOT).as_posix(),
        cases=list(cases.values()),reviewed_cases=len(cases),accepted_cases=sum(c['user_should_emit'] for c in cases.values()),
        pod_false_triggers_among_reviewed=sum(not c['user_should_emit'] and c['default_emitted'] for c in cases.values()),
        basis='User explicitly accepts these five contextual variants for the pronunciation-tolerant shared-reading pod. Historical strict-literal counters are retained and are not current pod defect counts.',
        runtime_asr_and_trial_measurements_unchanged=True,
        scope='Only the listed recordings have these listening/acceptance labels. This does not label unreviewed substitutions or alter omission/unrelated-speech expectations.')
    report['historical_metric_basis']='Original trial expectations and literal-word counters are retained. The later user acceptance assessment is separate; these five emissions are accepted pod behavior.'
    if 'saved_challenges' in report:
        report['saved_challenges']['close_word_counter_basis']='Historical strict-literal comparison. All five listed emissions are subsequently user-accepted under pod policy; see post_evaluation_pronunciation_review.'
    if 'human_labels_blank' in report.get('listening_review',{}):
        report['listening_review'].update(human_labels_blank=False,
            user_accepted_cases=5,independent_word_transcriptions=1,
            flagged_cases_basis='Originally flagged under strict literal-word expectations; subsequently accepted by the user for the pod.')
    if 'original_interpretation_limits' not in report:
        report['original_interpretation_limits']=list(report.get('limits',[]))
    report['limits']=[text+' The five reviewed close-word emissions were subsequently accepted by the user for the pod; retain the literal-word comparison separately.'
        if any(term in text.lower() for term in ('close wrong-word','close-word false','close wrong word')) else text
        for text in report['original_interpretation_limits']]
    return report
