import {useState} from 'react';
import {Link} from '../../router';
import {cameras} from '../../demo/model';
import {ProvenanceChip} from '../../lib/provenance';
import {ocrRequest,type OCRJob} from '../LiveOCRRun/ocrLiveApi';
import type {Upload} from '../LiveOCRRun/Evidence';
import {liveCaseStore,type LiveCase,type Placement} from './LiveCaseStore';

export default function PlaceOnMap({job,uploads,initialPlacements}:{job:OCRJob;uploads:Upload[];initialPlacements:Placement[]}){
 const readable=job.files.filter(f=>[...f.plates,...f.tracks].some(p=>p.status==='read'&&p.voted));
 const [edits,setEdits]=useState<Record<string,Placement>>({}),[created,setCreated]=useState<LiveCase[]>([]),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const placement=(file:string):Placement=>edits[file]||initialPlacements.find(p=>p.file===file)||{file,camera_id:'C01',ts_ist:'2026-09-30T10:12:05+05:30',staged:true,generated:false};
 const change=(file:string,value:Partial<Placement>)=>setEdits(old=>({...old,[file]:{...placement(file),...value}}));
 async function create(){setBusy(true);setError('');try{const {cases}=await ocrRequest<{cases:LiveCase[]}>(`jobs/${job.job_id}/trajectories`,{placements:readable.map(f=>placement(f.file))});liveCaseStore.add(cases,uploads);setCreated(cases);if(!cases.length)setError('No accepted plate reads to place.');}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 if(job.state!=='done'||!readable.length)return null;
 return <section className="live-placement"><h3>Place on map</h3><p>Group accepted reads of the same plate across clips using the placements below.</p><datalist id="live-case-cameras">{cameras.map(c=><option key={c.id} value={c.id}>{c.name} · {c.lat.toFixed(6)}, {c.lon.toFixed(6)}</option>)}</datalist>{readable.map(f=>{const p=placement(f.file),camera=cameras.find(c=>c.id===p.camera_id);return <div className="placement-row" key={f.file}><strong>{f.file}</strong><label>Camera node<input list="live-case-cameras" value={p.camera_id} aria-label={`Camera ${f.file}`} onChange={e=>change(f.file,{camera_id:e.target.value})}/><small>{camera?`${camera.name} · ${camera.lat.toFixed(6)}, ${camera.lon.toFixed(6)}`:'Choose an existing node'}</small></label><label>IST date and time<input type="datetime-local" step="1" value={p.ts_ist.replace('+05:30','')} aria-label={`IST time ${f.file}`} onChange={e=>change(f.file,{ts_ist:e.target.value+'+05:30'})}/></label><label><input type="checkbox" checked={p.staged} onChange={e=>change(f.file,{staged:e.target.checked})}/>Staged placement</label>{p.staged&&<ProvenanceChip source="staged"/>}{p.generated&&<ProvenanceChip source="generated"/>}</div>;})}<button className="primary" disabled={busy||readable.some(f=>!cameras.some(c=>c.id===placement(f.file).camera_id)||!Number.isFinite(Date.parse(placement(f.file).ts_ist)))} onClick={()=>void create()}>{busy?'Creating…':'Create trajectory'}</button>{error&&<p role="alert">{error}</p>}{created.map(c=><p key={c.id} role="status">{c.stops.length<2?'One sighting: a trajectory needs at least two':`${c.stops.length} sightings grouped by the voted plate`}. <Link to={`/trajectories?live_case=${c.id}`}>Open in Plate Trajectory</Link></p>)}</section>;
}
