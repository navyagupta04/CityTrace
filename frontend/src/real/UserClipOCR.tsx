import { useState } from 'react';
import { Panel,Badge } from '../components/UI';
import { useRealFootage } from './context';
import ClipEvidence from './ClipEvidence';
import { normalise } from '../demo/model';

export default function UserClipOCR(){
 const {bundle}=useRealFootage(),[id,setId]=useState('');
 const clips=bundle?.manifest.clips.filter(c=>c.evidence)||[],clip=clips.find(c=>c.id===id)||clips[0],e=clip?.evidence;
 if(!clip||!e)return null;
 const match=normalise(e.ocr_text)===normalise(e.plate);
 return <Panel title="OCR from your uploaded videos" subtitle="Actual offline recognition on manually selected plate crops" source="reviewed" className="mt-panel"><div className="padded"><label>Recording<select value={clip.id} onChange={event=>setId(event.target.value)}>{clips.map(c=><option key={c.id} value={c.id}>{c.evidence!.vehicle_label}</option>)}</select></label><div className="two-columns"><ClipEvidence clipId={clip.id}/><div className="ocr-readout"><Badge tone={match?'green':'amber'}>{match?'Exact agreement':'OCR correction needed'}</Badge><dl><dt>User-confirmed plate</dt><dd className="mono">{e.display_plate}</dd><dt>Raw engine output</dt><dd className="mono">{e.ocr_text||'Abstained'}</dd><dt>Engine confidence</dt><dd>{e.ocr_confidence==null?'Not available':`${(e.ocr_confidence*100).toFixed(1)}%`}</dd><dt>Engine</dt><dd>{e.ocr_engine}</dd></dl><p>Confidence is the engine’s score, not measured accuracy. The watchlist and clone case use your confirmed identity; they do not substitute it for the OCR output.</p><p>These reviewed examples are not a held-out benchmark and do not establish 90% accuracy. This plate is retained as supplied, without Indian-format substitutions.</p></div></div></div></Panel>;
}
