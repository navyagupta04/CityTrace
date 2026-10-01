import { createElement } from 'react';

export const provenance = {
 modelled: {text:'Modelled',tooltip:'Generated from the deterministic seeded model; not a field measurement.'},
 sample: {text:'Sample record',tooltip:'Not connected to any government system.'},
 live: {text:'LIVE RUN (this upload)',tooltip:'Computed by the local OCR pipeline from this upload; not the held-out test result.'},
 frozen: {text:'HELD-OUT TEST (frozen)',tooltip:'Computed on the frozen labelled test split.'},
 recorded: {text:'Recorded feed',tooltip:'User-supplied recording; placement on a Delhi camera is staged.'},
 measured: {text:'Measured from stream',tooltip:'Measured from browser playback in this session; network latency and plate accuracy are not inferred.'},
 footage: {text:'Recorded footage',tooltip:'Model output from a recorded video, not validated citywide observations.'},
 staged: {text:'Staged placement',tooltip:'The camera assignment is illustrative and does not identify the filming location.'},
 reviewed: {text:'User-reviewed recording',tooltip:'Identity supplied by the user after viewing the recording; not blind accuracy evidence.'},
};
export type Provenance = keyof typeof provenance;
export const displayAuditValue=(value:unknown)=>String(value).replace(/\bdemo\b/gi,'sample').replace(/\bsynthetic\b|\bsimulated\b/gi,'modelled');
export function ProvenanceChip({source}:{source:Provenance}) {
 const p=provenance[source];
 return createElement('span',{className:'provenance-chip',title:p.tooltip,'data-provenance':source,tabIndex:0},p.text);
}
