import { describe,it,expect,vi,afterEach } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { loadRealBundle,erasePlate,purgeBundle } from './loader';
import { percentile,zScore,bufferIndex,dayHour } from './calculations';
import SourceBadge,{maskPlate} from './SourceBadge';
import { assembleTrajectory } from './RealJourney';
import type { Bundle,RealTrajectory } from './types';
import cases from '../../../pipeline/tests/vote-parity.json';
import { votePlates } from './voting';
afterEach(()=>vi.unstubAllGlobals());
describe('real footage safeguards',()=>{
 it('agrees with Python on shared vote fixtures',()=>{for(const c of cases)expect(votePlates(c.reads)).toEqual({text:c.text,confidence:c.confidence});});
 it('has clear source and staged labels',()=>{const html=renderToStaticMarkup(<SourceBadge staged/>);expect(html).toContain('Recorded footage');expect(html).toContain('Staged placement');expect(maskPlate('DL01AB1234',true)).not.toContain('DL01AB1234');});
 it('handles an absent bundle',async()=>{vi.stubGlobal('fetch',vi.fn().mockResolvedValue({status:404}));expect(await loadRealBundle()).toBeNull();});
 it('loads independent bundle files',async()=>{vi.stubGlobal('fetch',vi.fn((path:string)=>Promise.resolve({ok:true,json:()=>Promise.resolve(path.endsWith('manifest.json')?{clips:[]}:path.endsWith('events.json')||path.endsWith('trajectories.json')?[]:{})})));expect((await loadRealBundle())?.manifest.clips).toEqual([]);});
 it('assembles sorted real stops without changing the seeded routes',()=>{const t={plate:'DL01AB1234',stops:[{camera_id:'C02',ts_ist:'2026-09-30T10:00:00+05:30',confidence:.9},{camera_id:'C01',ts_ist:'2026-09-30T09:00:00+05:30',confidence:.95}]} as RealTrajectory;const result=assembleTrajectory(t);expect(result.hops[0].camera_id).toBe('C01');expect(result.hops[1].seconds).toBe(3600);expect(t.stops[0].camera_id).toBe('C02');});
 it('purges and erases only a copy of the real store',()=>{const b={manifest:{clips:[]},tracks:{},analysis:{},counts:{},events:[{plate:'DL01AB1234',expires_at:'2000-01-01'}],trajectories:[{plate:'DL01AB1234',expires_at:'2000-01-01',stops:[]}],registry:{}} as unknown as Bundle;expect(erasePlate(b,'DL01AB1234').events).toHaveLength(0);expect(purgeBundle(b).events).toHaveLength(0);expect(b.events).toHaveLength(1);});
 it('computes percentiles, variability and IST cells',()=>{expect(percentile([4,1,3,2],.5)).toBe(2.5);expect(percentile([], .5)).toBeNull();expect(zScore(2,[1,2,3])).toBe(0);expect(bufferIndex([10,10,10])).toBe(0);expect(dayHour([{timestamp:'2026-09-24T00:00:00Z'}])[0][5]).toBe(1);});
});

