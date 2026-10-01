"""Rendered images below are test fixtures, never accuracy evidence."""
import threading
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from anpr.api import create_app
from anpr.ocr_live import magic_type, safe_name, JobService
from pipeline.common import config, read, ROOT
from pipeline.live import LivePipeline, empty_plate
from pipeline.live_metrics import score, verdict


def test_magic_and_names():
    for data in (b'\x89PNG\r\n\x1a\n',b'\xff\xd8\xff',b'RIFF0000WEBP'):
        assert magic_type(data)=='image'
    assert magic_type(b'0000ftypmp42')=='video'
    for data in (b'hello.jpg',b'<html>',b'0000ftypjunk'):
        with pytest.raises(ValueError):magic_type(data)
    assert safe_name('../../../../thing.jpg')=='thing.jpg'
    assert safe_name('C:\\x\\thing.jpg')=='thing.jpg'


def test_metrics():
    files=[dict(file='a',plates=[dict(empty_plate(),status='read',voted='DL01AB1234',vote_confidence=.9)]),
           dict(file='b',plates=[empty_plate()]),dict(file='unlabelled',plates=[empty_plate()])]
    m=score(files,{'a':'dl-01 ab1234','b':'DL01AB1234'},True)
    assert m['n_scored']==2 and m['plate_accuracy_all']['value']==.5
    assert m['cer']==.5 and m['coverage']==.5 and m['selective_accuracy']['value']==1
    assert m['plate_accuracy_all']['ci95']==pytest.approx([.0945312057,.9054687943])
    assert m['blind'] is True and m['reliability'][0]['accuracy']==1
    assert score(files,{},False)['plate_accuracy_all'] is None
    assert not score(files,{'a':'DL01AB1234'},False)['blind']
    files[0]['plates'].append(empty_plate())
    assert score(files[:1],{'a':'DL01AB1234'},True)['n_scored']==0
    assert score(files[:1],{'a#0':'DL01AB1234'},True)['n_scored']==1
    assert score(files[:1],{'a':'DL01AB1234','a#0':''},False)['n_scored']==0


@pytest.mark.parametrize('n,a,text',[(29,.8,'Inconclusive'),(30,.8,'Below'),(99,.95,'Inconclusive'),(100,.9,'Meets'),(100,.89,'Below')])
def test_verdict(n,a,text):
    assert verdict(n,a).startswith(text)


def test_real_engine_rendered_fixture(tmp_path):
    from PIL import Image, ImageDraw, ImageFont
    from pipeline.engines import select_engine
    cfg=read(ROOT/'configs/lab.yaml')
    engine=select_engine(cfg)
    image=Image.new('RGB',(700,160),'white')
    font=ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf',86)
    ImageDraw.Draw(image).text((25,25),'DL01AB1234',font=font,fill='black')
    path=tmp_path/'fixture.png';image.save(path)
    result=LivePipeline(engine,cfg).run(dict(file='fixture.png',path=path,type='image'), 'crop',15,60,lambda:None,lambda *args:None)
    assert result['engine']=='RapidOCR'
    assert result['plates'][0]['raw']
    assert result['plates'][0]['normalised']=='DL01AB1234'
    assert result['duration_ms']>0 and result['stage_ms']['ocr']>0


def test_api_guards_and_lifecycle(tmp_path):
    app=create_app(str(tmp_path/'db.sqlite'))
    with TestClient(app) as client:
        assert client.get('/api/ocr/status').status_code==401
        def login(name):
            data=client.post('/api/auth/login',json=dict(username=name,password='CityTrace@26127')).json()
            return {'Authorization':'Bearer '+data['access_token']}
        viewer=login('viewer');officer=login('officer')
        assert client.get('/api/ocr/status',headers=viewer).status_code==403
        service=app.state.ocr_jobs
        class FixturePipeline:
            def identify(self):return dict(engine='test fixture',engine_version='1',device='CPU',models=[])
            def run(self,item,*args):
                args[-2]();return dict(file=item['file'],plates=[empty_plate()],tracks=[])
        service.pipeline=FixturePipeline()
        assert client.post('/api/ocr/jobs',headers=officer,data={'purpose':'bad'},files={'files[]':('a.png',b'bad')}).status_code==422
        assert client.post('/api/ocr/jobs',headers=officer,data={'purpose':'testing'},files={'files[]':('a.png',b'bad')}).status_code==422
        from PIL import Image
        import io
        buf=io.BytesIO();Image.new('RGB',(100,30),'white').save(buf,format='PNG')
        response=client.post('/api/ocr/jobs',headers=officer,data={'purpose':'fixture test','expected':'{"a.png":"DL01AB1234"}'},files={'files[]':('a.png',buf.getvalue())})
        assert response.status_code==200,response.text
        jid=response.json()['job_id']
        for _ in range(100):
            job=client.get('/api/ocr/jobs/'+jid,headers=officer).json()
            if job['state']=='done':break
            time.sleep(.01)
        assert job['state']=='done' and job['metrics']['blind']
        assert job['purged'] and not service.jobs[jid]['folder'].exists()
        response=client.post(f'/api/ocr/jobs/{jid}/labels',headers=officer,json={'expected':{'a.png':'DL01AB1234'}})
        assert response.status_code==200 and not response.json()['metrics']['blind']
        assert client.get(f'/api/ocr/jobs/{jid}',headers=viewer).status_code==403
        assert client.delete(f'/api/ocr/jobs/{jid}',headers=officer).json()['purged']
        service.jobs[jid]['created']=0;service.expire()
        assert client.get(f'/api/ocr/jobs/{jid}',headers=officer).status_code==404


def test_queue_cancellation_timeout_failure_and_sweep(platform,tmp_path):
    cfg=read(ROOT/'configs/lab.yaml')
    entered,release=threading.Event(),threading.Event()
    class BlockingPipeline:
        def identify(self):return dict(engine='test fixture',engine_version='1',device='CPU',models=[])
        def run(self,item,mode,stride,seconds,check,progress):
            entered.set()
            while not release.wait(.01):check()
            check()
            return dict(file=item['file'],plates=[empty_plate()],tracks=[])
    service=JobService(platform.db,cfg,tmp_path/'jobs',BlockingPipeline())
    user={'role':'officer','username':'unit-test'}
    def create():
        import uuid
        folder=service.root/('job-'+uuid.uuid4().hex);folder.mkdir()
        path=folder/'input';path.write_bytes(b'private upload')
        return service.create(folder,[dict(file='test',path=path,type='image',sha256='fixture',size=14)],user,'fixture run','crop',1,60,{},False)
    def wait(jid,state):
        for _ in range(200):
            if service.jobs[jid]['state']==state and service.jobs[jid].get('purged'):return
            time.sleep(.01)
        assert service.jobs[jid]['state']==state
    try:
        first=create();assert entered.wait(2)
        second=create();assert service.jobs[second]['state']=='queued'
        assert service.jobs[first]['state']=='running'
        service.jobs[first]['cancel'].set();release.set();wait(first,'cancelled');wait(second,'done')
        assert not service.jobs[first]['folder'].exists()
        cfg['timeout_seconds']=-1;third=create();wait(third,'failed')
        assert 'timeout' in service.jobs[third]['error']
        cfg['timeout_seconds']=900
        service.jobs[second]['created']=0;service.expire();assert second not in service.jobs
        actions=[r['action'] for r in platform.db.rows('SELECT action FROM audit')]
        assert 'ocr_job_started' in actions and 'ocr_job_purged' in actions
    finally:service.close()


def test_limits_and_independent_file_errors(tmp_path):
    import io
    from PIL import Image
    app=create_app(str(tmp_path/'limits.sqlite'))
    with TestClient(app) as client:
        login=client.post('/api/auth/login',json=dict(username='officer',password='CityTrace@26127')).json()
        headers={'Authorization':'Bearer '+login['access_token']}
        service=app.state.ocr_jobs
        class FailingPipeline:
            def identify(self):return dict(engine='test fixture',engine_version='1',device='CPU',models=[])
            def run(self,*args):raise ValueError('Fixture decode failure')
        service.pipeline=FailingPipeline()
        def send(content,name='a.png',extra=None):
            return client.post('/api/ocr/jobs',headers=headers,data={'purpose':'fixture limit',**(extra or {})},files={'files[]':(name,content)})
        buf=io.BytesIO();Image.new('RGB',(10,10)).save(buf,format='PNG');data=buf.getvalue()
        service.cfg['image_mb']=.000001
        assert send(data).status_code==413
        service.cfg['image_mb']=10
        service.cfg['max_pixels']=1
        assert send(data).status_code==413
        service.cfg['max_pixels']=40000000
        assert send(data,extra={'max_seconds':'61'}).status_code==422
        assert send(b'\x89PNG\r\n\x1a\ncorrupt').status_code==422
        assert send(b'0000ftypmp42bad','test.mp4').status_code==422
        response=send(data)
        jid=response.json()['job_id']
        for _ in range(100):
            job=client.get('/api/ocr/jobs/'+jid,headers=headers).json()
            if job['state']=='done':break
            time.sleep(.01)
        assert job['files'][0]['status']=='failed'
        assert job['files'][0]['error']=='Fixture decode failure'
