"""Exact text equivalence across bounded, adjacent token groups."""


def exact_boundary_match(reference, heard):
    """Consume each reference word as one or two whole adjacent ASR tokens.

    No characters, words or gaps may be added, omitted, substituted or reused.
    This handles ASR word-boundary differences without a word-pair dictionary.
    """
    if not reference or not heard or any(not word for word in (*reference, *heard)):
        return False
    if ''.join(reference) != ''.join(heard):
        return False
    n, m = len(reference), len(heard)
    reached = {(0, 0)}
    for i in range(n):
        for j in range(m):
            if (i, j) not in reached:
                continue
            for width_heard in (1, 2):
                if j+width_heard <= m and reference[i] == ''.join(heard[j:j+width_heard]):
                    reached.add((i+1, j+width_heard))
    return (n, m) in reached


def recent_boundary_spans(reference, buffer):
    """Yield complete contiguous anchors ending within the last four tokens."""
    expected = ''.join(reference)
    query = buffer[-(2*len(reference)+3):]
    for end in range(len(query), max(0, len(query)-4), -1):
        for start in range(end-1, max(-1, end-2*len(reference)-1), -1):
            heard = query[start:end]
            length = sum(map(len, heard))
            if length > len(expected):
                break
            if length == len(expected):
                if heard != reference and exact_boundary_match(reference, heard):
                    yield query[max(0, start-3):start]
                break
