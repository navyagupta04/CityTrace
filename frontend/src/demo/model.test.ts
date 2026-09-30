import { describe, expect, it } from 'vitest';
import { cameras, roads, vehicles, reads, trajectoryFor, routeBetween, fuzzyDistance, densityAt, seeded, initialAlerts } from './model';
import { REGIONS } from '../constants/city';
import { mockApi, audit } from './api';

describe('Delhi demo data integrity',()=>{
 it('provides city-wide coverage and reproducible searchable records',()=>{
  expect(cameras).toHaveLength(40);expect(vehicles).toHaveLength(160);expect(reads.length).toBeGreaterThan(1500);
  expect(new Set(cameras.map(c=>c.region))).toEqual(new Set(REGIONS));
  expect(new Set(vehicles.map(v=>v.plate)).size).toBe(vehicles.length);
  const a=seeded(),b=seeded();expect(Array.from({length:10},a)).toEqual(Array.from({length:10},b));
  expect(reads.every(r=>vehicles.some(v=>v.id===r.identity_id&&v.plate===r.plate))).toBe(true);
 });
 it('connects every camera and reconstructs a complete chronological lifeline',()=>{
  for(const camera of cameras)expect(routeBetween('C01',camera.id).path[0]).toBe('C01');
  const trip=trajectoryFor(1,'2026-09-30');expect(trip.hops).toHaveLength(18);
  expect(trip.hops[0].camera_id).toBe('C21');expect(trip.hops.at(-1)!.camera_id).toBe('C21');
  expect(trip.total_distance_km).toBeGreaterThan(80);
  expect(trip.hops.some(h=>h.inferred_cameras.length>0)).toBe(true);
  expect(trip.hops.every((h,i)=>!i||h.timestamp>trip.hops[i-1].timestamp)).toBe(true);
  expect(trip.hops.some(h=>h.implausible)).toBe(false);
  expect(trajectoryFor(1).hops).toHaveLength(126);
  expect(roads.every(r=>r.distance_km>0)).toBe(true);
 });
 it('corrects look-alike plates and returns a real empty day',()=>{
  expect(fuzzyDistance('RJ-14-CB-22I0','RJ14CB2210')).toBe(.5);
  expect(trajectoryFor(4,'2026-09-24').found).toBe(false);
  expect(trajectoryFor(4,'2026-09-30').hops[1].implausible).toBe(true);
 });
 it('filters heatmap data and changes traffic intensity over time',()=>{
  expect(densityAt(9,'South Delhi')).toHaveLength(5);
  expect(densityAt(9,'South Delhi')[0]).toEqual(densityAt(9).find(d=>d.camera_id==='C26'));
  expect(densityAt(9)).toEqual(densityAt(9));
  expect(densityAt(9).reduce((s,d)=>s+d.count,0)).toBeGreaterThan(densityAt(3).reduce((s,d)=>s+d.count,0));
  const e=initialAlerts[0].evidence;
  expect(Number(e.implied_speed_kmh)).toBeCloseTo(Number(e.distance_km)/(Number(e.elapsed_seconds)/3600),0);
 });
});
describe('mock transport boundaries',()=>{
 it('logs purpose-limited search and supports profiles, attributes and workflow',async()=>{
  await mockApi('auth/login',{username:'admin',unit:'All Delhi'});
  await expect(mockApi('vehicles/search',{query:'DL01AB1234',reason:''})).rejects.toThrow('purpose');
  const found=await mockApi<{items:{plate:string}[]}>('vehicles/search',{query:'DL01AB1234',reason:'System evaluation DEMO-001'});
  expect(found.items[0].plate).toBe('DL01AB1234');
  const attributes=await mockApi<{items:{plate:string;colour:string}[]}>('attributes?vehicle_class=car&colour=White&plate_available=true');
  expect(attributes.items.some(v=>v.plate==='DL01AB1234')).toBe(true);
  expect(attributes.items.every(v=>v.colour==='White')).toBe(true);
  const workflow=await mockApi<{status:string}>('alerts/1/workflow',{status:'Acknowledged'});
  expect(workflow.status).toBe('Acknowledged');expect(audit.some(a=>a.action==='vehicle.search')).toBe(true);
  await mockApi('auth/login',{username:'viewer'});
  await expect(mockApi('vehicles/search',{reason:'DEMO-001'})).rejects.toThrow('Officer');
  await mockApi('auth/logout',{});
 });
});
