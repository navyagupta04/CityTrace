import { useSession } from '../session';
import { useRealFootage } from './context';
import { Link } from '../router';
import RealVideo from './RealVideo';
import { maskPlate } from './SourceBadge';

export default function ClipEvidence({clipId,video=true,trajectory=true}:{clipId:string;video?:boolean;trajectory?:boolean}){
 const {bundle}=useRealFootage(),{session}=useSession();
 const clip=bundle?.manifest.clips.find(c=>c.id===clipId),e=clip?.evidence,viewer=session?.user.role==='viewer';
 if(!clip||!e)return null;
 return <article className="clip-evidence"><h3>{e.vehicle_label}</h3>{video&&<RealVideo clipId={clipId} seek={e.time_s}/>}<div className="evidence-crop-row">{viewer?<p>Plate crop restricted for viewer role.</p>:e.crop?<img src={`/real/${e.crop}`} alt={`Source plate crop from ${e.vehicle_label}, frame ${e.frame}`} loading="lazy"/>:<p>Review the plate in the video at {e.time_s.toFixed(2)} s. No crop stored.</p>}<div><strong className="mono">{maskPlate(e.display_plate,viewer)}</strong><p>User-confirmed identity · frame {e.frame} · {e.time_s.toFixed(2)} s</p>{e.crop&&<small>Crop extracted from the source frame.</small>}</div></div><dl className="clip-evidence-metadata"><dt>Visible appearance · manual review</dt><dd>{e.colour} · {e.vehicle_class}</dd><dt>Raw OCR · unchanged</dt><dd className="mono">{e.ocr_text?maskPlate(e.ocr_text,viewer):'Abstained'}</dd><dt>OCR engine score</dt><dd>{e.ocr_confidence==null?'Not available':`${(e.ocr_confidence*100).toFixed(1)}%`} · not a cloning probability</dd><dt>Source filename</dt><dd>{e.original_filename}</dd></dl>{trajectory&&<Link className="button primary" to={`/trajectories?plate=${e.plate}&clip=${clipId}`}>Track {e.vehicle_label.toLowerCase()}</Link>}</article>;
}
