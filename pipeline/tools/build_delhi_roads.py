"""Download an OSM road extract once, route offline; never downloads video."""
import json, math, heapq, urllib.request, urllib.parse
from ..common import ROOT,write,read,now

def distance(a,b):
    lat1,lon1=map(math.radians,[a[1],a[0]]);lat2,lon2=map(math.radians,[b[1],b[0]])
    return 6371*2*math.asin(min(1,math.sqrt(math.sin((lat2-lat1)/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2)))

def build(cfg):
    cache=ROOT/cfg['cache']/'osm-delhi.json'
    query='[out:json][timeout:90];way["highway"~"^(motorway|trunk|primary|secondary|motorway_link|trunk_link|primary_link|secondary_link)$"](28.40,76.83,28.90,77.36);out geom;'
    if not cache.exists():
        for endpoint in ['https://overpass.private.coffee/api/interpreter','https://overpass-api.de/api/interpreter']:
            try:
                request=urllib.request.Request(endpoint+'?'+urllib.parse.urlencode({'data':query}),headers={'User-Agent':'CityTrace-offline-demo/1.0'})
                with urllib.request.urlopen(request,timeout=115) as response:data=json.load(response)
                if not data.get('elements'):raise ValueError('Empty road extract')
                write(cache,data);break
            except Exception as e:print(f'OSM endpoint unavailable: {e}',flush=True)
        else:print('Roads unavailable; schematic fallback remains active. Retry python -m pipeline build-delhi-roads.');return
    data=json.loads(cache.read_text(encoding='utf-8'));positions={};graph={};features=[]
    for way in data['elements']:
        if 'geometry' not in way:continue
        pts=[[round(p['lon'],6),round(p['lat'],6)] for p in way['geometry']];ids=way['nodes'];oneway=way.get('tags',{}).get('oneway')
        features.append({'type':'Feature','properties':{'highway':way['tags']['highway']},'geometry':{'type':'LineString','coordinates':pts}})
        for node,pt in zip(ids,pts):positions[node]=pt;graph.setdefault(node,[])
        for a,b,aa,bb in zip(ids,ids[1:],pts,pts[1:]):
            km=distance(aa,bb)
            if oneway!='-1':graph[a].append((b,km))
            if oneway not in ('yes','1'):graph[b].append((a,km))
    cameras=read(ROOT/'configs/cameras.json');snapped={}
    for key,c in cameras.items():
        node=min(positions,key=lambda n:distance([c['lon'],c['lat']],positions[n]));lon,lat=positions[node];snapped[key]={'node':node,'lat':lat,'lon':lon,'snap_distance_km':distance([c['lon'],c['lat']],[lon,lat])}
    def route(start,end):
        queue=[(0,start)];cost={start:0};previous={}
        while queue:
            d,node=heapq.heappop(queue)
            if node==end:
                path=[end]
                while path[-1]!=start:path.append(previous[path[-1]])
                return {'coordinates':[positions[n] for n in reversed(path)],'road_distance_km':d}
            if d!=cost[node]:continue
            for nxt,weight in graph[node]:
                nd=d+weight
                if nd<cost.get(nxt,float('inf')):cost[nxt]=nd;previous[nxt]=node;heapq.heappush(queue,(nd,nxt))
        return None
    routes={}
    for link in read(ROOT/'configs/links.json'):
        for a,b in [(link['from'],link['to']),(link['to'],link['from'])]:
            result=route(snapped[a]['node'],snapped[b]['node'])
            if result:routes[a+'-'+b]={**result,'from':a,'to':b,'straight_distance_km':distance([cameras[a]['lon'],cameras[a]['lat']],[cameras[b]['lon'],cameras[b]['lat']])}
    out=ROOT/cfg['output'];meta={'attribution':'Road data © OpenStreetMap contributors (ODbL)','extract_date':now(),'camera_placement':'illustrative','source':'OpenStreetMap'}
    write(out/'roads.json',{'type':'FeatureCollection','features':features,**meta});write(out/'routes.json',{'real_position':snapped,'links':routes,**meta})
    print(f"OSM roads: {(out/'roads.json').stat().st_size} bytes; {len(routes)}/130 directed routes",flush=True)
