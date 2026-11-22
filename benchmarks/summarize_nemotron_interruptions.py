"""Independently audit callback replay and summarize the interruption experiment."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks.run_nemotron_interruptions import pcm, read, sha, write
from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher


def text_diagnostics(out, protocol):
    """Scripted cumulative word updates isolate matching; times are interpolated."""
    rows = []
    for row in protocol['cases']:
        if row['kind'] != 'synthetic':
            continue
        matcher = TimelyEvidenceMatcher(read(out / row['manifest']), threshold=82, stability=2)
        words, triggers = [], []
        for turn in row['turns']:
            if not isinstance(turn['content'], str):
                continue
            new = turn['content'].split()
            for i, word in enumerate(new, 1):
                words.append(word)
                end = turn['start'] + (turn['end']-turn['start']) * i/len(new)
                text = ' '.join(words)
                update = matcher.process(text, [dict(start=0, end=end, text=text, completed=False)])
                if update.triggered:
                    triggers.append(dict(id=update.checkpoint_id, audio_end=end))
        update = matcher.process(' '.join(words), [dict(start=0, end=row['samples']/16000,
                                 text=' '.join(words), completed=True)])
        if update.triggered:
            triggers.append(dict(id=update.checkpoint_id, audio_end=row['samples']/16000))
        got = [t['id'] for t in triggers]
        resume = row.get('resume_turn')
        earliest = row['turns'][resume]['start'] if resume is not None else None
        premature = [t for t in triggers if t['id'] == row.get('target') and t['audio_end'] < earliest] if earliest is not None else []
        rows.append(dict(id=row['id'], hits=got, missed=sorted(set(row['expected'])-set(got)),
                         unexpected=sorted(set(got)-set(row['expected'])), premature=premature,
                         passed=set(got)==set(row['expected']) and len(got)==len(set(got)) and not premature))
    write(out / 'scripted-text-diagnostics.json', dict(
        warning='Perfect scripted words; linearly interpolated update times, not ASR or acoustic alignment.', cases=rows))
    return rows


def summarize(out):
    protocol = read(out / 'protocol.json')
    for path, digest in protocol['source_sha256'].items():
        assert sha(ROOT / path) == digest, path
    for path, digest in protocol['manifest_sha256'].items():
        assert sha(out / path) == digest, path
    for story in ('horse', 'tea', 'little_mermaid'):
        original = pcm(out / (story + '-original.wav'))
        paused = pcm(out / (story + '-midpoint-pause.wav'))
        row = next(r for r in protocol['cases'] if r['id'] == story + '-midpoint-pause')
        split = round(row['insertion_seconds'] * 16000) * 2
        assert paused[:split] + paused[split+15*16000*2:] == original
        assert paused[split:split+15*16000*2] == bytes(15*16000*2)
    diagnostics = text_diagnostics(out, protocol)
    aggregate = dict(protocol={k:v for k,v in protocol.items() if k != 'cases'}, modes={},
                     scripted_text_diagnostics=diagnostics)
    for mode in ('hints-low', 'hints-off'):
        folder = out / mode
        if not folder.exists():
            continue
        summaries = []
        for row in protocol['cases']:
            result = read(folder / (row['id'] + '.json'))
            summary = result['summary']
            assert sha(out / row['audio']) == row['audio_sha256']
            assert summary['samples_delivered'] == row['samples'] and summary['stream_done']
            assert summary['packet_acks'] == (row['samples']+1279)//1280
            matcher = TimelyEvidenceMatcher(read(out / row['manifest']), threshold=82, stability=2)
            replay = []
            for event in result['events']:
                update = matcher.process(event['text'], [dict(start=0, end=event['audio_end'],
                    text=event['text'], completed=event['final'])])
                assert (update.triggered, update.tracked_word_position, update.effect_suppressed,
                        update.skipped_checkpoint_ids) == (
                    event['update']['triggered'], event['update']['tracked_word_position'],
                    event['update']['effect_suppressed'], tuple(event['update']['skipped_checkpoint_ids']))
                if update.triggered:
                    replay.append(dict(id=update.checkpoint_id, audio_end=event['audio_end']))
            assert replay == result['triggers']
            assert result['events'][-1]['final']
            assert result['events'][-1]['audio_end'] == row['samples']/16000
            summaries.append(summary)
        synthetic = [s for s in summaries if s['kind'] == 'synthetic']
        positive = [s for s in synthetic if len(s['expected']) == 3]
        negative = [s for s in synthetic if len(s['expected']) == 2]
        pairs = []
        for story in ('horse', 'tea', 'little_mermaid'):
            baseline = next(s for s in summaries if s['id'] == story + '-original')
            paused = next(s for s in summaries if s['id'] == story + '-midpoint-pause')
            pairs.append(dict(story=story, original_hits=baseline['hits'], paused_hits=paused['hits'],
                              added=sorted(set(paused['hits'])-set(baseline['hits'])),
                              lost=sorted(set(baseline['hits'])-set(paused['hits']))))
        aggregate['modes'][mode] = dict(
            trials=len(summaries), complete_streams=len(summaries), callback_replay_agreement=len(summaries),
            synthetic_pass=sum(s['passed'] for s in synthetic), synthetic_total=len(synthetic),
            positive_pass=sum(s['passed'] for s in positive), positive_total=len(positive),
            negative_pass=sum(s['passed'] for s in negative), negative_total=len(negative),
            expected_synthetic_cues=sum(len(s['expected']) for s in synthetic),
            matched_synthetic_cues=sum(len(set(s['expected']) & set(s['hits'])) for s in synthetic),
            unexpected_cues=sum(len(s['unexpected']) for s in summaries),
            duplicate_cues=sum(sum(n-1 for n in s['duplicates'].values()) for s in summaries),
            premature_target_cues=sum(len(s['premature']) for s in summaries),
            original_pause_pairs=pairs, cases=summaries)
    write(out / 'audited-summary.json', aggregate)
    print(json.dumps({mode:{k:v for k,v in values.items() if k!='cases'}
                      for mode,values in aggregate['modes'].items()}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    summarize(parser.parse_args().output.resolve())
