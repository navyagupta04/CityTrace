"""Add the supplied generated sedan clip to the reviewed blue-vehicle clone case.

OCR is executed on unchanged source pixels in a manually reviewed ROI. The plate
link is the user's confirmation, never a replacement for the engine output.
Existing clips, watchlist events and trajectory stops are preserved.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
import cv2
from rapidocr_onnxruntime import RapidOCR

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'frontend/public/real'
CLIP_ID = 'user-vehicle-c'


def update_case(source: Path, frame_number=136, roi=(492, 382, 618, 439)):
    bundle_path = OUT / 'user-case-bundle.json'
    bundle = json.loads(bundle_path.read_text(encoding='utf-8'))
    blue = next(c for c in bundle['clips'] if c['id'] == 'user-vehicle-a')
    blue_stop = next(s for t in bundle['trajectories'] for s in t['stops']
                     if s['clip_id'] == blue['id'])
    cap = cv2.VideoCapture(str(source))
    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ok, image = cap.read()
    finally:
        cap.release()
    if not ok or fps <= 0:
        raise ValueError(f'Cannot decode {source} at frame {frame_number}')
    height, width = image.shape[:2]
    x1, y1, x2, y2 = roi
    if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
        raise ValueError('Reviewed plate ROI must lie inside the video frame')
    cv2.setNumThreads(1)
    engine = RapidOCR(intra_op_num_threads=1, inter_op_num_threads=1)
    result, _ = engine(image[y1:y2, x1:x2], use_det=False, use_cls=False, use_rec=True)
    raw, confidence = (result[0][0], float(result[0][1])) if result else ('', None)
    target = OUT / f'user/{CLIP_ID}.mp4'
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    sha256 = hashlib.sha256(target.read_bytes()).hexdigest()
    provenance = dict(source='real', expires_at=blue['expires_at'])
    clip = dict(
        **provenance, id=CLIP_ID, video=f'user/{CLIP_ID}.mp4', fps=fps,
        width=width, height=height, duration_s=total / fps, sha256=sha256,
        camera_id='C34', start_ist='2026-10-01T09:06:00+05:30', staged=True,
        generated=True,
        evidence=dict(
            plate=blue['evidence']['plate'], display_plate=blue['evidence']['display_plate'],
            identity_source='user_confirmed', vehicle_label='New daylight dark sedan',
            colour='Dark grey / black', vehicle_class='sedan', make='Not verified',
            appearance_source='manual_review', frame=frame_number,
            time_s=frame_number / fps, roi=list(roi), original_filename=source.name,
            ocr_text=raw, ocr_confidence=confidence,
            ocr_engine='RapidOCR 1.4.4 / PP-OCRv4',
            retention_basis='Source video retained for the requested comparison; no new crop or poster stored.',
        ),
    )
    stop = dict(**provenance, clip_id=CLIP_ID, camera_id=clip['camera_id'],
                ts_ist=clip['start_ist'], video_time_s=clip['evidence']['time_s'],
                track_id=1, confidence=0, staged=True, identity_source='user_confirmed')
    bundle['clips'] = [c for c in bundle['clips'] if c['id'] != CLIP_ID] + [clip]
    bundle['analysis'][CLIP_ID] = dict(**provenance, fps=fps, frame_stride=1, frames=[])
    bundle['tracks'][CLIP_ID] = []
    bundle['counts'][CLIP_ID] = dict(**provenance, lines=[], crossings=[], totals={},
                                    direction_totals={}, unique_tracks=0, track_classes={},
                                    dwell=dict(mean_s=None, median_s=None, values_s=[]))
    clone = next(e for e in bundle['events'] if e['id'] == 'clone-ai07204')
    clone.update(
        sightings=[blue_stop, stop], basis='appearance_mismatch',
        generated=True,
        explanation='Suspected plate cloning: the existing blue van and the new dark sedan '
                    'are linked to the same registration by your confirmation, but have '
                    'different body structures and colours. Compare the two source videos '
                    'at their reviewed sighting times. The raw OCR differs from the '
                    'confirmed identity, so this is a review alert, not an automatic exact-plate match.',
        review_reasons=[
            dict(code='same_confirmed_plate', label='Same user-confirmed registration',
                 detail='You identified both recordings as carrying the same plate. This '
                        'links the evidence for review; it is not an independent OCR agreement.'),
            dict(code='body_mismatch', label='Different vehicle body structure',
                 detail='The existing vehicle is a tall, box-shaped blue van with a short '
                        'bonnet and upright cabin. The new vehicle is a low four-door sedan '
                        'with a long bonnet and a separate rear boot. Lighting cannot '
                        'explain this structural difference.'),
            dict(code='colour_mismatch', label='Different visible body colour',
                 detail='The existing vehicle is bright blue; the new sedan appears dark '
                        'grey or black. Colour supports the body mismatch, but lighting '
                        'and repainting can affect colour and it is not sufficient alone.'),
        ],
        limitations=[
            'Appearance descriptions are manually reviewed observations, not classifier measurements.',
            'Raw OCR disagrees with the user-confirmed plate in both clips. Check the '
            'source frames before verifying the alert; the engine score is not cloning probability.',
            'The new recording is generated test footage. Its plate characters and on-screen '
            'clock may vary; these overlays do not establish a capture time or real camera identity.',
            'Delhi camera assignments and times are staged. No impossible-travel claim '
            'or continuous journey between these vehicles is used to trigger this alert.',
            'No registry or ownership record establishes which vehicle is legitimate. '
            'The case remains suspected until a reviewer verifies the identities.',
        ],
        factors=[dict(label='Same user-confirmed registration with different vehicle bodies', points=0)],
    )
    for key in ('distance_km', 'elapsed_s', 'implied_kmh'):
        clone.pop(key, None)
    journey = next(t for t in bundle['trajectories'] if t['plate'] == clip['evidence']['plate'])
    journey['stops'] = [s for s in journey['stops'] if s['clip_id'] != CLIP_ID] + [stop]
    bundle_path.write_text(json.dumps(bundle, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(clip=CLIP_ID, frame=frame_number, ocr_text=raw,
                         ocr_confidence=confidence, sha256=sha256)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    args = parser.parse_args()
    update_case(args.source)
