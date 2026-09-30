import type { Bundle } from './types';
export async function loadRealBundle():Promise<Bundle|null>{
 const response=await fetch('/real/manifest.json');if(response.status===404)return null;if(!response.ok)throw Error('Unable to load real-footage manifest');
 const manifest=await response.json();if(!Array.isArray(manifest.clips))throw Error('Invalid real-footage manifest');
 const json=async(path:string,optional=false)=>{const r=await fetch(`/real/${path}`);if(!r.ok){if(optional)return null;throw Error(`Missing bundle file: ${path}`);}return r.json();};
 const [analysis,tracks,counts,events,trajectories,metrics,privacy,registry]=await Promise.all([
 Promise.all(manifest.clips.map(async(c:{id:string})=>[c.id,await json(`analysis/${c.id}.json`)])),
 Promise.all(manifest.clips.map(async(c:{id:string})=>[c.id,await json(`tracks/${c.id}.json`)])),
 Promise.all(manifest.clips.map(async(c:{id:string})=>[c.id,await json(`counts/${c.id}.json`)])),json('events.json'),json('trajectories.json'),json('metrics.json',true),json('privacy.json',true),json('registry.json',true)]);
 return {manifest,analysis:Object.fromEntries(analysis),tracks:Object.fromEntries(tracks),counts:Object.fromEntries(counts),events,trajectories,metrics,privacy:privacy||{},registry:registry||{}};
}
export function erasePlate(bundle:Bundle,plate:string):Bundle{
 const copy=structuredClone(bundle);copy.trajectories=copy.trajectories.filter(t=>t.plate!==plate);copy.events=copy.events.filter(e=>e.plate!==plate);delete copy.registry[plate];
 for(const id of Object.keys(copy.tracks)){const ids=new Set(copy.tracks[id].filter(t=>t.plate.text===plate).map(t=>t.track_id));copy.tracks[id]=copy.tracks[id].filter(t=>!ids.has(t.track_id));copy.analysis[id].frames.forEach(f=>{f.detections=f.detections.filter(d=>!ids.has(d.track_id));});}
 return copy;
}
export function purgeBundle(bundle:Bundle,at=Date.now()):Bundle{
 const copy=structuredClone(bundle),valid=(r:{expires_at:string})=>Date.parse(r.expires_at)>at;
 copy.manifest.clips=copy.manifest.clips.filter(valid);copy.events=copy.events.filter(valid);copy.trajectories=copy.trajectories.filter(valid).map(t=>({...t,stops:t.stops.filter(valid)})).filter(t=>t.stops.length);
 for(const id of Object.keys(copy.tracks)){if(!copy.manifest.clips.some(c=>c.id===id)){delete copy.tracks[id];delete copy.analysis[id];delete copy.counts[id];}else{copy.tracks[id]=copy.tracks[id].filter(valid);copy.analysis[id].frames.forEach(f=>{f.detections=f.detections.filter(d=>copy.tracks[id].some(t=>t.track_id===d.track_id));});}}
 return copy;
}
