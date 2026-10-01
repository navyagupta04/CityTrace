"""Generated fixtures exercise software contracts, never accuracy evidence."""
import copy
import hashlib
import json
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from anpr.api import create_app
from anpr.live_cases import camera_graph, group_trajectories
from pipeline.common import ROOT, read
from pipeline.engines import select_engine
from pipeline.live import LivePipeline, empty_plate
from scripts.choose_test_cameras import choose


def test_camera_chain_and_no_seed_mutation():
    paths=[ROOT/'frontend/src/demo/model.ts', ROOT/'frontend/public/real/routes.json']
    before=[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
    cameras,edges=camera_graph()
    for n in (1,2):
        placements=[{'camera_id':'AUTO'} for _ in range(n)]
        rows=choose(placements,cameras,edges)
        for a,b,row in zip(placements,placements[1:],rows[1:]):
            assert 1<=edges[a['camera_id'],b['camera_id']][0]<=3
            assert 25<=row['speed_kmh']<=45
        pinned=copy.deepcopy(placements);choose(pinned,cameras,edges)
        assert [p['camera_id'] for p in pinned]==[p['camera_id'] for p in placements]
    with pytest.raises(ValueError,match='No connected'):
        choose([{'camera_id':'AUTO'} for _ in range(3)],cameras,edges)
    assert before==[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]


def results():
    return [dict(file=name,sha256=name*32,plates=[],tracks=[dict(empty_plate(),status='read',voted='DL04CT7391',vote_confidence=.93,first_time_s=1.5,time_s=2,track_id=1)]) for name in ('a','b')]


def placements():
    return [dict(file='b',camera_id='C05',ts_ist='2026-09-30T10:15:02+05:30',staged=True,generated=True),dict(file='a',camera_id='C01',ts_ist='2026-09-30T10:12:05+05:30',staged=True,generated=True)]


def test_group_order_abstention_single_and_travel():
    files=results(); original=copy.deepcopy(files)
    case=group_trajectories(files,placements(),'fixture')[0]
    assert [s['clip'] for s in case['stops']]==['a','b']
    assert all(not s['implausible'] for s in case['stops'])
    assert case['stops'][1]['speed_kmh']==pytest.approx(35,abs=.1)
    assert case['stops'][0]['video_time_s']==1.5
    assert case['generated'] and case['staged']
    assert files==original
    files[1]['tracks'][0]['status']='abstain'
    assert len(group_trajectories(files,placements(),'fixture')[0]['stops'])==1
    files[0]['tracks'][0]['status']='abstain'
    assert group_trajectories(files,placements(),'fixture')==[]
    same_time=placements();same_time[0]['ts_ist']=same_time[1]['ts_ist']
    assert group_trajectories(results(),same_time,'fixture')[0]['stops'][1]['implausible']
    invalid=placements();invalid[0]['camera_id']='unknown'
    with pytest.raises(ValueError):group_trajectories(results(),invalid,'fixture')


def make_video(path):
    """A moving grey rectangle with rendered text, not a photorealistic car."""
    import cv2
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    plate=Image.new('RGB',(630,110),(210,210,210))
    font_path=next((p for p in ['C:/Windows/Fonts/arialbd.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'] if Path(p).exists()),None)
    font=ImageFont.truetype(font_path,85) if font_path else ImageFont.load_default(size=85)
    ImageDraw.Draw(plate).text((12,3),'DL04CT7391',font=font,fill=(40,40,40))
    plate=np.array(plate.resize((310,110)))
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),10,(640,320))
    assert writer.isOpened()
    for i in range(12):
        frame=np.full((320,640,3),25,dtype=np.uint8);x=60+i*3
        cv2.rectangle(frame,(x,50),(x+420,260),(100,100,100),-1)
        frame[125:235,x+55:x+365]=plate
        writer.write(frame)
    writer.release()


def test_real_video_ocr_no_labels_and_case_audit(tmp_path):
    # Only vehicle localization is fixture-specific: YOLOX is not trained to call a
    # plain rectangle a car. Real decode, ByteTrack, text localization, OCR and vote run.
    import cv2
    import numpy as np
    import supervision as sv
    video=tmp_path/'moving-plate.mp4';make_video(video)
    cfg=read(ROOT/'configs/lab.yaml')
    cfg['plate']['top_k']=3  # Three actual OCR frames suffice for this unit fixture.
    pipeline=LivePipeline(select_engine(cfg),cfg)
    def rectangle_detector(image):
        mask=cv2.inRange(image,np.array([80,80,80],np.uint8),np.array([120,120,120],np.uint8))
        contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        x,y,w,h=cv2.boundingRect(max(contours,key=cv2.contourArea))
        return sv.Detections(xyxy=np.array([[x,y,x+w,y+h]],float),confidence=np.array([1.]),class_id=np.array([2]))
    pipeline.detector=rectangle_detector
    app=create_app(str(tmp_path/'fixture.sqlite'))
    with TestClient(app) as client:
        app.state.ocr_jobs.pipeline=pipeline
        token=client.post('/api/auth/login',json={'username':'officer','password':'CityTrace@26127'}).json()['access_token']
        headers={'Authorization':'Bearer '+token}
        result=client.post('/api/ocr/jobs',headers=headers,data={'purpose':'Generated video fixture','stride':'1'},files={'files[]':(video.name,video.read_bytes(),'video/mp4')})
        assert result.status_code==200,result.text
        jid=result.json()['job_id']
        for _ in range(1800):
            job=client.get('/api/ocr/jobs/'+jid,headers=headers).json()
            if job['state'] in ('done','failed'):break
            time.sleep(.1)
        assert job['state']=='done',job
        assert job['scored'] is False and job['metrics']=={'scored':False}
        assert job['files'][0]['tracks'][0]['voted']=='DL04CT7391',job['files']
        assert job['files'][0]['tracks'][0]['scored'] is False
        assert job['files'][0]['duration_ms']>0 and job['purged']
        placed=client.post(f'/api/ocr/jobs/{jid}/trajectories',headers=headers,json={'placements':[dict(file=video.name,camera_id='C01',ts_ist='2026-09-30T10:12:05+05:30',staged=True,generated=True)]})
        assert placed.status_code==200,placed.text
        assert len(placed.json()['cases'][0]['stops'])==1
        audit=app.state.ocr_jobs.db.rows("SELECT * FROM audit WHERE action='trajectory_created'")
        assert len(audit)==1 and 'DL04CT7391' not in json.dumps(audit)
        labelled=client.post(f'/api/ocr/jobs/{jid}/labels',headers=headers,json={'expected':{video.name:'DL04CT7391'}}).json()
        assert labelled['metrics']['blind'] is False and labelled['metrics']['n_scored']==1
