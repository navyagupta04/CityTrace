import { describe,it,expect } from 'vitest';
import { erasePlate,mergeSupplement,purgeBundle,type Supplement } from './loader';
import type { Bundle } from './types';
import { normalise } from '../demo/model';
import evidence from '../../public/real/user-case-bundle.json';

const base={manifest:{clips:[],config_hash:'original',models:{}},analysis:{},tracks:{},counts:{},events:[],trajectories:[],metrics:{status:'not_measured'},privacy:{retain_crops:false},registry:{}} as unknown as Bundle;
describe('uploaded two-vehicle evidence case',()=>{
 it('merges idempotently, preserving separate sightings and original evaluation',()=>{const first=mergeSupplement(base,evidence as Supplement),second=mergeSupplement(first,evidence as Supplement);expect(second.manifest.clips).toHaveLength(3);expect(second.events).toHaveLength(3);expect(second.trajectories[0].stops.map(s=>s.clip_id)).toEqual(['user-vehicle-a','user-vehicle-b','user-vehicle-c']);expect(second.metrics).toBe(base.metrics);expect(base.manifest.clips).toHaveLength(0);expect(second.privacy.retain_crops).toBe(false);});
 it('does not turn user confirmation or OCR confidence into a correct machine reading',()=>{for(const clip of evidence.clips){expect(normalise(clip.evidence.display_plate)).toBe('AI07204');expect(normalise(clip.evidence.ocr_text)).not.toBe('AI07204');expect(clip.evidence.identity_source).toBe('user_confirmed');expect(clip.staged).toBe(true);}expect(evidence.events.find(e=>e.type==='clone_suspect')?.sightings).toHaveLength(2);});
 it('removes reviewed identity/crop references as well as events on local erasure',()=>{const merged=mergeSupplement(base,evidence as Supplement),erased=erasePlate(merged,'AI07204');expect(erased.events).toHaveLength(0);expect(erased.trajectories).toHaveLength(0);expect(erased.manifest.clips.every(c=>!c.evidence)).toBe(true);expect(merged.manifest.clips[0].evidence).toBeDefined();});
 it('expires supplemental recordings and their identity records together',()=>{const purged=purgeBundle(mergeSupplement(base,evidence as Supplement),Date.parse('2026-11-01'));expect(purged.manifest.clips).toHaveLength(0);expect(purged.events).toHaveLength(0);expect(purged.trajectories).toHaveLength(0);});
 it('pairs the existing blue vehicle with the exact newly supplied clip for appearance review',()=>{const clone=evidence.events.find(e=>e.type==='clone_suspect')!;expect(clone.sightings?.map(s=>s.clip_id)).toEqual(['user-vehicle-a','user-vehicle-c']);expect(clone.basis).toBe('appearance_mismatch');expect(clone.review_reasons?.map(r=>r.code)).toContain('body_mismatch');expect(clone).not.toHaveProperty('implied_kmh');expect(evidence.clips.find(c=>c.id==='user-vehicle-c')?.evidence.original_filename).toBe('gemini_generated_video_bdab81d9.mp4');});
});
