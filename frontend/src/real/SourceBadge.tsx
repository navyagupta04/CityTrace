import { Badge } from '../components/UI';
export default function SourceBadge({staged=false,synthetic=false,reviewed=false}:{staged?:boolean;synthetic?:boolean;reviewed?:boolean}){return <span className="real-badges"><Badge tone={synthetic?'amber':'green'}>{synthetic?'SYNTHETIC':reviewed?'UPLOADED VIDEO · USER-CONFIRMED PLATE':'REAL FOOTAGE (model output)'}</Badge>{staged&&<Badge tone="amber">STAGED PLACEMENT</Badge>}</span>;}
export const maskPlate=(plate:string,viewer:boolean)=>viewer?`${plate.slice(0,2)}••••${plate.slice(-2)}`:plate;
