import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { api, getToken } from './api';
import { useSession } from './session';
import { MOCK } from './demo/api';
import type { Alert, Analytics, Camera, Density, Integrity, OD, Road } from './types';

interface DataState {cameras:Camera[];roads:Road[];analytics:Analytics|null;density:Density[];od:OD[];integrity:Integrity|null;alerts:Alert[];loading:boolean;error:string;updated:string;connected:boolean;reload:()=>Promise<void>}
const Context=createContext<DataState|null>(null);
export function DataProvider({children}:{children:ReactNode}){
  const {session}=useSession();const [data,setData]=useState<Omit<DataState,'reload'|'loading'|'error'|'connected'>>({cameras:[],roads:[],analytics:null,density:[],od:[],integrity:null,alerts:[],updated:''});
  const [loading,setLoading]=useState(true),[error,setError]=useState(''),[connected,setConnected]=useState(false);
  const reload=useCallback(async()=>{if(!session)return;try{const [network,analytics,density,od,integrity,alerts]=await Promise.all([api<{cameras:Camera[];roads:Road[]}>('cameras'),api<Analytics>('analytics/summary'),api<Density[]>('analytics/heatmap'),api<OD[]>('analytics/origin-destination'),api<Integrity>('integrity'),session.user.role==='viewer'?Promise.resolve([]):api<Alert[]>('alerts/workflow')]);setData({...network,analytics,density,od,integrity,alerts,updated:new Date().toISOString()});setError('');}catch(e){setError((e as Error).message);}finally{setLoading(false);}},[session]);
  useEffect(()=>{void reload();const timer=setInterval(()=>void reload(),30000);return()=>clearInterval(timer);},[reload]);
  useEffect(()=>{if(MOCK){setConnected(true);return;}if(!session||session.user.role==='viewer')return;let disposed=false;let socket:WebSocket;let timer:ReturnType<typeof setTimeout>;let debounce:ReturnType<typeof setTimeout>;
    const connect=()=>{socket=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/ws/alerts`);socket.onopen=()=>socket.send(JSON.stringify({token:getToken()}));socket.onmessage=event=>{if(disposed)return;setConnected(true);const message=JSON.parse(event.data);if(message.type==='alert'){clearTimeout(debounce);debounce=setTimeout(()=>void reload(),300);}};socket.onclose=()=>{if(!disposed){setConnected(false);timer=setTimeout(connect,5000);}};socket.onerror=()=>socket.close();};connect();return()=>{disposed=true;clearTimeout(timer);clearTimeout(debounce);socket?.close();};},[session,reload]);
  return <Context.Provider value={{...data,loading,error,connected,reload}}>{children}</Context.Provider>;
}
export function useData(){const data=useContext(Context);if(!data)throw Error('Data provider missing');return data;}
