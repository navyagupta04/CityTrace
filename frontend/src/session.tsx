import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { api, refreshSession, setToken } from './api';
import type { AuthConfig, Session } from './types';

interface AuthState {session: Session|null; config: AuthConfig|null; initializing: boolean; error: string; expiresAt: number; login: (username:string,password:string,unit:string,second_factor:string)=>Promise<void>; logout: ()=>Promise<void>; renew: ()=>Promise<void>}
const Context=createContext<AuthState|null>(null);
export function SessionProvider({children}:{children:ReactNode}) {
  const [session,setSession]=useState<Session|null>(null),[config,setConfig]=useState<AuthConfig|null>(null),[initializing,setInitializing]=useState(true),[error,setError]=useState(''),[expiresAt,setExpiresAt]=useState(0);
  const accept=useCallback((result:Session)=>{setToken(result.access_token);setSession(result);setExpiresAt(Date.now()+result.expires_in*1000);},[]);
  useEffect(()=>{let active=true;api<AuthConfig>('auth/config').then(async c=>{if(!active)return;setConfig(c);if(c.has_session){try{const result=await refreshSession();if(active)accept(result);}catch{setToken('');}}}).catch(e=>{if(active)setError(e.message);}).finally(()=>{if(active)setInitializing(false);});return()=>{active=false;};},[accept]);
  const login=async(username:string,password:string,unit:string,second_factor:string)=>{accept(await api<Session>('auth/login',{username,password,unit,second_factor}));};
  const logout=useCallback(async()=>{try{await api('auth/logout',{});}finally{setToken('');setSession(null);setExpiresAt(0);}},[]);
  const renew=async()=>{accept(await refreshSession());};
  useEffect(()=>{if(!session)return;const timer=setTimeout(()=>{void logout();},Math.max(0,expiresAt-Date.now()));return()=>clearTimeout(timer);},[session,expiresAt,logout]);
  return <Context.Provider value={{session,config,initializing,error,expiresAt,login,logout,renew}}>{children}</Context.Provider>;
}
export function useSession(){const value=useContext(Context);if(!value)throw Error('Session provider missing');return value;}
