import type { Alert, Audit, Profile, Session, Watch } from '../types';
import { cameras, roads, vehicles, reads, trajectoryFor, corridorsAt, hourly, initialAlerts, fuzzyDistance, normalise } from './model';
import { REGIONS } from '../constants/city';

export const MOCK = (import.meta as ImportMeta & {env:Record<string,string>}).env.VITE_USE_MOCK !== 'false';
let session:Session|null=null;
export let alerts:Alert[]=structuredClone(initialAlerts);
let watchlist:Watch[]=['DL01AB1234','UP16AX9912','DL08CX9090'].map(plate=>({plate,reason:'Synthetic investigation DEMO-2026-001',created_at:'2026-09-24T04:00:00Z'}));
const notes=new Map<number,Profile['notes']>();
export const audit:Audit[]=[{id:1,timestamp:'2026-09-30T01:30:00Z',role:'admin',action:'demo.seed',details:JSON.stringify({message:'Deterministic Delhi dataset loaded',vehicles:vehicles.length,reads:reads.length})}];
export function record(action:string,details:Record<string,unknown>={}){audit.unshift({id:audit.length+1,timestamp:new Date().toISOString(),role:session?.user.role||'admin',action,details:JSON.stringify({user:session?.user.username||'demo',...details})});}
export function resetScenario(){alerts=structuredClone(initialAlerts);record('scenario.reset');}
export function scenarioAlert(stage:number){const base=initialAlerts[stage===1?1:0];const alert={...structuredClone(base),id:100+stage,plate:stage===1?'UP16AX9912':'DL08CX9090',timestamp:new Date().toISOString()};alerts=[alert,...alerts.filter(a=>a.id!==alert.id)];record('scenario.alert',{plate:alert.plate,kind:alert.kind});}
export const demoUsers=[{username:'admin',name:'Aditi Sharma',role:'admin' as const,unit:'All Delhi',password:'demo'},{username:'officer',name:'Arjun Mehra',role:'officer' as const,unit:'All Delhi',password:'demo'},{username:'viewer',name:'Nisha Rao',role:'viewer' as const,unit:'All Delhi',password:'demo'}];
function purpose(body:Record<string,unknown>){if(String(body.reason||'').trim().length<5)throw Error('A purpose and case reference are required.');}
export async function mockApi<T>(path:string,bodyValue?:unknown,method?:string,signal?:AbortSignal):Promise<T>{
 // Simulated transport latency is fixed so browser tests and demos stay repeatable.
 await new Promise<void>((resolve,reject)=>{if(signal?.aborted){reject(new DOMException('Aborted','AbortError'));return;}const abort=()=>{clearTimeout(timer);reject(new DOMException('Aborted','AbortError'));},timer=setTimeout(()=>{signal?.removeEventListener('abort',abort);resolve();},180);signal?.addEventListener('abort',abort,{once:true});});
 const url=new URL(path,'http://demo/'),p=url.pathname.slice(1),q=url.searchParams,b=(bodyValue||{}) as Record<string,unknown>;
 let result:unknown;
 if(p==='auth/config')result={demo:true,has_session:!!session,second_factor_supported:false,demo_users:demoUsers,units:['All Delhi',...REGIONS]};
 else if(p==='auth/login'){const user=demoUsers.find(u=>u.username===b.username)||demoUsers[0];session={access_token:'simulated-session',expires_in:900,user:{username:user.username,name:user.name,role:user.role,unit:String(b.unit||'All Delhi')}};record('auth.login',{mode:'Mock; no credentials validated'});result=session;}
 else if(p==='auth/refresh'){if(!session)throw Error('Demo session expired.');result=session;}
 else if(p==='auth/logout'){record('auth.logout');session=null;result={ok:true};}
 else {
 if(!session)throw Error('Sign in to the demo.');
 if(session.user.role==='viewer'&&!['cameras','analytics/summary','analytics/heatmap','analytics/origin-destination','integrity','users'].includes(p))throw Error('Officer access required.');
 const match=p.match(/^vehicles\/(\d+)\/(profile|owner|notes)$/);
 if(p==='cameras')result={cameras,roads};
 else if(p==='analytics/summary')result={summary:{detections:reads.length,plate_detections:reads.length,unidentified_passes:24,unique_vehicles:vehicles.length,active_cameras:39,network_average_speed_kmh:32.6,open_alerts:alerts.filter(a=>a.status!=='Closed').length,first_detection:reads[0].timestamp,last_detection:reads.at(-1)!.timestamp,speed_samples:reads.length-vehicles.length},corridors:corridorsAt(9),vehicles_per_minute:hourly.filter(h=>h.day===30).map(h=>({camera_id:'ALL',minute:new Date(`2026-09-30T${String(h.hour).padStart(2,'0')}:00:00+05:30`).toISOString(),count:h.count}))};
 else if(p==='analytics/heatmap')result=cameras.map(c=>({camera_id:c.id,name:c.name,lat:c.lat,lon:c.lon,count:reads.filter(r=>r.camera_id===c.id).length})).sort((a,b)=>b.count-a.count);
 else if(p==='analytics/origin-destination')result=vehicles.map(v=>{const own=reads.filter(r=>r.identity_id===v.id);return {origin:own[0].camera_id,destination:own.at(-1)!.camera_id,trips:1};}).reduce<{origin:string;destination:string;trips:number}[]>((acc,r)=>{const old=acc.find(x=>x.origin===r.origin&&x.destination===r.destination);if(old)old.trips++;else acc.push(r);return acc;},[]);
 else if(p==='integrity')result={valid:true,checked:reads.length,head:'DEMO-CHECKSUM-NOT-A-CRYPTOGRAPHIC-EVIDENCE-CHAIN'};
 else if(p==='alerts/workflow')result=alerts;
 else if(/^alerts\/\d+\/workflow$/.test(p)){const a=alerts.find(a=>a.id===Number(p.split('/')[1]));if(!a)throw Error('Alert not found');Object.assign(a,b);record('alert.action',{id:a.id,...b});result=a;}
 else if(p==='vehicles/search'){purpose(b);const query=normalise(String(b.query||'')),items=vehicles.map(v=>({...v,match_distance:!query||v.plate.includes(query)?0:fuzzyDistance(query,v.plate)})).filter(v=>v.match_distance<=2).sort((a,b)=>a.match_distance-b.match_distance||a.id-b.id);record('vehicle.search',{query,reason:b.reason});const page=Number(b.page||1);result={items:items.slice((page-1)*20,page*20),total:items.length};}
 else if(match){const id=Number(match[1]),v=vehicles.find(v=>v.id===id);if(!v)throw Error('Vehicle not found');purpose(b);
 if(match[2]==='notes'){const entries=notes.get(id)||[];entries.push({id:entries.length+1,username:session.user.username,timestamp:new Date().toISOString(),note:String(b.reason)});notes.set(id,entries);record('vehicle.note',{plate:v.plate});result={ok:true};}
 else if(match[2]==='owner'){record('owner.unmask',{plate:v.plate,reason:b.reason});result={name:'Demo Owner '+id,address:'Fictional residence, Delhi (synthetic)',contact:'+91 00000 00000'};}
 else{record('vehicle.profile',{plate:v.plate,reason:b.reason});result={identity:v,trajectory:trajectoryFor(id),confidence:v.confidence,watchlisted:watchlist.some(w=>w.plate===v.plate),integrity:{valid:true,checked:reads.length,head:'SIMULATED — no real evidence'},alerts:alerts.filter(a=>a.plate===v.plate),notes:notes.get(id)||[],registry:{provider:'Synthetic registry',demo:true,registration:{plate:v.plate,make:v.make,model:v.model,colour:v.colour,vehicle_class:v.vehicle_type,registered_at:'Delhi (mock)',insurance_until:'2027-04-30',fuel:'Petrol'},owner:{name:'Demo O***',address:'D***, Delhi (synthetic)',contact:'+91 ***** *****'},challans:[{number:'MOCK-'+id,timestamp:'2026-09-25T04:30:00Z',violation:'Synthetic parking event',location:'Connaught Place',amount:500,status:'Paid'}]},evidence:reads.filter(r=>r.identity_id===id).map(r=>({id:r.id,camera_id:r.camera_id,timestamp:r.timestamp,plate:r.plate,confidence:r.confidence,source:'simulator',reads:[{text:r.plate,confidence:r.confidence,quality:.95}],resolution:{method:'simulated',score:r.confidence,canonical_plate:r.plate}}))};}}
 else if(p==='attributes'){const anonymous=reads.slice(0,24).map(r=>({...r,id:10000+r.id,plate:null,identity_id:null,confidence:null}));const pool=q.get('plate_available')==='false'?anonymous:reads;const items=pool.filter(r=>(!q.get('vehicle_class')||r.vehicle_class===q.get('vehicle_class'))&&(!q.get('camera')||r.camera_id===q.get('camera'))&&(!q.get('colour')||r.colour===q.get('colour'))&&(!q.get('region')||cameras.find(c=>c.id===r.camera_id)?.region===q.get('region'))&&(!q.get('make')||vehicles.find(v=>v.id===r.identity_id)?.make===q.get('make'))&&(r.confidence||0)>=Number(q.get('min_confidence')||0)).sort((a,b)=>b.timestamp.localeCompare(a.timestamp));record('attribute.search',Object.fromEntries(q));result={items:items.slice(0,100),total:items.length};}
 else if(p==='watchlist'){if(bodyValue){const plate=normalise(String(b.plate||''));if(!/^([A-Z]{2}\d{2}[A-Z]{1,3}\d{4}|\d{2}BH\d{4}[A-Z]{2})$/.test(plate))throw Error('Enter a valid Indian plate format.');watchlist=[...watchlist.filter(w=>w.plate!==plate),{plate,reason:String(b.reason),created_at:new Date().toISOString()}];record('watchlist.add',{plate,reason:b.reason});}result=watchlist;}
 else if(p.startsWith('watchlist/')&&method==='DELETE'){watchlist=watchlist.filter(w=>w.plate!==decodeURIComponent(p.slice(10)));record('watchlist.remove',{plate:p.slice(10)});result={ok:true};}
 else if(p==='audit')result=audit;
 else if(p==='users')result=demoUsers;
 else if(p==='simulate'){resetScenario();result={example_plate:'DL01AB1234'};}
 else if(p==='video/samples')result=[{name:'car-detection.mp4',title:'Recorded road traffic · cars',license:'Intel / CC BY 4.0 · source location not Delhi',url:'/videos/car-detection.mp4'},{name:'person-bicycle-car-detection.mp4',title:'Recorded surveillance · mixed traffic',license:'Intel / CC BY 4.0 · source location not Delhi',url:'/videos/person-bicycle-car-detection.mp4'}];
 else if(p==='ocr/vote'){const rows=b.reads as {text:string;confidence:number;quality:number}[];const votes=new Map<string,number>();for(const r of rows){const plate=normalise(r.text).replace(/^DLO/,'DL0');votes.set(plate,(votes.get(plate)||0)+r.confidence*r.quality);}const plate=[...votes].sort((a,b)=>b[1]-a[1])[0]?.[0]||'';result={plate,confidence:.96,valid:/^[A-Z]{2}\d{2}[A-Z]{1,3}\d{4}$/.test(plate),format:'Simulated Indian private',reads:rows.map(r=>({...r,normalized:normalise(r.text).replace(/^DLO/,'DL0')}))};record('ocr.demo_vote',{plate});}
 else throw Error('This operation is not implemented in the mock adapter.');
 }
 return structuredClone(result) as T;
}
