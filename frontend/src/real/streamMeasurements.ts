import { cameraHealth } from '../lib/cameraHealth';
import type { OverlayAnalysis } from './DetectionOverlay';
import { useEffect,useSyncExternalStore,type RefObject } from 'react';
export interface StreamMeasurement {at:number;fps:number|null;brightness:number|null;sharpness:number|null;decodeMs:number|null;dropped:number;stalled:boolean;playing:boolean;uptime:number;readRate:number|null;ocrConfidence:number|null;history:{time:string;fps:number|null;latency:number|null;issues:string[]}[]}
let snapshot:Record<string,StreamMeasurement>={};
const listeners=new Set<()=>void>();
const owners=new Map<string,HTMLVideoElement>();
const subscribe=(fn:()=>void)=>{listeners.add(fn);return()=>{listeners.delete(fn);};};
const getSnapshot=()=>snapshot;
const serverSnapshot:Record<string,StreamMeasurement>={};
export function useStreamMeasurements(){return useSyncExternalStore(subscribe,getSnapshot,()=>serverSnapshot);}
export function useMeasureVideo(id:string,ref:RefObject<HTMLVideoElement|null>,analysis:OverlayAnalysis|null=null){useEffect(()=>{
 const v=ref.current;if(!v)return;if(!owners.has(id))owners.set(id,v);
 const tracks=new Map<string|number,number>();for(const frame of analysis?.frames||[])for(const d of frame.detections)tracks.set(d.track_id,Math.max(tracks.get(d.track_id)||0,d.plate&&(d.plate_confidence||0)>=.8?d.plate_confidence||0:0));const accepted=[...tracks.values()].filter(n=>n>0),readRate=tracks.size?accepted.length/tracks.size:null,ocrConfidence=accepted.length?accepted.reduce((a,b)=>a+b,0)/accepted.length:null;
 const canvas=document.createElement('canvas');canvas.width=160;canvas.height=90;const ctx=canvas.getContext('2d',{willReadFrequently:true});
 let callback=0,lastFrames=0,lastAt=performance.now(),frames=0,lastFrameAt=performance.now(),decode:number|null=null,samples=0,healthy=0;
 const hasCallback=typeof v.requestVideoFrameCallback==='function';
 const onFrame=(_now:number,meta:VideoFrameCallbackMetadata)=>{frames=meta.presentedFrames;lastFrameAt=performance.now();decode=meta.processingDuration==null?null:meta.processingDuration*1000;callback=v.requestVideoFrameCallback(onFrame);};
 if(hasCallback)callback=v.requestVideoFrameCallback(onFrame);
 const timer=setInterval(()=>{const now=performance.now(),playing=!v.paused&&!v.ended&&!document.hidden;if(!playing||owners.get(id)!==v)return;
  let brightness:number|null=null,sharpness:number|null=null;
  if(ctx&&v.readyState>=2){try{ctx.drawImage(v,0,0,160,90);const pixels=ctx.getImageData(0,0,160,90).data,gray=new Float32Array(160*90);let sum=0;for(let i=0;i<gray.length;i++){gray[i]=.299*pixels[i*4]+.587*pixels[i*4+1]+.114*pixels[i*4+2];sum+=gray[i];}brightness=sum/gray.length;let lap=0,sq=0,n=0;for(let y=1;y<89;y++)for(let x=1;x<159;x++){const i=y*160+x,d=gray[i-1]+gray[i+1]+gray[i-160]+gray[i+160]-4*gray[i];lap+=d;sq+=d*d;n++;}sharpness=sq/n-(lap/n)**2;}catch{/* Canvas unavailable: values remain unmeasured. */}}
  const quality=v.getVideoPlaybackQuality?.(),currentFrames=hasCallback?frames:quality?.totalVideoFrames??0;
  const fps=hasCallback?Math.max(0,(currentFrames-lastFrames)*1000/(now-lastAt)):null;
  const stalled=hasCallback?now-lastFrameAt>3000:v.readyState<3;samples++;if(!stalled)healthy++;
  const history=[...(snapshot[id]?.history||[]),{time:new Date().toLocaleTimeString('en-IN',{timeZone:'Asia/Kolkata'}),fps,latency:decode,issues:cameraHealth({signal:!stalled,fps,latency:null,brightness,sharpness,readRate}).issues}].slice(-60);
  snapshot={...snapshot,[id]:{at:Date.now(),fps,brightness,sharpness,decodeMs:decode,dropped:quality?.droppedVideoFrames||0,stalled,playing,uptime:healthy/samples,readRate,ocrConfidence,history}};listeners.forEach(fn=>fn());lastAt=now;lastFrames=currentFrames;
 },3000);
 const reset=()=>{if(!owners.get(id)||owners.get(id)?.paused)owners.set(id,v);lastAt=performance.now();lastFrames=frames;lastFrameAt=lastAt;};v.addEventListener('playing',reset);
 return()=>{clearInterval(timer);if(callback)v.cancelVideoFrameCallback(callback);v.removeEventListener('playing',reset);if(owners.get(id)===v)owners.delete(id);if(snapshot[id]&&!owners.has(id)){snapshot={...snapshot,[id]:{...snapshot[id],playing:false}};listeners.forEach(fn=>fn());}};
 },[id,ref,analysis]);}
