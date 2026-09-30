"""Reproducible, user-authorized two-clip case; locations are illustrative."""
import os
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
import hashlib, json, shutil
from pathlib import Path
import cv2
from rapidocr_onnxruntime import RapidOCR

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'frontend/public/real'
DEST = OUT / 'user'
DEST.mkdir(parents=True, exist_ok=True)
cv2.setNumThreads(1)
ocr = RapidOCR(intra_op_num_threads=1, inter_op_num_threads=1)
specs = [
    ('user-vehicle-a', Path(r'D:\final\ibvap\test_videos\vehicle.mp4'), 85, (845, 1165, 1073, 1233), 'Blue', 'van', 'Peugeot', 'Daylight blue van', 'C10', '2026-10-01T09:00:00+05:30'),
    ('user-vehicle-b', Path(r'C:\Users\Navya gupta\OneDrive\Desktop\WhatsApp Video 2026-10-01 at 1.21.12 AM.mp4'), 135, (474, 374, 621, 451), 'Black', 'car', 'Mercedes-Benz', 'Night dark sedan', 'C34', '2026-10-01T09:03:00+05:30'),
]
provenance = dict(source='real', expires_at='2026-10-31T23:59:59+05:30')
bundle = dict(clips=[], analysis={}, tracks={}, counts={}, events=[], trajectories=[])
stops = []
for cid, path, frame, roi, colour, kind, make, label, camera, time in specs:
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
    ok, image = cap.read()
    cap.release()
    if not ok: raise RuntimeError(f'Cannot read {path} at frame {frame}')
    height, width = image.shape[:2]
    x1,y1,x2,y2 = roi
    crop = image[y1:y2, x1:x2]
    cv2.imwrite(str(DEST / f'{cid}-plate.png'), crop)
    cv2.imwrite(str(DEST / f'{cid}-frame.jpg'), image)
    shutil.copyfile(path, DEST / f'{cid}.mp4')
    result, elapsed = ocr(crop, use_det=False, use_cls=False, use_rec=True)
    print(cid, result, flush=True)
    raw, score = (result[0][0], float(result[0][1])) if result else ('', None)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    clip = dict(**provenance, id=cid, video=f'user/{cid}.mp4', fps=fps, width=width, height=height, duration_s=total/fps,
        sha256=sha, camera_id=camera, start_ist=time, staged=True,
        evidence=dict(plate='AI07204', display_plate='AI 0720-4', identity_source='user_confirmed', vehicle_label=label,
            colour=colour, vehicle_class=kind, make=make, crop=f'user/{cid}-plate.png', poster=f'user/{cid}-frame.jpg',
            frame=frame, time_s=frame/fps, roi=list(roi), original_filename=path.name,
            ocr_text=raw, ocr_confidence=score, ocr_engine='RapidOCR 1.4.4 / PP-OCRv4',
            retention_basis='User explicitly requested plate crops for these two clips.'))
    bundle['clips'].append(clip)
    bundle['analysis'][cid] = dict(**provenance, fps=fps, frame_stride=1, frames=[])
    bundle['tracks'][cid] = []
    bundle['counts'][cid] = dict(**provenance, lines=[], crossings=[], totals={}, direction_totals={}, unique_tracks=0, track_classes={}, dwell=dict(mean_s=None, median_s=None, values_s=[]))
    stop = dict(**provenance, clip_id=cid, camera_id=camera, ts_ist=time, video_time_s=frame/fps, track_id=1, confidence=0, staged=True, identity_source='user_confirmed')
    stops.append(stop)
    bundle['events'].append(dict(**stop, id=f'watchlist-{cid}', type='blacklist_match', plate='AI07204', explanation='User-requested test watchlist match for AI 0720-4. Identity is confirmed by the user; this is not an external blacklist lookup.', factors=[dict(label='User-confirmed plate on test watchlist', points=0)]))
bundle['events'].insert(0, dict(**stops[0], id='clone-ai07204', type='clone_suspect', plate='AI07204', sightings=stops,
    explanation='Two visibly different vehicles share the user-confirmed plate AI 0720-4: a blue van and a dark sedan. Review both source recordings and crops. This is a suspected duplicate-plate test case, not a verified crime. Delhi camera locations and capture times are staged; original recording provenance is unverified.',
    factors=[dict(label='Same user-confirmed plate on two different vehicle appearances', points=0)]))
bundle['trajectories'] = [dict(**provenance, plate='AI07204', stops=stops)]
(OUT / 'user-case-bundle.json').write_text(json.dumps(bundle, indent=2), encoding='utf-8')
print('Wrote user-case-bundle.json')
