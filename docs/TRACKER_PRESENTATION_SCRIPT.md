# Speaker script for slides 38 and 39

Allow about **two minutes** for both slides. Point to the tracker flow on slide 38, then use the two sentences on slide 39 to explain the score.

## Slide 38 · How the Tracker Follows the Story · about 65 seconds

“As the child reads, Nemotron sends us a transcript that updates as it hears more speech. The tracker takes those recent words and compares them with the book, starting near the last place it confirmed.

“It looks for words in the same order. Exact matches get full credit. Close spellings can get partial credit, and we have rules for words that sound similar or get split into two. A good alignment usually needs five matched words, including three different words, and a score of at least 82 out of 100.

“The tracker can look ahead by about 5 percent of the book's total word count, with limits for very short or long books. If the matches are unclear, it holds its place until more speech comes in.

“Once it finds the reader's place, it checks the cue for the effect. We normally need 80 percent of the cue words, including support for the ending and any words we marked as required. When the cue passes, we play the effect once.”

## Slide 39 · How a Cue Gets Its Score · about 50 seconds

“Here's an example. The book says, ‘The children quietly showed great patience.’ The transcript says ‘show’ and splits the sound of ‘patience’ into ‘pay seance.’

“Four words match exactly. ‘Show’ is close enough to ‘showed’ to earn 0.8. For ‘pay seance,’ we put the sounds of the two words together and use the CMU Pronouncing Dictionary to compare them with ‘patience.’ That earns another 0.75 for one book word. The four exact words give us the context to make that comparison.

“Add those credits and divide by the six book words. That gives us 92.5 out of 100, above the 82 cutoff. The cue check needs five of the six words. We have support for all six, so the effect can play.”

## Optional transition to the demo

“The score tells us where the reader is. The cue check tells us when the room should respond. Watch what happens when I read the line.”

## If asked about skips or testing

**What happens when the reader skips a line?** “The tracker holds its place until the new words give it enough evidence to move. In our Night Tiger replay, it held with four spelling-supported words and moved after one more exact word arrived. The target cue still had to pass its own check.”

**Why does the sound match earn 0.75?** “The words start and end with the same sounds. The middle has a consonant change, a vowel change, and an extra vowel. That falls within our tolerance for a close sound match. We give qualifying sound matches three-quarters of a word's credit.”

**How did you test it?** “We decoded fresh recordings with Nemotron at 160 milliseconds and replayed the transcript updates through the tracker. It reached 32 of 34 configured checkpoints. For Night Tiger, it fired all 14 cues that had media in the test manifest. We also replayed 25 saved recordings and got the same 48 out of 50 exact-reference cues as before.”
