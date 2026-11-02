import {useState} from 'react';
import NetworkMap from '../components/NetworkMap';
import {Panel} from '../components/UI';
import {cameras,roads} from '../demo/model';
import type {Trajectory} from '../types';

const stagedCameras=[
 {id:'CAM-PN-01',name:'Patel Nagar (approximate staged placement)',lat:28.645,lon:77.170,restricted:false},
 {id:'CAM-MN-01',name:'Moti Nagar (approximate staged placement)',lat:28.658,lon:77.142,restricted:false},
];
const mapCameras=[...cameras,...stagedCameras];
const mapRoads=[...roads,{from:'CAM-PN-01',to:'CAM-MN-01',distance_km:3.2,free_flow_kmh:35}];
const ist=(value:string)=>new Intl.DateTimeFormat('en-IN',{dateStyle:'medium',timeStyle:'medium',timeZone:'Asia/Kolkata'}).format(new Date(value));

export default function DatabaseTrajectory({trajectory}:{trajectory:Trajectory}){
 const [selected,setSelected]=useState(0),hop=trajectory.hops[selected];
 if(!hop)return null;
 const duration=trajectory.hops.length>1?(Date.parse(trajectory.hops.at(-1)!.timestamp)-Date.parse(trajectory.hops[0].timestamp))/60000:0;
 return <section className="mt-panel">
  <div className="real-notice">Database-backed sightings · real video footage · OCR is model-estimated · camera placements and timestamps are staged/illustrative.</div>
  <div className="journey-stats">{[['Sightings',trajectory.hops.length],['Route distance',`${trajectory.total_distance_km} km`],['Time between first and last',`${Math.round(duration)} min`],['Plate',trajectory.plate]].map(([name,value])=><div key={name}><small>{name}</small><strong>{value}</strong></div>)}</div>
  <div className="trajectory-layout">
   <Panel title="Patel Nagar → Moti Nagar" subtitle="Observed detections from the SQLite system of record; staged placements shown as approximate">
    <NetworkMap cameras={mapCameras} roads={mapRoads} trajectory={trajectory} progress={1} large region="All Delhi"/>
   </Panel>
   <Panel title="Video sightings" subtitle="Select a recorded sighting to inspect its OCR evidence">
    <div className="journey-timeline">{trajectory.hops.map((item,index)=><button type="button" className={`timeline-stop ${index===selected?'active':''}`} key={item.detection_id} onClick={()=>setSelected(index)}>
     <span className="stop-index">{index+1}</span><div><time>{ist(item.timestamp)} IST</time><strong>{item.camera_name}</strong><small>{item.camera_id} · {(item.confidence*100).toFixed(1)}% model confidence</small><small>{item.video_file||'Video source recorded'}</small><small>Staged location and time · real footage</small>
     {index>0&&<small>{item.leg_distance_km} km · {Math.round((item.seconds||0)/60)} min · {item.speed_kmh} km/h estimated</small>}
    </div></button>)}</div>
   </Panel>
  </div>
  <Panel title={`OCR evidence · ${hop.camera_name}`} className="mt-panel"><div className="padded evidence-grid">
   <div><strong>{hop.video_file||'Source video'}</strong><p>{hop.evidence_frame==null?'Evidence frame not recorded':`Frame ${hop.evidence_frame} · ${Number(hop.evidence_time_s||0).toFixed(3)} seconds`}</p><p>{hop.provenance||'real footage, OCR (model-estimated), staged camera placement'}</p>{hop.evidence_crop&&<img src={hop.evidence_crop} alt={`OCR plate crop from ${hop.video_file||hop.camera_id}`} style={{maxWidth:'100%',width:320,maxHeight:180,objectFit:'contain',background:'#fff',padding:8,borderRadius:4}}/>}</div>
   <div><h3>Frame candidates</h3>{hop.candidate_reads?.length?<div className="table-scroll"><table><thead><tr><th>Frame</th><th>Time</th><th>Read</th><th>Confidence</th></tr></thead><tbody>{hop.candidate_reads.map((candidate,index)=><tr key={`${candidate.frame}-${index}`}><td>{candidate.frame}</td><td>{Number(candidate.time_s||0).toFixed(3)} s</td><td className="mono">{candidate.text||candidate.normalised}</td><td>{(Number(candidate.confidence||0)*100).toFixed(1)}%</td></tr>)}</tbody></table></div>:<p>Per-frame candidates were not stored for this sighting.</p>}</div>
  </div></Panel>
 </section>;
}
