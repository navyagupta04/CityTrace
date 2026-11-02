"""Submit the two checked-in videos through the authenticated OCR Lab job API."""
from __future__ import annotations

import getpass
import base64
import json
import os
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
FILES = [ROOT/'videos'/'gemini_generated_video_4835b244.mp4',
         ROOT/'videos'/'WhatsApp Video 2026-10-01 at 2.14.46 PM.mp4']
BASE = os.getenv('CITYTRACE_API_BASE', 'http://127.0.0.1:8002/api').rstrip('/')


def main() -> None:
    username = os.getenv('CITYTRACE_DEMO_USER', 'officer')
    password = os.getenv('CITYTRACE_DEMO_PASSWORD') or getpass.getpass(f'Password for {username}: ')
    with httpx.Client(timeout=httpx.Timeout(900, connect=10)) as client:
        login = client.post(f'{BASE}/auth/login', json={'username':username,'password':password,'unit':'Central District'})
        login.raise_for_status()
        token = login.json()['access_token']
        headers = {'Authorization':f'Bearer {token}'}
        status = client.get(f'{BASE}/ocr/status', headers=headers)
        status.raise_for_status()
        engine = status.json()
        print(f"OCR engine: {engine['engine']} {engine['engine_version']} · {engine['device']}")
        if not engine['available']:
            raise SystemExit('OCR engine unavailable: '+ '; '.join(engine['reasons_if_unavailable']))
        files = [('files[]',(p.name,p.open('rb'),'video/mp4')) for p in FILES]
        response = client.post(f'{BASE}/ocr/jobs', headers=headers,
            data={'purpose':'Two-video staged demo OCR','mode':'scene','stride':'15','max_seconds':'60'},files=files)
        response.raise_for_status()
        jid = response.json()['job_id']
        print(f'Authenticated OCR job {jid} submitted for both videos.')
        while True:
            snapshot = client.get(f'{BASE}/ocr/jobs/{jid}',headers=headers)
            snapshot.raise_for_status()
            job = snapshot.json()
            print(f"{job['state']} · {job['progress']:.0f}% · {job['stage']}",flush=True)
            if job['state'] in ('done','failed','cancelled'):
                break
            time.sleep(3)
    out = ROOT/'output'/'two_video_ocr_result.json'
    out.parent.mkdir(exist_ok=True)
    evidence_dir = out.parent/'two_video_evidence'
    evidence_dir.mkdir(exist_ok=True)
    for file_result in job.get('files',[]):
        for plate in file_result.get('tracks',[]):
            image=plate.get('crop_image')
            if not image or ',' not in image:
                continue
            mime,payload=image.split(',',1)
            extension='jpg' if 'jpeg' in mime else 'png'
            crop_name=f"{Path(file_result['file']).stem}-track-{plate.get('track_id')}-frame-{plate.get('evidence_frame')}.{extension}"
            (evidence_dir/crop_name).write_bytes(base64.b64decode(payload))
            plate['evidence_crop_file']=f'output/two_video_evidence/{crop_name}'
    out.write_text(json.dumps(job,indent=2),encoding='utf-8')
    print(f'Result and best-frame crops saved locally to {out.relative_to(ROOT)}')
    for file in job.get('files',[]):
        print(f"\n{file['file']}: status={file.get('status')} sha256={file.get('sha256')}")
        candidates = [p for p in file.get('tracks',[]) if p.get('status')=='read' and p.get('voted')]
        if not candidates:
            print('No accepted OCR read. Candidate evidence follows:')
        for plate in candidates:
            print(f"  track={plate.get('track_id')} read={plate['voted']} vote_confidence={plate['vote_confidence']:.4f} "
                  f"ocr_confidence={plate['ocr_confidence']:.4f} reads={plate['n_reads']} best_frame={plate.get('evidence_frame')} "
                  f"crop={plate.get('evidence_crop_file','unavailable')}")
            for candidate in plate.get('candidate_reads',[]):
                print(f"    frame={candidate['frame']} t={candidate['time_s']:.3f}s raw={candidate['text']} "
                      f"normalized={candidate['normalised']} confidence={candidate['confidence']:.4f} quality={candidate['quality']:.4f}")
        if file.get('error'):
            print('  error:',file['error'])
    if job.get('state') != 'done':
        raise SystemExit(f"OCR job ended in {job.get('state')}: {job.get('error')}")


if __name__ == '__main__':
    main()
