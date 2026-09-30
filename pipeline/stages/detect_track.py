from collections import Counter
import math
from ..common import ROOT, expiry

CLASSES={2:'car',3:'motorcycle',5:'bus',7:'truck'}

class Detector:
    def __init__(self, cfg):
        import numpy as np
        self.cfg=cfg
        import cv2
        cv2.setNumThreads(2)
        self.net=cv2.dnn.readNetFromONNX(str(ROOT/cfg['weights']))
        grids=[]; strides=[]
        for stride in (8,16,32):
            y,x=np.mgrid[:640//stride,:640//stride]; grids.append(np.stack((x,y),-1).reshape(-1,2));strides.append(np.full((x.size,1),stride))
        self.grid=np.concatenate(grids);self.strides=np.concatenate(strides)

    def __call__(self, image):
        import cv2
        import numpy as np
        import supervision as sv
        h,w=image.shape[:2]; scale=min(640/w,640/h)
        resized=cv2.resize(cv2.cvtColor(image,cv2.COLOR_BGR2RGB),(int(w*scale),int(h*scale)))
        padded=np.full((640,640,3),114,dtype=np.uint8);padded[:resized.shape[0],:resized.shape[1]]=resized
        blob=padded.transpose(2,0,1)[None].astype(np.float32)
        self.net.setInput(blob)
        out=self.net.forward()[0]
        centres=(out[:,:2]+self.grid)*self.strides; sizes=np.exp(out[:,2:4])*self.strides
        scores=out[:,4,None]*out[:,5:];ids=scores.argmax(1);conf=scores.max(1)
        good=np.isin(ids,list(CLASSES))&(conf>=self.cfg['confidence'])
        xywh=np.column_stack((centres-sizes/2,sizes))[good]/scale;conf=conf[good];ids=ids[good]
        if not len(conf): return sv.Detections.empty()
        keep=cv2.dnn.NMSBoxesBatched(xywh.tolist(),conf.tolist(),ids.tolist(),self.cfg['confidence'],self.cfg['nms'])
        keep=np.asarray(keep,dtype=int).reshape(-1);xywh=xywh[keep];xyxy=xywh.copy();xyxy[:,2:]+=xyxy[:,:2]
        xyxy[:,[0,2]]=xyxy[:,[0,2]].clip(0,w);xyxy[:,[1,3]]=xyxy[:,[1,3]].clip(0,h)
        valid=(xyxy[:,2]>xyxy[:,0])&(xyxy[:,3]>xyxy[:,1])
        return sv.Detections(xyxy=xyxy[valid],confidence=conf[keep][valid],class_id=ids[keep][valid])

def colour(image):
    import cv2
    import numpy as np
    if image.size==0: return 'Unknown'
    h,w=image.shape[:2];image=image[h//4:max(h//4+1,3*h//4),w//4:max(w//4+1,3*w//4)]
    hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV).reshape(-1,3);hue,sat,val=np.median(hsv,axis=0)
    if val<65:return 'Black'
    if sat<40:return 'White' if val>180 else 'Silver'
    if hue<12 or hue>165:return 'Red'
    if 85<hue<135:return 'Blue'
    if 15<hue<40:return 'Yellow'
    return 'Unknown'

def run(clip,cfg,detector):
    import cv2
    import supervision as sv
    stride=cfg['frame_stride'];fps=clip['fps'];w=clip['width'];h=clip['height']
    tracker=sv.ByteTrack(frame_rate=max(1,round(fps/stride)),track_activation_threshold=cfg['detector']['confidence'],minimum_consecutive_frames=2)
    cap=cv2.VideoCapture(str(ROOT/clip['file']));frames=[];tracks={};index=0;ttl=expiry(cfg['privacy_settings']['reads_days'])
    while True:
        ok,image=cap.read()
        if not ok:break
        if index%stride:index+=1;continue
        detections=tracker.update_with_detections(detector(image));records=[]
        for box,confidence,cls,track_id in zip(detections.xyxy,detections.confidence,detections.class_id,detections.tracker_id):
            x1,y1,x2,y2=map(float,box);tid=int(track_id);kind=CLASSES[int(cls)];normal=[x1/w,y1/h,x2/w,y2/h]
            crop=image[int(y1):math.ceil(y2),int(x1):math.ceil(x2)];shade=colour(crop)
            det={'track_id':tid,'class':kind,'confidence':float(confidence),'box':normal,'colour':shade,'source':'real','expires_at':ttl};records.append(det)
            track=tracks.setdefault(tid,{'track_id':tid,'class':kind,'colour':shade,'first_frame':index,'last_frame':index,'best_frame':index,'best_confidence':0,'frames':[],'source':'real','expires_at':ttl,'plate':{'text':None,'format_valid':False,'vote_confidence':0,'n_reads':0,'status':'abstain','alternatives':[]}})
            track['last_frame']=index
            if confidence>track['best_confidence']:track.update(best_confidence=float(confidence),best_frame=index)
            track['frames'].append({'frame':index,'box':normal,'confidence':float(confidence),'colour':shade,'source':'real','expires_at':ttl})
        frames.append({'frame':index,'timestamp':index/fps,'detections':records,'source':'real','expires_at':ttl})
        if index%(stride*100)==0:print(f"{clip['id']}: frame {index}/{clip['frame_count']} · {len(tracks)} tracks",flush=True)
        index+=1
    cap.release()
    for track in tracks.values():
        track['dwell_s']=(track['last_frame']-track['first_frame'])/fps
        track['class']=Counter(d['class'] for f in frames for d in f['detections'] if d['track_id']==track['track_id']).most_common(1)[0][0]
        track['colour']=Counter(f['colour'] for f in track['frames']).most_common(1)[0][0]
    return {'fps':fps,'frame_stride':stride,'frames':frames,'source':'real','expires_at':ttl},list(tracks.values())
