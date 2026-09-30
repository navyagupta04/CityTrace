import { useSession } from '../session';
import { useRealFootage } from './context';
import { Link } from '../router';
import RealVideo from './RealVideo';
import { maskPlate } from './SourceBadge';

export default function ClipEvidence({clipId,video=true,trajectory=true}:{clipId:string;video?:boolean;trajectory?:boolean}){
 const {bundle}=useRealFootage(),{session}=useSession();
 const clip=bundle?.manifest.clips.find(c=>c.id===clipId),e=clip?.evidence,viewer=session?.user.role==='viewer';
 if(!clip||!e)return null;
 return <article className="clip-evidence"><h3>{e.vehicle_label}</h3>{video&&<RealVideo clipId={clipId} seek={e.time_s}/>}<div className="evidence-crop-row">{viewer?<p>Plate crop restricted for viewer role.</p>:<img src={`/real/${e.crop}`} alt={`Actual plate crop from ${e.vehicle_label}, frame ${e.frame}`} loading="lazy"/>}<div><strong className="mono">{maskPlate(e.display_plate,viewer)}</strong><p>User-confirmed identity · frame {e.frame} · {e.time_s.toFixed(2)} s</p><small>Crop extracted from this video; no plate text was generated.</small></div></div>{trajectory&&<Link className="button primary" to={`/trajectories?plate=${e.plate}&clip=${clipId}`}>Track {e.vehicle_label.toLowerCase()}</Link>}</article>;
}
