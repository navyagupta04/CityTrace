"""Delhi road-aligned density from local seeded JSON files; no new database."""
from datetime import datetime, timedelta
from pathlib import Path
import json
import math
import threading
import heapq
import urllib.request
from fastapi import HTTPException, Query
from .config import IST

ROOT = Path(__file__).resolve().parent.parent
ZONES = ['Central Delhi', 'North Delhi', 'North West Delhi', 'West Delhi',
         'South West Delhi', 'South Delhi', 'South East Delhi', 'East Delhi']


class GISStore:
    """Local JSON aggregates. No additional database is needed."""
    def __init__(self, directory=None):
        self.directory = Path(directory or ROOT/'data/gis-density')
        self.lock = threading.RLock()
        self.routes = json.loads((ROOT/'frontend/public/real/routes.json').read_text())
        self.route_directory=self.directory/'routes'
        if self.route_directory.is_dir():
            for path in self.route_directory.glob('C*-C*.json'):
                self.routes['links'][path.stem]=json.loads(path.read_text())
        raw = json.loads((ROOT/'configs/cameras.json').read_text())
        self.cameras = []
        for i,camera in enumerate(raw.values()):
            c=dict(**camera,zone=ZONES[i//5],status='Offline' if i==12 else 'Processing' if i==36 else 'Online')
            c.update(self.routes['real_position'].get(c['id'],{}))
            self.cameras.append(c)

    def route(self,from_id,to_id,refresh=False):
        lookup={c['id']:c for c in self.cameras}
        if from_id not in lookup or to_id not in lookup:raise ValueError('Unknown camera ID')
        key=from_id+'-'+to_id
        if refresh:
            a,b=lookup[from_id],lookup[to_id]
            url=f"https://router.project-osrm.org/route/v1/driving/{a['lon']},{a['lat']};{b['lon']},{b['lat']}?overview=full&geometries=geojson"
            try:
                with urllib.request.urlopen(url,timeout=4) as response:body=json.load(response)
                result=body['routes'][0]
                lat1,lat2=math.radians(a['lat']),math.radians(b['lat'])
                delta_lat=lat2-lat1;delta_lon=math.radians(b['lon']-a['lon'])
                hav=math.sin(delta_lat/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(delta_lon/2)**2
                straight=6371*2*math.asin(min(1,math.sqrt(hav)))
                road=dict(coordinates=result['geometry']['coordinates'],road_distance_km=result['distance']/1000,straight_distance_km=straight,provider='OSRM',**{'from':from_id,'to':to_id})
                with self.lock:
                    self.route_directory.mkdir(parents=True,exist_ok=True)
                    path=self.route_directory/(key+'.json');tmp=path.with_suffix('.tmp')
                    tmp.write_text(json.dumps(road),encoding='utf-8');tmp.replace(path)
                    self.routes['links'][key]=road
                return dict(**road,cached=False)
            except Exception:
                pass  # The bundled road graph remains usable while OSRM is offline.
        links=self.routes['links']
        if key in links:return dict(**links[key],cached=True)
        reverse=links.get(to_id+'-'+from_id)
        if reverse:return dict(coordinates=list(reversed(reverse['coordinates'])),road_distance_km=reverse['road_distance_km'],cached=True)
        pending=[(0.,from_id,[])];visited=set()
        while pending:
            cost,node,path=heapq.heappop(pending)
            if node in visited:continue
            visited.add(node)
            if node==to_id:return dict(coordinates=path,road_distance_km=cost,cached=True,provider='Cached OSM graph')
            for edge in links.values():
                a,b=edge['from'],edge['to']
                nxt=b if a==node else a if b==node else None
                if nxt and nxt not in visited:
                    coords=edge['coordinates'] if a==node else list(reversed(edge['coordinates']))
                    heapq.heappush(pending,(cost+edge['road_distance_km'],nxt,path+(coords[1:] if path else coords)))
        raise ValueError('No cached road route is available')

    def seed_day(self, day):
        with self.lock:
            path=self.directory/(day.isoformat()+'.json')
            if path.is_file():return json.loads(path.read_text())
            rows=[]
            major={'C01','C02','C03','C06','C08','C16','C24','C25','C28','C33','C35'}
            for i,c in enumerate(self.cameras):
                for quarter in range(96):
                    hour=quarter/4
                    rush=math.exp(-((hour-9)/1.8)**2)+1.55*math.exp(-((hour-18.5)/2.1)**2)
                    count=round((8+(i*7%13)+rush*(35 if c['id'] in major else 19))*(1.25 if c['zone']=='Central Delhi' else 1))
                    if c['status']=='Offline':count=0
                    ts=datetime.combine(day,datetime.min.time(),tzinfo=IST)+timedelta(minutes=quarter*15)
                    rows.append(dict(camera_id=c['id'],bucket=ts.isoformat(),vehicles=count,reads=round(count*.92),source='seeded_demo'))
            self.directory.mkdir(parents=True,exist_ok=True)
            tmp=path.with_suffix('.tmp')
            tmp.write_text(json.dumps(rows),encoding='utf-8');tmp.replace(path)
            return rows

    def density(self,start,end,region='All Delhi'):
        if end<=start or end-start>timedelta(days=31):
            raise ValueError('Choose a positive time window no longer than 31 days')
        scoped=[c for c in self.cameras if region=='All Delhi' or c['zone']==region]
        ids={c['id'] for c in scoped}
        counts={c['id']:dict(**c,vehicles=0,reads=0,last_detection=None) for c in scoped}
        hours={}
        day=start.date()
        while day<=end.date():
            for row in self.seed_day(day):
                timestamp=datetime.fromisoformat(row['bucket'])
                if row['camera_id'] not in ids or not start<=timestamp<end:continue
                c=counts[row['camera_id']]
                c['vehicles']+=row['vehicles'];c['reads']+=row['reads']
                if row['vehicles'] and (not c['last_detection'] or row['bucket']>c['last_detection']):c['last_detection']=row['bucket']
                hour=timestamp.strftime('%H:00');hours[hour]=hours.get(hour,0)+row['vehicles']
            day+=timedelta(days=1)
        cameras=list(counts.values())
        totals={c['id']:int(c['vehicles']) for c in cameras}
        points=[[c['lat'],c['lon'],totals[c['id']]] for c in cameras if totals[c['id']]]
        for road in self.routes['links'].values():
            weight=(totals.get(road['from'],0)+totals.get(road['to'],0))/2
            if weight:
                points.extend([lat,lon,weight] for lon,lat in sample_line(road['coordinates']))
        merged={}
        for lat,lon,weight in points:
            key=(round(lat,5),round(lon,5));merged[key]=max(merged.get(key,0),weight)
        points=[[lat,lon,weight] for (lat,lon),weight in merged.items()]
        zones={z:sum(c['vehicles'] for c in cameras if c['zone']==z) for z in ZONES}
        total=sum(totals.values())
        return dict(points=points,cameras=cameras,total_vehicles=total,
                    peak_zone=max(zones,key=zones.get) if total else None,
                    peak_hour=max(hours,key=hours.get) if total else None,
                    start=start.isoformat(),end=end.isoformat(),source='seeded_demo',storage='Local JSON files',
                    geometry_source='Cached OpenStreetMap road geometry',
                    units='Vehicle detections (not unique citywide vehicles)',max_intensity=max([p[2] for p in points],default=1))


def sample_line(coordinates,spacing=.0022):
    points=[]
    remaining=0.
    for a,b in zip(coordinates,coordinates[1:]):
        length=math.hypot((b[0]-a[0])*.88,b[1]-a[1])
        if not length:continue
        offset=remaining
        while offset<length:
            points.append([a[0]+(b[0]-a[0])*offset/length,a[1]+(b[1]-a[1])*offset/length])
            offset+=spacing
        remaining=offset-length
    return points+[coordinates[-1]] if coordinates else []


def register_gis(app):
    store=GISStore()
    app.state.gis=store

    @app.get('/api/gis/routes')
    def routes():return store.routes

    @app.get('/api/gis/route')
    def route(from_id:str,to_id:str,refresh:bool=False):
        try:return store.route(from_id,to_id,refresh)
        except ValueError as error:raise HTTPException(404,str(error)) from error

    @app.get('/api/gis/density')
    def density(window:str='today',start:datetime|None=None,end:datetime|None=None,region:str='All Delhi'):
        now=datetime.now(IST)
        if window=='last_hour':start,end=now-timedelta(hours=1),now
        elif window=='today':start=now.replace(hour=0,minute=0,second=0,microsecond=0);end=now
        elif window!='custom' or start is None or end is None:raise HTTPException(422,'Use last_hour, today or custom with start and end')
        if start.tzinfo is None or end.tzinfo is None:raise HTTPException(422,'Start and end must include a timezone')
        if region!='All Delhi' and region not in ZONES:raise HTTPException(422,'Unknown Delhi region')
        try:return store.density(start.astimezone(IST),end.astimezone(IST),region)
        except ValueError as error:raise HTTPException(422,str(error)) from error
        except Exception as error:raise HTTPException(503,'Local GIS density files could not be read.') from error
