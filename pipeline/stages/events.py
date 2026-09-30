from collections import defaultdict
from datetime import datetime,timedelta
import math
from ..common import ROOT,read,expiry

def events_and_trajectories(clips,payload,cfg):
    watch=read(ROOT/cfg['watchlist']).get('plates',[]);watch={v if isinstance(v,str) else v['plate'] for v in watch}
    grouped=defaultdict(list);events=[];ttl=expiry(cfg['privacy_settings']['evidence_days'])
    for clip in clips:
        for track in payload[clip['id']]['tracks']:
            plate=track['plate']
            if plate['status']!='read':continue
            seconds=track['first_frame']/clip['fps'];ts=(datetime.fromisoformat(clip['start_ist'])+timedelta(seconds=seconds)).isoformat()
            stop={'clip_id':clip['id'],'camera_id':clip['camera_id'],'ts_ist':ts,'video_time_s':seconds,'track_id':track['track_id'],'confidence':plate['vote_confidence'],'staged':clip['staged'],'source':'real','expires_at':ttl}
            grouped[plate['text']].append(stop)
            if plate['text'] in watch:events.append({'id':f"real-watch-{clip['id']}-{track['track_id']}",'type':'watchlist_hit','plate':plate['text'],**stop,'explanation':'Voted read matches the configured demo watchlist. Human verification required.','factors':[{'label':'Watchlist match','points':40}]})
    # Camera geometry is exported independently from the seeded frontend dataset.
    positions=read(ROOT/'configs/cameras.json',{})
    for plate,stops in grouped.items():
        stops.sort(key=lambda s:s['ts_ist'])
        for a,b in zip(stops,stops[1:]):
            if a['camera_id']==b['camera_id'] or not positions:continue
            aa=positions.get(a['camera_id']);bb=positions.get(b['camera_id'])
            if not aa or not bb:continue
            lat1,lon1=map(math.radians,[aa['lat'],aa['lon']]);lat2,lon2=map(math.radians,[bb['lat'],bb['lon']]);km=6371*2*math.asin(min(1,math.sqrt(math.sin((lat2-lat1)/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2)))
            seconds=(datetime.fromisoformat(b['ts_ist'])-datetime.fromisoformat(a['ts_ist'])).total_seconds();speed=km/max(seconds,1)*3600
            if speed>cfg['clone_speed_limit_kmh']:events.append({'id':f"real-clone-{b['clip_id']}-{b['track_id']}",'type':'clone_suspect','plate':plate,**b,'staged':a['staged'] or b['staged'],'sightings':[a,b],'distance_km':km,'elapsed_s':seconds,'implied_kmh':speed,'explanation':'Impossible-travel flag for human verification, not proof. Straight-line distance is a conservative lower bound.','factors':[{'label':'Impossible travel','points':35},{'label':'Independent camera reads','points':10}]+([{'label':'Watchlist match','points':40}] if plate in watch else [])})
    return events,[{'plate':plate,'stops':stops,'source':'real','expires_at':ttl} for plate,stops in grouped.items()]

