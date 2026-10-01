import {useEffect,useMemo,useRef,useState} from 'react';
import {CircleMarker,GeoJSON,LayerGroup,LayersControl,MapContainer,Marker,Polygon,Polyline,Popup,ScaleControl,TileLayer,useMap} from 'react-leaflet';
import L from 'leaflet';
import 'leaflet.heat';
import 'leaflet/dist/leaflet.css';
import type {GeoJsonObject} from 'geojson';
import type {NetworkMapProps} from './NetworkMap';
import {useRoads} from '../real/RoadLayer';
import {cameraById,initialAlerts,normalise,trajectoryFor,vehicles} from '../demo/model';
import boundary from '../demo/delhi-boundary.json';
import {REGIONS} from '../constants/city';
import {roadRoute,type Coordinate} from './gisRoutes';
import {clock} from '../utils';

type CameraStats={id:string;name:string;status:string;zone:string;lat:number;lon:number;vehicles:number;reads:number;last_detection:string|null};
type DensityResult={points:[number,number,number][];cameras:CameraStats[];total_vehicles:number;peak_zone:string|null;peak_hour:string|null;start:string;end:string;source:string;storage:string;max_intensity:number};
const toLatLng=(points:Coordinate[])=>points.map(([lon,lat])=>[lat,lon] as Coordinate);
const colours={Online:'#24b894',Offline:'#e76570',Processing:'#e8a742'};
const localTime=(date:Date)=>new Date(+date+19800000).toISOString().slice(0,16);
const NCR:L.LatLngBoundsExpression=[[28.15,76.45],[29.18,78.05]];
const cache=new Map<string,{time:number;promise:Promise<DensityResult>}>();
function loadDensity(query:string){
 const existing=cache.get(query);if(existing&&Date.now()-existing.time<60000)return existing.promise;
 const promise=fetch(`/api/gis/density?${query}`).then(async response=>{if(!response.ok)throw Error('Density service unavailable. Road routes remain available.');return response.json();});
 cache.set(query,{time:Date.now(),promise});promise.catch(()=>cache.delete(query));return promise;
}
function HeatLayer({points,max,visible}:{points:[number,number,number][];max:number;visible:boolean}){
 const map=useMap(),layer=useRef<L.HeatLayer|null>(null);
 useEffect(()=>{const heat=L.heatLayer([],{radius:18,blur:18,maxZoom:12,minOpacity:.015,gradient:{.1:'#247cff',.35:'#20bf83',.55:'#ffe453',.75:'#ff973d',1:'#f34245'}});layer.current=heat;return()=>{heat.remove();layer.current=null;};},[map]);
 useEffect(()=>{const heat=layer.current;if(!heat)return;const update=()=>{heat.setOptions({max:Math.max(1,max*Math.max(1,20*Math.pow(2,11-map.getZoom())))});heat.redraw();};heat.setLatLngs(points);update();map.on('zoomend',update);if(visible)heat.addTo(map);else heat.remove();return()=>{map.off('zoomend',update);};},[map,points,max,visible]);
 return null;
}
function Focus({point}:{point?:Coordinate}){const map=useMap();useEffect(()=>{if(point)map.flyTo(point,14,{duration:.6});},[map,point?.[0],point?.[1]]);return null;}
function RouteFit({points,token}:{points:Coordinate[];token:string}){const map=useMap();useEffect(()=>{if(points.length)map.fitBounds(points,{padding:[35,35],maxZoom:14});},[map,token]);return null;}
function Controls(){
 const map=useMap(),[message,setMessage]=useState('');
 useEffect(()=>{const failure=()=>setMessage('Location unavailable. Search for a camera or centre on Delhi.');map.on('locationerror',failure);return()=>{map.off('locationerror',failure);};},[map]);
 return <div className="gis-locate"><button aria-label="Centre map on Delhi" onClick={()=>map.flyTo([28.63,77.21],11)}>◎ Delhi</button><button aria-label="Locate my position" onClick={()=>{setMessage('');map.locate({setView:true,maxZoom:14});}}>Locate me</button>{message&&<small role="status">{message}</small>}</div>;
}
export default function StreetMap({densityPeriod,cameras,trajectory,compare,progress=1,onCamera,focusCamera,large=false,region='All Delhi',onRegion,heat=false,flows=[]}:NetworkMapProps){
 const network=useRoads(),[window,setWindow]=useState(densityPeriod?'selected':'today'),[start,setStart]=useState(localTime(new Date(Date.now()-3600000))),[end,setEnd]=useState(localTime(new Date()));
 const [result,setResult]=useState<DensityResult|null>(null),[today,setToday]=useState<DensityResult|null>(null),[error,setError]=useState(''),[loading,setLoading]=useState(false),[densityVisible,setDensityVisible]=useState(heat),[tileError,setTileError]=useState(false);
 const [search,setSearch]=useState(''),[searchMessage,setSearchMessage]=useState(''),[searchedCamera,setSearchedCamera]=useState(''),[searchedRoute,setSearchedRoute]=useState<ReturnType<typeof trajectoryFor>|null>(null);
 const query=useMemo(()=>{const p=new URLSearchParams({window:window==='selected'?'custom':window,region});if(window==='selected'&&densityPeriod){p.set('start',densityPeriod.start);p.set('end',densityPeriod.end);}if(window==='custom'){p.set('start',start+':00+05:30');p.set('end',end+':00+05:30');}return p.toString();},[window,region,start,end,densityPeriod?.start,densityPeriod?.end]);
 useEffect(()=>{let active=true;setLoading(true);setError('');loadDensity(query).then(data=>{if(active)setResult(data);}).catch(e=>{if(active){setError(e.message);setResult(null);}}).finally(()=>{if(active)setLoading(false);});return()=>{active=false;};},[query]);
 useEffect(()=>{let active=true;loadDensity('window=today').then(data=>{if(active)setToday(data);}).catch(()=>{});return()=>{active=false;};},[]);
 const mapped=useMemo(()=>cameras.filter(c=>region==='All Delhi'||cameraById.get(c.id)?.region===region).map(c=>({...c,...network?.routes.real_position[c.id]})),[cameras,region,network]);
 const lookup=useMemo(()=>new Map(cameras.map(c=>[c.id,{...c,...network?.routes.real_position[c.id]}])),[cameras,network]);
 const stats=new Map(today?.cameras.map(c=>[c.id,c])||[]),trip=searchedRoute||trajectory;
 const edge=(from:string,to:string)=>toLatLng(roadRoute(network,from,to));
 const route=(ids:string[])=>ids.slice(1).flatMap((id,i)=>{const points=edge(ids[i],id);return i?points.slice(1):points;});
 const path=(t:NonNullable<typeof trajectory>)=>route(t.hops.flatMap((h,i)=>i?[...h.inferred_cameras,h.camera_id]:[h.camera_id]));
 const segments=trip?.hops.slice(1).flatMap((hop,i)=>{
  const fraction=Math.max(0,Math.min(1,(searchedRoute?1:progress)*(trip.hops.length-1)-i)),points=route([trip.hops[i].camera_id,...hop.inferred_cameras,hop.camera_id]);
  if(!fraction||points.length<2)return [];
  const position=fraction*(points.length-1),index=Math.min(points.length-2,Math.floor(position)),ratio=position-index;
  const finish:Coordinate=[points[index][0]+(points[index+1][0]-points[index][0])*ratio,points[index][1]+(points[index+1][1]-points[index][1])*ratio];
  return [{id:hop.detection_id,points:[...points.slice(0,index+1),finish],finish,inferred:hop.inferred_cameras.length>0}];
 })||[];
 const focus=lookup.get(searchedCamera||focusCamera||'');
 function find(){
  setSearchMessage('');const text=search.trim().toLowerCase();
  const camera=cameras.find(c=>c.id.toLowerCase()===text||c.name.toLowerCase().includes(text));
  if(text&&camera){setSearchedCamera(camera.id);setSearchedRoute(null);setSearchMessage(`${camera.id} · ${camera.name}`);return;}
  const vehicle=vehicles.find(v=>normalise(v.plate)===normalise(search));
  if(vehicle){setSearchedCamera('');setSearchedRoute(trajectoryFor(vehicle.id,'2026-09-30'));setSearchMessage(`${vehicle.plate} · sample observations · 30 September`);return;}
  setSearchMessage('No camera or sample plate found. Try C03, ITO or DL01AB1234.');
 }
 const missing=trip?.hops.slice(1).some((h,i)=>!roadRoute(network,trip.hops[i].camera_id,h.camera_id).length);
 return <div className="gis-workspace">
  <div className="gis-toolbar"><form onSubmit={e=>{e.preventDefault();find();}}><label>Camera or plate<input aria-label="Map camera or plate search" placeholder="C03, ITO or DL01AB1234" value={search} onChange={e=>setSearch(e.target.value)}/></label><button type="submit">Find</button></form>{onRegion&&<label>Region<select aria-label="Geographic map region" value={region} onChange={e=>onRegion(e.target.value)}><option>All Delhi</option>{REGIONS.map(r=><option key={r}>{r}</option>)}</select></label>}<label>Density window<select aria-label="Density time window" value={window} onChange={e=>setWindow(e.target.value)}>{densityPeriod&&<option value="selected">Selected traffic hour</option>}<option value="last_hour">Last 1 hour</option><option value="today">Today</option><option value="custom">Custom</option></select></label>{window==='custom'&&<><label>Start · IST<input aria-label="Density start" type="datetime-local" value={start} onChange={e=>setStart(e.target.value)}/></label><label>End · IST<input aria-label="Density end" type="datetime-local" value={end} onChange={e=>setEnd(e.target.value)}/></label></>}</div>
  {searchMessage&&<p role="status" className="gis-message">{searchMessage}</p>}
  <div className={`gis-map ${large?'large':''}`}>
   <MapContainer center={[28.63,77.21]} zoom={11} minZoom={9} maxZoom={18} maxBounds={NCR} maxBoundsViscosity={.9} scrollWheelZoom style={{height:'100%',width:'100%'}}>
    <Focus point={focus?[focus.lat,focus.lon]:undefined}/><RouteFit points={searchedRoute?path(searchedRoute):[]} token={searchedRoute?.plate||''}/><Controls/><ScaleControl position="bottomleft" imperial={false}/>
    <GeoJSON data={boundary as GeoJsonObject} style={{color:'#809bbb',weight:2,fillOpacity:0,dashArray:'6 4'}}/>
    <LayersControl position="topright">
     <LayersControl.BaseLayer checked name="Road view"><TileLayer className="gis-road-tiles" url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a> · Boundary: DataMeet (CC BY-SA 2.5 IN)' eventHandlers={{tileerror:()=>setTileError(true),tileload:()=>setTileError(false)}}/></LayersControl.BaseLayer>
     <LayersControl.BaseLayer name="Satellite view"><TileLayer url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}" attribution='Tiles &copy; Esri · Sources: Esri, Maxar, Earthstar Geographics, and the GIS User Community' eventHandlers={{tileerror:()=>setTileError(true),tileload:()=>setTileError(false)}}/></LayersControl.BaseLayer>
     <LayersControl.Overlay checked name="Cameras"><LayerGroup>{mapped.map(c=>{
      const data=stats.get(c.id),state=(data?.status||(cameraById.get(c.id)?.status==='Maintenance'?'Offline':cameraById.get(c.id)?.status==='Degraded'?'Processing':'Online')) as keyof typeof colours;
      const stop=trip?.hops.findIndex(h=>h.camera_id===c.id);
      return <Marker key={c.id} title={`${c.id} · ${c.name} · ${state}`} position={[c.lat,c.lon]} icon={L.divIcon({className:'gis-camera',html:`<span style="background:${colours[state]}">${stop!=null&&stop>=0?stop+1:''}</span>`,iconSize:[24,24],iconAnchor:[12,12]})} eventHandlers={{click:()=>onCamera?.(c)}}><Popup><strong>{c.id} · {c.name}</strong><p>{state} · {cameraById.get(c.id)?.region}</p><p>Vehicles today: {data?.vehicles??'Unavailable'}<br/>ANPR reads: {data?.reads??'Unavailable'}<br/>Last detection: {data?.last_detection?clock(data.last_detection)+' IST':'No detection today'}</p><small>Local seeded aggregate counts · placements snapped to cached OSM roads</small></Popup></Marker>;
     })}</LayerGroup></LayersControl.Overlay>
     <LayersControl.Overlay checked name="Vehicle Routes"><LayerGroup>{compare&&<Polyline positions={path(compare)} pathOptions={{color:'#a083e5',weight:4,dashArray:'6 5'}}/>}{segments.map(s=><Polyline key={s.id} positions={s.points} pathOptions={{color:'#1699bf',weight:5,dashArray:s.inferred?'7 5':undefined}}/>)}{segments.length>0&&<CircleMarker center={segments.at(-1)!.finish} radius={8} pathOptions={{color:'#fff',fillColor:'#1699bf',fillOpacity:1}}><Popup>{trip?.plate} · replay position</Popup></CircleMarker>}{flows.map((flow,i)=><Polyline key={i} positions={edge(flow.from,flow.to)} pathOptions={{color:'#a083e5',weight:Math.min(9,2+flow.count/4)}}/>)}</LayerGroup></LayersControl.Overlay>
     <LayersControl.Overlay checked={heat} name="Traffic Density"><LayerGroup eventHandlers={{add:()=>setDensityVisible(true),remove:()=>setDensityVisible(false)}}/></LayersControl.Overlay>
     <LayersControl.Overlay name="Restricted Zones"><LayerGroup>{mapped.filter(c=>c.restricted).map(c=><Polygon key={c.id} positions={[[c.lat-.004,c.lon-.005],[c.lat+.004,c.lon-.005],[c.lat+.004,c.lon+.005],[c.lat-.004,c.lon+.005]]} pathOptions={{color:'#e8a742',fillOpacity:.1}}><Popup>{c.name} · illustrative restricted zone</Popup></Polygon>)}</LayerGroup></LayersControl.Overlay>
     <LayersControl.Overlay name="Incidents and Alerts"><LayerGroup>{initialAlerts.map(alert=>{const c=lookup.get(alert.camera_id);return c?<CircleMarker key={alert.id} center={[c.lat,c.lon]} radius={11} pathOptions={{color:'#e76570'}}><Popup>{alert.kind}: {alert.explanation}<br/><small>Modelled incident</small></Popup></CircleMarker>:null;})}</LayerGroup></LayersControl.Overlay>
    </LayersControl>
    <HeatLayer points={result?.points||[]} max={result?.max_intensity||1} visible={densityVisible}/>
   </MapContainer>
   {tileError&&<p role="status" className="gis-tile-notice">Tiles unavailable. Cached routes still work; use Cached schematic for an offline basemap.</p>}
   {densityVisible&&<div className="gis-heat-legend">Low <i/> High</div>}
  </div>
  {missing&&network&&<p className="gis-message">Road geometry is unavailable for a leg; no straight-line route is substituted.</p>}
  <div className="gis-summary" aria-live="polite"><span>Vehicle detections<strong>{loading?'Updating…':result?.total_vehicles.toLocaleString()??'Unavailable'}</strong></span><span>Peak zone<strong>{result?.peak_zone||'No detections'}</strong></span><span>Peak hour · IST<strong>{result?.peak_hour||'—'}</strong></span><small>{error||`${mapped.length} cameras · ${result?.storage||'Local files'} · seeded demo counts · cached OSM road routing`}</small></div>
 </div>;
}
