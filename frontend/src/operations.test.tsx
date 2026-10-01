import {liveCaseStore,type LiveCase,caseGeoJSON} from './real/LiveCases/LiveCaseStore';
import PlaceOnMap from './real/LiveCases/PlaceOnMap';
import LiveCaseJourney from './real/LiveCases/LiveCaseJourney';
// @vitest-environment jsdom
import { act,type ReactNode } from 'react';
import { createRoot,type Root } from 'react-dom/client';
import { beforeEach,afterEach,describe,it,expect,vi } from 'vitest';
import { StrictMode } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { cameraHealth } from './lib/cameraHealth';
import { exportJob,jobCSV,parseLabelsCSV } from './real/LiveOCRRun/export';
import AccuracyPanel from './real/LiveOCRRun/AccuracyPanel';
import LiveOCRRun,{ResultTable} from './real/LiveOCRRun/LiveOCRRun';
import type { OCRJob } from './real/LiveOCRRun/ocrLiveApi';
import { ocrRequest } from './real/LiveOCRRun/ocrLiveApi';
import LiveFeeds from './real/LiveFeeds';
import { liveFeeds } from './real/liveFeeds.config';
import NetworkMap,{project} from './components/NetworkMap';
import { HashRouter } from './router';
import { cameras,roads,reads,initialAlerts,densityAt } from './demo/model';
import Overview from './pages/Overview';
import Traffic from './pages/Traffic';
import Live from './pages/Live';
import CameraHealth from './pages/CameraHealth';
import Attributes from './pages/Attributes';
import Search from './pages/Search';
import Profile from './pages/Profile';
import SignIn from './pages/SignIn';
import Video from './pages/Video';
import Trajectory from './pages/Trajectory';
import Privacy from './real/Privacy';
import { MapPage,AnalyticsPage,AlertsPage,WatchlistPage,AttributesPage,OCRPage,AuditPage,Administration } from './pages/Intelligence';
const session={user:{username:'officer',name:'Officer One',role:'officer',unit:'Central District'}};
vi.mock('./session',()=>({useSession:()=>({session,config:{demo:true,units:['Central District'],demo_users:[]},login:vi.fn()})}));
vi.mock('./demo/context',()=>({useDemo:()=>({region:'All Delhi',setRegion:vi.fn(),tick:0,start:vi.fn(),stop:vi.fn()})}));
vi.mock('./data',()=>({useData:()=>({cameras,roads,alerts:initialAlerts,density:densityAt(9),analytics:{summary:{detections:reads.length},corridors:[],vehicles_per_minute:[]},od:[],reload:vi.fn(),integrity:{valid:true,checked:0}})}));
vi.mock('./real/context',()=>({useRealFootage:()=>({bundle:null,workflow:{},audit:[],erased:[],purge:vi.fn(),erase:vi.fn()})}));
vi.mock('./api',()=>({getToken:()=>'',api:vi.fn(async()=>[]),authenticatedBlob:vi.fn()}));
vi.mock('./real/LiveOCRRun/ocrLiveApi',async importOriginal=>({...await importOriginal<object>(),ocrRequest:vi.fn()}));
let host:HTMLDivElement,root:Root;
beforeEach(()=>{Object.assign(globalThis,{IS_REACT_ACT_ENVIRONMENT:true});vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:false,status:404,headers:new Headers()}));vi.stubGlobal('IntersectionObserver',class{constructor(private callback:(entries:{isIntersecting:boolean}[])=>void){}observe(){this.callback([{isIntersecting:true}]);}disconnect(){}});vi.stubGlobal('ResizeObserver',class{observe(){}unobserve(){}disconnect(){}});window.matchMedia=vi.fn().mockReturnValue({matches:true,addListener(){},removeListener(){},addEventListener(){},removeEventListener(){}});vi.spyOn(HTMLMediaElement.prototype,'play').mockResolvedValue();vi.spyOn(HTMLMediaElement.prototype,'pause').mockImplementation(()=>{});vi.spyOn(HTMLMediaElement.prototype,'load').mockImplementation(()=>{});vi.spyOn(HTMLCanvasElement.prototype,'getContext').mockReturnValue(null);vi.mocked(ocrRequest).mockRejectedValue(Error('Backend unreachable'));host=document.createElement('div');document.body.append(host);root=createRoot(host);});
afterEach(async()=>{session.user.role='officer';liveCaseStore.clear();await act(async()=>root.unmount());host.remove();vi.restoreAllMocks();vi.unstubAllGlobals();});
const render=async(node:ReactNode)=>{await act(async()=>root.render(node));};
const click=async(text:string)=>{const button=[...host.querySelectorAll('button')].find(b=>b.textContent===text);expect(button).toBeTruthy();await act(async()=>button!.click());};
const fixture:OCRJob={job_id:'fixture',state:'done',stage:'complete',progress:100,engine:'Fixture',engine_version:'test only',device:'CPU',duration_ms:20,purged:true,files:[{file:'fixture.png',sha256:'test',type:'image',mode_used:'crop',duration_ms:20,status:'read',tracks:[],plates:[{track_id:null,box:null,raw:'DLO1AB1234',normalised:'DL01AB1234',voted:'DL01AB1234',format_valid:true,format:'standard',ocr_confidence:.9,vote_confidence:.85,n_reads:1,status:'read',expected:'DL01AB1234',exact_match:true,cer:0},{track_id:2,box:null,raw:'',normalised:'',voted:null,format_valid:false,format:'unknown',ocr_confidence:0,vote_confidence:0,n_reads:0,status:'abstain'}]}],metrics:{n_scored:1,blind:true,verdict:'Inconclusive: too few labelled samples (N = 1)',plate_accuracy_all:{value:1,n:1,correct:1,ci95:[.2065,1]},cer:0,coverage:1,selective_accuracy:{value:1,n:1,correct:1,ci95:[.2065,1]},coverage_curve:[],reliability:[],error_cases:[]}};

describe('live OCR UI and health',()=>{
 it('computes health by documented weights and never fills missing measurements',()=>{const ideal={signal:true,fps:25,latency:0,brightness:128,sharpness:250,readRate:1};expect(cameraHealth(ideal).total).toBe(100);expect(cameraHealth({...ideal,signal:false}).status).toBe('Offline');const half=cameraHealth({signal:true,fps:12.5,latency:500,brightness:64,sharpness:125,readRate:.5});expect(half.total).toBe(65);expect(half.status).toBe('Degraded');expect(cameraHealth({...ideal,readRate:null}).total).toBeNull();});
 it('shows unavailable without fabricated results when backend is down',async()=>{await render(<LiveOCRRun/>);expect(host.textContent).toContain('Unavailable');expect(host.textContent).toContain('Backend unreachable');expect(host.querySelector('table')).toBeNull();expect([...host.querySelectorAll('button')].find(b=>b.textContent==='Run OCR pipeline')?.disabled).toBe(true);});
 it('renders mixed read and abstain rows',async()=>{await render(<ResultTable job={fixture} uploads={[]} labels={{}} onLabel={()=>{}}/>);expect(host.textContent).toContain('DL01AB1234');expect(host.textContent).toContain('abstain');expect(host.textContent).toContain('Not scored');});
 it('renders verdict, Wilson interval, source and post-hoc note',()=>{const html=renderToStaticMarkup(<AccuracyPanel metrics={{...fixture.metrics,blind:false}}/>);expect(html).toContain('LIVE RUN (this upload)');expect(html).toContain('95% Wilson');expect(html).toContain('Labels entered after viewing results, not blind');expect(html).toContain('N = 1');});
 it('exports BOM CSV, safe formulas and role-masked plate text',()=>{expect(jobCSV(fixture,true).charCodeAt(0)).toBe(0xfeff);expect(jobCSV(fixture,true)).toContain('DL01AB1234');expect(JSON.stringify(exportJob(fixture,false))).not.toContain('DL01AB1234');expect(jobCSV(fixture,false)).not.toContain('DLO1AB1234');expect(parseLabelsCSV('filename,plate\n"a,b.png","DL01AB1234"')).toEqual({'a,b.png':'DL01AB1234'});});
 it('renders N videos, handles a missing video, pauses all and locates a camera',async()=>{await render(<LiveFeeds feeds={liveFeeds.slice(0,3)}/>);expect(host.querySelectorAll('video')).toHaveLength(3);expect(host.querySelector('a')?.getAttribute('href')).toBe('/#/map?camera=C01&focus=1');await act(async()=>host.querySelector('video')!.dispatchEvent(new Event('error')));expect(host.textContent).toContain('Video unavailable');vi.mocked(HTMLMediaElement.prototype.pause).mockClear();await click('Pause all');for(const video of host.querySelectorAll('video'))expect(vi.mocked(HTMLMediaElement.prototype.pause).mock.contexts).toContain(video);});
 it('keeps video sources after StrictMode cleanup and remount',async()=>{await render(<StrictMode><LiveFeeds feeds={liveFeeds.slice(0,2)}/></StrictMode>);for(const video of host.querySelectorAll('video'))expect(video.getAttribute('src')).toMatch(/^\/videos\/live\//);});
 it('polls real job progress and recomputes post-run labels',async()=>{
  let polls=0;
  vi.mocked(ocrRequest).mockImplementation(async(path,body)=>{
   if(path==='status')return {available:true,engine:'test fixture',engine_version:'1',device:'CPU',reasons_if_unavailable:[]};
   if(path==='jobs')return {job_id:'fixture'};
   if(path.endsWith('/labels')){expect(body).toHaveProperty('expected');return {...fixture,metrics:{...fixture.metrics,blind:false}};}
   return polls++?fixture:{...fixture,state:'running',stage:'fixture.png: OCR',progress:42,files:[]};
  });
  vi.stubGlobal('URL',Object.assign(URL,{createObjectURL:()=> 'blob:test',revokeObjectURL:vi.fn()}));
  await render(<LiveOCRRun/>);
  const file=host.querySelector<HTMLInputElement>('input[type=file]')!;
  Object.defineProperty(file,'files',{value:[new File(['test fixture'],'fixture.png',{type:'image/png'})]});
  await act(async()=>file.dispatchEvent(new Event('change',{bubbles:true})));
  const purpose=[...host.querySelectorAll('label')].find(n=>n.textContent==='Purpose (required)')!.querySelector('input')!;
  await act(async()=>{Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')!.set!.call(purpose,'test purpose');purpose.dispatchEvent(new Event('input',{bubbles:true}));});
  await click('Run OCR pipeline');
  expect(host.textContent).toContain('fixture.png: OCR');expect(host.querySelector('progress')?.value).toBe(42);
  await act(async()=>{await new Promise(resolve=>setTimeout(resolve,800));});
  expect(host.textContent).toContain('done');
  await click('Save labels and recompute (not blind)');
  expect(host.textContent).toContain('Labels entered after viewing results, not blind');
 });
 it('focuses the existing map on a camera and allows reset',async()=>{await render(<NetworkMap cameras={cameras} roads={roads} focusCamera="C02"/>);const [x,y]=project(cameras[1].lon,cameras[1].lat);const view=host.querySelector('svg')!.getAttribute('viewBox')!.split(' ').map(Number);expect(view[0]+view[2]/2).toBeCloseTo(x);expect(view[1]+view[3]/2).toBeCloseTo(y);expect(view[2]).toBeLessThan(840);await act(async()=>host.querySelector<HTMLButtonElement>('[aria-label="Reset map view"]')!.click());expect(host.querySelector('svg')!.getAttribute('viewBox')).toBe('0 0 840 900');});
 it('preserves Locate focus when the parent resets an earlier region, then allows manual region control',async()=>{await render(<NetworkMap cameras={cameras} roads={roads} focusCamera="C02" region="South Delhi"/>);await render(<NetworkMap cameras={cameras} roads={roads} focusCamera="C02" region="All Delhi"/>);const [x,y]=project(cameras[1].lon,cameras[1].lat),view=host.querySelector('svg')!.getAttribute('viewBox')!.split(' ').map(Number);expect(view[0]+view[2]/2).toBeCloseTo(x);expect(view[1]+view[3]/2).toBeCloseTo(y);const select=host.querySelector<HTMLSelectElement>('[aria-label="Map region"]')!;await act(async()=>{select.value='South Delhi';select.dispatchEvent(new Event('change',{bubbles:true}));});await render(<NetworkMap cameras={cameras} roads={roads} focusCamera="C02" region="South Delhi"/>);expect(host.querySelector('.camera-selected')).toBeNull();});
 it('reads the Locate URL parameter and handles unknown cameras',async()=>{window.location.hash='/map?camera=C03&focus=1';await render(<HashRouter><MapPage/></HashRouter>);const [x,y]=project(cameras[2].lon,cameras[2].lat),view=host.querySelector('svg')!.getAttribute('viewBox')!.split(' ').map(Number);expect(view[0]+view[2]/2).toBeCloseTo(x);expect(view[1]+view[3]/2).toBeCloseTo(y);expect(host.textContent).toContain('Back to Camera Health');await render(<NetworkMap cameras={cameras} roads={roads} focusCamera="unknown"/>);expect(host.textContent).toContain('Unknown camera ID');expect(host.querySelector('svg')!.getAttribute('viewBox')).toBe('0 0 840 900');window.location.hash='/';});
 it('retains OCR sections and removes only the density footage tab',async()=>{await render(<OCRPage/>);for(const text of ['Run OCR pipeline on your own image or video','Measured on real footage','Reference benchmark','Plate evidence','Multi-frame voting','Human-review queue'])expect(host.textContent).toContain(text);await render(<Traffic/>);expect([...host.querySelectorAll('[role=tab]')].map(n=>n.textContent)).toEqual(['Density heatmap','Origin–Destination','Congestion hotspots','Trends','Deep dive']);});
});

describe('plain OCR and two-clip live cases',()=>{
 const setValue=async(input:HTMLInputElement,value:string)=>{await act(async()=>{Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')!.set!.call(input,value);input.dispatchEvent(new Event('input',{bubbles:true}));});};
 const purpose=()=>[...host.querySelectorAll('label')].find(n=>n.textContent==='Purpose (required)')!.querySelector('input')!;
 const unscored:OCRJob={...fixture,scored:false,metrics:{scored:false},files:fixture.files.map(f=>({...f,plates:f.plates.map(p=>({...p,expected:undefined,exact_match:null,cer:null}))}))};
 function urls(){vi.stubGlobal('URL',Object.assign(URL,{createObjectURL:()=> 'blob:case',revokeObjectURL:vi.fn()}));}
 it('runs without labels or CSV and has no scoring request or verdict',async()=>{
  urls();vi.mocked(ocrRequest).mockImplementation(async(path,body)=>{if(path==='status')return {available:true,engine:'Fixture',device:'CPU'};if(path==='jobs'){expect(body).toBeInstanceOf(FormData);expect((body as FormData).has('expected')).toBe(false);expect((body as FormData).has('blind')).toBe(false);return {job_id:'plain'};}return unscored;});
  await render(<LiveOCRRun/>);expect(host.querySelector<HTMLDetailsElement>('.accuracy-step')?.open).toBe(false);
  const input=host.querySelector<HTMLInputElement>('input[type=file]')!;Object.defineProperty(input,'files',{value:[new File(['fixture'],'fixture.png',{type:'image/png'})]});await act(async()=>input.dispatchEvent(new Event('change',{bubbles:true})));await setValue(purpose(),'Test plain OCR');
  expect([...host.querySelectorAll('button')].find(b=>b.textContent==='Run OCR pipeline')!.disabled).toBe(false);await click('Run OCR pipeline');
  expect(host.textContent).toContain('Not scored. Add expected plates to measure accuracy.');expect([...host.querySelectorAll('th')].map(n=>n.textContent)).not.toContain('Match / CER');expect(host.textContent).not.toContain('Inconclusive:');
  await click('Measure accuracy');expect(host.querySelector<HTMLDetailsElement>('.accuracy-step')?.open).toBe(true);
 });
 it.each([2,3])('loads exactly %i configured files with no expected labels by default',async count=>{
  urls();const places=Array.from({length:count},(_,i)=>({file:`cam-${i}.mp4`,url:`/videos/test-case/cam-${i}.mp4`,camera_id:i?'C05':'C01',start_ist:`10:1${i}:05`,sha256:'fixture'}));
  const fetcher=vi.fn(async(url:string)=>url.endsWith('manifest.json')?{ok:true,json:async()=>({date:'2026-09-30',generated:true,expected_plate:'DL04CT7391',placements:places})}:{ok:true,blob:async()=>new Blob(['fixture'])});vi.stubGlobal('fetch',fetcher);
  vi.mocked(ocrRequest).mockImplementation(async path=>path==='status'?{available:true,engine:'fixture'}:{job_id:'test'});
  await render(<LiveOCRRun/>);await click('Load test case');expect(host.querySelectorAll('.upload-cards video')).toHaveLength(count);expect(fetcher.mock.calls.filter(([p])=>p.endsWith('.mp4'))).toHaveLength(count);
  for(const input of host.querySelectorAll<HTMLInputElement>('[aria-label^="Expected plate"]'))expect(input.value).toBe('');
 });
 it('sends blind true only with labels entered before a run',async()=>{
  urls();vi.mocked(ocrRequest).mockImplementation(async(path,body)=>{if(path==='status')return {available:true,engine:'fixture'};if(path==='jobs'){expect((body as FormData).get('blind')).toBe('true');expect(JSON.parse((body as FormData).get('expected') as string)).toEqual({'fixture.png':'DL04CT7391'});return {job_id:'labelled'};}return fixture;});
  await render(<LiveOCRRun/>);const input=host.querySelector<HTMLInputElement>('input[type=file]')!;Object.defineProperty(input,'files',{value:[new File(['fixture'],'fixture.png',{type:'image/png'})]});await act(async()=>input.dispatchEvent(new Event('change',{bubbles:true})));await setValue(purpose(),'Blind fixture check');await setValue(host.querySelector<HTMLInputElement>('[aria-label="Expected plate fixture.png"]')!,'DL04CT7391');await click('Run OCR pipeline');expect(host.textContent).toContain('Blind: labels entered before this run');
 });
 const testCase:LiveCase={id:'case-test',plate:'DL04CT7391',purpose:'Case fixture test',generated:true,staged:true,total_distance_km:1.719,geojson:{type:'LineString',coordinates:[[77.217,28.631],[77.218,28.643]]},stops:[0,1].map(i=>({clip:`cam-${i}.mp4`,sha256:'a'.repeat(64),camera_id:i?'C05':'C01',camera:cameras[i?4:0],ts_ist:`2026-09-30T10:${i?'15:02':'12:05'}+05:30`,video_time_s:1.5,vote_confidence:.93,staged:true,generated:true,track_id:1,evidence:{...fixture.files[0].plates[0],voted:'DL04CT7391',track_id:1,time_s:2},observed_span_s:3,leg_distance_km:i?1.719:0,seconds:i?177:null,speed_kmh:i?35:null,inferred_cameras:[],implausible:false}))};
 it('creates a placed case and adds its preset without changing existing presets',async()=>{
  urls();const job={...unscored,files:testCase.stops.map(s=>({...unscored.files[0],file:s.clip,tracks:[],plates:[s.evidence]}))};const places=testCase.stops.map(s=>({file:s.clip,camera_id:s.camera_id,ts_ist:s.ts_ist,staged:true,generated:true}));
  vi.mocked(ocrRequest).mockImplementation(async(path,body)=>{expect(path).toBe('jobs/fixture/trajectories');expect(body).toEqual({placements:places});return {cases:[testCase]};});
  await render(<Trajectory/>);expect(host.textContent).not.toContain('Test case: same vehicle');
  await render(<PlaceOnMap job={job} uploads={[]} initialPlacements={places}/>);expect(host.querySelector<HTMLInputElement>('[aria-label="Camera cam-1.mp4"]')?.value).toBe('C05');await click('Create trajectory');expect(liveCaseStore.getSnapshot()[0].stops.map(s=>s.clip)).toEqual(['cam-0.mp4','cam-1.mp4']);expect(host.textContent).toContain('Open in Plate Trajectory');expect(host.querySelector('a')?.getAttribute('href')).toBe('/#/trajectories?live_case=case-test');
  await render(<Trajectory/>);expect(host.textContent).toContain('Test case: same vehicle, 2 cameras');expect(host.textContent).toContain('DL01AB1234');await click('Test case: same vehicle, 2 cameras');expect(host.querySelectorAll('[data-provenance="generated"]').length).toBeGreaterThanOrEqual(3);expect(host.textContent).toContain('35 km/h');
 });
 it('masks the case plate for Viewer including GeoJSON and withholds evidence pixels',async()=>{
  session.user.role='viewer';await render(<LiveCaseJourney value={testCase}/>);expect(host.textContent).not.toContain('DL04CT7391');expect(host.textContent).toContain('DL••••91');expect(host.querySelector('video')).toBeNull();const exported=JSON.stringify(caseGeoJSON(testCase,false));expect(exported).not.toContain('DL04CT7391');expect(exported).toContain('"generated":true');expect(exported).toContain('"staged":true');
 });
 it('seeks actual stop time and best OCR evidence frame',async()=>{
  const uploads=testCase.stops.map(s=>({file:new File(['fixture'],s.clip,{type:'video/mp4'}),url:'blob:fixture'}));await render(<LiveCaseJourney value={{...testCase,uploads}}/>);let video=host.querySelector('video')!;await act(async()=>video.dispatchEvent(new Event('loadedmetadata')));expect(video.currentTime).toBe(1.5);await click('Seek track #1 · 2.00s');expect(video.currentTime).toBe(2);await click('Stop 2 · New Delhi Railway Station');video=host.querySelector('video')!;await act(async()=>video.dispatchEvent(new Event('loadedmetadata')));expect(video.currentTime).toBe(1.5);
 });
});

describe('rendered page wording guard',()=>{
 for(const [name,Component] of Object.entries({Overview,Traffic,Live,CameraHealth,Attributes,Search,Profile,SignIn,Video,Trajectory,Privacy,MapPage,AnalyticsPage,AlertsPage,WatchlistPage,AttributesPage,OCRPage,AuditPage,Administration}))it(name,async()=>{await render(<Component/>);const clone=host.cloneNode(true) as HTMLElement;clone.querySelectorAll('[data-data-sources]').forEach(el=>el.remove());clone.querySelectorAll('script,style').forEach(el=>el.remove());const visible=clone.textContent||'';expect(visible).not.toMatch(/\b(demo|synthetic|simulated|mock|fake|dummy)\b/i);for(const node of clone.querySelectorAll('[aria-label],[title]'))if(!node.hasAttribute('data-provenance'))expect(`${node.getAttribute('aria-label')||''} ${node.getAttribute('title')||''}`).not.toMatch(/\b(demo|synthetic|simulated|mock|fake|dummy)\b/i);});
});
