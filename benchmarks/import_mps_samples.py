"""Import locally downloaded MPS Grade 3 paragraph recordings.

Requires source README.md, data.json, selected.json and WAVs in output/mps/source.
Does not infer ages, generate timestamps, or download/redistribute data.
"""
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from alignment_matcher import AlignmentMatcher
from checkpoint_matcher import normalize_text
from timely_matcher import TimelyEvidenceMatcher
import soundfile as sf

SOURCE = ROOT / 'output/mps/source'
LIB = ROOT / 'recordings/library'
REPO = 'https://github.com/DAP-Lab/mps_dataset'
ANCHORS = {
    '1': [('hundred_sheep', 'He had a hundred sheep.'),
          ('riverside', 'he took the sheep to the riverside.'),
          ('lost_sheep', 'One sheep was lost. The shepherd was sad.')],
    '2': [('found_in_bush', 'he found the sheep in a bush.'),
          ('carried_home', 'He got the sheep out and carried it home.'),
          ('happy_friends', 'All of them were happy too.')],
}
EVENTS = {'SIL', 'BR', 'ON', 'FP', 'IR', 'MB', 'WH'}

def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    rows = json.loads((SOURCE/'selected.json').read_text(encoding='utf-8'))
    assert len(rows) == 6
    prompts = {r['metaData']['paragraphID']: r['promptText'] for r in rows}
    assert set(prompts) == {'1','2'}
    assert all(r['metaData']['grade']=='3' and r['promptText']==prompts[r['metaData']['paragraphID']] for r in rows)
    acquisition = LIB/'acquisition/mps'
    acquisition.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SOURCE/'README.md', acquisition/'SOURCE_README.txt')
    save(acquisition/'selected_source_rows.json', rows)
    report=[]
    for row in sorted(rows,key=lambda r:r['audioID']):
        meta=row['metaData']
        paragraph=meta['paragraphID']
        story=f'mps-the-lost-sheep-part-{paragraph}'
        reader='mps-'+meta['speakerID']
        folder=LIB/'stories'/story/'readers'/reader
        folder.mkdir(parents=True, exist_ok=True)
        wav=SOURCE/(row['audioID']+'.wav')
        info=sf.info(wav)
        assert info.samplerate==16000 and info.channels==1 and info.subtype=='PCM_16'
        shutil.copyfile(wav,folder/'audio.wav')
        passage=row['promptText']
        (folder/'passage.txt').write_text(passage+'\n',encoding='utf-8')
        (folder/'full_story.txt').write_text(prompts['1']+'\n\n'+prompts['2']+'\n',encoding='utf-8')
        (folder/'transcript.txt').write_text(row['manualTranscript']+'\n',encoding='utf-8')
        spoken=' '.join(w for w in row['manualTranscript'].split() if w not in EVENTS)
        (folder/'speech_transcript.txt').write_text(spoken+'\n',encoding='utf-8')
        save(folder/'text_alignment.json',row['textAlignment'])
        source=dict(dataset='Maharashtra Primary Schools (MPS)', audio_id=row['audioID'],
                    metadata=meta, age_years=None, age_status='not provided; grade is not age',
                    repository=REPO, audio_url=REPO.replace('github.com','raw.githubusercontent.com')+'/master/'+row['audioPath'],
                    metadata_url=REPO+'/blob/master/data.json', downloaded_date='2026-10-29',
                    audio_sha256=digest(wav), metadata_sha256=digest(SOURCE/'data.json'),
                    duration_seconds=info.duration,sample_rate=info.samplerate,channels=info.channels,
                    transcript_origin='Provider manualTranscript; human transcription/QC following ASR assistance',
                    passage_origin='Provider promptText; English 400 Reading Programme, Level 2 Card 34',
                    license_status='Provider says use governed by a license; contact prao@iitb.ac.in. No general redistribution license asserted.',
                    locally_listened=False, word_timestamps_available=False)
        save(folder/'source.json',source)
        save(folder/'text_status.json',dict(kind='provider_original_prompt',file='passage.txt',
              note='Independent promptText supplied by MPS, not reconstructed from child speech. full_story.txt contains both paragraphs; this audio reads only the indicated paragraph. Exact age unknown.'))
        words=normalize_text(passage).split()
        book=f'library-{story}-{reader}'
        checkpoints=[]
        for position,(name,text) in enumerate(ANCHORS[paragraph],1):
            anchor=normalize_text(text).split()
            hits=[i for i in range(len(words)-len(anchor)+1) if words[i:i+len(anchor)]==anchor]
            assert len(hits)==1,(name,hits)
            checkpoints.append(dict(id=name,book_id=book,checkpoint_position=position,page=1,
                checkpoint_text=text,word_start=hits[0],word_end=hits[0]+len(anchor),effect=dict(effect_id=name)))
        manifest=dict(book_id=book,title=f'The Lost Sheep — paragraph {paragraph} — {reader} (Grade 3, age unknown)',
            threshold=82,stability=2,min_coverage=0.8,pages=[dict(page=1,text=passage)],checkpoints=checkpoints,
            provenance=dict(dataset='MPS',reference_status='provider original prompt',audio_id=row['audioID'],
                age_years=None,timing_status='No public word timestamps; do not score trigger delay against fabricated expectations.'))
        AlignmentMatcher(manifest)
        save(folder/'checkpoints.json',manifest)
        save(folder/'timing_status.json',dict(status='not_available',expected_timestamps=None,
            reason='Public data.json has text alignment and miscue labels, but no temporal word alignment. No SRT or expected.json invented.'))
        # Exercise real reader transcript text and ideal passage separately. This is not live ASR/audio testing.
        result={}
        for label,text in [('ideal_passage',passage),('provider_transcript',spoken)]:
            matcher=TimelyEvidenceMatcher(manifest)
            tokens=normalize_text(text).split()
            caught=[]
            for end in range(1,len(tokens)+1):
                snapshot=' '.join(tokens[:end])
                update=matcher.process(snapshot)
                if update.triggered:caught.append(update.checkpoint_id)
            update=matcher.process(' '.join(tokens),[dict(start=0,end=info.duration,text=' '.join(tokens),completed=True)])
            if update.triggered:caught.append(update.checkpoint_id)
            result[label]=dict(triggered=caught,missing=[c['id'] for c in checkpoints if c['id'] not in caught],
                               duplicate_triggers=len(caught)!=len(set(caught)))
        assert not result['ideal_passage']['missing'],result
        save(folder/'checkpoint_text_test.json',dict(matcher='TimelyEvidenceMatcher (current split mode)',test_type='Cumulative text replay only; no ASR or audio timing validation',results=result))
        (folder/'README.md').write_text(f'# The Lost Sheep, paragraph {paragraph}: {reader}\n\nGrade 3, {meta["gender"]}. **Exact age is unknown**, not confirmed seven. Same speaker IDs across the two paragraph folders indicate the same child.\n\n- [Original supplied paragraph](passage.txt) and [complete two-paragraph story](full_story.txt)\n- [Human-reviewed spoken transcript with event labels](transcript.txt)\n- [Speech-only view](speech_transcript.txt): removes SIL/BR/ON/FP/IR/MB/WH tokens, preserves misreadings and Devanagari\n- [Original word/miscue alignment](text_alignment.json)\n- [Audio](audio.wav), [checkpoints](checkpoints.json), [provenance](source.json)\n- [Text replay checks](checkpoint_text_test.json) and [timing status](timing_status.json)\n\nThree text checkpoints come from the supplied passage. No expected trigger times are provided. Audio has not been independently listened to; provider transcription is not silently corrected to match the passage.\n\nMPS use is governed by a license; provider directs inquiries to prao@iitb.ac.in. Kept local and Git-ignored. Cite Gothi et al. (2024), A Dataset and Two-pass System for Reading Miscue Detection, DOI 10.21437/Interspeech.2024-1639.\n',encoding='utf-8')
        report.append(dict(audio_id=row['audioID'],path=folder.relative_to(LIB).as_posix(),duration=info.duration,
                           grade=3,age_years=None,checkpoints=3,text_test=result,audio_sha256=source['audio_sha256']))
    save(acquisition/'import_report.json',dict(dataset='MPS',exact_ages_available=False,recordings=report,
        total_seconds=sum(x['duration'] for x in report),note='User approved Grade 3 with exact age unknown. Local use only; no redistribution license inferred.'))
    for paragraph in ['1','2']:
        story=LIB/'stories'/f'mps-the-lost-sheep-part-{paragraph}'
        lines=[f'# MPS: The Lost Sheep, paragraph {paragraph}', '',
               'Three Grade 3 readers in India. Exact ages are not supplied; none is labelled confirmed seven. Each speaker also reads the other paragraph in its corresponding story folder.', '',
               '| Reader | Original passage | Spoken transcript | Recording | Checkpoints |',
               '| --- | --- | --- | --- | --- |']
        for folder in sorted((story/'readers').iterdir()):
            if folder.is_dir():
                p='readers/'+folder.name+'/'
                lines.append(f'| [{folder.name}]({p}README.md) | [Passage]({p}passage.txt) | [Transcript]({p}transcript.txt) | [Audio]({p}audio.wav) | [Checkpoints]({p}checkpoints.json) |')
        (story/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    catalogue=LIB/'README.md'
    original=catalogue.read_text(encoding='utf-8')
    start='<!-- mps-samples -->'
    end='<!-- /mps-samples -->'
    if start in original:
        a,b=original.split(start,1)
        original=a+b.split(end,1)[1]
    lines=[start, '## MPS samples: Grade 3, exact ages unknown', '',
           'Six Indian Grade 3 recordings, three speakers, 3m14s total. Original supplied text, human-reviewed transcript, miscue alignment and three text checkpoints per recording. No expected audio timestamps. Provider license terms require clarification before redistribution; samples remain local and ignored by Git.', '',
           '| Paragraph | Reader | Passage | Transcript | Audio | Checkpoints |', '| --- | --- | --- | --- | --- | --- |']
    for item in report:
        p=item['path']+'/'
        paragraph=item['audio_id'].rsplit('_',1)[1]
        reader=item['audio_id'].split('_',1)[0]
        lines.append(f'| {paragraph} | [{reader}]({p}README.md) | [Text]({p}passage.txt) | [Transcript]({p}transcript.txt) | [Play]({p}audio.wav) | [Checkpoints]({p}checkpoints.json) |')
    lines += ['', '[Import and text-test report](acquisition/mps/import_report.json). Text replay: 18/18 ideal passage anchors, 17/18 provider-transcript anchors, no duplicate triggers. This is not live ASR validation.', end, '']
    catalogue.write_text(original.rstrip()+'\n\n'+'\n'.join(lines),encoding='utf-8')
    inventory=json.loads((LIB/'inventory.json').read_text(encoding='utf-8'))
    inventory['catalogue']=[x for x in inventory['catalogue'] if not x['story'].startswith('mps-the-lost-sheep-part-')]
    for item in report:
        path=Path(item['path'])
        inventory['catalogue'].append(dict(story=path.parts[1],reader=path.name,path=item['path'],audio=item['path']+'/audio.wav'))
    inventory.setdefault('imports',{})['mps_grade3']=dict(report='acquisition/mps/import_report.json',recordings=6,speakers=3,age_years=None)
    save(LIB/'inventory.json',inventory)
    print(json.dumps(dict(recordings=len(report),speakers=len({r['metaData']['speakerID'] for r in rows}),
                         seconds=sum(x['duration'] for x in report),checkpoints=18,
                         text_results=[dict(audio_id=x['audio_id'],**x['text_test']) for x in report]),indent=2))

if __name__=='__main__':
    main()
