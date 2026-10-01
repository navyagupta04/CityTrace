"""Authenticated local OCR jobs. Source uploads never enter public/static directories."""
import asyncio
import copy
import hashlib
import json
import os
import re
import shutil
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from pipeline.common import ROOT, read
from pipeline.engines import select_engine
from pipeline.live import LivePipeline
from pipeline.live_metrics import score

SETUP = 'python -m pip install -r requirements-dev.txt -r pipeline/requirements.txt; python -m uvicorn anpr.api:app --host 127.0.0.1 --port 8000'


def magic_type(data):
    if data.startswith(b'\x89PNG\r\n\x1a\n') or data.startswith(b'\xff\xd8\xff') or (data[:4] == b'RIFF' and data[8:12] == b'WEBP'):
        return 'image'
    if (data[4:8] == b'ftyp' and data[8:12] in (b'isom',b'iso2',b'mp41',b'mp42',b'avc1',b'qt  ',b'M4V ',b'dash')) or (data[:4] == b'\x1aE\xdf\xa3' and b'webm' in data[:4096]):
        return 'video'
    raise ValueError('Unsupported file signature; use PNG, JPEG, WebP, MP4, WebM or MOV')


def safe_name(name):
    return re.sub(r'[^\w. -]', '_', name.replace('\\','/').split('/')[-1])[:150] or 'upload'


def validate_labels(value):
    if not isinstance(value, dict) or len(value) > 10000 or any(not isinstance(k,str) or not isinstance(v,str) or len(k)>200 or len(v)>30 for k,v in value.items()):
        raise HTTPException(422, 'Expected labels must be a filename (or filename#track_id) to plate map')
    return {safe_name(k):v for k,v in value.items()} if not any('#' in k for k in value) else value


class Cancelled(Exception):
    pass


class JobService:
    def __init__(self, db, cfg=None, root=None, pipeline=None):
        self.db = db
        self.cfg = cfg or read(Path(os.getenv('OCR_LAB_CONFIG', str(ROOT/'configs/lab.yaml'))))
        self.root = Path(root or Path(tempfile.gettempdir())/'citytrace-ocr-lab')
        self.root.mkdir(parents=True, exist_ok=True)
        self.jobs = {}
        self.lock = threading.RLock()
        self.engine_lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='ocr-lab')
        self.pipeline = pipeline
        self.stop = threading.Event()
        for folder in self.root.glob('job-*'):
            if folder.is_dir() and not folder.is_symlink() and folder.resolve().parent == self.root.resolve() and time.time()-folder.stat().st_mtime > self.cfg['ttl_seconds']:
                shutil.rmtree(folder)
        self.sweeper = threading.Thread(target=self._sweep, daemon=True)
        self.sweeper.start()

    def status(self):
        reasons = []
        with self.engine_lock:
            if self.pipeline is None:
                try:
                    self.pipeline = LivePipeline(select_engine(self.cfg), self.cfg)
                except Exception as error:
                    reasons.append(str(error))
        details = self.pipeline.identify() if self.pipeline else dict(engine=None,engine_version=None,device='CPU',models=[])
        return dict(available=self.pipeline is not None, **details, modes=['auto','crop','scene'],
                    limits={k:self.cfg[k] for k in ('image_mb','video_mb','max_files','max_seconds','ttl_seconds','timeout_seconds')},
                    reasons_if_unavailable=reasons, setup=SETUP)

    def audit(self, job, action, details):
        with self.db.transaction():
            self.db.audit(job['user']['role'], action, {'user':job['user']['username'],'job_id':job['job_id'], **details})

    def purge(self, job):
        # Retry on Windows after the worker releases an active VideoCapture handle.
        try:
            if job['folder'].resolve().parent != self.root.resolve() or not job['folder'].name.startswith('job-'):
                raise RuntimeError('Refusing purge outside the private job directory')
            if job['folder'].exists():
                shutil.rmtree(job['folder'])
            if not job.get('purged'):
                self.audit(job, 'ocr_job_purged', {})
            job['purged'] = True
        except OSError:
            job['purged'] = False

    def expire(self):
        with self.lock:
            for jid, job in list(self.jobs.items()):
                if time.time()-job['created'] > self.cfg['ttl_seconds']:
                    job['cancel'].set()
                    self.purge(job)
                    if job['purged']:
                        del self.jobs[jid]

    def _sweep(self):
        while not self.stop.wait(5):
            self.expire()

    def close(self):
        self.stop.set()
        with self.lock:
            for job in self.jobs.values():
                job['cancel'].set()
        self.executor.shutdown(wait=True, cancel_futures=True)
        for job in self.jobs.values():
            self.purge(job)

    def create(self, folder, items, user, purpose, mode, stride, seconds, labels, blind):
        with self.lock:
            if sum(j['state'] in ('queued','running') for j in self.jobs.values()) >= self.cfg['max_jobs']:
                raise HTTPException(429, 'OCR queue is full; try again after an active job ends')
            jid = folder.name[4:]
            job = dict(job_id=jid, folder=folder, items=items, user=user, purpose=purpose, mode=mode,
                       stride=stride, seconds=seconds, labels=labels, blind=bool(labels and blind),
                       state='queued', stage='queued', progress=0, files=[], created=time.time(), cancel=threading.Event())
            self.jobs[jid] = job
            self.audit(job, 'ocr_job_started', {'purpose':purpose,'file_count':len(items),
                       'files':[{k:v for k,v in item.items() if k!='path'} for item in items]})
            self.executor.submit(self.run, job)
            return jid

    def run(self, job):
        start = time.monotonic()
        def check():
            if job['cancel'].is_set():
                raise Cancelled()
            if time.monotonic()-start > self.cfg['timeout_seconds']:
                raise TimeoutError('OCR job exceeded the configured timeout')
        try:
            check()
            with self.lock:
                job['state'] = 'running'
            for i, item in enumerate(job['items']):
                check()
                file_start = time.monotonic()
                def progress(stage, amount):
                    check()
                    with self.lock:
                        job.update(stage=f"{item['file']}: {stage}", progress=min(99,100*(i+amount)/len(job['items'])))
                try:
                    result = self.pipeline.run(item,job['mode'],job['stride'],job['seconds'],check,progress)
                except (Cancelled, TimeoutError):
                    raise
                except Exception as error:
                    result = {k:v for k,v in item.items() if k!='path'}
                    result.update(self.pipeline.identify(), status='failed', error=str(error),plates=[],tracks=[],
                                  duration_ms=(time.monotonic()-file_start)*1000)
                with self.lock:
                    job['files'].append(result)
            check()
            with self.lock:
                job.update(state='done',stage='complete',progress=100)
        except Cancelled:
            job.update(state='cancelled',stage='cancelled',files=[])
        except Exception as error:
            job.update(state='failed',stage='failed',error=str(error))
        finally:
            with self.lock:
                job['duration_ms'] = (time.monotonic()-start)*1000
                if job['cancel'].is_set():
                    job.update(state='cancelled',files=[],labels={})
                self.audit(job,'ocr_job_completed',{'state':job['state'],'files':len(job['files']), 'duration_ms':job['duration_ms']})
                self.purge(job)

    def get(self, jid, user):
        self.expire()
        job = self.jobs.get(jid)
        if not job or job['user']['username'] != user['username']:
            raise HTTPException(404, 'OCR job not found or expired')
        return job

    def snapshot(self, job):
        with self.lock:
            result = {k:copy.deepcopy(job[k]) for k in ('job_id','state','stage','progress','files','blind')}
            result.update(self.pipeline.identify() if self.pipeline else {})
            result.update(duration_ms=job.get('duration_ms'),error=job.get('error'),purged=job.get('purged',False))
            result['metrics'] = score(result['files'],job['labels'],job['blind'])
            result['timings'] = {stage:sum(f.get('stage_ms',{}).get(stage,0) for f in result['files']) for stage in ('decode','detect','track','localise','ocr','vote')}
            return result


class Labels(BaseModel):
    expected: dict[str,str]


def register_ocr_live(app, db, officer):
    service = JobService(db)
    app.state.ocr_jobs = service
    router = APIRouter(prefix='/api/ocr', dependencies=[])

    @router.get('/status')
    def status(user=Depends(officer)):
        return service.status()

    @router.post('/jobs')
    async def create(request:Request, user=Depends(officer)):
        # Starlette spools multipart files to temporary storage; close the form on every path.
        try:
            async with request.form(max_files=service.cfg['max_files'], max_fields=10, max_part_size=1024*1024) as form:
                purpose = str(form.get('purpose','')).strip()
                mode = str(form.get('mode','auto'))
                stride = int(str(form.get('stride',service.cfg['frame_stride'])))
                seconds = float(str(form.get('max_seconds',service.cfg['max_seconds'])))
                if len(purpose)<5 or len(purpose)>400 or mode not in ('auto','crop','scene') or not 1<=stride<=300 or not 0<seconds<=service.cfg['max_seconds']:
                    raise HTTPException(422,'Purpose must be 5–400 characters; check mode, stride (1–300) and duration limits')
                labels = validate_labels(json.loads(str(form.get('expected','{}'))))
                files = form.getlist('files[]') or form.getlist('files')
                if not 1<=len(files)<=service.cfg['max_files']:
                    raise HTTPException(422,'Upload 1 to 20 files')
                status = await asyncio.to_thread(service.status)
                if not status['available']:
                    raise HTTPException(503, '; '.join(status['reasons_if_unavailable']))
                folder = service.root / ('job-'+uuid.uuid4().hex)
                folder.mkdir()
                try:
                    items, names = [], set()
                    for upload in files:
                        if not hasattr(upload,'read'):
                            raise HTTPException(422,'Each file must be a multipart upload')
                        name = safe_name(upload.filename or 'upload')
                        if name in names:
                            raise HTTPException(422,'Duplicate filenames are ambiguous; rename before uploading')
                        names.add(name)
                        head = await upload.read(4096)
                        kind = magic_type(head)
                        maximum = service.cfg['image_mb' if kind=='image' else 'video_mb']*1024*1024
                        path = folder / f'{len(items)}.upload'
                        size, sha = 0, hashlib.sha256()
                        with path.open('wb') as out:
                            chunk = head
                            while chunk:
                                size += len(chunk)
                                if size>maximum:
                                    raise HTTPException(413,f'{name} exceeds the {kind} size limit')
                                sha.update(chunk)
                                out.write(chunk)
                                chunk = await upload.read(1024*1024)
                        if kind=='video':
                            def duration():
                                import cv2
                                cap=cv2.VideoCapture(str(path))
                                try:
                                    fps=cap.get(cv2.CAP_PROP_FPS)
                                    frames=cap.get(cv2.CAP_PROP_FRAME_COUNT)
                                    return frames/fps if fps>0 else 0
                                finally:
                                    cap.release()
                            length = await asyncio.to_thread(duration)
                            if not 0<length<=service.cfg['max_seconds']+.1:
                                raise HTTPException(422,f'{name}: unknown duration or longer than {service.cfg["max_seconds"]} seconds')
                        else:
                            from PIL import Image
                            with Image.open(path) as image:
                                if image.width*image.height>service.cfg['max_pixels']:
                                    raise HTTPException(413,'Decoded image exceeds pixel limit')
                                image.verify()
                        items.append(dict(file=name,sha256=sha.hexdigest(),type=kind,size=size,path=path))
                    jid=service.create(folder,items,user,purpose,mode,stride,seconds,labels,str(form.get('blind','true')).lower()=='true')
                    return {'job_id':jid}
                except Exception:
                    shutil.rmtree(folder,ignore_errors=True)
                    raise
        except (ValueError, TypeError, OSError) as error:
            raise HTTPException(422,str(error)) from error

    @router.get('/jobs/{jid}')
    @router.get('/jobs/{jid}/result')
    def result(jid:str,user=Depends(officer)):
        return service.snapshot(service.get(jid,user))

    @router.post('/jobs/{jid}/labels')
    def labels(jid:str,body:Labels,user=Depends(officer)):
        with service.lock:
            job=service.get(jid,user)
            if job['state']!='done':
                raise HTTPException(409,'Labels can be changed after completion')
            job.update(labels=validate_labels(body.expected),blind=False)
            return service.snapshot(job)

    @router.delete('/jobs/{jid}')
    def cancel(jid:str,user=Depends(officer)):
        with service.lock:
            job=service.get(jid,user)
            job['cancel'].set()
            job.update(state='cancelled',stage='cancelled',files=[],labels={})
            service.purge(job)
            return {'state':'cancelled','purged':job['purged']}

    app.include_router(router)
