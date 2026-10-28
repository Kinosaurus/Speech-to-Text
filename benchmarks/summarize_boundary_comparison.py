"""Summarize live three-way tracker results without treating counts as timing accuracy."""
import hashlib
import argparse
import json
from pathlib import Path
import statistics

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/timely-streaming-2026-10-28'
MODES=('original','split','boundary','timely')


def main():
    global OUT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=OUT)
    args=parser.parse_args()
    OUT=args.output
    runs=json.loads((OUT/'results.json').read_text())
    protocol=json.loads((OUT/'protocol.json').read_text())
    for name,digest in protocol['source_sha256'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest, name
    rows=[]
    for run in runs:
        for book,expected in run['expected'].items():
            groups={mode:[t for t in run['triggers'] if t['mode']==mode and t['book']==book]
                    for mode in MODES}
            # First Fat Cat anchor was reportedly skipped in historical listening
            # notes. Keep its activation as an unresolved catch-up, not a success.
            uncertain={'fat_cat_on_mat'} if book=='fat_cat' else set()
            row=dict(run=run['id'],condition=run['condition'],book=book,
                     expected=list(expected),uncertain_reading=list(uncertain),modes={})
            for mode,triggers in groups.items():
                seen={t['scene'] for t in triggers}
                row['modes'][mode]=dict(caught=sorted(seen & expected.keys()),
                     missed=sorted(expected.keys()-seen),unexpected=sorted(seen-expected.keys()),
                     duplicates=len(triggers)-len(seen),
                     early_against_approx_annotation=[t['scene'] for t in triggers if t.get('approx_delay_seconds',0)<0],
                     triggers=triggers)
            row['paired_timing']=[]
            fixed={t['scene']:t for t in groups['timely']}
            for reference in ('original','split','boundary'):
                prior={t['scene']:t for t in groups[reference]}
                for scene in sorted(prior.keys() & fixed.keys()):
                    row['paired_timing'].append(dict(reference=reference,scene=scene,
                        timely_minus_reference_seconds=fixed[scene]['callback_seconds']-prior[scene]['callback_seconds']))
            rows.append(row)
    aggregates=[]
    for condition in sorted({r['condition'] for r in rows}):
        for family in ('development','ocsc-standard','ocsc-early'):
            group=[r for r in rows if r['condition']==condition and
                   (r['book']==family if family.startswith('ocsc') else not r['book'].startswith('ocsc'))]
            if not group:continue
            totals={mode:dict(caught=sum(len(r['modes'][mode]['caught']) for r in group),
                             missed=sum(len(r['modes'][mode]['missed']) for r in group),
                             unexpected=sum(len(r['modes'][mode]['unexpected']) for r in group),
                             duplicates=sum(r['modes'][mode]['duplicates'] for r in group)) for mode in MODES}
            aggregates.append(dict(condition=condition,family=family,comparisons=len(group),
                                   configured_opportunities=sum(len(r['expected']) for r in group),modes=totals))
    timing=[]
    for reference in ('original','split','boundary'):
        deltas=[t['timely_minus_reference_seconds'] for r in rows for t in r['paired_timing'] if t['reference']==reference]
        timing.append(dict(reference=reference,paired_count=len(deltas),
                           median_seconds=statistics.median(deltas) if deltas else None,
                           minimum_seconds=min(deltas,default=None),maximum_seconds=max(deltas,default=None)))
    report=dict(completed_runs=len(runs),planned_runs=len(protocol['jobs']),
                all_complete=len(runs)==len(protocol['jobs']),
                limits='Same-clip and same-ASR comparisons. Development scene arrivals are not manually timed; counts include a disputed Fat Cat anchor. OCSC timings are approximate automatic CHAT annotations. Standard and early manifests share the same two audio streams, so their results are correlated. Off-book controls test only these clips/books.',
                aggregate=aggregates,paired_timing=timing,rows=rows)
    (OUT/'comparison.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:report[k] for k in ('completed_runs','planned_runs','aggregate','paired_timing')},indent=2))


if __name__=='__main__':main()
