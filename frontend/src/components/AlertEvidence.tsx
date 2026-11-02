import type {Alert, Camera, Road, Trajectory} from '../types';
import SimulatedFeed, {PlateCrop} from './SimulatedFeed';
import NetworkMap from './NetworkMap';
import {Badge} from './UI';

type CameraEvidence={id:string;name:string;lat:number;lon:number};
export default function AlertEvidence({alert}:{alert:Alert}){
 const factors=(alert.evidence.factors||[]) as {label:string;points:number}[];
 const score=Math.min(100,Math.max(0,Number(alert.evidence.priority_score??factors.reduce((s,f)=>s+f.points,0))));
 const clone=['CLONED_PLATE','cloned_plate'].includes(alert.kind),provenance=String(alert.evidence.provenance||'');
 const locations=(alert.evidence.cameras||[]) as CameraEvidence[];
 const cameras:Camera[]=locations.map(c=>({id:c.id,name:c.name,lat:c.lat,lon:c.lon,restricted:false}));
 const ids=(alert.evidence.detection_ids||[]) as number[],times=(alert.evidence.timestamps||[]) as string[],confidence=(alert.evidence.confidence||[]) as number[];
 const gap=Number(alert.evidence.actual_gap_seconds||0),distance=Number(alert.evidence.distance_km||0);
 const journey:Trajectory={found:true,plate:alert.plate,identity_id:0,vehicle_type:'car',total_distance_km:distance,
  geojson:{type:'LineString',coordinates:[]},hops:cameras.map((camera,i)=>({detection_id:ids[i]||i+1,camera_id:camera.id,camera_name:camera.name,
   timestamp:times[i]||alert.timestamp,confidence:confidence[i]||0,observed_plate:alert.plate,leg_distance_km:i?distance:0,
   seconds:i?gap:null,speed_kmh:i?Number(alert.evidence.implied_speed_kmph)||null:null,inferred_cameras:[],implausible:clone}))};
 const route:Road[]=cameras.length===2?[{from:cameras[0].id,to:cameras[1].id,distance_km:distance,free_flow_kmh:50}]:[];
 return <div className="alert-evidence">
  {!provenance&&<><SimulatedFeed camera={alert.camera_id} plate={alert.plate} compact paused/><PlateCrop plate={alert.plate}/></>}
  {provenance&&<Badge tone="amber">{provenance}</Badge>}
  <div className="score-header"><strong>{score}<small>/100</small></strong><div><h3>Priority for review</h3><Badge tone={score>75?'red':score>30?'amber':'green'}>{score>75?'High':score>30?'Suspicious':'Normal'}</Badge></div></div>
  {factors.map(f=><div className="score-factor" key={f.label}><span>{f.label}</span><i><b style={{width:`${Math.abs(f.points)}%`}}/></i><strong>{f.points>0?'+':''}{f.points}</strong></div>)}
  {clone&&<div className="impossible-travel"><h3>Suspected cloned plate · evidence</h3><p>{alert.explanation}</p><strong>{distance} km · {gap} seconds · implied {String(alert.evidence.implied_speed_kmph??'—')} km/h</strong><p>Required minimum gap: {String(alert.evidence.required_min_gap_seconds)} seconds. Both observations are linked to hash-chained detections for human review.</p>{cameras.length===2&&<NetworkMap cameras={cameras} roads={route} trajectory={journey} progress={1} large region="All Delhi"/>}</div>}
  {alert.kind==='watchlist'&&<div className="impossible-travel"><h3>Watchlist evidence</h3><p>Reason: {String(alert.evidence.reason||'Not supplied')}</p><p>Case: {String(alert.evidence.case_number||'Not supplied')}</p><p>Matched plate: {String(alert.evidence.watchlist_plate||'')}</p></div>}
  {alert.kind==='overspeed'&&<div className="impossible-travel"><h3>Speed evidence</h3><p>Reported/estimated speed: {String(alert.evidence.speed_kmph)} km/h</p><p>Configured limit: {String(alert.evidence.limit_kmph)} km/h (+ {String(alert.evidence.tolerance_kmph)} km/h tolerance)</p><p>Method: {String(alert.evidence.method)}</p></div>}
  {alert.kind==='wrong_way'&&<div className="impossible-travel"><h3>Direction evidence</h3><p>Reported bearing: {String(alert.evidence.direction_degrees)}° · expected: {String(alert.evidence.expected_bearing_degrees)}°</p><p>Difference: {String(alert.evidence.difference_degrees)}° · allowed: {String(alert.evidence.tolerance_degrees)}°</p></div>}
  <p className="muted">Alerts are investigative leads for human review, not enforcement.</p>
 </div>;
}
