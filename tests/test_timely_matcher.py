import json
from pathlib import Path
import unittest

from books_to_life.matching.alignment_matcher import AlignmentSpan
from books_to_life.matching.boundary_matcher import BoundaryEvidenceMatcher
from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher
from books_to_life.matching.transcript_display import TranscriptEvidence


def config():
    text='grandma has a big house with lots of steps'
    return dict(book_id='timely',threshold=82,stability=2,min_coverage=.8,
                pages=[dict(page=1,text=text)],checkpoints=[dict(id='steps',book_id='timely',
                checkpoint_position=1,checkpoint_text=text,effect={'effect_id':'steps'})])


def feed(m,text,t):
    return m.process(text,[dict(start=0,end=t,text=text,completed=False)])


class TimelyTests(unittest.TestCase):
    def test_default_lookahead_scales_with_book_length(self):
        for word_count, expected in [(100, 12), (250, 15), (275, 17), (482, 29), (800, 48), (1500, 60)]:
            with self.subTest(word_count=word_count):
                manifest = config()
                page = manifest['pages'][0]
                page['text'] += ' pebble' * (word_count - len(page['text'].split()))
                self.assertEqual(TimelyEvidenceMatcher(manifest).window_words, expected)

    def test_default_lookahead_does_not_expand_after_misses(self):
        manifest = config()
        cue = manifest['checkpoints'][0]['checkpoint_text']
        manifest['pages'][0]['text'] = 'pebble ' * 24 + cue
        matcher = TimelyEvidenceMatcher(manifest)
        self.assertEqual(matcher.window_words, 12)
        for end in range(1, 10):
            update = feed(matcher, cue, end)
            self.assertFalse(update.triggered)
            self.assertFalse(update.recovering)
            self.assertEqual(update.tracked_word_position, 0)

    def test_one_shot_resumes_after_aside_with_an_exact_endpoint_and_book_context(self):
        context = 'we followed a narrow path through the garden'
        prefix = 'the small rabbit hurried across the wooden'
        manifest = config()
        manifest['pages'][0]['text'] = f'{context} {prefix} bridge we watched quietly from the hill'
        manifest['checkpoints'][0]['checkpoint_text'] = f'{prefix} bridge'
        aside = 'please pass the blue notebook'
        for resume, should_fire in (
            ('bridge we watched quietly', True),
            ('bridge I saw something', False),
            ('we watched quietly', False),
        ):
            with self.subTest(resume=resume):
                matcher = TimelyEvidenceMatcher(manifest)
                # The preceding page context has already been confirmed.
                matcher.tracked_word_position = len(context.split())
                head = f'{context} {prefix}'
                self.assertFalse(feed(matcher, head, 1).triggered)
                self.assertFalse(feed(matcher, f'{head} {aside}', 3).triggered)
                segments = [
                    dict(start=0, end=3, text=f'{head} {aside}', completed=True),
                    dict(start=3, end=4, text=resume, completed=False),
                ]
                update = matcher.process(f'{head} {aside} {resume}', segments)
                self.assertEqual(update.triggered, should_fire)

    def test_article_omissions_work_on_an_unconfigured_first_checkpoint(self):
        anchor = 'a nimble rabbit brushed the leaves beside wooden gates'
        manifest = config()
        context = 'we followed a narrow path through the garden'
        manifest['pages'][0]['text'] = context + ' ' + anchor
        manifest['checkpoints'][0]['checkpoint_text'] = anchor
        matcher = TimelyEvidenceMatcher(manifest)
        matcher.explain_matches = True
        feed(matcher, 'we followed a narrow path', 1)
        feed(matcher, context, 2)
        self.assertGreater(matcher.tracked_word_position, 0)
        update = feed(matcher, context + ' nimble rabbit brushed leaves beside wooden gates', 3)
        self.assertTrue(update.triggered)
        self.assertEqual(
            [word.expected for word in update.cue_word_evidence if word.kind == 'article_waived'],
            ['a', 'the'],
        )

    def test_missing_content_word_gets_no_credit_even_when_cue_fires(self):
        path = Path(__file__).resolve().parents[1] / (
            'recordings/library/stories/sample/readers/demo/checkpoints.json'
        )
        matcher = TimelyEvidenceMatcher.from_file(path)
        matcher.explain_matches = True
        feed(matcher, 'Mila found a silver seed', 1)
        anchor = 'Mila found a silver seed beside the old gate'
        feed(matcher, anchor, 2)
        text = anchor + ' She carried'
        update = feed(matcher, text, 3)
        self.assertTrue(update.triggered)
        evidence = TranscriptEvidence().update(text, matcher._buffer, update)['evidence']
        self.assertIn({'expected': 'tiny', 'heard': None, 'kind': 'omitted', 'credit': None},
                      evidence['cue_words'])

    def test_sky_garden_flower_accepts_missing_article_and_two_near_words(self):
        path = Path(__file__).resolve().parents[1] / (
            'recordings/library/stories/sample/readers/demo/checkpoints.json'
        )
        for ending, should_fire in (('flower', True), ('garden', False)):
            with self.subTest(ending=ending):
                matcher = TimelyEvidenceMatcher.from_file(path)
                matcher.current_index = 3
                matcher.tracked_word_position = matcher.checkpoint_ranges[2][1]
                matcher._misses = matcher.recovery_after
                update = feed(matcher, 'the little seat opened into right blue ' + ending, 5)
                self.assertEqual(update.triggered, should_fire)
                if should_fire:
                    self.assertEqual(update.checkpoint_id, 'flower_opens')
                    self.assertEqual([word for _, word, _ in update.partial_words], ['seed', 'bright'])

    def test_sky_garden_grass_tolerates_dropped_articles_with_endpoint_evidence(self):
        path = Path(__file__).resolve().parents[1] / (
            'recordings/library/stories/sample/readers/demo/checkpoints.json'
        )
        seed = 'Mila found a tiny silver slit beside the old gate'
        prior = seed + ' She carried it carefully and to quiet water and press onto warm soil'
        grass = 'soft green glass coat across floor like ribbon'
        variants = (
            (grass, True),
            (grass.replace('ribbon', 'river'), False),
            ('repeat ' + grass, False),
            ('soft green birds across floor like ribbon', False),
        )
        for phrase, should_fire in variants:
            with self.subTest(phrase=phrase):
                matcher = TimelyEvidenceMatcher.from_file(path)
                matcher.explain_matches = True
                feed(matcher, seed, 1)
                self.assertTrue(feed(matcher, seed + ' She carried', 2).triggered)
                feed(matcher, prior, 3)
                matcher._misses = matcher.recovery_after
                update = feed(matcher, prior + ' ' + phrase, 4)
                self.assertEqual(update.triggered, should_fire)
                self.assertEqual('grass_grows' in matcher.triggered_checkpoint_ids, should_fire)
                if should_fire:
                    self.assertGreater(update.score, 87.5)
                    transcript = prior + '. Soft green glass coat across floor like ribbon.'
                    display = TranscriptEvidence()
                    panel = display.update(transcript, matcher._buffer, update)
                    self.assertEqual(panel['text'], transcript)
                    self.assertEqual(panel['score'], round(update.score, 1))
                    self.assertIn({'expected': 'curled', 'heard': 'coat', 'kind': 'sound', 'credit': .5},
                                  panel['evidence']['words'])
                    self.assertEqual(
                        [word['expected'] for word in panel['evidence']['cue_words'] if word['kind'] == 'article_waived'],
                        ['the', 'a'],
                    )
                    self.assertEqual(
                        [(transcript[word['start']:word['end']], word['expected']) for word in panel['partial']],
                        [('glass', 'grass'), ('coat', 'curled')],
                    )
                    revised = transcript.replace('glass coat', 'grass curled')
                    later = feed(matcher, revised, 5)
                    self.assertEqual(display.update(revised, matcher._buffer, later)['partial'], [])

    def test_short_post_cue_match_cannot_skip_several_cues(self):
        manifest = config()
        cues = [
            'grandma has a big house with lots of steps',
            'the little rabbit looked out through the window',
            'plants need sunshine to grow nice vegetables and flowers',
        ]
        manifest['pages'] = [
            dict(page=1, text=' '.join(cues[:2])),
            dict(page=2, text=cues[2] + ' gardens do well if they get enough rain'),
        ]
        manifest['checkpoints'] = [
            dict(id=str(i), book_id='timely', checkpoint_position=i + 1,
                 page=1 if i < 2 else 2, checkpoint_text=cue, effect={'effect_id': str(i)})
            for i, cue in enumerate(cues)
        ]
        matcher = TimelyEvidenceMatcher(manifest)
        matcher._misses = matcher.recovery_after * 4
        for second, partial in enumerate(('gardens do well if they', 'do well if they get'), 1):
            self.assertFalse(feed(matcher, partial, second).triggered)
        self.assertEqual(matcher.current_index, 0)
        self.assertEqual(matcher.tracked_word_position, 0)
        self.assertFalse(matcher.skipped_checkpoint_ids)
        start, end = matcher.checkpoint_ranges[2]
        self.assertTrue(matcher._supports_forward_jump(AlignmentSpan(start, end, 100, 9, 9)))

    def test_repetition_with_supported_near_spelling_ending(self):
        old,new=BoundaryEvidenceMatcher(config()),TimelyEvidenceMatcher(config())
        for m in (old,new):feed(m,'grandma has a big house with',1)
        text='grandma has a big house with with a lot of stops'
        self.assertFalse(feed(old,text,2).triggered)
        self.assertTrue(feed(new,text,2).triggered)

    def test_scoped_recovery_threshold_uses_recent_prefix(self):
        m=TimelyEvidenceMatcher(config())
        feed(m,'grandma has a big house with lots of',1)
        for t in (2,3,4):feed(m,'unrelated speech about going outside',t)
        self.assertTrue(feed(m,'grandma has a big house with with a lot of steps',5).triggered)

    def test_no_prefix_stale_prefix_or_same_audio_cannot_supply_credit(self):
        text='grandma has a big house with with a lot of stops'
        self.assertFalse(feed(TimelyEvidenceMatcher(config()),text,2).triggered)
        for t in (1,30):
            m=TimelyEvidenceMatcher(config())
            feed(m,'grandma has a big house with',1)
            self.assertFalse(feed(m,text,t).triggered)

    def test_wrong_ending_and_prompts_do_not_get_repeat_credit(self):
        for prefix,ending in [('', 'doors'),('do not ', 'steps'),('please repeat ', 'steps')]:
            m=TimelyEvidenceMatcher(config())
            feed(m,prefix+'grandma has a big house with',1)
            self.assertFalse(feed(m,prefix+'grandma has a big house with with a lot of '+ending,2).triggered)

    def test_unrecognised_ending_is_not_guessed_from_prefix(self):
        cfg=config();cfg['pages'][0]['text']='I like to help her'
        cfg['checkpoints'][0]['checkpoint_text']='I like to help her'
        m=TimelyEvidenceMatcher(cfg)
        feed(m,'I like to',1)
        self.assertFalse(feed(m,'I like to hope for',2).triggered)

    def test_exact_prefix_before_filler_counts_only_on_next_audio(self):
        m=TimelyEvidenceMatcher(config())
        self.assertFalse(feed(m,'has a big house with a lot',1).triggered)
        self.assertFalse(feed(m,'has a big house with a lot of steps',1).triggered)
        m=TimelyEvidenceMatcher(config())
        feed(m,'has a big house with a lot',1)
        self.assertTrue(feed(m,'has a big house with a lot of steps',2).triggered)


class SkyGardenInterruptionTests(unittest.TestCase):
    def replay(self, turns, stability=1, cumulative=False):
        manifest_path = (
            Path(__file__).resolve().parents[1]
            / "recordings/library/stories/sample/readers/demo/checkpoints.json"
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        matcher = TimelyEvidenceMatcher(manifest, stability=stability)
        segments = []
        updates = []
        for start, end, text in turns:
            segments.append(dict(start=start, end=end, text=text, completed=True))
            transcript = " ".join(segment["text"] for segment in segments)
            snapshot = ([dict(start=0, end=end, text=transcript, completed=False)]
                        if cumulative else segments)
            updates.append(matcher.process(transcript, snapshot))
        return updates

    def test_child_finishes_after_parent_question(self):
        updates = self.replay([
            (0.0, 1.4, "Mila found a tiny silver"),
            (2.0, 4.5, "Take your time, what does that word say?"),
            (5.0, 6.6, "seed beside the old gate"),
            (7.0, 8.6, "seed beside the old gate"),
        ])
        self.assertEqual([update.tracked_word_position for update in updates[:3]], [5, 5, 10])
        self.assertEqual([update.triggered for update in updates], [False, False, True, False])
        self.assertEqual(updates[2].checkpoint_id, "seed_found")

    def test_parent_can_finish_after_long_pause_at_either_stability(self):
        for stability in (1, 2):
            with self.subTest(stability=stability):
                updates = self.replay([
                    (0.0, 1.4, "Mila found a tiny silver"),
                    (90.0, 91.6, "seed beside the old gate"),
                    (92.0, 93.6, "seed beside the old gate"),
                ], stability=stability)
                self.assertEqual([update.triggered for update in updates], [False, True, False])
                self.assertEqual(updates[1].checkpoint_id, "seed_found")

    def test_cumulative_parakeet_snapshot_preserves_interrupted_cue(self):
        updates = self.replay([
            (0.0, 1.4, "Mila found a tiny silver"),
            (2.0, 4.5, "Take your time, what does that word say?"),
            (90.0, 91.6, "seed beside the old gate"),
            (92.0, 93.6, "seed beside the old gate"),
        ], stability=2, cumulative=True)
        self.assertEqual([update.triggered for update in updates], [False, False, True, False])
        self.assertEqual(updates[2].checkpoint_id, "seed_found")

    def test_stray_endpoint_after_conversation_does_not_finish_cue(self):
        updates = self.replay([
            (0.0, 1.4, "Mila found a tiny silver"),
            (2.0, 4.5, "Take your time, what does that word say?"),
            (90.0, 90.5, "gate"),
        ])
        self.assertFalse(any(update.triggered for update in updates))


if __name__=='__main__':unittest.main()
