import { useRealFootage } from './context';
import { cameraById } from '../demo/model';
import { Panel,Empty } from '../components/UI';
import ClipEvidence from './ClipEvidence';

export default function RealAttributes({filters}:{filters:{kind:string;colour:string;make:string;region:string;camera:string;confidence:number;availability:string}}){
 const {bundle}=useRealFootage();
 const matches=bundle?.manifest.clips.filter(c=>{const e=c.evidence;return e&&(!filters.kind||e.vehicle_class===filters.kind)&&(!filters.colour||e.colour.toLowerCase()===filters.colour.toLowerCase())&&(!filters.make||e.make===filters.make)&&(!filters.region||cameraById.get(c.camera_id)?.region===filters.region)&&(!filters.camera||c.camera_id===filters.camera)&&filters.availability==='available'&&filters.confidence===0;})||[];
 return <Panel title={`Uploaded video results · ${matches.length}`} subtitle="Reviewed appearance attributes · user-confirmed plates · locations staged for testing" className="mt-panel"><div className="padded">{matches.length?<div className="two-evidence-grid">{matches.map(c=><div key={c.id}><p>{c.evidence!.colour} · {c.evidence!.vehicle_class} · {c.evidence!.make} · {cameraById.get(c.camera_id)?.region}</p><ClipEvidence clipId={c.id}/></div>)}</div>:<Empty title="No uploaded clips match these filters" message={filters.confidence>0?'Reviewed annotations have no model confidence score. Set minimum confidence to 0% to include them.':'Clear filters to see both supplied recordings, or try Blue + Van or Black + Car.'}/>}</div></Panel>;
}
