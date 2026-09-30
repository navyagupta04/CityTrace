import { createContext,useContext,useEffect,useState,type ReactNode } from 'react';
import { loadRealBundle,erasePlate,purgeBundle } from './loader';
import type { Bundle } from './types';
import { record } from '../demo/api';
const Context=createContext<{bundle:Bundle|null;error:string;loading:boolean;erase:(plate:string)=>void;purge:()=>void}>({bundle:null,error:'',loading:false,erase:()=>{},purge:()=>{}});
export function RealFootageProvider({children}:{children:ReactNode}){const [bundle,setBundle]=useState<Bundle|null>(null),[error,setError]=useState(''),[loading,setLoading]=useState(true);useEffect(()=>{let active=true;loadRealBundle().then(b=>{if(active)setBundle(b);}).catch(e=>{if(active)setError(e.message);}).finally(()=>{if(active)setLoading(false);});return()=>{active=false;};},[]);return <Context.Provider value={{bundle,error,loading,erase:plate=>{setBundle(b=>b?erasePlate(b,plate):b);record('privacy.erasure',{plate,persistence:'in-memory only'});},purge:()=>{setBundle(b=>b?purgeBundle(b):b);record('privacy.purge',{persistence:'in-memory only'});}}}>{children}</Context.Provider>;}
export const useRealFootage=()=>useContext(Context);
