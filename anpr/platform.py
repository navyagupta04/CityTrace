"""Application service coordinating evidence, resolution, and intelligence."""
from dataclasses import asdict
from datetime import datetime, timezone
import json
from .db import Database, utcnow
from .graph import CameraGraph
from .identity import IdentityResolver
from .alerts import AlertEngine
from .vision import Read, vote
from .plates import normalize
from . import analytics, trajectory


class Platform:
    def __init__(self, database=':memory:'):
        self.db = Database(database)
        self.graph = CameraGraph()
        self.resolver = IdentityResolver(self.db, self.graph)
        self.alert_engine = AlertEngine(self.db, self.graph)

    def ingest(self, event: dict) -> dict:
        if event['camera_id'] not in self.graph.cameras:
            raise ValueError('Unknown camera id')
        timestamp = datetime.fromisoformat(event['timestamp'])
        if timestamp.tzinfo is None:
            raise ValueError('Timestamp must include timezone')
        timestamp = timestamp.astimezone(timezone.utc).isoformat()
        reads = [Read(**r) for r in event['reads']]
        plate, confidence = vote(reads)
        if not plate:
            raise ValueError('At least one nonempty plate read is required')
        with self.db.transaction():
            existing = self.db.rows('SELECT id,payload,hash FROM detections WHERE event_id=?', (event['event_id'],))
            if existing:
                row = existing[0]
                return {'detection': {**json.loads(row['payload']), 'id': row['id'], 'hash': row['hash']}, 'alerts': [], 'duplicate': True}
            resolution = self.resolver.resolve(plate, confidence, event['vehicle_type'], event['camera_id'], timestamp)
            evidence = {'event_id': event['event_id'], 'camera_id': event['camera_id'], 'timestamp': timestamp,
                        'plate': plate, 'confidence': confidence, 'vehicle_type': event['vehicle_type'],
                        'identity_id': resolution['identity_id'], 'resolution': resolution,
                        'reads': [asdict(r) for r in reads], 'source': event.get('source', 'api')}
            detection = self.db.append(evidence)
            alerts = self.alert_engine.evaluate(detection)
            return {'detection': detection, 'alerts': alerts, 'duplicate': False}

    def watch(self, plate: str, reason: str):
        plate = normalize(plate)
        if not plate.valid:
            raise ValueError('Watchlist requires a valid standard Indian or BH plate')
        with self.db.transaction():
            self.db.conn.execute('INSERT INTO watchlist VALUES (?,?,?) ON CONFLICT(plate) DO UPDATE SET reason=excluded.reason',
                                 (plate.text, reason, utcnow()))
            self.db.audit('officer', 'watchlist.add', {'plate': plate.text, 'reason': reason})
        return {'plate': plate.text, 'reason': reason}

    def search(self, plate: str, role='officer'):
        with self.db.transaction():
            result = trajectory.search(self.db, self.graph, plate)
            self.db.audit(role, 'plate.search', {'query': plate, 'found': result['found'], 'identity_id': result.get('identity_id')})
            return result

    def analytics(self):
        with self.db.lock:
            return analytics.compute(self.db, self.graph)
