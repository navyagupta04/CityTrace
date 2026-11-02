"""Append a hash-chained observation directly to the configured SQLite DB.

The running API's database poller evaluates this row within its configured interval.
"""
import argparse
from datetime import datetime
import os
import sys
import uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from anpr.config import Settings
from anpr.db import Database
from anpr.graph import CameraGraph
from anpr.plates import normalize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plate', required=True)
    parser.add_argument('--camera', required=True)
    parser.add_argument('--timestamp', required=True, help='ISO timestamp with timezone')
    parser.add_argument('--confidence', type=float, default=.95)
    parser.add_argument('--speed-kmph', type=float)
    parser.add_argument('--direction', help='bearing degrees or N, S, E, W')
    args = parser.parse_args()
    stamp = datetime.fromisoformat(args.timestamp)
    if stamp.tzinfo is None:
        parser.error('--timestamp must include a timezone, for example +05:30')
    plate = normalize(args.plate).text
    database = Database(Settings().database)
    try:
        if database.verify()['valid'] is not True:
            raise SystemExit('Refusing manual append: current evidence hash chain does not verify.')
        graph = CameraGraph()
        if args.camera not in graph.cameras:
            raise SystemExit(f'Unknown camera id: {args.camera}')
        identities = database.rows('SELECT i.id FROM identities i LEFT JOIN aliases a ON a.identity_id=i.id WHERE a.plate=? OR i.plate=? LIMIT 1', (plate, plate))
        if not identities:
            raise SystemExit(f'No existing canonical identity for {plate}; ingest its first sighting through /api/ingest.')
        event = {'event_id': 'manual-' + uuid.uuid4().hex, 'identity_id': identities[0]['id'],
                 'camera_id': args.camera, 'timestamp': stamp.isoformat(), 'plate': plate,
                 'confidence': args.confidence, 'vehicle_type': 'car', 'resolution': {'method': 'manual_db_append'},
                 'reads': [{'text': plate, 'confidence': args.confidence, 'quality': 1.0}],
                 'source': 'manual database import',
                 'metadata': {'provenance': 'manual database import'},
                 'speed_kmph': args.speed_kmph, 'direction': args.direction}
        with database.transaction():
            row = database.append(event)
        print(f"Appended detection id={row['id']} for {plate} at {args.camera}; the running poller checks it within {Settings().poll_interval_seconds:g}s.")
    finally:
        database.close()


if __name__ == '__main__':
    main()
