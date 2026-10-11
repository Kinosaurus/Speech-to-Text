/**
 * Highlight the final result showing correct, skipped, and substituted words.
 *
 * Uses the AlignmentResult's matchedRefIndices, skippedRefIndices, and repetitionRefIndices
 * to determine how to style each word.
 *
 * @param result - The alignment result from TextAligner.
 * @param refWords - The original reference words (with original casing/punctuation).
 * @param finalResultWords - The ASR word results for click-to-play functionality.
 * @param onWordClick - Callback when a word is clicked.
 * @returns A div element with highlighted words.
 */
const highlightFinalResult = ({ result, refWords, finalResultWords, onWordClick, }) => {
    const container = document.createElement('div');
    // Create sets for fast lookup
    const matchedSet = new Set(result.matchedRefIndices);
    const skippedSet = new Set(result.skippedRefIndices);
    const repetitionSet = new Set(result.repetitionRefIndices);
    // Build a map from reference index to recognized word index for click handling
    const refToRecMap = new Map();
    for (const item of result.trace) {
        if (item.op === 0) {
            // MATCH
            refToRecMap.set(item.refIndex, item.recIndex);
        }
        else if (item.op === 1) {
            // SUBSTITUTION
            refToRecMap.set(item.refIndex, item.recIndex);
        }
    }
    for (let i = 0; i < refWords.length; i++) {
        const refWord = refWords[i];
        const spanElement = document.createElement('span');
        spanElement.textContent = refWord;
        if (matchedSet.has(i)) {
            spanElement.classList.add('correct-underline');
            const recIndex = refToRecMap.get(i);
            if (recIndex !== undefined && finalResultWords[recIndex]) {
                const word = finalResultWords[recIndex];
                spanElement.addEventListener('click', (e) => onWordClick(e, word));
            }
        }
        else if (skippedSet.has(i)) {
            spanElement.classList.add('deletion-underline');
        }
        else if (repetitionSet.has(i)) {
            spanElement.classList.add('repetition-underline');
        }
        else {
            // Substitution - word was said differently
            spanElement.classList.add('substitution-underline');
            const recIndex = refToRecMap.get(i);
            if (recIndex !== undefined && finalResultWords[recIndex]) {
                const word = finalResultWords[recIndex];
                spanElement.addEventListener('click', (e) => onWordClick(e, word));
            }
        }
        container.append(spanElement, ' ');
    }
    return container;
};
/**
 * Highlight the next word to be read based on the furthest matched index.
 *
 * Uses the AlignmentResult's furthestMatchedIndex to determine which word
 * to highlight as the next expected word.
 *
 * @param result - The alignment result from TextAligner.
 * @param refWords - The original reference words.
 * @returns A div element with the next word highlighted.
 */
const highlightNextWord = ({ result, refWords, }) => {
    const container = document.createElement('div');
    // The next word to read is the one after the furthest matched index
    const furthestIndex = result.furthestMatchedIndex;
    const nextWordIndex = furthestIndex >= 0 ? furthestIndex + 1 : 0;
    for (let i = 0; i < refWords.length; i++) {
        const refWord = refWords[i];
        const spanElement = document.createElement('span');
        spanElement.textContent = refWord;
        if (i === nextWordIndex) {
            spanElement.classList.add('correct-accent');
        }
        container.append(spanElement, ' ');
    }
    return container;
};

export { highlightFinalResult, highlightNextWord };
