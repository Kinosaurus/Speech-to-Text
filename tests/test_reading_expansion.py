import unittest

from benchmarks.prepare_mps_expansion import provider_anchor_evidence, select


class ReadingExpansionTests(unittest.TestCase):
    def test_selection_is_repeatable_balanced_and_excludes_old_speakers(self):
        rows = []
        for grade in ('4', '5'):
            for gender in ('Female', 'Male'):
                for number in range(5):
                    speaker = f'{grade}-{gender}-{number}'
                    for paragraph in ('1', '2'):
                        rows.append(dict(audioID=f'{speaker}-{paragraph}', metaData=dict(
                            speakerID=speaker, grade=grade, gender=gender, paragraphID=paragraph)))
        excluded = {'4-Female-0', '5-Male-0'}
        first = select(rows, excluded)
        self.assertEqual(first, select(list(reversed(rows)), excluded))
        speakers = {r['metaData']['speakerID']: r['metaData'] for r in first}
        self.assertEqual(len(first), 12)
        self.assertEqual(len(speakers), 6)
        self.assertFalse(excluded & speakers.keys())
        self.assertEqual(sum(m['gender'] == 'Female' for m in speakers.values()), 3)
        self.assertEqual(sum(m['grade'] == '4' for m in speakers.values()), 3)

    def test_provider_deletion_is_preserved_instead_of_becoming_correct_speech(self):
        row = dict(promptText='The frog jumped away.', textAlignment=[
            dict(promptTextWord='the', manualTranscriptWord='the', miscueLabel='c'),
            dict(promptTextWord='frog', manualTranscriptWord='frog', miscueLabel='c'),
            dict(promptTextWord='jumped', manualTranscriptWord='hopped', miscueLabel='s'),
            dict(promptTextWord='away', manualTranscriptWord='<eps>', miscueLabel='d')])
        evidence = provider_anchor_evidence(row, 1, 4)
        self.assertEqual((evidence['correct'], evidence['substitutions'], evidence['deletions']), (1, 1, 1))
        self.assertFalse(evidence['temporal_gold'])

    def test_incompatible_alignment_is_explicitly_unscored(self):
        evidence = provider_anchor_evidence(dict(promptText='A different sentence.',
            textAlignment=[dict(promptTextWord='hello', manualTranscriptWord='hello', miscueLabel='c')]), 0, 1)
        self.assertEqual(evidence['status'], 'provider_alignment_tokenization_mismatch')
        self.assertNotIn('correct', evidence)


if __name__ == '__main__':
    unittest.main()
