export interface HealthInput {signal:boolean|null;fps:number|null;latency:number|null;brightness:number|null;sharpness:number|null;readRate:number|null}
const clamp=(n:number)=>Math.max(0,Math.min(1,n));
export function cameraHealth(v:HealthInput){
 const components={connectivity:v.signal==null?null:v.signal?30:0,frameRate:v.fps==null?null:20*clamp(v.fps/25),latency:v.latency==null?null:15*clamp(1-v.latency/1000),imageQuality:v.brightness==null||v.sharpness==null?null:20*(clamp(1-Math.abs(v.brightness-128)/128)+clamp(v.sharpness/250))/2,plateReadRate:v.readRate==null?null:15*clamp(v.readRate)};
 const known=Object.values(components).filter((n):n is number=>n!=null),total=known.length===5?Math.round(known.reduce((a,b)=>a+b,0)):null;
 const status=v.signal===false?'Offline':total==null?'Unmeasured':total>=85?'Online':total>=60?'Degraded':'Offline';
 const issues:string[]=[];
 if(v.signal===false)issues.push('stalled stream');
 if(v.brightness!=null&&v.brightness<50)issues.push('low light');
 if(v.sharpness!=null&&v.sharpness<30)issues.push('blur');
 if(v.brightness!=null&&v.brightness<12&&v.sharpness!=null&&v.sharpness<5)issues.push('obstruction','tamper suspicion');
 if(v.latency!=null&&v.latency>400)issues.push('high latency');
 if(v.readRate!=null&&v.readRate<.6)issues.push('low read rate');
 return {components,total,status,issues};
}
