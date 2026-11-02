"""Configurable anomaly rules. Alerts are investigative leads for human review."""
from datetime import datetime, timedelta
import json
from math import asin, cos, radians, sin, sqrt
from zoneinfo import ZoneInfo
from .db import canonical
from .plates import weighted_distance
from .alert_rules import load_rules


def _fallback_distance(a, b):
    """Road-distance estimate when no graph path exists."""
    r = 6371.0
    lat1, lon1 = radians(a.lat), radians(a.lon)
    lat2, lon2 = radians(b.lat), radians(b.lon)
    h = sin((lat2-lat1)/2)**2 + cos(lat1)*cos(lat2)*sin((lon2-lon1)/2)**2
    return 2*r*asin(sqrt(h))*1.3


def _bearing(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) % 360
    return {'N': 0, 'E': 90, 'S': 180, 'W': 270}.get(str(value).strip().upper())


class AlertEngine:
    def __init__(self, db, graph, rules=None):
        self.db, self.graph = db, graph
        self.rules = rules or load_rules()

    def public_rules(self):
        return self.rules.model_dump(mode='json')

    def evaluate(self, event: dict) -> list[dict]:
        alerts = []
        evidence_payload = event.get('payload') if isinstance(event.get('payload'), dict) else event
        metadata = evidence_payload.get('metadata') or {}
        provenance = metadata.get('provenance') or metadata.get('provenance_label')

        def emit(kind, severity, explanation, evidence):
            score = {'LOW': 20, 'MEDIUM': 55, 'HIGH': 85, 'CRITICAL': 95}.get(severity, 50)
            evidence = {**evidence, 'priority_score': score}
            evidence = {**evidence, 'provenance': provenance} if provenance else evidence
            with self.db.lock:
                cursor = self.db.conn.execute('''INSERT INTO alerts
                    (detection_id,kind,severity,plate,camera_id,timestamp,explanation,evidence)
                    VALUES (?,?,?,?,?,?,?,?)''', (event['id'], kind, severity, event['plate'], event['camera_id'],
                                                  event['timestamp'], explanation, canonical(evidence)))
                alerts.append({'id': cursor.lastrowid, 'plate': event['plate'], 'camera_id': event['camera_id'],
                               'timestamp': event['timestamp'], 'kind': kind, 'severity': severity,
                               'explanation': explanation, 'evidence': evidence})

        # The canonical identity is the primary join; conservative OCR similarity is a fallback.
        for row in self.db.rows('SELECT * FROM watchlist'):
            distance = weighted_distance(event['plate'], row['plate'])
            if distance <= self.rules.blacklist.max_fuzzy_distance:
                reason = row['reason'].lower()
                severity = (self.rules.blacklist.severity_by_reason.get('fuzzy', 'MEDIUM') if distance > 0 else
                            self.rules.blacklist.severity_by_reason.get(reason, self.rules.blacklist.severity_by_reason.get('default', 'HIGH')))
                emit('watchlist', severity, f'Suspected watchlist match ({row["reason"]}); verify visually and confirm case details.',
                     {'watchlist_plate': row['plate'], 'reason': row['reason'], 'case_number': row['reason'].split('·', 1)[1].strip() if '·' in row['reason'] else None,
                      'distance': distance, 'confidence': event['confidence'], 'detection_id': event['id']})

        clone = self.rules.clone_plate
        clone_suspected = False
        if clone.enabled:
            # A unique, conservative OCR variant can be considered for this
            # alert only without changing the persistent canonical identity.
            peers = self.db.rows('SELECT id,plate FROM identities WHERE vehicle_type=(SELECT vehicle_type FROM identities WHERE id=?)',
                                 (event['identity_id'],))
            fuzzy = [row for row in peers if row['id'] != event['identity_id'] and
                     weighted_distance(event['plate'], row['plate']) <= clone.fuzzy_identity_distance]
            candidate_ids = {int(event['identity_id'])}
            if len(fuzzy) == 1:
                candidate_ids.add(int(fuzzy[0]['id']))
            previous = self.db.rows('''SELECT * FROM detections WHERE identity_id=? AND id<>?
                ORDER BY timestamp DESC''', (event['identity_id'], event['id']))
            if len(candidate_ids) > 1:
                previous += self.db.rows('''SELECT * FROM detections WHERE identity_id=? AND id<>?
                                            ORDER BY timestamp DESC''', (next(iter(candidate_ids-{int(event['identity_id'])})), event['id']))
            now = datetime.fromisoformat(event['timestamp'])
            for other in previous:
                if clone.require_distinct_cameras and other['camera_id'] == event['camera_id']:
                    continue
                then = datetime.fromisoformat(other['timestamp'])
                seconds = abs((now-then).total_seconds())
                if seconds > clone.lookback_window_minutes*60:
                    continue
                try:
                    km, path = self.graph.shortest(other['camera_id'], event['camera_id'])
                except (ValueError, KeyError):
                    km, path = float('inf'), []
                if not path or km == float('inf'):
                    a, b = self.graph.cameras.get(other['camera_id']), self.graph.cameras.get(event['camera_id'])
                    if not a or not b:
                        continue
                    km = _fallback_distance(a, b)
                required = km*3600/clone.max_plausible_speed_kmph
                if seconds < clone.min_gap_seconds_to_flag or (seconds > 0 and seconds >= required):
                    continue
                payload = json.loads(other['payload'])
                old_confidence = float(other['confidence'])
                current_confidence = float(event['confidence'])
                if min(old_confidence, current_confidence) < clone.min_read_confidence:
                    emit('needs_review', 'LOW', 'Low-confidence plate observations need manual review; no cloned-plate alert was raised.',
                         {'detection_ids': [other['id'], event['id']], 'reason': 'below clone confidence threshold',
                          'confidence': [old_confidence, current_confidence]})
                    continue
                # Check existing evidence pair so retries/backfills cannot duplicate this pair.
                pair = {int(other['id']), int(event['id'])}
                duplicate = any(set(map(int, json.loads(row['evidence']).get('detection_ids', []))) == pair
                                for row in self.db.rows("SELECT evidence FROM alerts WHERE kind='cloned_plate'"))
                if duplicate:
                    continue
                previous_camera = self.graph.cameras[other['camera_id']]
                current_camera = self.graph.cameras[event['camera_id']]
                speed = round(km*3600/seconds, 1) if seconds > 0 else None
                explain = (f'Suspected cloned plate: same plate seen at {previous_camera.name} and {current_camera.name}, '
                           f'{km:.1f} km apart in {seconds:g} seconds; '
                           f'needs {clone.max_plausible_speed_kmph:g} km/h plausibility threshold.' if seconds > 0 else
                           f'Suspected cloned plate: simultaneous sightings at {previous_camera.name} and {current_camera.name}.')
                emit('cloned_plate', clone.severity, explain, {
                    'detection_ids': [other['id'], event['id']],
                    'cameras': [{'id': previous_camera.id, 'name': previous_camera.name, 'lat': previous_camera.lat, 'lon': previous_camera.lon},
                                {'id': current_camera.id, 'name': current_camera.name, 'lat': current_camera.lat, 'lon': current_camera.lon}],
                    'timestamps': [other['timestamp'], event['timestamp']], 'distance_km': round(km, 2),
                    'actual_gap_seconds': seconds, 'required_min_gap_seconds': round(required, 1),
                    'implied_speed_kmph': speed, 'implied_speed_kmh': speed, 'seconds': seconds,
                    'confidence': [old_confidence, current_confidence],
                    'path': path, 'provenance': provenance})
                clone_suspected = True
                # One nearest impossible leg is sufficient for this new sighting.
                break

        camera = self.graph.cameras.get(event['camera_id'])
        if not camera:
            return alerts
        restricted = self.rules.restricted_hours
        local = datetime.fromisoformat(event['timestamp']).astimezone(ZoneInfo(restricted.timezone))
        start, end = restricted.start_hour, restricted.end_hour
        hour = local.hour
        in_hours = (hour >= start or hour < end) if start > end else start <= hour < end
        if restricted.enabled and getattr(camera, 'restricted', False) and in_hours:
            emit('restricted_zone', restricted.severity,
                 f'Suspected restricted-hours observation at {camera.name}; verify authorization.',
                 {'detection_id': event['id'], 'local_hour': hour, 'timezone': restricted.timezone, 'confidence': event['confidence']})

        speed_rule = self.rules.overspeed
        reported = evidence_payload.get('speed_kmph')
        limit = speed_rule.camera_limits_kmph.get(event['camera_id'], speed_rule.default_limit_kmph)
        zone = metadata.get('zone')
        if zone:
            limit = speed_rule.zone_limits_kmph.get(str(zone), limit)
        measured_speed, speed_method = (float(reported), 'camera_reported_speed') if reported is not None else (None, None)
        if measured_speed is None:
            prior = self.db.rows('SELECT * FROM detections WHERE identity_id=? AND id<>? ORDER BY timestamp DESC LIMIT 1',
                                 (event['identity_id'], event['id']))
            if prior:
                seconds = abs((datetime.fromisoformat(event['timestamp'])-datetime.fromisoformat(prior[0]['timestamp'])).total_seconds())
                try:
                    distance, path = self.graph.shortest(prior[0]['camera_id'], event['camera_id'])
                except ValueError:
                    distance, path = float('inf'), []
                if not path:
                    a, b = self.graph.cameras.get(prior[0]['camera_id']), self.graph.cameras.get(event['camera_id'])
                    distance = _fallback_distance(a, b) if a and b else 0
                measured_speed = distance*3600/seconds if seconds > 0 else None
                speed_method = 'average_between_cameras'
        if (speed_rule.enabled and not clone_suspected and measured_speed is not None and (speed_method != 'average_between_cameras' or measured_speed <= self.rules.clone_plate.max_plausible_speed_kmph)
                and measured_speed > limit + speed_rule.tolerance_kmph):
            emit('overspeed', speed_rule.severity, f'Suspected overspeed: estimated {measured_speed:.1f} km/h against {limit:g} km/h limit.',
                 {'speed_kmph': round(measured_speed, 1), 'limit_kmph': limit, 'tolerance_kmph': speed_rule.tolerance_kmph,
                  'method': speed_method, 'confidence': event['confidence']})

        way = self.rules.wrong_way
        expected = way.expected_bearings_degrees.get(event['camera_id'], getattr(camera, 'expected_bearing', None))
        direction = _bearing(evidence_payload.get('direction'))
        if way.enabled and expected is not None and direction is not None and event['confidence'] >= way.min_read_confidence:
            difference = abs((direction-_bearing(expected)+180) % 360-180)
            if difference > way.direction_tolerance_degrees:
                emit('wrong_way', way.severity, f'Suspected wrong-way travel at {camera.name}; reported direction differs from expected bearing.',
                     {'direction_degrees': direction, 'expected_bearing_degrees': _bearing(expected), 'difference_degrees': difference,
                      'tolerance_degrees': way.direction_tolerance_degrees})

        repeat = self.rules.repeat_visits
        if repeat.enabled:
            cutoff = (datetime.fromisoformat(event['timestamp'])-timedelta(minutes=repeat.window_minutes)).isoformat()
            visits = self.db.rows('SELECT id,timestamp FROM detections WHERE identity_id=? AND camera_id=? AND timestamp>=? ORDER BY timestamp',
                                  (event['identity_id'], event['camera_id'], cutoff))
            if len(visits) >= repeat.count:
                emit('repeat_visits', repeat.severity,
                     f'Suspected repeat visits: {len(visits)} sightings at {camera.name} within {repeat.window_minutes} minutes.',
                     {'detection_ids': [r['id'] for r in visits], 'camera_id': camera.id,
                      'visit_count': len(visits), 'window_minutes': repeat.window_minutes})
        return alerts


def list_alerts(db, limit=100):
    return [{**row, 'evidence': json.loads(row['evidence'])} for row in
            db.rows('SELECT * FROM alerts ORDER BY timestamp DESC,id DESC LIMIT ?', (limit,))]
