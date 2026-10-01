import { createContext, useContext, useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { record, resetScenario, scenarioAlert } from './api';
import { useData } from '../data';

interface State {region:string;setRegion:(v:string)=>void;tick:number;running:boolean;elapsed:number;notice:string;start:()=>void;stop:()=>void;reset:()=>void}
const Context=createContext<State|null>(null);
export function DemoProvider({children}:{children:ReactNode}){const [region,setRegion]=useState('All Delhi'),[tick,setTick]=useState(0),[running,setRunning]=useState(false),[elapsed,setElapsed]=useState(0),[notice,setNotice]=useState(''),d=useData(),reload=useRef(d.reload);reload.current=d.reload;
 // One shared one-second bus. Hidden tabs pause the scripted scenario and ticker.
 useEffect(()=>{const timer=setInterval(()=>{if(document.hidden)return;setTick(t=>t+1);},1000);return()=>clearInterval(timer);},[]);
 useEffect(()=>{if(!running)return;setElapsed(e=>e+1);},[tick,running]);
 useEffect(()=>{if(!running)return;if(elapsed===3)setNotice('UP16AX9912 read at Narela. modelled journey started.');if(elapsed===6){scenarioAlert(1);setNotice('Watchlist match: UP16AX9912. Review the new alert.');void reload.current();}if(elapsed===14)setNotice('UP16AX9912 reached Connaught Place; route deviation flagged.');if(elapsed===18){scenarioAlert(2);setNotice('Impossible travel: DL08CX9090 at Narela and Badarpur.');void reload.current();}if(elapsed>=30){setRunning(false);setNotice('Scenario complete: two modelled alerts added. Open Alerts to review.');record('scenario.complete');}},[elapsed,running]);
 const start=()=>{resetScenario();setElapsed(0);setRunning(true);setNotice('Scenario playback started. Follow the plates and alerts over 30 seconds.');record('scenario.start');};
 const stop=()=>{setRunning(false);setNotice('Scenario paused. Reset or run it again.');};
 const reset=()=>{setRunning(false);setElapsed(0);resetScenario();setNotice('Scenario reset to the seeded alerts.');void d.reload();};
 return <Context.Provider value={{region,setRegion,tick,running,elapsed,notice,start,stop,reset}}>{children}</Context.Provider>;
}
export function useDemo(){const ctx=useContext(Context);if(!ctx)throw Error('sample provider missing');return ctx;}
