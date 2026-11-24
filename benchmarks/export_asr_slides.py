"""Create aggregate-only, Canva-importable editable tables styled after source slide 24."""
import argparse
import csv
import html
import json
from pathlib import Path


STYLE = '''
*{box-sizing:border-box}body{margin:0;background:#e1e6ea;color:#183950;font-family:Arial,sans-serif}
.page{position:relative;width:1920px;height:1080px;background:#faf7f2;border-top:14px solid #6aabd6;padding:62px 120px 65px;overflow:hidden;margin:0 0 32px}
h1{margin:0 0 24px;font-family:"Trebuchet MS",Arial,sans-serif;font-size:68px;line-height:1.12;font-weight:800;color:#183950}
.scope{font-size:29px;line-height:1.3;color:#475569;margin:0 0 28px}.scope strong{color:#a64434}
table{width:100%;border-collapse:collapse;table-layout:fixed;font-size:34px;line-height:1.15}
th{background:#166653;color:#fff;text-align:left;padding:17px 20px;font-size:30px;font-weight:700;border-bottom:3px solid #166653}
td{padding:17px 20px;border-bottom:2px solid #d8ded9;font-variant-numeric:tabular-nums;color:#183950}
tr:nth-child(even) td{background:#eef2ea}.winner td{background:#dcecdf;color:#166653;font-weight:700}
.callout{color:#a64434;font-size:32px;font-weight:700;line-height:1.25;margin:28px 0 18px}
.foot{font-size:25px;line-height:1.32;color:#475569;margin:0}.small table{font-size:26px}.small th{font-size:24px;padding:10px 12px}.small td{padding:8px 12px}
.pageNum{position:absolute;right:50px;bottom:30px;font-size:20px;color:#183950}
@media print{body{background:white}.page{margin:0;break-after:page}@page{size:1920px 1080px;margin:0}}
'''


def esc(value):
    return html.escape(str(value))


def table(headers, rows, widths=None, classes=None):
    columns = '' if not widths else '<colgroup>'+''.join(f'<col style="width:{w}%">' for w in widths)+'</colgroup>'
    return '<table>'+columns+'<thead><tr>'+''.join('<th>'+esc(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join(
        '<tr'+(' class="winner"' if classes and i in classes else '')+'>'+''.join('<td>'+esc(v)+'</td>' for v in row)+'</tr>'
        for i,row in enumerate(rows))+'</tbody></table>'


def fmt(value, suffix=' s'):
    return '—' if value is None else f'{value:.2f}{suffix}'


def export(directory, all_models):
    sweep = json.loads((directory / 'boost-comparison.json').read_text(encoding='utf-8'))
    models = json.loads(all_models.read_text(encoding='utf-8'))
    rows = sweep['rows']
    best_wer = min(row['wer_percent'] for row in rows)
    most_cues = max(row['cues_fired'] for row in rows)
    best = [i for i,row in enumerate(rows) if row['wer_percent']==best_wer and row['cues_fired']==most_cues]
    body = table(['Boost','Est. WER','Median word latency','Checkpoints fired'],
                 [[f'{r["boost"]:g}',f'{r["wer_percent"]:.1f}%',fmt(r['word_median_seconds']),f'{r["cues_fired"]}/{r["configured_cues"]}'] for r in rows],
                 [18,24,29,29],best)
    # Show the actual tradeoff rather than automatically calling one setting best.
    low = ', '.join(f'{r["boost"]:g}' for r in rows if r['wer_percent']==best_wer)
    cues = ', '.join(f'{r["boost"]:g}' for r in rows if r['cues_fired']==most_cues)
    finding = f'Lowest estimated WER: {best_wer:.1f}% at boost {low}. Most checkpoints: {most_cues}/7 at boost {cues}.'
    page1 = f'''<section class="page" data-document-role="page" data-label="NeMo full-text boost sweep" data-speaker-notes="{esc(sweep['conditions']+' '+sweep['reference'])}">
<h1>Does a higher NeMo boost help?</h1><p class="scope"><strong>ESTIMATED</strong> · Tea, Fat Cat and Little Mermaid · Same recordings and full supplied text</p>
{body}<p class="callout">{esc(finding)}</p>
<p class="foot">Word error uses unverified Whisper Small drafts. Timing uses the same {sweep['common_words']} correctly aligned word occurrences at every boost. Word delay is stable ASR arrival minus the estimated word ending. One Fat Cat phrase was reportedly skipped. {len(sweep.get('coarse_timing_flags',[]))} cue timing(s) need review against coarse listening marks. No sound or projector timing.</p><span class="pageNum">1</span></section>'''
    # Shared-file metrics compare every scored model using exactly the same audio and words.
    def short_label(label):
        return label.replace(' · ',', ').replace(' (sweep)','').replace('full-book phrase boosting','full text, boost 1').replace('full-book reading graph','book graph').replace('checkpoint phrase hints','checkpoint hints').replace('Official Moonshine','Moonshine').replace('no hints','unhinted')
    model_rows = [[short_label(r['label']),
                   '—' if r['shared_wer_percent'] is None else f'{r["shared_wer_percent"]:.1f}%',
                   fmt(r['same_word_median_seconds']),
                   '—' if r['cues_fired'] is None else f'{r["cues_fired"]}/{r["configured_cues"]}'] for r in models['rows']]
    # Split the all-model table so the audience can read labels and numbers comfortably.
    pages = [page1]
    for index, start in enumerate(range(0,len(model_rows),10),2):
        part = model_rows[start:start+10]
        title = 'How do the ASR configurations compare?' if start==0 else 'How do the remaining settings compare?'
        grid = table(['Configuration','Est. WER','Median word latency','Checkpoints fired'],part,[43,18,21,18])
        pages.append(f'''<section class="page small" data-document-role="page" data-label="All ASR configurations {index-1}" data-speaker-notes="{esc(models['conditions']+' '+models['reference'])}">
<h1>{title}</h1><p class="scope"><strong>ESTIMATED</strong> · Shared recording: Little Mermaid · Same {models['common_words']} timed word occurrences</p>
{grid}<p class="callout">Compare word error, recognition delay and checkpoint triggers together.</p>
<p class="foot">All metrics use the same Mermaid recording. A dash means no complete comparable trial. References and word endings are provisional. CPU Whisper uses earlier inline delivery; others use queued input or Keen's browser clock. Median is the middle measured word delay.</p><span class="pageNum">{index}</span></section>''')
    output = directory / 'canva-asr-tables.html'
    output.write_text('<!doctype html><html><head><meta charset="utf-8"><title>Reading Pod ASR benchmark tables</title><style>'+STYLE+'</style></head><body>'+''.join(pages)+'</body></html>',encoding='utf-8')
    # Tab-separated copy is convenient for pasting into Canva's native table cells.
    with (directory / 'canva-boost-table.tsv').open('w',newline='',encoding='utf-8-sig') as file:
        writer=csv.writer(file,delimiter='\t');writer.writerow(['Boost','Estimated WER','Median word latency','Checkpoints fired/configured'])
        for r in rows:writer.writerow([f'{r["boost"]:g}',f'{r["wer_percent"]:.1f}%',fmt(r['word_median_seconds']),f'{r["cues_fired"]}/{r["configured_cues"]}'])
    print(json.dumps({'file':str(output.resolve()),'pages':len(pages),'finding':finding}),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sweep',type=Path,required=True)
    parser.add_argument('--all-models',type=Path,required=True)
    args=parser.parse_args();export(args.sweep,args.all_models)


if __name__=='__main__':main()
