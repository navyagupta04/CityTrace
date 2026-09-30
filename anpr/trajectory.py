"""Ordered observed hops with explicitly marked shortest-path inferences."""
from datetime import datetime
from .config import MAX_SPEED_KMH
from .plates import normalize, weighted_distance


def search(db, graph, query: str) -> dict:
    plate = normalize(query).text
    candidates = db.rows('SELECT * FROM identities')
    ranked = sorted(((weighted_distance(plate, row['plate']), row) for row in candidates), key=lambda x: (x[0], -x[1]['confidence']))
    alias = db.rows('SELECT identity_id FROM aliases WHERE plate=?', (plate,))
    if alias:
        identity = next(row for row in candidates if row['id'] == alias[0]['identity_id'])
        distance = 0
    elif ranked and ranked[0][0] <= 1.3:
        distance, identity = ranked[0]
    else:
        return {'query': plate, 'found': False, 'hops': [], 'geojson': {'type': 'LineString', 'coordinates': []}}
    rows = db.rows('SELECT * FROM detections WHERE identity_id=? ORDER BY timestamp,id', (identity['id'],))
    hops, coordinates, total = [], [], 0.0
    previous = None
    for row in rows:
        km, path, seconds, speed = 0.0, [row['camera_id']], None, None
        if previous:
            km, path = graph.shortest(previous['camera_id'], row['camera_id'])
            seconds = (datetime.fromisoformat(row['timestamp']) - datetime.fromisoformat(previous['timestamp'])).total_seconds()
            speed = round(km * 3600 / seconds, 1) if seconds > 0 else None
        total += km
        for node in path if not coordinates else path[1:]:
            camera = graph.cameras[node]
            coordinates.append([camera.lon, camera.lat])
        hops.append({'detection_id': row['id'], 'camera_id': row['camera_id'], 'camera_name': graph.cameras[row['camera_id']].name,
                     'timestamp': row['timestamp'], 'confidence': row['confidence'], 'observed_plate': row['plate'],
                     'leg_distance_km': round(km, 2), 'seconds': seconds, 'speed_kmh': speed,
                     'inferred_cameras': path[1:-1], 'implausible': bool(previous and km and (seconds == 0 or speed > MAX_SPEED_KMH))})
        previous = row
    if len(coordinates) == 1:
        coordinates *= 2  # valid degenerate GeoJSON LineString for a single observation
    return {'found': True, 'query': plate, 'match_distance': distance, 'plate': identity['plate'],
            'identity_id': identity['id'], 'vehicle_type': identity['vehicle_type'], 'hops': hops,
            'total_distance_km': round(total, 2), 'geojson': {'type': 'LineString', 'coordinates': coordinates}}
