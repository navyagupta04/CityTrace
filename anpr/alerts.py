"""Rules that report evidence and uncertainty, never automatic enforcement."""
from datetime import datetime
import json
from .config import MAX_SPEED_KMH, IST
from .db import canonical
from .plates import weighted_distance


class AlertEngine:
    def __init__(self, db, graph):
        self.db, self.graph = db, graph

    def evaluate(self, event: dict) -> list[dict]:
        alerts = []

        def emit(kind, severity, explanation, evidence):
            item = {k: event[k] for k in ('plate', 'camera_id', 'timestamp')}
            item.update(kind=kind, severity=severity, explanation=explanation, evidence=evidence)
            cursor = self.db.conn.execute('''INSERT INTO alerts
                (detection_id,kind,severity,plate,camera_id,timestamp,explanation,evidence)
                VALUES (?,?,?,?,?,?,?,?)''', (event['id'], kind, severity, item['plate'], item['camera_id'],
                                            item['timestamp'], explanation, canonical(evidence)))
            alerts.append({'id': cursor.lastrowid, **item})

        for entry in self.db.rows('SELECT * FROM watchlist'):
            distance = weighted_distance(event['plate'], entry['plate'])
            if distance <= 0.6:
                exact = distance == 0
                emit('watchlist', 'HIGH' if exact else 'MEDIUM',
                     f"{'Exact watchlist match' if exact else 'Look-alike watchlist match; verify visually'}: {entry['reason']}",
                     {'watchlist_plate': entry['plate'], 'distance': distance, 'confidence': event['confidence'], 'detection_id': event['id']})
        # Compare neighboring same-plate reads on BOTH sides to handle late ingestion.
        matches = self.db.rows('SELECT * FROM detections WHERE plate=? AND id<>? ORDER BY timestamp', (event['plate'], event['id']))
        before = [d for d in matches if d['timestamp'] <= event['timestamp']]
        after = [d for d in matches if d['timestamp'] > event['timestamp']]
        for other in before[-1:] + after[:1]:
            km, _ = self.graph.shortest(other['camera_id'], event['camera_id'])
            seconds = abs((datetime.fromisoformat(event['timestamp']) - datetime.fromisoformat(other['timestamp'])).total_seconds())
            if km and (seconds == 0 or km * 3600 / seconds > MAX_SPEED_KMH):
                speed = round(km * 3600 / seconds, 1) if seconds else None
                high = min(event['confidence'], other['confidence']) >= 0.8
                speed_text = f'{speed} km/h' if speed is not None else 'simultaneous sightings'
                emit('cloned_plate', 'HIGH' if high else 'MEDIUM',
                     f"Possible cloned plate: {km:g} km in {seconds / 60:g} minutes ({speed_text}), above {MAX_SPEED_KMH:g} km/h. "
                     + ('Both reads are high confidence; review images.' if high else 'Low-confidence evidence; verify visually.'),
                     {'detection_ids': [other['id'], event['id']], 'cameras': [other['camera_id'], event['camera_id']],
                      'confidence': [other['confidence'], event['confidence']], 'distance_km': km, 'seconds': seconds, 'implied_speed_kmh': speed})
        camera = self.graph.cameras[event['camera_id']]
        hour = datetime.fromisoformat(event['timestamp']).astimezone(IST).hour
        start, end = camera.restricted_start, camera.restricted_end
        in_hours = (hour >= start or hour < end) if start > end else start <= hour < end
        if camera.restricted and in_hours:
            emit('restricted_zone', 'MEDIUM',
                 f'Vehicle observed at {camera.name} during restricted hours {start:02}:00–{end:02}:00 IST. Verify authorization.',
                 {'detection_id': event['id'], 'local_hour': hour, 'timezone': 'Asia/Kolkata', 'confidence': event['confidence']})
        return alerts


def list_alerts(db, limit=100):
    return [{**row, 'evidence': json.loads(row['evidence'])} for row in
            db.rows('SELECT * FROM alerts ORDER BY timestamp DESC,id DESC LIMIT ?', (limit,))]
