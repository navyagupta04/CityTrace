import { describe, expect, it } from 'vitest';
import { splitTrips, volumeSeries } from './utils';
import type { Hop } from './types';

describe('traffic display transformations',()=>{
  it('aggregates cameras into IST hourly volume',()=>{
    expect(volumeSeries([{camera_id:'C01',minute:'2026-09-30T03:05',count:2},{camera_id:'C02',minute:'2026-09-30T03:55',count:4}])).toEqual([{hour:'08:00',count:2},{hour:'09:00',count:4}]);
  });
  it('splits trips only when the dwell gap exceeds 30 minutes',()=>{
    const hops=['03:00','03:30','04:01'].map(timestamp=>({timestamp:`2026-09-30T${timestamp}:00Z`}) as Hop);
    expect(splitTrips(hops).map(t=>t.length)).toEqual([2,1]);
    expect(splitTrips([])).toEqual([]);
  });
});
