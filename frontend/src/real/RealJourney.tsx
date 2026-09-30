import { useEffect,useRef,useState } from 'react';
import { Panel,Empty } from '../components/UI';
import NetworkMap from '../components/NetworkMap';
import { cameras,cameraById,roads,normalise,routeBetween,haversine } from '../demo/model';
import type { Trajectory } from '../types';
import type { RealTrajectory } from './types';
import { useRealFootage } from './context';
import RealVideo from './RealVideo';
import ClipEvidence from './ClipEvidence';
import { record } from '../demo/api';

export function assembleTrajectory(real:RealTrajectory):Trajectory{
 const stops=[...real.stops].filter(s=>cameraById.has(s.camera_id)).sort((a,b)=>a.ts_ist.localeCompare(b.ts_ist));
 const hops=stops.map((s,i)=>{const prev=stops[i-1],r=prev?routeBetween(prev.camera_id,s.camera_id):{distance:0,path:[]},seconds=prev?(Date.parse(s.ts_ist)-Date.parse(prev.ts_ist))/1000:0;return {detection_id:i,camera_id:s.camera_id,camera_name:cameraById.get(s.camera_id)!.name,timestamp:s.ts_ist,confidence:s.confidence,observed_plate:real.plate,leg_distance_km:r.distance,seconds,speed_kmh:null,inferred_cameras:r.path.slice(1,-1),implausible:!!prev&&haversine(cameraById.get(prev.camera_id)!,cameraById.get(s.camera_id)!)/Math.max(1,seconds)*3600>110};});
 return {found:!!stops.length,plate:real.plate,identity_id:0,vehicle_type:'unclassified',hops,total_distance_km:hops.reduce((n,h)=>n+h.leg_distance_km,0),geojson:{type:'LineString',coordinates:stops.map(s=>{const c=cameraById.get(s.camera_id)!;return [c.lon,c.lat];})}};
}

export default function RealJourney({plate='',clipId='',onSelect}:{plate?:string;clipId?:string;onSelect?:(plate:string,clipId:string)=>void}){
 const {bundle}=useRealFootage(),[preview,setPreview]=useState(''),[status,setStatus]=useState(''),[busy,setBusy]=useState(false),uploadGeneration=useRef(0);
 useEffect(()=>()=>{if(preview)URL.revokeObjectURL(preview);},[preview]);
 useEffect(()=>()=>{uploadGeneration.current++;},[]);
 const clips=bundle?.manifest.clips||[],real=bundle?.trajectories.find(t=>t.plate===normalise(plate)),allStops=real?.stops||[],stops=clipId?allStops.filter(s=>s.clip_id===clipId):allStops;
 const select=(value:string,id='')=>{onSelect?.(normalise(value),id);record('real.trajectory.search',{plate:normalise(value),clip_id:id,purpose:'Uploaded video evaluation'});};
 async function upload(file:File){
  const generation=++uploadGeneration.current;setStatus('');setPreview('');
  if(file.size>100*1024*1024){setStatus('Choose a clip under 100 MB for local matching.');return;}
  setBusy(true);
  try{const bytes=await file.arrayBuffer(),digest=await crypto.subtle.digest('SHA-256',bytes),sha=Array.from(new Uint8Array(digest),b=>b.toString(16).padStart(2,'0')).join('');if(generation!==uploadGeneration.current)return;
   const matched=clips.find(c=>c.sha256===sha),journey=matched&&bundle?.trajectories.find(t=>t.stops.some(s=>s.clip_id===matched.id));
   if(matched&&journey){select(journey.plate,matched.id);setStatus(`Matched ${file.name} to its reviewed evidence by SHA-256.`);}
   else{setPreview(URL.createObjectURL(file));select('','');setStatus('This file has no processed identity evidence yet. Local preview only; run the offline pipeline before tracking a new recording.');}
  }catch{if(generation===uploadGeneration.current)setStatus('Could not read this video. Try selecting the original file again.');}
  finally{if(generation===uploadGeneration.current)setBusy(false);}
 }
 function exportJourney(){if(!real)return;const geo=allStops.some(s=>s.identity_source==='user_confirmed')?{type:'FeatureCollection',features:stops.map(s=>{const c=cameraById.get(s.camera_id);return {type:'Feature',geometry:{type:'Point',coordinates:[c?.lon,c?.lat]},properties:{...s,plate:real.plate,note:'Separate vehicle evidence; placements illustrative, no journey between vehicles implied.'}};})}:{type:'Feature',geometry:assembleTrajectory(real).geojson,properties:{...real,stops}};const url=URL.createObjectURL(new Blob([JSON.stringify(geo,null,2)],{type:'application/geo+json'})),a=document.createElement('a');a.href=url;a.download=`${real.plate}-sightings.geojson`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
 return <><Panel title="Track using an uploaded video" subtitle="Select either supplied clip, or match the original file locally" className="mt-panel"><div className="padded"><div className="filter-bar"><label>Upload video<input aria-label="Upload trajectory video" type="file" accept="video/*" disabled={busy} onChange={e=>{const file=e.target.files?.[0];if(file)void upload(file);e.target.value='';}}/></label>{clips.filter(c=>c.evidence).map(c=><button key={c.id} onClick={()=>select(c.evidence!.plate,c.id)}>{c.evidence!.vehicle_label} · {c.evidence!.display_plate}</button>)}</div><p role="status">{busy?'Matching file…':status||'The two supplied videos are ready. Matching checks the file hash; it does not claim fresh OCR inference.'}</p>{preview&&<video className="upload-video-preview" src={preview} controls playsInline/>}</div></Panel>
 {real&&<Panel title={`Uploaded footage trajectory · ${real.plate==='AI07204'?'AI 0720-4':real.plate}`} subtitle="Each recording remains a separate vehicle observation" className="mt-panel"><div className="padded"><div className="filter-bar"><button onClick={()=>select(real.plate)}>Both vehicles</button>{allStops.map(s=><button className={clipId===s.clip_id?'selected':''} key={s.clip_id} onClick={()=>select(real.plate,s.clip_id)}>{clips.find(c=>c.id===s.clip_id)?.evidence?.vehicle_label||s.clip_id}</button>)}<button onClick={exportJourney}>Export sighting GeoJSON</button><button onClick={()=>window.print()}>Print case file</button></div><p className="real-notice">{allStops.some(s=>s.identity_source==='user_confirmed')?'Two separate vehicles share this plate. Each clip currently contributes one reviewed sighting. Delhi locations and capture times are staged for testing; no continuous journey between the two cars is inferred.':'Locations marked staged are illustrative; review the recording for each observation.'}</p>{!stops.length?<Empty title="No sighting for this video" message="Choose one of the available recordings above."/>:stops.map(s=>{const clip=clips.find(c=>c.id===s.clip_id);return <section className="vehicle-journey" key={`${s.clip_id}-${s.track_id}`}><h3>{clip?.evidence?.vehicle_label||s.clip_id} · {cameraById.get(s.camera_id)?.name}</h3><p>Single observed stop · {s.ts_ist} · {s.staged?'illustrative assignment':'recorded placement'}</p><div className="two-columns"><NetworkMap cameras={cameras} roads={roads} trajectory={assembleTrajectory(allStops.some(item=>item.identity_source==='user_confirmed')?{...real,stops:[s]}:real)} large/>{clip?.evidence?<ClipEvidence clipId={s.clip_id} trajectory={false}/>:<RealVideo clipId={s.clip_id} seek={s.video_time_s} trackId={s.track_id}/>}</div></section>;})}</div></Panel>}</>;
}
