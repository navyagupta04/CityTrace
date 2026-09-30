"""Blind local labelling server; temporary crops removed on Ctrl+C."""
import json,tempfile,shutil,http.server,webbrowser
from ..common import ROOT
def serve(cfg,clip_id=None):
    import cv2
    out=ROOT/cfg['output'];manifest=json.loads((out/'manifest.json').read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory(prefix='citytrace-label-') as tmp:
        from pathlib import Path
        folder=Path(tmp);records=[]
        for clip in manifest['clips']:
            if clip_id and clip['id']!=clip_id:continue
            cap=cv2.VideoCapture(str(ROOT/clip['file']))
            for t in json.loads((out/'tracks'/(clip['id']+'.json')).read_text(encoding='utf-8')):
                cap.set(cv2.CAP_PROP_POS_FRAMES,t['best_frame']);ok,image=cap.read()
                if not ok:continue
                f=next(f for f in t['frames'] if f['frame']==t['best_frame']);h,w=image.shape[:2];x1,y1,x2,y2=[int(v*d) for v,d in zip(f['box'],[w,h,w,h])];name=f"{clip['id']}-{t['track_id']}.jpg";cv2.imwrite(str(folder/name),image[y1:y2,x1:x2])
                # Deliberately omit model plate and OCR values from the browser data.
                records.append({'clip_id':clip['id'],'track_id':t['track_id'],'vehicle_class':t['class'],'image':name})
            cap.release()
        html=(ROOT/'pipeline/tools/label_tracks.html').read_text(encoding='utf-8').replace('__RECORDS__',json.dumps(records));(folder/'index.html').write_text(html,encoding='utf-8')
        handler=lambda *args,**kwargs:http.server.SimpleHTTPRequestHandler(*args,directory=tmp,**kwargs)
        with http.server.ThreadingHTTPServer(('127.0.0.1',8766),handler) as server:
            print('Blind labels: http://127.0.0.1:8766 · Ctrl+C removes temporary crops. Save downloaded CSV into data/ground_truth/.',flush=True)
            try:server.serve_forever()
            except KeyboardInterrupt:pass
