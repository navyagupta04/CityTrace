"""Local YOLO tracking + optional plate detector + PaddleOCR 3.x ingestion.

Run python -m tools.process_video --help. No vision imports occur at module load.
"""
import argparse
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import time
from urllib.request import Request, urlopen
from urllib.error import URLError
from anpr.vision import Read, TrackAggregator, plate_quality, vote
from anpr.plates import clean
from anpr.config import CAMERAS


def ocr_candidates(results) -> list[tuple[str, float]]:
    """Parse PaddleOCR 3.x result mappings, including split plate text lines."""
    candidates = []
    for result in results:
        texts = result.get('rec_texts', [])
        scores = result.get('rec_scores', [])
        pairs = [(str(text), float(score)) for text, score in zip(texts, scores)]
        candidates.extend(pairs)
        if 1 < len(pairs) <= 3:
            candidates.append((''.join(text for text, _ in pairs), min(score for _, score in pairs)))
    return [(text, score) for text, score in candidates if 8 <= len(clean(text)) <= 12 and score >= 0.35]


def post_event(api: str, endpoint: str, event: dict, key: str, spool: Path):
    """Spool before delivery; retries use the same ingestion id."""
    spool.parent.mkdir(parents=True, exist_ok=True)
    with spool.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({'endpoint': endpoint, 'event': event}) + '\n')
    request = Request(api.rstrip('/') + '/api/' + endpoint, data=json.dumps(event).encode(), method='POST',
                      headers={'Content-Type': 'application/json', 'X-Role': 'officer', 'X-API-Key': key})
    for attempt in range(3):
        try:
            with urlopen(request, timeout=20) as response:
                return json.load(response)
        except URLError:
            if attempt == 2:
                raise
            time.sleep(0.5 * (attempt + 1))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video', type=Path)
    parser.add_argument('--camera', required=True, choices=[c.id for c in CAMERAS])
    parser.add_argument('--vehicle-model', type=Path, required=True, help='Existing local YOLO .pt weights; never auto-downloaded')
    parser.add_argument('--plate-model', type=Path, help='Local plate-specific YOLO detector (recommended)')
    parser.add_argument('--ocr-det-dir', type=Path, help='Local PaddleOCR detection model directory')
    parser.add_argument('--ocr-rec-dir', type=Path, help='Local PaddleOCR recognition model directory')
    parser.add_argument('--detect-only', action='store_true', help='Track and post anonymous traffic counts, with no OCR')
    parser.add_argument('--api', default='http://127.0.0.1:8000')
    parser.add_argument('--start', help='Capture start in ISO 8601 with timezone; default current UTC')
    parser.add_argument('--ocr-every', type=int, default=5)
    parser.add_argument('--output-video', type=Path)
    parser.add_argument('--analysis-json', type=Path, help='Write real per-frame detections for the React video overlay')
    parser.add_argument('--spool', type=Path, default=Path('output/video-events.jsonl'))
    args = parser.parse_args()
    for path in [args.video, args.vehicle_model] + ([args.plate_model] if args.plate_model else []):
        if not path.is_file():
            parser.error(f'File does not exist: {path}')
    if args.ocr_every < 1:
        parser.error('--ocr-every must be positive')
    if not args.detect_only and not all(p and p.is_dir() for p in (args.ocr_det_dir, args.ocr_rec_dir)):
        parser.error('OCR requires local --ocr-det-dir and --ocr-rec-dir; use --detect-only for density tests')
    start = datetime.fromisoformat(args.start) if args.start else datetime.now(timezone.utc)
    if start.tzinfo is None:
        parser.error('--start requires an explicit timezone')
    try:
        import cv2
        from ultralytics import YOLO
    except ImportError as error:
        parser.exit(2, f'Optional vision dependencies missing: {error}. Install requirements-vision.txt\n')
    detector = YOLO(str(args.vehicle_model.resolve()))
    plate_detector = YOLO(str(args.plate_model.resolve())) if args.plate_model else None
    ocr = None
    if not args.detect_only:
        try:
            from paddleocr import PaddleOCR
        except ImportError:
            parser.exit(2, 'PaddleOCR is missing. Install requirements-vision.txt\n')
        ocr = PaddleOCR(device='cpu', text_detection_model_dir=str(args.ocr_det_dir.resolve()),
                        text_recognition_model_dir=str(args.ocr_rec_dir.resolve()),
                        use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False)
    capture = cv2.VideoCapture(str(args.video))
    if not capture.isOpened():
        parser.exit(2, 'Could not open video\n')
    fps = capture.get(cv2.CAP_PROP_FPS)
    if not fps or fps <= 0:
        capture.release()
        parser.exit(2, 'Video has no valid frame rate; remux it with explicit timestamps\n')
    # Stable replay IDs when file, camera and capture start are identical.
    with args.video.open('rb') as stream:
        file_hash = sha256()
        while chunk := stream.read(1024 * 1024):
            file_hash.update(chunk)
    run_id = sha256((file_hash.hexdigest() + args.camera + start.isoformat()).encode()).hexdigest()[:20]
    aggregator = TrackAggregator()
    frame_number, posted, unidentified = 0, 0, 0
    writer = None
    analysis_stream = None
    analysis_first = True
    stable_boxes = {}
    track_observations = {}
    if args.analysis_json:
        args.analysis_json.parent.mkdir(parents=True, exist_ok=True)
        analysis_stream = args.analysis_json.open('w', encoding='utf-8')
        analysis_stream.write(json.dumps({'fps': fps})[:-1] + ',"frames":[')
    key = os.getenv('ANPR_API_KEY', '')
    if args.output_video:
        args.output_video.parent.mkdir(parents=True, exist_ok=True)
        size = (int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        writer = cv2.VideoWriter(str(args.output_video), cv2.VideoWriter_fourcc(*'mp4v'), fps, size)
        if not writer.isOpened():
            capture.release()
            parser.exit(2, 'Could not create output video\n')

    def deliver(ready):
        nonlocal posted, unidentified
        for track_id, track in ready:
            event = {'event_id': f'video-{run_id}-{track_id}-{track.first:.3f}', 'camera_id': args.camera,
                     'timestamp': (start + timedelta(seconds=track.first)).isoformat(),
                     'vehicle_type': track.vehicle_type, 'source': f'video:{file_hash.hexdigest()[:16]}'}
            if track.reads and vote(track.reads)[0]:
                event['reads'] = [asdict(r) for r in track.reads]
                post_event(args.api, 'ingest', event, key, args.spool)
                posted += 1
            else:
                post_event(args.api, 'traffic', event, key, args.spool)
                unidentified += 1
            print(f'Track {track_id}: {"plate event" if track.reads else "unidentified traffic pass"}', flush=True)

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            seconds = frame_number / fps
            deliver(aggregator.flush(seconds))
            result = detector.track(frame, persist=True, tracker='bytetrack.yaml', device='cpu', verbose=False,
                                    classes=[2, 3, 5, 7], conf=0.4)[0]
            boxes = result.boxes
            frame_detections = []
            if boxes is not None and boxes.id is not None:
                for xyxy, track_id, category, detection_confidence in zip(boxes.xyxy.cpu().tolist(), boxes.id.int().cpu().tolist(), boxes.cls.int().cpu().tolist(), boxes.conf.cpu().tolist()):
                    vehicle_type = {2: 'car', 3: 'motorcycle', 5: 'bus', 7: 'truck'}.get(category, 'unknown')
                    read = None
                    if ocr and frame_number % args.ocr_every == 0:
                        x1, y1, x2, y2 = [int(v) for v in xyxy]
                        crop = frame[max(0, y1):max(0, y2), max(0, x1):max(0, x2)]
                        if crop.size:
                            if plate_detector:
                                plates = plate_detector.predict(crop, device='cpu', verbose=False)[0].boxes
                                if plates is not None and len(plates):
                                    best = int(plates.conf.argmax())
                                    a, b, c, d = [int(v) for v in plates.xyxy[best].cpu().tolist()]
                                    crop = crop[max(0, b):max(0, d), max(0, a):max(0, c)]
                                else:
                                    crop = None
                            else:
                                # Explicit heuristic fallback, unsuitable for accuracy claims.
                                height, width = crop.shape[:2]
                                crop = crop[int(height * .5):, int(width * .15):int(width * .85)]
                            if crop is not None and crop.size and crop.shape[1] >= 40 and crop.shape[0] >= 12:
                                candidates = ocr_candidates(ocr.predict(crop))
                                if candidates:
                                    text, confidence = max(candidates, key=lambda r: r[1])
                                    read = Read(text, confidence, plate_quality(crop))
                    aggregator.add(str(track_id), seconds, vehicle_type, read)
                    # Bound memory and request size for stationary tracks.
                    track = aggregator.tracks[str(track_id)]
                    if len(track.reads) > 120:
                        track.reads = sorted(track.reads, key=lambda r: r.confidence * r.quality, reverse=True)[:120]
                    if analysis_stream:
                        height, width = frame.shape[:2]
                        previous = stable_boxes.get(track_id, xyxy)
                        smooth = [0.6 * new + 0.4 * old for new, old in zip(xyxy, previous)]
                        stable_boxes[track_id] = smooth
                        track_observations[track_id] = track_observations.get(track_id, 0) + 1
                        normalized_box = [max(0, min(1, value / (width if i % 2 == 0 else height))) for i, value in enumerate(smooth)]
                        area = (normalized_box[2] - normalized_box[0]) * (normalized_box[3] - normalized_box[1])
                        if track_observations[track_id] >= 3 and area >= 0.0002:
                            record = {'track_id': track_id, 'class': vehicle_type, 'confidence': round(float(detection_confidence), 4), 'box': normalized_box}
                            if track.reads:
                                plate_text, plate_confidence = vote(track.reads)
                                if plate_confidence >= 0.8:
                                    record.update(plate=plate_text, plate_confidence=plate_confidence)
                            frame_detections.append(record)
            if analysis_stream:
                if not analysis_first:
                    analysis_stream.write(',')
                analysis_stream.write(json.dumps({'frame': frame_number, 'timestamp': seconds, 'detections': frame_detections}))
                analysis_first = False
            if writer:
                writer.write(result.plot())
            frame_number += 1
        deliver(aggregator.flush(frame_number / fps, force=True))
    finally:
        capture.release()
        if writer:
            writer.release()
        if analysis_stream:
            analysis_stream.write(']}')
            analysis_stream.close()
    print(json.dumps({'frames': frame_number, 'plate_events': posted, 'unidentified_passes': unidentified,
                      'spool': str(args.spool), 'note': 'No plate identity is invented for unreadable vehicles.'}, indent=2))


if __name__ == '__main__':
    main()
