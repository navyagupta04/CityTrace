import { Badge } from '../components/UI';
export default function SourceBadge({staged=false,synthetic=false}:{staged?:boolean;synthetic?:boolean}){return <span className="real-badges"><Badge tone={synthetic?'amber':'green'}>{synthetic?'SYNTHETIC':'REAL FOOTAGE (model output)'}</Badge>{staged&&<Badge tone="amber">STAGED PLACEMENT</Badge>}</span>;}
export const maskPlate=(plate:string,viewer:boolean)=>viewer?`${plate.slice(0,2)}••••${plate.slice(-2)}`:plate;
