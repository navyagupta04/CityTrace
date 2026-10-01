"""Multi-frame pass aggregation and optional, lazily imported vision helpers."""
from collections import defaultdict
from dataclasses import dataclass, field
from .plates import normalize, clean


@dataclass(frozen=True)
class Read:
    text: str
    confidence: float
    quality: float = 1.0
    characters: tuple = ()
    detection_confidence: float | None = None


def vote(reads: list[Read]) -> tuple[str, float]:
    """Weighted character vote within the strongest length cohort.

    Confidence includes OCR certainty, image quality and inter-frame agreement;
    consensus alone must not convert poor reads into high-confidence evidence.
    """
    if not reads:
        return '', 0.0
    groups = defaultdict(list)
    for read in reads:
        text = normalize(read.text).text
        if text:
            groups[len(text)].append((text, max(0, read.confidence * read.quality), read))
    if not groups:
        return '', 0.0
    group = max(groups.values(), key=lambda g: sum(w for _, w, _ in g))
    total = sum(w for _, w, _ in group)
    if total == 0:
        return normalize(group[0][0]).text, 0.0
    result, agreements = [], []
    for i in range(len(group[0][0])):
        weights = defaultdict(float)
        for text, weight, _ in group:
            weights[text[i]] += weight
        char = max(weights, key=weights.get)
        result.append(char)
        agreements.append(weights[char] / total)
    certainty = sum(w * read.confidence * (0.5 + 0.5 * read.quality) for _, w, read in group) / total
    agreement = sum(agreements) / len(agreements)
    cohort = total / sum(w for g in groups.values() for _, w, _ in g)
    return normalize(''.join(result)).text, round(certainty * agreement * cohort, 4)


def plate_quality(crop) -> float:
    """Laplacian sharpness and nonclipped exposure, computed only with OpenCV."""
    import cv2
    import numpy as np
    if crop is None or crop.size == 0:
        return 0.0
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    sharpness = min(float(cv2.Laplacian(gray, cv2.CV_64F).var()) / 250, 1)
    exposure = float(np.mean((gray > 15) & (gray < 240)))
    return round(0.5 * sharpness + 0.5 * exposure, 4)


@dataclass
class Track:
    first: float
    last: float
    vehicle_type: str
    reads: list[Read] = field(default_factory=list)


class TrackAggregator:
    """Emit one pass per track after disappearance or at end of video."""
    def __init__(self, gap_seconds: float = 2.0):
        self.tracks: dict[str, Track] = {}
        self.gap_seconds = gap_seconds

    def add(self, track_id: str, seconds: float, vehicle_type: str, read: Read | None):
        track = self.tracks.setdefault(track_id, Track(seconds, seconds, vehicle_type))
        track.last = seconds
        if read and clean(read.text):
            track.reads.append(read)

    def flush(self, seconds: float, force: bool = False) -> list[tuple[str, Track]]:
        ready = [(key, track) for key, track in self.tracks.items()
                 if force or seconds - track.last > self.gap_seconds]
        for key, _ in ready:
            del self.tracks[key]
        return ready
