import type { Hop, Minute } from './types';
export const number = (value: number | null | undefined) => value == null ? '—' : value.toLocaleString('en-IN', { maximumFractionDigits: 1 });
export const date = (value: string) => new Date(value).toLocaleString('en-IN', { timeZone:'Asia/Kolkata', day:'2-digit', month:'short', hour:'2-digit', minute:'2-digit', hour12:false });
export const clock = (value: string) => new Date(value).toLocaleTimeString('en-IN', { timeZone:'Asia/Kolkata',hour:'2-digit',minute:'2-digit',hour12:false });
export const label = (value: string) => value.replaceAll('_',' ').replace(/\b\w/g, x => x.toUpperCase());
export function volumeSeries(minutes: Minute[]) {
  const groups = new Map<string, number>();
  minutes.forEach(m => {const utc=Date.parse(/(?:Z|[+-]\d\d:\d\d)$/.test(m.minute)?m.minute:m.minute+'Z');const key=new Date(utc+19800000).toISOString().slice(0,13);groups.set(key,(groups.get(key)||0)+m.count);});
  return [...groups].sort(([a],[b])=>a.localeCompare(b)).map(([hour,count])=>({hour:hour.slice(11)+':00', count}));
}
export function splitTrips(hops: Hop[]) {
  const trips: Hop[][]=[];
  for (const hop of hops) {
    const trip=trips.at(-1);
    if (!trip || +new Date(hop.timestamp)-+new Date(trip.at(-1)!.timestamp)>1800000) trips.push([hop]);
    else trip.push(hop);
  }
  return trips;
}
