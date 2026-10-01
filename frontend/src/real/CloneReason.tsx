import { useSession } from '../session';
import { useRealFootage } from './context';
import { maskPlate } from './SourceBadge';
import type { RealEvent } from './types';

export default function CloneReason({alert}:{alert:RealEvent}) {
 const {bundle}=useRealFootage(),{session}=useSession();
 const viewer=session?.user.role==='viewer';
 const clips=(alert.sightings||[]).map(s=>bundle?.manifest.clips.find(c=>c.id===s.clip_id));
 if(!alert.review_reasons?.length)return null;
 return <section className="clone-reason" aria-label="Reason for suspected plate cloning">
  <h3>Why this plate is flagged</h3>
  <p>Alert basis: same user-confirmed registration on visibly different vehicle bodies.</p>
  <ol>{alert.review_reasons.map(reason=><li key={reason.code}><strong>{reason.label}</strong><p>{reason.detail}</p></li>)}</ol>
  <div className="table-scroll"><table>
   <caption>Comparison of the two source recordings</caption>
   <thead><tr><th scope="col">Evidence</th>{clips.map((clip,i)=><th scope="col" key={alert.sightings![i].clip_id}>{clip?.evidence?.vehicle_label||alert.sightings![i].clip_id}</th>)}</tr></thead>
   <tbody>
    <tr><th scope="row">Confirmed registration</th>{clips.map((c,i)=><td key={i}>{c?.evidence?maskPlate(c.evidence.display_plate,viewer):'Not confirmed'}</td>)}</tr>
    <tr><th scope="row">Body type · manual review</th>{clips.map((c,i)=><td key={i}>{c?.evidence?.vehicle_class||'Not reviewed'}</td>)}</tr>
    <tr><th scope="row">Colour · manual review</th>{clips.map((c,i)=><td key={i}>{c?.evidence?.colour||'Not reviewed'}</td>)}</tr>
    <tr><th scope="row">Raw OCR · unchanged</th>{clips.map((c,i)=><td className="mono" key={i}>{c?.evidence?.ocr_text?maskPlate(c.evidence.ocr_text,viewer):'Abstained'}</td>)}</tr>
    <tr><th scope="row">OCR engine score</th>{clips.map((c,i)=><td key={i}>{c?.evidence?.ocr_confidence==null?'Not available':`${(c.evidence.ocr_confidence*100).toFixed(1)}%`}</td>)}</tr>
    <tr><th scope="row">Reviewed sighting in video</th>{clips.map((c,i)=><td key={i}>{c?.evidence?`${c.evidence.time_s.toFixed(2)} s · frame ${c.evidence.frame}`:'Not available'}</td>)}</tr>
    <tr><th scope="row">Original filename</th>{clips.map((c,i)=><td className="clone-filename" key={i}>{c?.evidence?.original_filename||'Not available'}</td>)}</tr>
   </tbody>
  </table></div>
  <h3>What still needs verification</h3>
  <ul>{alert.limitations?.map(text=><li key={text}>{text}</li>)}</ul>
 </section>;
}
