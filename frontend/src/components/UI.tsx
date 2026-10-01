import { ProvenanceChip,type Provenance } from '../lib/provenance';
import { motion, useReducedMotion, animate } from 'framer-motion';
import { useEffect, useRef } from 'react';
import type { ReactNode } from 'react';
import { AlertCircle, ArrowUpRight, SearchX, LoaderCircle, ScanLine } from 'lucide-react';
import { Link } from '../router';
import { useSession } from '../session';
import { number } from '../utils';

export function Logo({compact=false}:{compact?:boolean}){return <div className="brand"><span className="brand-symbol"><ScanLine size={23}/></span>{!compact&&<div><strong>CityTrace<span>.</span></strong><small>TRAFFIC INTELLIGENCE</small></div>}</div>;}
export function Panel({title,subtitle,action,children,source,className=''}:{title?:string;subtitle?:string;action?:ReactNode;children:ReactNode;source?:Provenance;className?:string}){return <section className={`panel ${className}`}>{title&&<div className="panel-heading"><div><h2>{title} {source&&<ProvenanceChip source={source}/>}</h2>{subtitle&&<p>{subtitle}</p>}</div>{action}</div>}{!title&&source&&<ProvenanceChip source={source}/>} {children}</section>;}
export function PageHeader({eyebrow='COMMAND CENTRE',title,description,actions}:{eyebrow?:string;title:string;description:string;actions?:ReactNode}){return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div><div className="page-actions">{actions}</div></div>;}
export function Plate({value}:{value:string}){const {session}=useSession();const text=session?.user.role==='viewer'?value.replace(/^([A-Z]{2})([0-9]{2})[A-Z]+([0-9]{4})$/,'$1-$2-**-$3'):value;return <span className="plate"><span className="plate-country">IND</span>{text}</span>;}
export function Badge({children,tone='neutral'}:{children:ReactNode;tone?:string}){return <span className={`badge ${tone}`}>{children}</span>;}
export function Empty({title='No observations yet',message='Run a scenario or ingest detection events to populate this view.',action}:{title?:string;message?:string;action?:ReactNode}){return <div className="empty-state"><SearchX size={27}/><h3>{title}</h3><p>{message}</p>{action}</div>;}
export function ErrorMessage({message,retry}:{message:string;retry?:()=>void}){return <div className="error-message" role="alert"><AlertCircle size={17}/><span>{message}</span>{retry&&<button onClick={retry}>Retry</button>}</div>;}
export function Loading({label='Loading intelligence…'}:{label?:string}){return <div className="loading" role="status"><LoaderCircle className="spin" size={22}/>{label}</div>;}
export function Page({children}:{children:ReactNode}){const reduce=useReducedMotion();return <motion.div initial={{opacity:0,y:reduce?0:6}} animate={{opacity:1,y:0}} transition={{duration:.22}}>{children}</motion.div>;}
export function Count({value}:{value:number|null|undefined}){const ref=useRef<HTMLSpanElement>(null),reduce=useReducedMotion();useEffect(()=>{if(!ref.current)return;if(value==null){ref.current.textContent='—';return;}if(reduce){ref.current.textContent=number(value);return;}const controls=animate(0,value,{duration:.7,onUpdate:v=>{if(ref.current)ref.current.textContent=number(Number.isInteger(value)?Math.round(v):Math.round(v*10)/10);}});return()=>controls.stop();},[value,reduce]);return <span ref={ref}>{number(value)}</span>;}
export function ViewLink({to,children='View all'}:{to:string;children?:ReactNode}){return <Link className="text-link" to={to}>{children}<ArrowUpRight size={14}/></Link>;}
export function Modal({title,onClose,children,className=''}:{title:string;onClose:()=>void;children:ReactNode;className?:string}){const ref=useRef<HTMLDialogElement>(null);useEffect(()=>{const dialog=ref.current;dialog?.showModal();return()=>dialog?.close();},[]);return <dialog ref={ref} className={`modal native-modal ${className}`} aria-label={title} onCancel={onClose} onClick={e=>{if(e.target===ref.current)onClose();}}><h2>{title}</h2>{children}</dialog>;}
