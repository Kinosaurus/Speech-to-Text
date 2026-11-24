"""Match adjacent token groups without changing their transcript text."""


PROMPT_WORDS = frozenset({'not', 'never', 'dont', "don't", 'say', 'repeat'})


def _boundary_paths(reference, heard, end, word_credit):
    # Walk backwards from a recent endpoint. A path must cover the full
    # reference in order and consume each transcript token at most once.
    states = [{} for _ in range(len(reference) + 1)]
    states[-1][end, False] = (0.0, ())
    for i in range(len(reference), 0, -1):
        word = reference[i - 1]
        for (j, changed), (score, suffix) in states[i].items():
            if j == 0:
                continue
            options = []
            credit = word_credit(word, heard[j - 1])
            if credit is not None:
                options.append((1, 1, credit))
            if j >= 2 and word == heard[j - 2] + heard[j - 1]:
                options.append((1, 2, 1.0))
            # Keep authored prompts and negation visible. "notice" cannot
            # supply the two book words "not ice".
            if (i >= 2 and reference[i - 2] not in PROMPT_WORDS and word not in PROMPT_WORDS
                    and reference[i - 2] + word == heard[j - 1]):
                options.append((2, 1, 2.0))
            for book_width, heard_width, credit in options:
                book_start, heard_start = i - book_width, j - heard_width
                key = (heard_start, changed or book_width != heard_width)
                previous = states[book_start].get(key)
                total = score + credit
                if previous is None or total > previous[0]:
                    group = (reference[book_start:i], heard[heard_start:j], credit)
                    states[book_start][key] = (total, (group, *suffix))
    return states[0]


def exact_boundary_match(reference, heard):
    """Allow an exact join of two adjacent words on either side."""
    if not reference or not heard or any(not word for word in (*reference, *heard)):
        return False
    if ''.join(reference) != ''.join(heard):
        return False
    paths = _boundary_paths(reference, heard, len(heard), lambda word, token: 1.0 if word == token else None)
    return (0, False) in paths or (0, True) in paths


def recent_boundary_matches(reference, buffer, word_credit):
    """Yield prefix, credit and groups for recent cues with a spacing change."""
    query = buffer[-(2*len(reference)+3):]
    for end in range(len(query), max(0, len(query)-4), -1):
        for (start, changed), (score, groups) in _boundary_paths(reference, query, end, word_credit).items():
            if changed:
                yield query[max(0, start-3):start], score, groups
