import { useEffect,useState } from 'react';
import { Panel,Modal,Badge } from '../components/UI';
import { useRealFootage } from './context';
import RealVideo from './RealVideo';
import ClipEvidence from './ClipEvidence';
import CloneReason from './CloneReason';
import SourceBadge,{maskPlate} from './SourceBadge';
import { useSession } from '../session';
import { record } from '../demo/api';
import type { RealEvent } from './types';

export default function RealAlerts(){
 const {bundle,workflow,setWorkflow}=useRealFootage(),{session}=useSession();
 const [selected,setSelected]=useState<RealEvent|null>(null),[draft,setDraft]=useState({status:'Open',assignee:'',note:''}),[running,setRunning]=useState(false),[step,setStep]=useState(0);
 const events=[...(bundle?.events||[])].sort((a,b)=>Number(b.type==='clone_suspect')-Number(a.type==='clone_suspect'));
 const viewer=session?.user.role==='viewer';
 const displayPlate=(plate:string)=>maskPlate(plate==='AI07204'?'AI 0720-4':plate,viewer);
 useEffect(()=>{if(!running||!events.length)return;const timer=setInterval(()=>setStep(i=>{if(i>=events.length-1){setRunning(false);return i;}return i+1;}),3000);return()=>clearInterval(timer);},[running,events.length]);
 if(!events.length)return null;
 function openAlert(alert:RealEvent){
  setDraft(workflow[alert.id]||{status:'Open',assignee:'',note:''});setSelected(alert);
  record('real.alert.evidence_viewed',{id:alert.id,clip_ids:(alert.sightings||[alert]).map(s=>s.clip_id)});
 }
 return <Panel title="Video evidence cases" subtitle={`${events.length} alerts · test watchlist matches and duplicate-plate review`} className="mt-panel" action={<button onClick={()=>{setStep(0);setRunning(!running);}}>{running?'Stop replay':'Replay case alerts'}</button>}>
  <div className="padded video-case-cards">{(running?events.slice(0,step+1):events).map(alert=><article className="video-case-card" key={alert.id}>
   <SourceBadge staged={alert.staged} reviewed={alert.identity_source==='user_confirmed'} generated={alert.generated}/>
   <h3>{alert.type==='clone_suspect'?'Suspected cloned plate':'Test blacklist match'} · {displayPlate(alert.plate)}</h3>
   <p>{alert.type==='clone_suspect'?(alert.basis==='appearance_mismatch'?'Blue van vs new dark sedan · same confirmed registration, different body structure':'Two vehicles · two recordings · compare the evidence'):`${bundle?.manifest.clips.find(c=>c.id===alert.clip_id)?.evidence?.vehicle_label||alert.clip_id} · user-requested test watchlist`}</p>
   <Badge>{workflow[alert.id]?.status||'Open'}</Badge>
   <button className="primary" onClick={()=>openAlert(alert)}>{alert.type==='clone_suspect'?'Review both vehicles':'Review blacklist evidence'}</button>
  </article>)}</div>
  {selected&&<Modal title={selected.type==='clone_suspect'?`Cloned plate review · ${displayPlate(selected.plate)}`:'Blacklist evidence review'} onClose={()=>setSelected(null)}>
   <div className="spread"><Badge tone="amber">Human review required</Badge><button onClick={()=>setSelected(null)}>Close evidence</button></div>
   <SourceBadge staged={selected.staged} reviewed={selected.identity_source==='user_confirmed'} generated={selected.generated}/>
   <p className="real-notice">{viewer?selected.explanation.replaceAll(selected.plate,displayPlate(selected.plate)).replaceAll('AI 0720-4',displayPlate(selected.plate)):selected.explanation}</p>
   {selected.type==='clone_suspect'&&<CloneReason alert={selected}/>}
   <div className="two-evidence-grid">{(selected.sightings||[selected]).map(s=>bundle?.manifest.clips.find(c=>c.id===s.clip_id)?.evidence?<ClipEvidence key={s.clip_id} clipId={s.clip_id}/>:<RealVideo key={s.clip_id} clipId={s.clip_id} seek={s.video_time_s} trackId={s.track_id}/>)}</div>
   {selected.distance_km!=null&&<p>{selected.distance_km.toFixed(2)} km · {selected.implied_kmh?.toFixed(1)} km/h implied by assigned times. Placements may be illustrative.</p>}
   <form className="form-stack" onSubmit={e=>{e.preventDefault();setWorkflow(w=>({...w,[selected.id]:draft}));record('real.alert.workflow',{id:selected.id,...draft});setSelected(null);}}>
    <label>Status<select value={draft.status} onChange={e=>setDraft({...draft,status:e.target.value})}>{['Open','Acknowledged','Verified','Dispatched','Closed','False Positive'].map(s=><option key={s}>{s}</option>)}</select></label>
    <label>Assignee<input value={draft.assignee} onChange={e=>setDraft({...draft,assignee:e.target.value})}/></label>
    <label>Review note<textarea value={draft.note} onChange={e=>setDraft({...draft,note:e.target.value})}/></label>
    <button className="primary">Save review</button>
   </form>
  </Modal>}
 </Panel>;
}
