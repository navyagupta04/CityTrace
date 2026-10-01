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
        assert clip['evidence']['time_s'] == clip['evidence']['frame'] / clip['fps']
        assert 0 <= clip['evidence']['time_s'] < clip['duration_s']
        x1,y1,x2,y2 = clip['evidence']['roi']
        assert 0 <= x1 < x2 <= frame.shape[1] and 0 <= y1 < y2 <= frame.shape[0]
        if clip['evidence'].get('crop'):
            crop = cv2.imread(str(ROOT / clip['evidence']['crop']))
            assert np.array_equal(crop, frame[y1:y2,x1:x2])


def test_clone_pairs_blue_vehicle_with_new_source_and_keeps_older_evidence():
    data = json.loads((ROOT / 'user-case-bundle.json').read_text())
    clips = {c['id']: c for c in data['clips']}
    clone = next(e for e in data['events'] if e['type'] == 'clone_suspect')
    assert [s['clip_id'] for s in clone['sightings']] == ['user-vehicle-a', 'user-vehicle-c']
    assert clips['user-vehicle-c']['evidence']['original_filename'] == 'gemini_generated_video_bdab81d9.mp4'
    assert clips['user-vehicle-c']['generated'] is True
    assert not clips['user-vehicle-c']['evidence'].get('crop')
    assert not clips['user-vehicle-c']['evidence'].get('poster')
    assert clips['user-vehicle-c']['evidence']['ocr_text'] != clips['user-vehicle-c']['evidence']['plate']
    assert clone['basis'] == 'appearance_mismatch'
    assert {r['code'] for r in clone['review_reasons']} == {'same_confirmed_plate', 'body_mismatch', 'colour_mismatch'}
    assert 'distance_km' not in clone and 'implied_kmh' not in clone
    assert any(e['id'] == 'watchlist-user-vehicle-b' for e in data['events'])
    assert len(data['trajectories'][0]['stops']) == 3
