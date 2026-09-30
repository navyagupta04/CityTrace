"""Deterministic analytics over observed passes; reject physically impossible legs."""
from collections import Counter, defaultdict
from datetime import datetime
import numpy as np
from .config import ROADS, MAX_SPEED_KMH


def compute(db, graph) -> dict:
    rows = db.rows('SELECT * FROM detections ORDER BY timestamp,id')
    traffic = db.rows('SELECT * FROM traffic ORDER BY timestamp')
    density, minute = Counter(), Counter()
    tracks = defaultdict(list)
    for row in rows:
        density[row['camera_id']] += 1
        minute[(row['camera_id'], row['timestamp'][:16])] += 1
        tracks[row['identity_id']].append(row)
    for row in traffic:
        density[row['camera_id']] += 1
        minute[(row['camera_id'], row['timestamp'][:16])] += 1
    speeds = defaultdict(list)
    od = Counter()
    for track in tracks.values():
        trip = [track[0]]
        for a, b in zip(track, track[1:]):
            seconds = (datetime.fromisoformat(b['timestamp']) - datetime.fromisoformat(a['timestamp'])).total_seconds()
            if seconds > 1800:
                if len(trip) > 1:
                    od[(trip[0]['camera_id'], trip[-1]['camera_id'])] += 1
                trip = []
            trip.append(b)
            if b['camera_id'] in graph.edges[a['camera_id']] and 0 < seconds <= 1800:
                km, _ = graph.edges[a['camera_id']][b['camera_id']]
                speed = km * 3600 / seconds
                if speed <= MAX_SPEED_KMH:
                    speeds[tuple(sorted((a['camera_id'], b['camera_id'])))].append(speed)
        if len(trip) > 1:
            od[(trip[0]['camera_id'], trip[-1]['camera_id'])] += 1
    corridors = []
    all_speeds = []
    for a, b, km, free in ROADS:
        values = speeds[tuple(sorted((a, b)))]
        all_speeds.extend(values)
        median = float(np.median(values)) if values else None
        index = free / median if median else None
        level = 'unknown' if index is None else ('free' if index < 1.4 else 'moderate' if index < 2 else 'heavy' if index < 3 else 'congested')
        corridors.append({'from': a, 'to': b, 'distance_km': km, 'free_flow_kmh': free,
                          'median_speed_kmh': round(median, 1) if median else None,
                          'congestion_index': round(index, 2) if index else None, 'level': level, 'samples': len(values)})
    heatmap = [{'camera_id': c.id, 'name': c.name, 'lat': c.lat, 'lon': c.lon, 'count': density[c.id]} for c in graph.cameras.values()]
    timestamps = sorted(r['timestamp'] for r in rows + traffic)
    summary = {'detections': len(rows) + len(traffic), 'plate_detections': len(rows), 'unidentified_passes': len(traffic), 'unique_vehicles': len(tracks), 'active_cameras': len(density),
               'network_average_speed_kmh': round(float(np.mean(all_speeds)), 1) if all_speeds else None,
               'open_alerts': db.rows('SELECT COUNT(*) AS n FROM alerts')[0]['n'],
               'first_detection': timestamps[0] if timestamps else None,
               'last_detection': timestamps[-1] if timestamps else None,
               'scope': 'all retained detections', 'speed_samples': len(all_speeds)}
    return {'summary': summary, 'corridors': corridors, 'heatmap': sorted(heatmap, key=lambda x: -x['count']),
            'origin_destination': [{'origin': a, 'destination': b, 'trips': n} for (a, b), n in od.most_common()],
            'vehicles_per_minute': [{'camera_id': c, 'minute': m, 'count': n} for (c, m), n in sorted(minute.items())]}
