"""Indian plate normalization, positional correction and confusion-aware distance."""
import re
from dataclasses import dataclass
from .config import STATES

DIGITS = dict(zip('ODILZSGB', '00112568'))
LETTERS = dict(zip('012568', 'OIZSGB'))
LOOKALIKES = {frozenset(p) for p in ('0O', '1I', '1L', '8B', '5S', '2Z', '6G', '0D')}


def clean(text: str) -> str:
    return re.sub('[^A-Z0-9]', '', text.upper())


@dataclass(frozen=True)
class Plate:
    text: str
    valid: bool
    format: str


def normalize(text: str) -> Plate:
    """Correct only format-defined slots; retain unrecognized reads as evidence."""
    raw = clean(text)
    candidates = []
    # Standard AA 0[0] A[A[A]] 0000 and Bharat 00 BH 0000 AA.
    patterns = [('standard', 'LL' + 'D' * district + 'L' * series + 'DDDD')
                for district in (2, 1) for series in (2, 1, 3)]
    patterns.insert(0, ('BH', 'DDLLDDDDLL'))
    for kind, pattern in patterns:
        if len(raw) != len(pattern):
            continue
        value = ''.join((DIGITS if slot == 'D' else LETTERS).get(c, c)
                        for c, slot in zip(raw, pattern))
        if not all(c.isdigit() if s == 'D' else c.isalpha() for c, s in zip(value, pattern)):
            continue
        valid = (value[2:4] == 'BH' and 21 <= int(value[:2]) <= 99) if kind == 'BH' else value[:2] in STATES
        if valid:
            candidates.append((sum(a != b for a, b in zip(raw, value)), value, kind))
    if candidates:
        _, value, kind = min(candidates, key=lambda c: c[0])
        return Plate(value, True, kind)
    return Plate(raw, False, 'unknown')


def weighted_distance(a: str, b: str) -> float:
    """Levenshtein distance: visual substitutions cost 0.3; other edits cost 1."""
    a, b = clean(a), clean(b)
    row = list(map(float, range(len(b) + 1)))
    for i, x in enumerate(a, 1):
        nxt = [float(i)]
        for j, y in enumerate(b, 1):
            cost = 0 if x == y else (0.3 if frozenset((x, y)) in LOOKALIKES else 1)
            nxt.append(min(nxt[-1] + 1, row[j] + 1, row[j - 1] + cost))
        row = nxt
    return round(row[-1], 6)
