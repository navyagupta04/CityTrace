"""Upload inference, with no lookup tables or predicted identities supplied by labels."""
import time
import base64
from pathlib import Path
from .common import ROOT
from .stages.ocr import split_lines, prepare_piece
from .stages.vote import aggregate
from anpr.vision import Read, plate_quality
from anpr.plates import normalize


def empty_plate(reason='No candidate passed plate grammar and vote threshold'):
    return dict(track_id=None, box=None, raw='', normalised='', voted=None, format_valid=False,
                format='unknown', ocr_confidence=0., vote_confidence=0., n_reads=0,
                status='abstain', reason=reason, first_time_s=None,
                character_confidences=[], plate_detection_confidence=None,
                detection_confidence_source='not_measured', low_confidence=True,
                confidence_threshold=.8, confidence_basis='per_detection_not_accuracy')


def pixel_image(image, extension='.png'):
    import cv2
    ok, encoded=cv2.imencode(extension,image)
    if not ok:return None
    mime='image/png' if extension=='.png' else 'image/jpeg'
    return f'data:{mime};base64,'+base64.b64encode(encoded).decode('ascii')


def plate_crop(image, box):
    if not box:return None
    x,y,w,h=map(int,box)
    crop=image[max(0,y):max(0,y)+h,max(0,x):max(0,x)+w]
    return pixel_image(crop) if crop.size else None


class LivePipeline:
    def __init__(self, engine, cfg):
        self.engine, self.cfg = engine, cfg
        self.detector = None
        self.plate_detector = None
        self.detector_scores = {}

    def identify(self):
        return dict(engine=self.engine.name, engine_version=self.engine.version,
                    device=self.engine.device, models=self.engine.models)

    def crop(self, image, stage):
        start = time.perf_counter()
        readings = []
        for piece in split_lines(image, self.cfg['plate']['two_line_aspect_ratio']):
            readings.extend(getattr(self.engine, 'read_detailed', self.engine.read)(prepare_piece(piece)))
        stage['ocr'] += (time.perf_counter() - start) * 1000
        raw = ''.join(r['text'] for r in readings)
        total = sum(len(r['text']) for r in readings)
        conf = sum(r['confidence']*len(r['text']) for r in readings) / total if total else 0
        chars = tuple(c for r in readings for c in r.get('characters', []))
        return Read(raw, conf, plate_quality(image), chars)

    def localise(self, image, mode, stage, check):
        import cv2
        h, w = image.shape[:2]
        self.detector_scores = {}
        if mode == 'auto':
            mode = 'crop' if 1.2 <= w/h <= 5.5 and w <= 1200 and h <= 400 else 'scene'
        if mode == 'crop':
            return [([0, 0, w, h], self.crop(image, stage))], mode
        check()
        start = time.perf_counter()
        boxes = []
        weights = self.cfg['plate'].get('detector_weights')
        if weights:
            if not (ROOT / weights).is_file():
                raise ValueError('Configured plate detector weights do not exist locally')
            if self.plate_detector is None:
                from ultralytics import YOLO
                self.plate_detector = YOLO(str(ROOT / weights))
            for box in self.plate_detector.predict(image, verbose=False)[0].boxes:
                boxes.append(list(map(float, box.xyxy[0].tolist())) + [float(box.conf[0])])
        else:
            words = getattr(self.engine, 'read_detailed', self.engine.read)(image)
            for word in words:
                points = word['box']
                xs, ys = [p[0] for p in points], [p[1] for p in points]
                boxes.append([min(xs), min(ys), max(xs), max(ys), word.get('detection_confidence')])
            # Join neighbouring lines before aspect filtering, supporting two-line plates.
            for i, a in enumerate(list(boxes)):
                for b in boxes[:i]:
                    overlap = min(a[2], b[2])-max(a[0], b[0])
                    gap = max(a[1], b[1])-min(a[3], b[3])
                    if overlap > .5*min(a[2]-a[0], b[2]-b[0]) and 0 <= gap < max(a[3]-a[1], b[3]-b[1]):
                        score = min(a[4], b[4]) if a[4] is not None and b[4] is not None else None
                        boxes.append([min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]), score])
        stage['localise'] += (time.perf_counter()-start)*1000
        candidates, seen = [], []
        for candidate in boxes[:100]:
            a, b, c, d, score = candidate
            check()
            if not weights and not 1.2 <= (c-a)/max(1, d-b) <= 5.5:
                continue
            px, py = (c-a)*.08, (d-b)*.18
            x, y, x2, y2 = max(0, int(a-px)), max(0, int(b-py)), min(w, int(c+px)), min(h, int(d+py))
            if x2 <= x or y2 <= y:
                continue
            read = self.crop(image[y:y2, x:x2], stage)
            normal = normalize(read.text)
            duplicate=False
            for text,previous in seen:
                left,top,right,bottom=previous
                intersection=max(0,min(x2,right)-max(x,left))*max(0,min(y2,bottom)-max(y,top))
                union=(x2-x)*(y2-y)+(right-left)*(bottom-top)-intersection
                if text==normal.text and union and intersection/union>.5:duplicate=True
            if normal.valid and not duplicate:
                seen.append((normal.text,(x,y,x2,y2)))
                candidates.append(([x, y, x2-x, y2-y], Read(read.text, read.confidence, read.quality, read.characters, score)))
        return candidates, mode

    def voted(self, candidates, stage):
        start = time.perf_counter()
        result = empty_plate()
        if candidates:
            box, best = max(candidates, key=lambda r: r[1].confidence*r[1].quality)
            normal = normalize(best.text)
            voted = aggregate([read for _, read in candidates], self.cfg['plate']['vote_threshold'])
            result.update(box=box, raw=best.text, normalised=normal.text, format=normal.format,
                          ocr_confidence=best.confidence, voted=voted.pop('text'), **voted)
            threshold = self.cfg.get('confidence_warning_threshold', .8)
            result.update(character_confidences=list(best.characters),
                          plate_detection_confidence=best.detection_confidence,
                          detection_confidence_source='plate_detector' if self.cfg['plate'].get('detector_weights') else 'ppocr_text_region',
                          confidence_threshold=threshold,
                          low_confidence=best.confidence < threshold,
                          confidence_basis='per_detection_not_accuracy')
            if result['status'] == 'read':
                result['reason'] = None
            elif normal.valid:
                result['reason'] = f"Vote confidence below {self.cfg['plate']['vote_threshold']:.2f} threshold"
        stage['vote'] += (time.perf_counter()-start)*1000
        return result

    def run(self, item, mode, stride, max_seconds, check, progress):
        import cv2
        start = time.perf_counter()
        stage = dict.fromkeys(('decode', 'detect', 'track', 'localise', 'ocr', 'vote'), 0.)
        path = str(item['path'])
        result = {k: v for k, v in item.items() if k != 'path'}
        result.update(self.identify(), plates=[], tracks=[], source='LIVE RUN (this upload)')
        check()
        if item['type'] == 'image':
            import numpy as np
            t = time.perf_counter()
            image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
            stage['decode'] += (time.perf_counter()-t)*1000
            if image is None:
                raise ValueError('Image could not be decoded')
            if image.shape[0]*image.shape[1] > self.cfg['max_pixels']:
                raise ValueError('Decoded image exceeds pixel limit')
            progress('plate localise / OCR', .3)
            candidates, used = self.localise(image, mode, stage, check)
            result['mode_used'] = used
            result['plates'] = [self.voted([candidate], stage) for candidate in candidates] or [empty_plate()]
            scale=min(1.,1600/max(image.shape[:2]))
            annotated=cv2.resize(image,None,fx=scale,fy=scale) if scale<1 else image.copy()
            result.update(image_width=image.shape[1],image_height=image.shape[0])
            for plate in result['plates']:
                if not plate['box']:continue
                plate['crop_image']=plate_crop(image,plate['box'])
                x,y,w,h=(int(value*scale) for value in plate['box'])
                cv2.rectangle(annotated,(x,y),(x+w,y+h),(40,190,100),2)
                cv2.putText(annotated,plate['normalised'],(x,max(20,y-8)),cv2.FONT_HERSHEY_SIMPLEX,.6,(40,190,100),2)
            result['annotated_image']=pixel_image(annotated,'.jpg')
        else:
            import supervision as sv
            from .stages.detect_track import Detector
            if not (ROOT / self.cfg['detector']['weights']).is_file():
                raise ValueError('Video vehicle detector unavailable: install local YOLOX weights')
            t = time.perf_counter()
            if self.detector is None:
                self.detector = Detector(self.cfg['detector'])
            stage['detect'] += (time.perf_counter()-t)*1000
            cap = cv2.VideoCapture(path)
            tracks = {}
            try:
                fps = cap.get(cv2.CAP_PROP_FPS)
                count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                if not fps or not count or count/fps > self.cfg['max_seconds']+.1:
                    raise ValueError('Video duration unavailable or exceeds configured limit')
                limit = min(int(count), int(max_seconds*fps))
                tracker = sv.ByteTrack(frame_rate=max(1, round(fps/stride)),
                                       track_activation_threshold=self.cfg['detector']['confidence'], minimum_consecutive_frames=2)
                for index in range(0, limit, stride):
                    check()
                    t = time.perf_counter()
                    cap.set(cv2.CAP_PROP_POS_FRAMES, index)
                    ok, image = cap.read()
                    stage['decode'] += (time.perf_counter()-t)*1000
                    if not ok:
                        raise ValueError(f'Cannot decode frame {index}')
                    t = time.perf_counter()
                    detections = self.detector(image)
                    stage['detect'] += (time.perf_counter()-t)*1000
                    t = time.perf_counter()
                    detections = tracker.update_with_detections(detections)
                    stage['track'] += (time.perf_counter()-t)*1000
                    for box, tid in zip(detections.xyxy, detections.tracker_id):
                        a, b, c, d = map(int, box)
                        crop = image[max(0,b):d, max(0,a):c]
                        if not crop.size:
                            continue
                        track = tracks.setdefault(int(tid), dict(first_frame=index, last_frame=index, frames=[]))
                        track['last_frame'] = index
                        # Bound retained frame memory: only a deterministic best-K list per track.
                        track['frames'].append((plate_quality(crop), index, [a,b,c-a,d-b]))
                        track['frames'] = sorted(track['frames'], key=lambda r: (-r[0], r[1]))[:self.cfg['plate']['top_k']]
                    progress('detect / track', .6*(index+stride)/max(1,limit))
                for position, (tid, track) in enumerate(tracks.items()):
                    candidates = []
                    best_frame = track['first_frame']
                    best_score = -1
                    for _, index, (a,b,w,h) in track.pop('frames'):
                        check()
                        t = time.perf_counter()
                        cap.set(cv2.CAP_PROP_POS_FRAMES, index)
                        ok, image = cap.read()
                        stage['decode'] += (time.perf_counter()-t)*1000
                        if not ok:
                            continue
                        found, _ = self.localise(image[b:b+h,a:a+w], 'scene', stage, check)
                        # One best plate candidate per vehicle frame; unrelated vehicle tracks never vote together.
                        if found:
                            box, read = max(found, key=lambda r:r[1].confidence*r[1].quality)
                            candidates.append(([box[0]+a,box[1]+b,box[2],box[3]], read))
                            if read.confidence*read.quality > best_score:
                                best_frame, best_score = index, read.confidence*read.quality
                    plate = self.voted(candidates, stage)
                    plate.update(track_id=tid, first_time_s=track['first_frame']/fps,
                                 time_s=best_frame/fps, **track)
                    if plate['box']:
                        cap.set(cv2.CAP_PROP_POS_FRAMES,best_frame)
                        ok, best_image=cap.read()
                        if ok:plate['crop_image']=plate_crop(best_image,plate['box'])
                    result['tracks'].append(plate)
                    progress('plate localise / OCR / vote', .6+.4*(position+1)/max(1,len(tracks)))
                result.update(mode_used='scene', video_fps=fps, sampled_seconds=limit/fps)
                result['models'] = result['models'] + [self.cfg['detector']['name'], self.cfg['detector']['weights'], 'Supervision ByteTrack 0.25.1']
                if not tracks:
                    result['plates'] = [empty_plate('No vehicle tracks detected in sampled frames')]
            finally:
                cap.release()
        check()
        result.update(duration_ms=(time.perf_counter()-start)*1000, stage_ms=stage,
                      status='read' if any(p['status']=='read' for p in result['tracks']+result['plates']) else 'abstain')
        return result
