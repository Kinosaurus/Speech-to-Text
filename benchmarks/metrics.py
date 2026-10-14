"""Transparent reference scoring and revision-safe transcript snapshots."""
import re


def words(text):
    text = text.lower().replace('\u2019', "'")
    # Orthographic choices are not recognition errors ("couldn't" vs "could not").
    contractions = {"can't": 'can not', "cannot": 'can not', "won't": 'will not',
                    "i'm": 'i am', "it's": 'it is', "that's": 'that is',
                    "there's": 'there is', "what's": 'what is', "who's": 'who is',
                    "you're": 'you are', "we're": 'we are', "they're": 'they are'}
    tokens = re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)?", text)
    normalized = []
    for token in tokens:
        if token in contractions:
            normalized.extend(contractions[token].split())
        elif token.endswith("n't"):
            normalized.extend((token[:-3], 'not'))
        else:
            normalized.append(token)
    return normalized


def edit_alignment(reference, hypothesis):
    """Return edit counts and reference->hypothesis matches for word timing."""
    r, h = words(reference), words(hypothesis)
    matrix = [[0] * (len(h) + 1) for _ in range(len(r) + 1)]
    for i in range(len(r) + 1):
        matrix[i][0] = i
    for j in range(len(h) + 1):
        matrix[0][j] = j
    for i in range(1, len(r) + 1):
        for j in range(1, len(h) + 1):
            matrix[i][j] = min(matrix[i - 1][j] + 1, matrix[i][j - 1] + 1,
                               matrix[i - 1][j - 1] + (r[i - 1] != h[j - 1]))
    i, j = len(r), len(h)
    counts = dict(substitutions=0, deletions=0, insertions=0)
    matches = {}
    while i or j:
        if i and j and matrix[i][j] == matrix[i - 1][j - 1] + (r[i - 1] != h[j - 1]):
            if r[i - 1] == h[j - 1]:
                matches[i - 1] = j - 1
            else:
                counts['substitutions'] += 1
            i -= 1
            j -= 1
        elif i and matrix[i][j] == matrix[i - 1][j] + 1:
            counts['deletions'] += 1
            i -= 1
        else:
            counts['insertions'] += 1
            j -= 1
    return {**counts, 'reference_words': len(r),
            'wer': sum(counts.values()) / len(r) if r else None}, matches


def latest_text(segments):
    """A full backend snapshot replaces its predecessor; never concatenate revisions."""
    return ' '.join(str(s.get('text', '')).strip() for s in segments).strip()


def estimated_anchor_times(reference, timed_words, checkpoints):
    """Estimate endpoints with a separate offline transcript; not manual ground truth."""
    tokens = []
    for item in timed_words:
        tokens.extend({'word': token, 'end': float(item['end'])} for token in words(item['word']))
    _, matches = edit_alignment(reference, ' '.join(item['word'] for item in tokens))
    from checkpoint_matcher import normalize_text
    reference_tokens = normalize_text(reference).split()
    result = {}
    for checkpoint in checkpoints:
        endpoint = len(words(' '.join(reference_tokens[:checkpoint['word_end']]))) - 1
        if endpoint in matches:
            result[str(checkpoint['id'])] = tokens[matches[endpoint]]['end']
    return result
