"""Seed exactly two accepted OCR tracks through Platform.ingest; optionally refresh Postgres mirror."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from anpr.graph import CameraGraph
from anpr.platform import Platform

PROVENANCE = 'real footage, OCR (model-estimated), staged camera placement'
DEFAULT_START = '2026-11-02T10:00:00+05:30'


def accepted_track(file_result: dict) -> dict:
    matches = [p for p in file_result.get('tracks', []) if p.get('status') == 'read' and p.get('voted')]
    if len(matches) != 1:
        candidates = [(p.get('track_id'),p.get('status'),p.get('voted'),p.get('vote_confidence')) for p in file_result.get('tracks',[])]
        raise ValueError(f"{file_result.get('file')}: expected exactly one accepted OCR track, found {len(matches)}. Tracks: {candidates}")
    plate = matches[0]
    if not plate.get('candidate_reads'):
        raise ValueError(f"{file_result.get('file')}: missing per-frame OCR candidates; rerun the current OCR Lab pipeline")
    return plate


def main() -> None:
    from scripts.sync_to_postgres import load_local_env
    load_local_env()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ocr-result', type=Path, default=ROOT/'output'/'two_video_ocr_result.json')
    parser.add_argument('--start', default=DEFAULT_START, help='Video 1 staged IST timestamp; Video 2 is 15 minutes later')
    args = parser.parse_args()
    result = json.loads(args.ocr_result.read_text(encoding='utf-8'))
    if result.get('state') != 'done' or len(result.get('files', [])) != 2:
        raise SystemExit('Need a completed authenticated OCR job containing exactly two video results.')
    graph = CameraGraph()
    start = datetime.fromisoformat(args.start)
    if start.tzinfo is None:
        raise SystemExit('--start must include a timezone (use +05:30 for IST).')
    placements = [('CAM-PN-01', start), ('CAM-MN-01', start+timedelta(minutes=15))]
    database = os.getenv('ANPR_DATABASE','data/two_video_demo.sqlite3')
    if database != ':memory:' and not Path(database).is_absolute():
        database = str(ROOT/database)
    platform = Platform(database)
    summaries=[]
    try:
        for file_result,(camera_id,timestamp) in zip(result['files'],placements):
            plate = accepted_track(file_result)
            event_id = 'two-video-'+hashlib.sha256((file_result['sha256']+'|'+camera_id).encode()).hexdigest()[:32]
            frame = {'frame':plate.get('evidence_frame'),'time_s':plate.get('time_s'),'crop_image':plate.get('crop_image')}
            metadata = {'provenance':PROVENANCE,'footage':'real video file; OCR model-estimated',
                        'camera_placement':'staged/illustrative','timestamp':'staged/illustrative',
                        'camera_name':graph.cameras[camera_id].name,'coordinates_approximate':True,
                        'video_file':file_result['file'],'video_sha256':file_result['sha256'],
                        'track_id':plate['track_id'],'accepted_plate':plate['voted'],
                        'vote_confidence':plate['vote_confidence'],'ocr_confidence':plate['ocr_confidence'],
                        'candidate_reads':plate['candidate_reads'],'evidence_frame':frame}
            reads=[{'text':c['text'],'confidence':c['confidence'],'quality':c['quality']} for c in plate['candidate_reads']]
            event={'event_id':event_id,'camera_id':camera_id,'timestamp':timestamp.isoformat(),
                   'vehicle_type':'car','reads':reads,
                   'source':'real footage, OCR (model-estimated), staged camera placement','metadata':metadata}
            ingested=platform.ingest(event)
            detection=ingested['detection']
            summaries.append({'file':file_result['file'],'plate':detection['plate'],'confidence':detection['confidence'],
                'camera':graph.cameras[camera_id].name,'camera_id':camera_id,'timestamp':detection['timestamp'],
                'detection_id':detection['id'],'hash':detection['hash'],'duplicate':ingested['duplicate'],
                'vote_confidence_from_ocr':plate['vote_confidence'],'candidate_reads':plate['candidate_reads'],
                'evidence_frame':{'frame':frame['frame'],'time_s':frame['time_s'],
                                  'crop_file':plate.get('evidence_crop_file')},'provenance':PROVENANCE})
        if summaries[0]['plate'] != summaries[1]['plate']:
            raise SystemExit('The two actual OCR results did not resolve to one canonical plate; no trajectory seeded.')
        trajectory=platform.search(summaries[0]['plate'])
        integrity=platform.db.verify()
    finally:
        platform.db.close()
    if not integrity['valid']:
        raise SystemExit('SQLite evidence chain verification failed after ingestion.')
    if not trajectory.get('found') or len(trajectory['hops']) != 2:
        raise SystemExit('Expected a two-sighting trajectory after ingestion.')
    print(json.dumps({'sqlite_database':database,'sightings':summaries,'trajectory':trajectory,'sqlite_integrity':integrity},indent=2))
    if os.getenv('DATABASE_URL','').strip():
        from scripts.sync_to_postgres import sync
        print('PostgreSQL mirror refresh:')
        print(json.dumps(sync(),indent=2))
    else:
        print('PostgreSQL mirror not updated (DATABASE_URL is unset); SQLite remains the system of record.')


if __name__ == '__main__':
    main()
