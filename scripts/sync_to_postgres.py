"""Refresh the optional PostgreSQL proof mirror from the SQLite system of record."""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from anpr.config import CAMERAS
from anpr.graph import CameraGraph


def load_local_env() -> None:
    """Read only the two demo database variables from an ignored local .env file."""
    path = ROOT/'.env'
    if not path.is_file():
        return
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key,value=line.split('=',1)
        key,value=key.strip(),value.strip().strip('"').strip("'")
        if key in ('DATABASE_URL','ANPR_DATABASE') and value and key not in os.environ:
            os.environ[key]=value


def as_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def verify_sqlite(db: sqlite3.Connection) -> dict:
    from anpr.db import digest
    meta = {r['key']: r['value'] for r in db.execute('SELECT key,value FROM metadata')}
    previous = meta['anchor']
    rows = db.execute('SELECT id,payload,prev_hash,hash FROM detections ORDER BY id').fetchall()
    for row in rows:
        if row['prev_hash'] != previous or row['hash'] != digest(previous, row['payload']):
            return {'valid': False, 'checked': len(rows), 'broken_at': row['id']}
        previous = row['hash']
    return {'valid': previous == meta['head'] and len(rows) == int(meta['count']),
            'checked': len(rows), 'head': previous, 'anchor': meta['anchor']}


def sync() -> dict:
    load_local_env()
    url = os.getenv('DATABASE_URL', '').strip()
    if not url:
        raise SystemExit('DATABASE_URL is not set; no PostgreSQL mirror was updated.')
    try:
        import psycopg
    except ImportError as error:
        raise SystemExit('Optional PostgreSQL driver missing. Install with: python -m pip install -r requirements-postgres.txt') from error

    db_path = os.getenv('ANPR_DATABASE', 'data/nexus.sqlite3')
    if db_path != ':memory:' and not Path(db_path).is_absolute():
        db_path = str(ROOT / db_path)
    source = sqlite3.connect(db_path)
    source.row_factory = sqlite3.Row
    integrity = verify_sqlite(source)
    if not integrity['valid']:
        source.close()
        raise SystemExit('SQLite evidence hash-chain verification failed; refusing to mirror.')

    graph = CameraGraph()
    cameras = [c for c in CAMERAS]
    detections = source.execute('SELECT * FROM detections ORDER BY id').fetchall()
    identities = source.execute('SELECT * FROM identities ORDER BY id').fetchall()
    aliases = source.execute('SELECT * FROM aliases ORDER BY plate').fetchall()
    traffic = source.execute('SELECT * FROM traffic ORDER BY timestamp,event_id').fetchall()
    watchlist = source.execute('SELECT * FROM watchlist ORDER BY plate').fetchall()
    alerts = source.execute('SELECT * FROM alerts ORDER BY id').fetchall()
    audit = source.execute('SELECT * FROM audit ORDER BY id').fetchall()
    metadata = source.execute('SELECT * FROM metadata ORDER BY key').fetchall()

    with psycopg.connect(url) as pg:
        with pg.cursor() as cur:
            # Replace the mirror snapshot in one transaction; it is never the write authority.
            for table in ('alerts','trajectory_hops','detections','aliases','identities','traffic','watchlist','audit','metadata','cameras'):
                cur.execute(f'DELETE FROM {table}')
            cur.executemany('''INSERT INTO cameras(camera_id,name,latitude,longitude,coordinate_accuracy,provenance)
                VALUES (%s,%s,%s,%s,%s,%s)''', [
                (c.id, c.name, c.lat, c.lon,
                 'approximate' if c.id in ('CAM-PN-01','CAM-MN-01') else 'illustrative',
                 'staged/illustrative placement; not filming location' if c.id in ('CAM-PN-01','CAM-MN-01') else 'illustrative graph node; not a verified camera position')
                for c in cameras])
            cur.executemany('INSERT INTO identities(id,plate,vehicle_type,confidence,valid) VALUES (%s,%s,%s,%s,%s)', [
                (r['id'],r['plate'],r['vehicle_type'],r['confidence'],bool(r['valid'])) for r in identities])
            cur.executemany('INSERT INTO aliases(plate,identity_id) VALUES (%s,%s)', [(r['plate'],r['identity_id']) for r in aliases])
            cur.executemany('''INSERT INTO detections(id,event_id,identity_id,camera_id,observed_at,plate,confidence,payload,prev_hash,hash)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''', [
                (r['id'],r['event_id'],r['identity_id'],r['camera_id'],as_dt(r['timestamp']),r['plate'],r['confidence'],r['payload'],r['prev_hash'],r['hash']) for r in detections])

            by_identity: dict[int, list[sqlite3.Row]] = {}
            for row in detections:
                by_identity.setdefault(row['identity_id'], []).append(row)
            hops = []
            for identity_id, rows in by_identity.items():
                rows.sort(key=lambda r: (r['timestamp'], r['id']))
                previous = None
                for order, row in enumerate(rows, 1):
                    payload = json.loads(row['payload'])
                    meta = payload.get('metadata') or {}
                    provenance = meta.get('provenance', 'real footage, OCR (model-estimated)')
                    prev_camera = previous['camera_id'] if previous else None
                    distance = seconds = speed = None
                    direction = 'origin sighting'
                    if previous:
                        distance, _path = graph.shortest(prev_camera, row['camera_id'])
                        seconds = (as_dt(row['timestamp']) - as_dt(previous['timestamp'])).total_seconds()
                        speed = round(distance * 3600 / seconds, 1) if seconds > 0 else None
                        direction = f"{graph.cameras[prev_camera].name} → {graph.cameras[row['camera_id']].name}"
                    hops.append((row['id'],identity_id,order,row['camera_id'],as_dt(row['timestamp']),prev_camera,
                                 distance,seconds,speed,direction, row['confidence'], provenance))
                    previous = row
            cur.executemany('''INSERT INTO trajectory_hops(detection_id,identity_id,hop_order,camera_id,observed_at,
                previous_camera_id,leg_distance_km,travel_seconds,speed_kmh,direction,confidence,provenance)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''', hops)
            cur.executemany('''INSERT INTO alerts(id,detection_id,kind,severity,plate,camera_id,observed_at,explanation,evidence)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)''', [
                (r['id'],r['detection_id'],r['kind'],r['severity'],r['plate'],r['camera_id'],as_dt(r['timestamp']),r['explanation'],r['evidence']) for r in alerts])
            cur.executemany('INSERT INTO audit(id,observed_at,role,action,details) VALUES (%s,%s,%s,%s,%s)', [
                (r['id'],as_dt(r['timestamp']),r['role'],r['action'],r['details']) for r in audit])
            cur.executemany('INSERT INTO metadata(key,value) VALUES (%s,%s)', [(r['key'],r['value']) for r in metadata])
            cur.executemany('INSERT INTO watchlist(plate,reason,created_at) VALUES (%s,%s,%s)', [
                (r['plate'],r['reason'],as_dt(r['created_at'])) for r in watchlist])
            cur.executemany('INSERT INTO traffic(event_id,camera_id,observed_at,vehicle_type,source) VALUES (%s,%s,%s,%s,%s)', [
                (r['event_id'],r['camera_id'],as_dt(r['timestamp']),r['vehicle_type'],r['source']) for r in traffic])
            cur.execute('SELECT id,payload,prev_hash,hash FROM detections ORDER BY id')
            mirrored = cur.fetchall()
            head = {r['key']:r['value'] for r in metadata}['anchor']
            from anpr.db import digest
            for row in mirrored:
                if row[2] != head or row[3] != digest(head, row[1]):
                    raise RuntimeError(f"PostgreSQL mirror chain mismatch at detection {row[0]}")
                head = row[3]
            expected = {r['key']:r['value'] for r in metadata}
            if head != expected['head'] or len(mirrored) != int(expected['count']):
                raise RuntimeError('PostgreSQL mirror chain tail/count mismatch')
            pg_integrity = {'valid':True,'checked':len(mirrored),'head':head}
            cur.execute('''INSERT INTO metadata(key,value) VALUES (%s,%s)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value''',
                ('mirror_integrity',json.dumps(pg_integrity,separators=(',',':'))))
    source.close()
    return {'sqlite_integrity': integrity, 'postgres_integrity': pg_integrity,
            'detections': len(detections), 'trajectory_hops': len(hops), 'mirror': True}


if __name__ == '__main__':
    result = sync()
    print(json.dumps(result, indent=2))
