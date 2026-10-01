import { ProvenanceChip } from '../lib/provenance';
export default function SourceBadge({staged=false,synthetic=false,reviewed=false}:{staged?:boolean;synthetic?:boolean;reviewed?:boolean}){return <span className="real-badges"><ProvenanceChip source={synthetic?'modelled':reviewed?'reviewed':'footage'}/>{staged&&<ProvenanceChip source="staged"/>}</span>;}
export const maskPlate=(plate:string,viewer:boolean)=>viewer?`${plate.slice(0,2)}••••${plate.slice(-2)}`:plate;
