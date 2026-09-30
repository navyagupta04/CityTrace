"""Optional local plate models. Missing models cause abstention, never fake reads."""
from ..common import ROOT

def split_lines(crop,aspect_ratio=2):
    return [crop[:crop.shape[0]//2],crop[crop.shape[0]//2:]] if crop.shape[1]/crop.shape[0]<aspect_ratio else [crop]

def read_plates(clip,analysis,tracks,cfg):
    settings=cfg['plate']
    if not all(settings.get(k) for k in ('detector_weights','ocr_det_dir','ocr_rec_dir')):
        for track in tracks:track['plate']['reason']='Plate detector and OCR weights not configured; abstained'
        return
    import cv2
    from ultralytics import YOLO
    from paddleocr import PaddleOCR
    from anpr.vision import Read,plate_quality
    from .vote import aggregate
    detector=YOLO(str(ROOT/settings['detector_weights']))
    engine=PaddleOCR(det_model_dir=str(ROOT/settings['ocr_det_dir']),rec_model_dir=str(ROOT/settings['ocr_rec_dir']),lang='en',use_angle_cls=False,show_log=False)
    cap=cv2.VideoCapture(str(ROOT/clip['file']))
    for track in tracks:
        candidates=[]
        # Deterministic spread avoids selecting only adjacent near-identical frames.
        fs=track['frames'];step=max(1,len(fs)//max(1,settings['top_k']*3))
        for f in fs[::step]:
            cap.set(cv2.CAP_PROP_POS_FRAMES,f['frame']);ok,image=cap.read()
            if not ok:continue
            h,w=image.shape[:2];x1,y1,x2,y2=[int(v*s) for v,s in zip(f['box'],[w,h,w,h])];vehicle=image[y1:y2,x1:x2]
            if not vehicle.size:continue
            result=detector.predict(vehicle,verbose=False)[0]
            for box in result.boxes:
                a,b,c,d=map(int,box.xyxy[0].tolist());crop=vehicle[max(0,b):d,max(0,a):c]
                if not crop.size:continue
                quality=plate_quality(crop);candidates.append((quality*float(box.conf[0]),f,crop,[(x1+a)/w,(y1+b)/h,(x1+c)/w,(y1+d)/h],quality))
        readings=[]
        for _,f,crop,pbox,quality in sorted(candidates,key=lambda x:-x[0])[:settings['top_k']]:
            f['plate_box']=pbox;f['plate_height_px']=crop.shape[0]
            pieces=split_lines(crop,settings['two_line_aspect_ratio'])
            text='';conf=[]
            for piece in pieces:
                gray=cv2.cvtColor(piece,cv2.COLOR_BGR2GRAY);gray=cv2.createCLAHE(2,(8,8)).apply(gray)
                scale=max(1,48/gray.shape[0]);prepared=cv2.resize(gray,None,fx=scale,fy=scale,interpolation=cv2.INTER_CUBIC)
                result=engine.ocr(cv2.cvtColor(prepared,cv2.COLOR_GRAY2BGR),cls=False)
                for line in (result[0] or []) if result else []:text+=line[1][0];conf.append(float(line[1][1]))
            certainty=sum(conf)/len(conf) if conf else 0
            f.update(ocr=text,ocr_conf=certainty,quality=quality)
            readings.append(Read(text,certainty,quality))
            if settings.get('retain_crops') and cfg['privacy_settings'].get('retain_crops'):
                folder=ROOT/cfg['output']/'crops'/clip['id'];folder.mkdir(parents=True,exist_ok=True);cv2.imwrite(str(folder/f"{track['track_id']}-{f['frame']}.jpg"),crop)
        track['plate']=aggregate(readings,settings['vote_threshold'])
        track['best_plate_height_px']=max((f.get('plate_height_px',0) for f in fs),default=0)
        if track['plate']['status']=='read':
            for frame in analysis['frames']:
                for det in frame['detections']:
                    if det['track_id']==track['track_id']:det.update(plate=track['plate']['text'],plate_confidence=track['plate']['vote_confidence'])
    cap.release()
