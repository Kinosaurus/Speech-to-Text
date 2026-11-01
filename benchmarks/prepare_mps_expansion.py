"""Freeze and import a speaker-disjoint, untuned MPS reading test expansion.

The country is India, not Singapore. Provider audio, prompts and transcripts
stay in ignored local folders; the provider has not granted redistribution here.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path, PurePosixPath
import random
import re
import shutil
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from books_to_life.matching.alignment_matcher import AlignmentMatcher
from books_to_life.matching.checkpoint_matcher import normalize_text
from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher
import soundfile as sf

DEST = ROOT / 'output/mps-expansion-2026-11-02'
LIB = ROOT / 'recordings/library'
REPO = 'https://github.com/DAP-Lab/mps_dataset'
SEED = 20261102
# Defined before downloading or decoding any selected audio; never fit to ASR.
ANCHORS = {
    ('4', '1'): [('thick_legs', 'short tails and thick legs'),
                 ('fish_and_seals', 'usually eat fish and seals'),
                 ('keep_away', 'keep away from us')],
    ('4', '2'): [('hibernate', 'bears hibernate from October to April'),
                 ('clever_bears', 'they can smell very well and are very clever'),
                 ('begging_paws', 'by sitting up and holding out their paws')],
    ('5', '1'): [('wing_colours', 'the brilliant colours of their wings'),
                 ('small_scales', 'covered with very small scales'),
                 ('fine_patterns', 'make very fine patterns')],
    ('5', '2'): [('black_circles', 'large, black circles on their wings'),
                 ('escape_enemies', 'escape from its enemies'),
                 ('damaged_wing', 'a bit of the wing')],
}


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch(url, path, limit):
    if path.exists():
        return
    request = urllib.request.Request(url, headers={'User-Agent': 'BooksToLife-local-evaluation'})
    with urllib.request.urlopen(request, timeout=90) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f'Unexpectedly large download: {url}')
    path.write_bytes(data)


def select(rows, excluded):
    rng = random.Random(SEED)
    selected = []
    for grade, genders in [('4', ['Female', 'Male', 'Female']),
                           ('5', ['Male', 'Female', 'Male'])]:
        groups = defaultdict(list)
        for row in rows:
            meta = row['metaData']
            if meta['grade'] == grade and meta['speakerID'] not in excluded:
                groups[meta['speakerID']].append(row)
        candidates = {speaker: pair for speaker, pair in groups.items()
                      if len(pair) == 2 and {r['metaData']['paragraphID'] for r in pair} == {'1', '2'}}
        for gender in genders:
            pool = sorted(s for s, pair in candidates.items() if pair[0]['metaData']['gender'] == gender)
            speaker = rng.choice(pool)
            selected.extend(sorted(candidates.pop(speaker), key=lambda r: r['audioID']))
    return selected


def provider_anchor_evidence(row, start, end):
    """Retain provider miscues; this is textual evidence, not word timestamps."""
    aligned = []
    for item in row['textAlignment']:
        token = item['promptTextWord']
        if token == '<eps>':
            continue
        for word in normalize_text(token).split():
            aligned.append(dict(prompt=word, spoken=item['manualTranscriptWord'],
                                label=item['miscueLabel']))
    words = normalize_text(row['promptText']).split()
    if [a['prompt'] for a in aligned] != words:
        return dict(status='provider_alignment_tokenization_mismatch', temporal_gold=False)
    evidence = aligned[start:end]
    return dict(status='provider_word_alignment', temporal_gold=False, words=evidence,
                correct=sum(w['label'].lower() == 'c' for w in evidence),
                substitutions=sum(w['label'].lower() == 's' for w in evidence),
                deletions=sum(w['label'].lower() == 'd' for w in evidence))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true', help='Fetch selected public provider files over HTTPS.')
    args = parser.parse_args()
    source = DEST / 'source'
    source.mkdir(parents=True, exist_ok=True)
    if args.download:
        fetch('https://api.github.com/repos/DAP-Lab/mps_dataset/commits/master', DEST / 'revision.json', 200000)
        revision = json.loads((DEST / 'revision.json').read_text(encoding='utf-8'))['sha']
        if not re.fullmatch(r'[0-9a-f]{40}', revision):
            raise ValueError('Invalid upstream revision')
        base = f'https://raw.githubusercontent.com/DAP-Lab/mps_dataset/{revision}/'
        fetch(base + 'data.json', source / 'data.json', 25 * 1024 * 1024)
        fetch(base + 'README.md', source / 'README.md', 100000)
    else:
        revision = json.loads((DEST / 'revision.json').read_text(encoding='utf-8'))['sha']
        base = f'https://raw.githubusercontent.com/DAP-Lab/mps_dataset/{revision}/'
    rows = json.loads((source / 'data.json').read_text(encoding='utf-8'))
    old = json.loads((ROOT / 'output/mps/source/selected.json').read_text(encoding='utf-8'))
    excluded = {r['metaData']['speakerID'] for r in old}
    chosen = select(rows, excluded)
    assert len(chosen) == 12 and len({r['metaData']['speakerID'] for r in chosen}) == 6
    selection = dict(seed=SEED, country='India', region='South Asia; not Southeast Asia',
        selected_ids=[r['audioID'] for r in chosen], speakers=sorted({r['metaData']['speakerID'] for r in chosen}),
        excluded_speakers=sorted(excluded), metadata_sha256=digest(source / 'data.json'), revision=revision,
        policy='Three paired-paragraph speakers per grade, 4 and 5; three female and three male IDs total. '
               'Sorted candidates sampled using a fixed RNG seed. No selection by ASR, reading score, duration, or checkpoint outcome.',
        checkpoints=ANCHORS_TO_JSON())
    frozen = DEST / 'selection.json'
    if frozen.exists():
        assert json.loads(frozen.read_text(encoding='utf-8')) == selection
    else:
        write(frozen, selection)
    write(source / 'selected.json', chosen)
    report = []
    for row in chosen:
        meta = row['metaData']
        grade, paragraph = meta['grade'], meta['paragraphID']
        raw = PurePosixPath(row['audioPath'])
        assert not raw.is_absolute() and '..' not in raw.parts and raw.suffix == '.wav'
        wav = source / (row['audioID'] + '.wav')
        if args.download:
            fetch(base + raw.as_posix(), wav, 20 * 1024 * 1024)
        info = sf.info(wav)
        assert info.samplerate == 16000 and info.channels == 1 and info.subtype == 'PCM_16'
        name = 'bears' if grade == '4' else 'butterflies'
        folder = LIB / f'stories/mps-{name}-part-{paragraph}/readers/mps-{meta["speakerID"]}'
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / 'audio.wav'
        if target.exists():
            assert digest(target) == digest(wav)
        else:
            shutil.copyfile(wav, target)
        passage = row['promptText']
        words = normalize_text(passage).split()
        book_id = f'mps-expansion-{row["audioID"]}'
        checkpoints = []
        for position, (name, text) in enumerate(ANCHORS[grade, paragraph], 1):
            anchor = normalize_text(text).split()
            hits = [i for i in range(len(words) - len(anchor) + 1) if words[i:i + len(anchor)] == anchor]
            assert len(hits) == 1, (row['audioID'], name, hits)
            start, end = hits[0], hits[0] + len(anchor)
            checkpoints.append(dict(id=name, book_id=book_id, checkpoint_position=position, page=1,
                checkpoint_text=text, word_start=start, word_end=end, effect=dict(effect_id=name)))
        manifest = dict(book_id=book_id,
            title=f'MPS Grade {grade}, paragraph {paragraph}, reader {meta["speakerID"]}',
            threshold=82, stability=2, min_coverage=0.8, pages=[dict(page=1, text=passage)],
            checkpoints=checkpoints, provenance=dict(country='India', dataset='MPS',
                original_prompt=True, age_years=None, checkpoint_policy='Frozen before live ASR; not selected for recognition performance'))
        # Book-authored effect semantics are versioned separately from the
        # provider passage and the ASR transcript. Preserve pre-policy manifests.
        policy = json.loads((ROOT / 'benchmarks/pilot_effect_policy.json').read_text(encoding='utf-8'))
        for cp in manifest['checkpoints']:
            cp['effect_policy'] = policy['default_effect_policy']
            for rule in policy['rules']:
                if normalize_text(cp['checkpoint_text']) == normalize_text(rule['checkpoint_text']):
                    cp['required_words'] = rule['required_words']
        previous = folder / 'checkpoints.json'
        if previous.exists() and json.loads(previous.read_text(encoding='utf-8')) != manifest:
            history = folder / 'history/before-effect-policy-2026-11-02'
            history.mkdir(parents=True, exist_ok=True)
            if not (history / 'checkpoints.json').exists():
                shutil.copyfile(previous, history / 'checkpoints.json')
        AlignmentMatcher(manifest)
        matcher = TimelyEvidenceMatcher(manifest)
        triggered = []
        for end in range(1, len(words) + 1):
            update = matcher.process(' '.join(words[:end]))
            if update.triggered:
                triggered.append(update.checkpoint_id)
        update = matcher.process(passage, [dict(start=0, end=info.duration, text=passage, completed=True)])
        if update.triggered:
            triggered.append(update.checkpoint_id)
        assert triggered == [cp['id'] for cp in checkpoints], (row['audioID'], triggered)
        write(folder / 'checkpoints.json', manifest)
        (folder / 'passage.txt').write_text(passage + '\n', encoding='utf-8')
        (folder / 'transcript.txt').write_text(row['manualTranscript'] + '\n', encoding='utf-8')
        write(folder / 'text_alignment.json', row['textAlignment'])
        write(folder / 'checkpoint_evidence.json', {cp['id']: provider_anchor_evidence(row, cp['word_start'], cp['word_end']) for cp in checkpoints})
        write(folder / 'checkpoint_text_test.json', dict(kind='ideal-text plumbing check; not audio accuracy', triggered=triggered))
        write(folder / 'timing_status.json', dict(status='no_temporal_gold', manual_verification=False,
            note='Provider text alignment is not an audio timestamp. No timing gold or latency claim is fabricated.'))
        write(folder / 'source.json', dict(country='India', region='South Asia', dataset='MPS',
            metadata=meta, age_years=None, downloaded_date='2026-11-02', repository=REPO,
            revision=revision, audio_url=base + raw.as_posix(), audio_sha256=digest(wav),
            metadata_sha256=selection['metadata_sha256'], duration_seconds=info.duration,
            passage_origin='Provider promptText, independent of child transcription',
            transcript_origin='Provider manualTranscript and textAlignment', manually_listened=False,
            license_status='Provider says use governed by a license; contact prao@iitb.ac.in. No redistribution permission asserted.'))
        (folder / 'README.md').write_text(
            f'# MPS additional reader {meta["speakerID"]}, paragraph {paragraph}\n\n'
            'Country: **India, not Singapore or Southeast Asia**. Grade is supplied; individual age is unknown.\n\n'
            '[Original passage](passage.txt) · [Provider transcript](transcript.txt) · [Audio](audio.wav) · '
            '[Checkpoints](checkpoints.json) · [Provider anchor evidence](checkpoint_evidence.json) · '
            '[Source and terms](source.json)\n\n'
            'Three fixed passage checkpoints. Ideal-text checks passed. See the expansion report for fresh audio results. '
            'There are no human-verified checkpoint timestamps. Keep this provider data local.\n', encoding='utf-8')
        report.append(dict(audio_id=row['audioID'], path=folder.relative_to(LIB).as_posix(),
            audio_sha256=digest(target), manifest_sha256=digest(folder / 'checkpoints.json'),
            grade=int(grade), age_years=None, gender=meta['gender'], reader=meta['speakerID'],
            duration_seconds=info.duration, country='India'))
        print('IMPORTED', row['audioID'], round(info.duration, 3), flush=True)
    write(DEST / 'jobs.json', dict(selection=selection, recordings=report))
    print('READY', len(report), 'recordings;', round(sum(r['duration_seconds'] for r in report), 2), 'seconds', flush=True)


def ANCHORS_TO_JSON():
    return {grade + '-' + paragraph: [dict(id=name, text=text) for name, text in anchors]
            for (grade, paragraph), anchors in ANCHORS.items()}


if __name__ == '__main__':
    main()
