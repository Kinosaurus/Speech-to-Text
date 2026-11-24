# Reading Pod tracker and matcher

The Reading Pod follows a reader through the book and plays sound or projection effects at configured checkpoints. It uses two decisions. The **tracker** confirms the reader's position from a sequence of transcript updates. The **cue check** then decides whether the evidence supports playing the effect for that checkpoint. Separating these decisions lets the tracker keep following the book when it has enough context for the position and an incomplete cue ending.

The `first-pipeline` release used a 6% lookahead. In the saved 25-recording Nemotron replay, it preserved every trigger and the **0.48 s** median estimated delay. In fresh GPU decoding, it reached **32 of 34** configured checkpoints across four recordings. On the Night Tiger recording, it reached **27 of 28** checkpoints and all **14** with sound or visual media listed in the manifest. The current local tracker uses the 5% lookahead described below. [Verified tracker revision](https://github.com/Kinosaurus/Speech-to-Text/commit/78d7bbf71873dbb1e48219f44cef24ee2b68c610)

## Inputs and reading state

Nemotron 160 ms produces a rolling transcript as the reader speaks. **160 ms** is the model's streaming chunk setting. The tracker receives text snapshots and can replace partial text when Nemotron revises it. It retains up to **32 recent transcript words**. The book manifest supplies the ordered page text, checkpoint phrases, and their effects. Each checkpoint uses one phrase, `checkpoint_text`. Full page text remains available as context between checkpoints. [Transcript ingestion and search](../books_to_life/matching/alignment_matcher.py)

The tracker maintains the last confirmed book-word position, the next unread checkpoint, and a record of fired and skipped checkpoints. By default, it searches up to **32 words behind** the confirmed position and ahead by the following amount:

```text
Forward window = clamp(round(0.05 × loaded book words), 12, 60)
```

For *The Night Tiger*, `0.05 × 482 = 24.10`, so the forward limit is **24 words**. Missed updates preserve the default cap. A book with an explicit `alignment.window_words` setting can instead use wider recovery after repeated misses. The backward window lets the tracker recognise a reread, while confirmed progress moves forward through the book. [Forward window and progress](../books_to_life/matching/timely_matcher.py) · [Effect policies](EFFECT_POLICIES.md)

## How the tracker calculates an alignment score

The ordinary matcher compares different lengths of recent speech with the nearby book text. It uses local sequence alignment to find ordered pairs of words. It can retain a strong passage match when the transcript contains an extra word, misses a word, or recognises a word imperfectly.

For transcript word `i` and book word `j`, the alignment search uses these values:

```text
s = spelling similarity on a 0 to 1 scale
pair reward = 2 × s when s ≥ 0.75, otherwise −1
extra or missing word = −2

D(i, j) = max(0,
              D(i−1, j−1) + pair reward,
              D(i−1, j) − 2,
              D(i, j−1) − 2)
```

These values select the sequence of word pairs. The tracker then calculates the reported score using the credits from the selected alignment. A matched pair earns its similarity as credit. An unmatched word contributes zero and can still count toward the length of the aligned span.

```text
Alignment score = 100 × sum of matched-word credits
                       ÷ max(aligned transcript words, aligned book words)
```

The denominator uses the two aligned spans. For example, five exact matches in a six-word alignment score `100 × 5 ÷ 6 = 83.3`. The **82/100** cutoff is the configured starting threshold used in the pilot tests. It expresses how closely the spans match under this formula. [Alignment implementation](../books_to_life/matching/alignment_matcher.py) · [Original threshold recommendation](BOOKS_TO_LIFE_POD_NOTES.md)

## How imperfect words contribute

| Evidence | Credit and conditions |
|---|---|
| Exact word | **1.00** word credit. |
| Fuzzy spelling | Ordinary alignment accepts similarity of **75/100** or higher. `show` against `showed` earns **0.80**. The separate single-word phonetic phrase rule uses **0.75** for a supported spelling variant. |
| Exact split or join | `note book` and `notebook` can match in either direction. Exact groups earn full credit in book-word units. Other words can match by spelling if they meet their usual threshold. |
| CMU pronunciation | The system compares dictionary pronunciations of recognised words. An eligible close sound match can earn **0.75**. The single-word phonetic phrase rule can award **0.50** for a weaker sound match supported by the surrounding text. |
| CMU grouped words | The tracker can combine the pronunciations of two adjacent transcript words to support one optional book word for **0.75** credit. It requires **four other distinct exact words**. Remaining words can qualify through fuzzy spelling. |

The grouped sound and exact spacing rules have separate checks. `note book` joins to the same letters as `notebook`. For `pay seance`, the matcher joins the sounds before comparing them with `patience`. Credits apply to the alignment and leave the transcript text intact. [Spelling groups](../books_to_life/matching/word_boundaries.py) · [Pronunciation comparisons](../books_to_life/matching/phonetic_endpoint.py) · [Cue matching rules](../books_to_life/matching/effect_permission.py)

### Worked example

**Book** — “The children quietly **showed** great **patience**.”  
**Transcript** — “The children quietly **show** great **pay seance**.”

The four exact words supply **4.00** credits. The fuzzy spelling match adds **0.80**. The grouped pronunciation match adds **0.75**. The seven transcript tokens are compared in **six book-word units** after grouping `pay seance`.

The two pronunciations share the first two sounds (`P EY`) and the last two (`N S`). In the middle, changing `SH` to `S` costs **1**, changing a vowel costs **0.25**, and the extra vowel costs **1**. The total of **2.25** meets the grouped rule's edit limit. A qualifying pair earns a fixed **0.75** word credit. [Pronunciation comparison](../books_to_life/matching/phonetic_endpoint.py)

```text
100 × (4.00 + 0.80 + 0.75) ÷ 6 = 92.5/100
```

The alignment clears **82/100**. The cue check has support for **six of six** words, with **five** needed after rounding up `80% × 6`. The final word has eligible grouped sound support. The controlled replay fired the cue. Marking `patience` as a required word makes this sound-only match insufficient. [Worked example regression test](../tests/test_contextual_phonetic_progress.py)

## When the tracker moves or waits

An ordinary alignment needs at least **five matched transcript words**, including **three distinct words**, and matches for at least **80%** of the aligned transcript span. The matched words follow book order and can contain gaps. When two separate, non-overlapping scenes score within **less than four points**, the tracker waits for more evidence. An acceptable candidate normally requires **two confirmations**. Fresh forward progress or a sufficiently strong revised or finalised transcript can contribute evidence. Duplicate updates contribute no confirmation. *The Night Tiger* specifies **one confirmation** at 24 of its 28 checkpoints. [Candidate selection](../books_to_life/matching/alignment_matcher.py) · [Independent confirmations](../books_to_life/matching/evidence_matcher.py)

For a skip, the tracker has to establish a later position from the transcript within its search window. The guarded CMU candidate applies to the **next checkpoint**. In a Night Tiger replay from word **434**, “threw my windows and into” supplied three exact words, one fuzzy word and one CMU-only word. The tracker held its position. Adding `bed` gave it a five-word ordinary alignment, “my windows and into bed,” scoring **98.46/100**. It moved to word **451** and marked page 32 as skipped. The destination cue still went through its own effect check. If a parent speaks off-script, the tracker can hold its last position. Either voice can supply story words because both reach the same transcript. [Forward-jump and interruption rules](../books_to_life/matching/timely_matcher.py)

## When the effect plays

An `ambience` effect can follow a confirmed reading position. A `one_shot` effect normally needs **80% of cue words in order**, rounded up, plus support for the cue ending and any required words. Required words use a stricter **85/100** spelling threshold. A one-shot plays once per session. If a cue fails, the tracker can retain the confirmed position and withhold playback. [Effect permission](../books_to_life/matching/effect_permission.py)

The next, already confirmed cue can also accept an optional final fragment such as `w` for `walls`. The fragment must start the expected word and follow at least **five distinct consecutive exact cue words**, with more context required for longer cues. This allows the Moving Shadows effect to play when the reader's position is clear and the last ASR word is still incomplete. [Final-word fragment rule](../books_to_life/matching/effect_permission.py)

## Verification with Nemotron 160 ms

**Fresh GPU decoding.** Four WAV files were fed to the production Nemotron decoder in **80 ms input packets** with **160 ms model chunks** and fixed hints. The resulting transcript updates were replayed through the `first-pipeline` tracker. The recording inputs and decoder outputs were kept local.

| Recording | Checkpoint events | Events with manifest media |
|---|---:|---:|
| Shepherd passage | **3/3** | — |
| Horse | **1/1** | **1/1** |
| Little Mermaid | **1/2** | **1/2** |
| Night Tiger interruption fixture | **27/28** | **14/14** |
| **Total** | **32/34** | **16/17** |

The Little Mermaid speech cue was withheld, as it was in the saved benchmark. The Night Tiger replay reached the end of the book and withheld `cat_purr`, which had no sound or visual file listed in the tested manifest. No duplicate events fired. This is a saved-audio recognition and tracker check. Physical microphone, projector and speaker timing require a live setup. [Fresh replay totals](../output/nemotron-160-release-verification/fresh-summary.json)

**Saved corpus replay.** The current tracker replayed the same fixed-hint Nemotron updates used in the earlier seeded sample of **25 recordings across 13 passage sections**. It fired **48/50** cues appearing verbatim in the references, or **42/42** on the 21 recordings with spoken references. Both versions fired the same cue IDs and had a **0.48 s** median estimated delay on the 41 shared timed cues. One sheep cue fired **1.29 s later**. Sixteen additional cues fired outside the verbatim-reference set. This set includes wording variants and needs audio review to classify false triggers. [Saved replay results](../output/nemotron-160-release-verification/results.json)

The updated `first-pipeline` branch ran **301 unit tests** with **one skip and zero failures**. The local React production build also passed.

**5% follow-up.** Replaying the same Night Tiger Nemotron 160 ms transcript at **24** and **29** words produced the same **27/28 checkpoint events** and **14/14 media cues** on the same updates. Three earlier saved Night Tiger streams also fired the same cues on the same updates under both limits. The local suite ran **307 tests** with one skip and zero failures.
