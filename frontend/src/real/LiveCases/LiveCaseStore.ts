import {useSyncExternalStore} from 'react';
import type {PlateResult} from '../LiveOCRRun/ocrLiveApi';
import type {Upload} from '../LiveOCRRun/Evidence';
import type {Camera,Trajectory} from '../../types';

export interface Placement {file:string;camera_id:string;ts_ist:string;staged:boolean;generated:boolean}
export interface TestCaseManifest {name:string;date:string;generated:boolean;expected_plate?:string;placements:{file:string;url:string;camera_id:string;start_ist:string;sha256:string}[]}
export interface LiveStop {clip:string;sha256:string;camera_id:string;camera:Camera;ts_ist:string;video_time_s:number;vote_confidence:number;staged:boolean;generated:boolean;track_id:number|null;evidence:PlateResult;observed_span_s:number|null;leg_distance_km:number;seconds:number|null;speed_kmh:number|null;inferred_cameras:string[];implausible:boolean}
export interface LiveCase {id:string;plate:string;purpose:string;stops:LiveStop[];total_distance_km:number;generated:boolean;staged:boolean;geojson:Trajectory['geojson'];uploads?:Upload[]}
let cases:LiveCase[]=[];
const listeners=new Set<()=>void>();
const notify=()=>listeners.forEach(fn=>fn());
export const liveCaseStore={
 getSnapshot:()=>cases,
 subscribe:(listener:()=>void)=>{listeners.add(listener);return()=>{listeners.delete(listener);};},
 add:(incoming:LiveCase[],uploads:Upload[])=>{
  const replaced=new Set(incoming.map(c=>c.id));
  for(const c of cases.filter(c=>replaced.has(c.id)))c.uploads?.forEach(u=>URL.revokeObjectURL(u.url));
  cases=[...cases.filter(c=>!replaced.has(c.id)),...incoming.map(c=>({...c,uploads:uploads.filter(u=>c.stops.some(s=>s.clip===u.file.name)).map(u=>({file:u.file,url:URL.createObjectURL(u.file)}))}))];
  while(cases.length>20)cases.shift()?.uploads?.forEach(u=>URL.revokeObjectURL(u.url));
  notify();
 },
 clear:()=>{cases.forEach(c=>c.uploads?.forEach(u=>URL.revokeObjectURL(u.url)));cases=[];notify();},
};
export function useLiveCases(){return useSyncExternalStore(liveCaseStore.subscribe,liveCaseStore.getSnapshot,liveCaseStore.getSnapshot);}
export const plateText=(plate:string,authorised:boolean)=>authorised?plate:`${plate.slice(0,2)}••••${plate.slice(-2)}`;
export function mapTrajectory(c:LiveCase,authorised:boolean):Trajectory{return {found:true,plate:plateText(c.plate,authorised),identity_id:0,vehicle_type:'unclassified',total_distance_km:c.total_distance_km,geojson:c.geojson,hops:c.stops.map((s,i)=>({detection_id:i,camera_id:s.camera_id,camera_name:s.camera.name,timestamp:s.ts_ist,confidence:s.vote_confidence,observed_plate:plateText(c.plate,authorised),leg_distance_km:s.leg_distance_km,seconds:s.seconds,speed_kmh:s.speed_kmh,inferred_cameras:s.inferred_cameras,implausible:s.implausible}))};}
export function caseGeoJSON(c:LiveCase,authorised:boolean){return {type:'FeatureCollection',features:[{type:'Feature',geometry:c.geojson,properties:{plate:plateText(c.plate,authorised),purpose:c.purpose,generated:c.generated,staged:c.staged}},...c.stops.map(s=>({type:'Feature',geometry:{type:'Point',coordinates:[s.camera.lon,s.camera.lat]},properties:{clip:s.clip,camera_id:s.camera_id,ts_ist:s.ts_ist,video_time_s:s.video_time_s,vote_confidence:s.vote_confidence,generated:s.generated,staged:s.staged,sha256:s.sha256,plate:plateText(c.plate,authorised),speed_kmh:s.speed_kmh,implausible:s.implausible}}))]};}
