import { Panel } from '../components/UI';
import { Link } from '../router';
import { useRealFootage } from './context';

export default function UserWatchlist(){
 const {bundle}=useRealFootage();
 const hits=bundle?.events.filter(e=>e.type==='blacklist_match'&&e.identity_source==='user_confirmed')||[];
 if(!hits.length)return null;
 return <Panel title="Uploaded footage test watchlist" subtitle="User-requested local case · independent of external blacklist services" className="mt-panel"><div className="padded"><strong className="mono">AI 0720-4</strong><p>{hits.length} matched recordings using the user-confirmed identity. Review the video and plate crops before accepting a match.</p><Link className="button primary" to="/alerts">Open video alerts</Link></div></Panel>;
}
