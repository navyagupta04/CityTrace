"""Cases derived exclusively from completed OCR reads and explicit placements."""
import hashlib
import heapq
import json
import math
import re
from datetime import datetime
from pathlib import Path
from pipeline.common import ROOT
from .config import MAX_SPEED_KMH
from .plates import normalize


def camera_graph(root=ROOT):
    # Read the existing frontend graph without executing or modifying seeded data.
    source = (root/'frontend/src/demo/model.ts').read_text(encoding='utf-8')
    sites = re.search(r'const sites:.*?=\[(.*?)\n\];', source, re.S).group(1)
    cameras = {f'C{i+1:02}': dict(id=f'C{i+1:02}', name=n, lat=float(a), lon=float(b))
               for i, (n, a, b) in enumerate(re.findall(r"\['([^']+)',([\d.]+),([\d.]+)\]", sites))}
    links = json.loads(re.search(r'const links=(\[.*?\]);', source).group(1))
    path = root/'frontend/public/real/routes.json'
    routes = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    for cid, position in routes.get('real_position', {}).items():
        if cid in cameras:
            cameras[cid].update(lat=position['lat'], lon=position['lon'])
    edges = {}
    for a, b in links:
        a, b = f'C{a:02}', f'C{b:02}'
        link = routes.get('links', {}).get(f'{a}-{b}') or routes.get('links', {}).get(f'{b}-{a}')
        distance = link['road_distance_km'] if link else straight_km(cameras[a], cameras[b])*1.3
        points = link['coordinates'] if link else [[cameras[a]['lon'], cameras[a]['lat']], [cameras[b]['lon'], cameras[b]['lat']]]
        if points and abs(points[0][0]-cameras[a]['lon'])+abs(points[0][1]-cameras[a]['lat']) > abs(points[-1][0]-cameras[a]['lon'])+abs(points[-1][1]-cameras[a]['lat']):
            points = list(reversed(points))
        edges[a, b] = (float(distance), points)
        edges[b, a] = (float(distance), list(reversed(points)))
    return cameras, edges


def straight_km(a, b):
    lat1, lat2 = math.radians(a['lat']), math.radians(b['lat'])
    value = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(math.radians(b['lon']-a['lon'])/2)**2
    return 6371*2*math.asin(min(1, math.sqrt(value)))


def shortest(edges, start, end):
    queue, visited = [(0, start, [start], [])], set()
    while queue:
        distance, node, path, points = heapq.heappop(queue)
        if node == end:
            return distance, path, points
        if node in visited:
            continue
        visited.add(node)
        for (a, b), (km, coordinates) in edges.items():
            if a == node and b not in visited:
                heapq.heappush(queue, (distance+km, b, path+[b], points+coordinates[1:] if points else coordinates))
    raise ValueError('Camera nodes are not connected')


def group_trajectories(files, placements, purpose, generated_hashes=()):
    cameras, edges = camera_graph()
    selected = {}
    for place in placements:
        name = place['file']
        if name in selected:
            raise ValueError('Only one placement per clip is allowed')
        if place['camera_id'] not in cameras:
            raise ValueError('Choose an existing camera node')
        stamp = datetime.fromisoformat(place['ts_ist'])
        if stamp.utcoffset() is None or stamp.utcoffset().total_seconds() != 19800:
            raise ValueError('Placement times must include the IST +05:30 offset')
        selected[name] = place
    groups = {}
    for file in files:
        place = selected.get(file['file'])
        if not place:
            continue
        # One stop per normalized plate per file: keep its strongest accepted track.
        best = {}
        for plate in file.get('tracks', [])+file.get('plates', []):
            text = normalize(plate.get('voted') or '').text
            if plate.get('status') != 'read' or not text:
                continue
            if text not in best or plate['vote_confidence'] > best[text]['vote_confidence']:
                best[text] = plate
        for text, plate in best.items():
            fps = file.get('video_fps') or 0
            duration = (plate.get('last_frame',0)-plate.get('first_frame',0))/fps if fps else None
            groups.setdefault(text, []).append(dict(clip=file['file'], sha256=file['sha256'], camera_id=place['camera_id'],
                ts_ist=place['ts_ist'], video_time_s=plate.get('first_time_s') or 0, vote_confidence=plate['vote_confidence'],
                staged=bool(place.get('staged', True)), generated=file['sha256'] in generated_hashes or bool(place.get('generated',False)),
                track_id=plate.get('track_id'), evidence=plate, observed_span_s=duration))
    cases = []
    for plate, stops in sorted(groups.items()):
        stops.sort(key=lambda s:(datetime.fromisoformat(s['ts_ist']),s['clip']))
        points, total = [], 0
        for i, stop in enumerate(stops):
            camera = cameras[stop['camera_id']]
            distance, seconds, speed, route = 0, None, None, [stop['camera_id']]
            coords = [[camera['lon'],camera['lat']]]
            if i:
                previous = stops[i-1]
                distance, route, coords = shortest(edges, previous['camera_id'], stop['camera_id'])
                seconds = (datetime.fromisoformat(stop['ts_ist'])-datetime.fromisoformat(previous['ts_ist'])).total_seconds()
                speed = distance*3600/seconds if seconds > 0 else None
            total += distance
            points += coords[1:] if points else coords
            stop.update(camera=camera, leg_distance_km=round(distance,3), seconds=seconds, speed_kmh=round(speed,1) if speed is not None else None,
                        inferred_cameras=route[1:-1], implausible=bool(i and distance and (seconds == 0 or speed > MAX_SPEED_KMH)))
        token = hashlib.sha256((plate+'|'+ '|'.join(s['sha256']+s['ts_ist'] for s in stops)).encode()).hexdigest()[:20]
        cases.append(dict(id=token,plate=plate,purpose=purpose,stops=stops,total_distance_km=round(total,3),generated=any(s['generated'] for s in stops),
                          staged=any(s['staged'] for s in stops),geojson=dict(type='LineString',coordinates=points if len(points)>1 else points*2)))
    return cases
