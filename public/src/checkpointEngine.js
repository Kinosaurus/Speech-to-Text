/**
 * Checkpoint engine.
 *
 * Decides when a child has "reached" a checkpoint phrase while reading aloud.
 * Tuned to be forgiving of mispronunciations and to let a skipped
 * checkpoint be recovered if the child goes back and re-reads it.
 *
 * Usage:
 *   const engine = createCheckpointEngine(bookConfig, event => { ... });
 *   engine.update(alignment, transcript, isFinal);
 */
import { normalize } from './textUtils.js';

// Children mispronounce, drop endings ("pretty" for "prettiest") and the
// recogniser mishears them, so words are compared loosely.
export function wordsClose(a, b) {
  if (!a || !b) return false;
  if (a === b) return true;

  const shorter = a.length <= b.length ? a : b;
  const longer = a.length <= b.length ? b : a;

  // Same stem: pretty / prettiest, look / looked, leg / legs
  if (shorter.length >= 3 && longer.startsWith(shorter)) return true;

  if (shorter.length < 4) return false;

  // Edit-distance similarity for near-misses
  const prev = Array.from({ length: b.length + 1 }, (_, j) => j);
  for (let i = 1; i <= a.length; i++) {
    let diagonal = prev[0];
    prev[0] = i;
    for (let j = 1; j <= b.length; j++) {
      const temp = prev[j];
      prev[j] = Math.min(
        prev[j] + 1,
        prev[j - 1] + 1,
        diagonal + (a[i - 1] === b[j - 1] ? 0 : 1)
      );
      diagonal = temp;
    }
  }
  return 1 - prev[b.length] / longer.length >= 0.7;
}

// Ordered, tolerant match of the checkpoint phrase against the end of the
// transcript (longest common subsequence). This catches a re-read even
// when the aligner has already moved past the checkpoint.
export function transcriptCoverage(checkpointText, transcript) {
  const target = normalize(checkpointText).split(' ').filter(Boolean);
  const spoken = normalize(transcript).split(' ').filter(Boolean);

  if (!target.length || !spoken.length) return 0;

  const tail = spoken.slice(-(target.length + 6));
  const table = Array.from(
    { length: target.length + 1 },
    () => new Array(tail.length + 1).fill(0)
  );

  for (let i = 1; i <= target.length; i++) {
    for (let j = 1; j <= tail.length; j++) {
      table[i][j] = wordsClose(target[i - 1], tail[j - 1])
        ? table[i - 1][j - 1] + 1
        : Math.max(table[i - 1][j], table[i][j - 1]);
    }
  }

  return table[target.length][tail.length] / target.length;
}

export function createCheckpointEngine(config, onEvent) {
  // Deliberately forgiving defaults for young readers. The JSON values are
  // only used if they are MORE lenient than these.
  const settings = {
    minCoverage: Math.min(Number(config.min_coverage ?? 0.6), 0.6),
    stability: Math.min(
      Math.max(1, Number(config.stability ?? 2)),
      2
    ),
    substitutionCredit: 0.5, // a mispronounced word still counts half
    recoveryAfter: Math.max(
      1,
      Number(config.alignment?.recovery_after ?? 3)
    ),
    backtrackWords: Math.max(
      0,
      Number(config.alignment?.backtrack_words ?? 32)
    )
  };

  const checkpoints = config.checkpoints.map(checkpoint => ({
    ...checkpoint,
    status: 'pending',
    consecutiveHits: 0,
    recovered: false
  }));

  function alignmentCoverage(alignment, start, end) {
    const matchedSet = new Set(alignment?.matchedRefIndices ?? []);
    const substituted = new Set();

    for (const item of alignment?.trace ?? []) {
      if (item.op === 1) substituted.add(item.refIndex); // substitution
    }

    let score = 0;
    for (let index = start; index < end; index++) {
      if (matchedSet.has(index)) score += 1;
      else if (substituted.has(index)) score += settings.substitutionCredit;
    }

    return end > start ? score / (end - start) : 0;
  }

  function update(alignment, transcript, isFinal = false) {
    const furthestIndex = Number.isInteger(alignment?.furthestMatchedIndex)
      ? alignment.furthestMatchedIndex
      : -1;

    for (const checkpoint of checkpoints) {
      if (checkpoint.status === 'triggered') continue;

      const start = checkpoint.word_start;
      const end = checkpoint.word_end;
      const wasSkipped = checkpoint.status === 'skipped';

      // A skipped checkpoint can only be recovered while the reader is
      // still near it, so a re-read much later is not mistaken for it.
      if (
        wasSkipped &&
        furthestIndex - end > settings.backtrackWords
      ) {
        continue;
      }

      // Best of: aligner result (with half credit for mispronounced
      // words) and a tolerant look at what was just said.
      const coverage = Math.max(
        alignmentCoverage(alignment, start, end),
        transcriptCoverage(checkpoint.checkpoint_text, transcript)
      );

      if (coverage >= settings.minCoverage) {
        checkpoint.consecutiveHits += 1;
      } else {
        checkpoint.consecutiveHits = 0;
      }

      // The final result counts as confirmation, so a child who reads it
      // correctly once is never penalised for the stability rule.
      const confirmed =
        checkpoint.consecutiveHits >= settings.stability ||
        (isFinal && checkpoint.consecutiveHits >= 1);

      if (confirmed) {
        checkpoint.status = 'triggered';
        checkpoint.recovered = wasSkipped;

        onEvent({
          type: 'triggered',
          recovered: wasSkipped,
          checkpoint,
          message: wasSkipped
            ? `Checkpoint recovered after re-read: ${checkpoint.checkpoint_text}`
            : `Checkpoint reached: ${checkpoint.checkpoint_text}`
        });

        continue;
      }

      if (
        checkpoint.status === 'pending' &&
        furthestIndex >= end + settings.recoveryAfter - 1
      ) {
        checkpoint.status = 'skipped';
        checkpoint.consecutiveHits = 0;

        onEvent({
          type: 'skipped',
          checkpoint,
          message: `Possible skipped checkpoint: ${checkpoint.checkpoint_text}`
        });
      }
    }

    return {
      furthestIndex,
      checkpoints: checkpoints.map(checkpoint => ({ ...checkpoint }))
    };
  }

  function reset() {
    for (const checkpoint of checkpoints) {
      checkpoint.status = 'pending';
      checkpoint.consecutiveHits = 0;
      checkpoint.recovered = false;
    }
  }

  function getStates() {
    return checkpoints.map(checkpoint => ({ ...checkpoint }));
  }

  return { update, reset, getStates };
}
