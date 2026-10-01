import RealWorkspace from '../real/RealWorkspace';
import LiveFeeds from '../real/LiveFeeds';
import { useRef, useState } from 'react';
import { Link } from '../router';
import { Maximize, Pause, Play } from 'lucide-react';
import { Badge, Page, PageHeader, Panel, Plate } from '../components/UI';
import SimulatedFeed from '../components/SimulatedFeed';
import { cameras, reads, cameraById } from '../demo/model';
import { useDemo } from '../demo/context';
import { useData } from '../data';
import { ProvenanceChip } from '../lib/provenance';
export default function Live(){const {region,tick,running,start,stop,elapsed}=useDemo(),d=useData(),[paused,setPaused]=useState(false),container=useRef<HTMLDivElement>(null);const scoped=cameras.filter(c=>region==='All Delhi'||c.region===region),offset=Math.floor(tick/10)%Math.max(1,scoped.length),selected=Array.from({length:4},(_,i)=>scoped[(offset+i)%scoped.length]),recent=reads.filter(r=>region==='All Delhi'||cameraById.get(r.camera_id)?.region===region),ticker=Array.from({length:10},(_,i)=>recent[(recent.length-1-Math.floor(tick/3)-i+recent.length*100)%recent.length]);
 const full=()=>{if(document.fullscreenElement)void document.exitFullscreen();else void container.current?.requestFullscreen().catch(()=>{});};
 return <div ref={container}><Page><PageHeader title="Live monitoring" description="Recorded camera feeds, playback measurements and historical plate observations." actions={<><button onClick={full}><Maximize size={15}/>Full screen</button><button className="primary" onClick={running?stop:start}>{running?<Pause size={15}/>:<Play size={15}/>} {running?`Stop scenario · ${elapsed}s`:'Run scenario'}</button><Link className="button" to="/camera-health">Camera Health Intelligence</Link></>}/><LiveFeeds/>
 <div className="two-columns mt-panel"><Panel title="Historical plate-read ticker" subtitle="Recorded observation times · rotating every 3 seconds" action={<ProvenanceChip source="modelled"/>}><div className="ticker-list" aria-live="off">{ticker.map((r,i)=>r&&<div key={i}><Plate value={r.plate}/><span>{cameraById.get(r.camera_id)?.name}</span><time>{new Date(r.timestamp).toLocaleTimeString('en-IN',{timeZone:'Asia/Kolkata',hour12:false})} IST</time></div>)}</div></Panel><Panel title="Latest scenario alerts" subtitle="Events for operator workflow review" action={<ProvenanceChip source="modelled"/>}><div className="padded">{d.alerts.slice(0,3).map(a=><div className="case-note" key={a.id}><Badge tone="amber">{a.kind}</Badge><p>{a.explanation}</p><Link className="text-link" to="/alerts">Review {a.plate} →</Link></div>)}</div></Panel></div>
 <details className="mt-panel"><summary>Additional sources</summary><RealWorkspace/><div className="filter-bar"><ProvenanceChip source="modelled"/><button onClick={()=>setPaused(!paused)}>{paused?'Resume feeds':'Pause feeds'}</button></div><div className="live-camera-grid">{selected.map((c,i)=><Panel key={c.id}><SimulatedFeed camera={c.id} plate={['DL01AB1234','RJ14CB2210','UP16AX9912','DL08CX9090'][i]} compact paused={paused}/><div className="feed-link"><ProvenanceChip source="modelled"/><Link to={`/trajectories?plate=${['DL01AB1234','RJ14CB2210','UP16AX9912','DL08CX9090'][i]}`}>Track plate →</Link></div></Panel>)}</div></details></Page></div>;
}
