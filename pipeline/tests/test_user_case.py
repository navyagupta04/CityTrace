"""Verify the evidence artifacts against actual video bytes, not invented crops."""
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2] / 'frontend/public/real'

def test_user_evidence_crops_are_exact_source_pixels():
    data = json.loads((ROOT / 'user-case-bundle.json').read_text())
    for clip in data['clips']:
        video = ROOT / clip['video']
        assert hashlib.sha256(video.read_bytes()).hexdigest() == clip['sha256']
        cap = cv2.VideoCapture(str(video))
        cap.set(cv2.CAP_PROP_POS_FRAMES, clip['evidence']['frame'])
        ok, frame = cap.read()
        cap.release()
        assert ok
        x1,y1,x2,y2 = clip['evidence']['roi']
        crop = cv2.imread(str(ROOT / clip['evidence']['crop']))
        assert np.array_equal(crop, frame[y1:y2,x1:x2])
        assert 0 <= clip['evidence']['time_s'] < clip['duration_s']
