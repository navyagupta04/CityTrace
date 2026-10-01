// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { beforeEach,afterEach,describe,it,expect,vi } from 'vitest';
import { HashRouter } from '../router';
import RealAlerts from './RealAlerts';
import { mergeSupplement, type Supplement } from './loader';
import type { Bundle } from './types';
import evidence from '../../public/real/user-case-bundle.json';

const testState=vi.hoisted(()=>({role:'officer',save:vi.fn(),record:vi.fn()}));
const base={manifest:{clips:[],config_hash:'original',models:{}},analysis:{},tracks:{},counts:{},events:[],trajectories:[],metrics:null,privacy:{},registry:{}} as unknown as Bundle;
vi.mock('../session',()=>({useSession:()=>({session:{user:{role:testState.role}}})}));
vi.mock('../demo/api',()=>({record:(...args:unknown[])=>testState.record(...args)}));
vi.mock('./context',()=>({useRealFootage:()=>({bundle:mergeSupplement(base,evidence as Supplement),workflow:{},setWorkflow:testState.save})}));
let host:HTMLDivElement,root:Root;
beforeEach(()=>{
 testState.role='officer';vi.clearAllMocks();Object.assign(globalThis,{IS_REACT_ACT_ENVIRONMENT:true});
 if(!HTMLDialogElement.prototype.showModal)Object.defineProperty(HTMLDialogElement.prototype,'showModal',{configurable:true,value(){}});
 if(!HTMLDialogElement.prototype.close)Object.defineProperty(HTMLDialogElement.prototype,'close',{configurable:true,value(){}});
 vi.spyOn(HTMLDialogElement.prototype,'showModal').mockImplementation(function(this:HTMLDialogElement){this.setAttribute('open','');});
 vi.spyOn(HTMLDialogElement.prototype,'close').mockImplementation(function(this:HTMLDialogElement){this.removeAttribute('open');});
 host=document.createElement('div');document.body.append(host);root=createRoot(host);
});
afterEach(async()=>{await act(async()=>root.unmount());host.remove();vi.restoreAllMocks();});
async function openCase(){
 await act(async()=>root.render(<HashRouter><RealAlerts/></HashRouter>));
 const button=[...host.querySelectorAll('button')].find(b=>b.textContent==='Review both vehicles')!;
 await act(async()=>button.click());
 return host.querySelector('dialog')!;
}
describe('new video plate cloning review',()=>{
 it('opens exactly the requested pair, explains the reason and seeks both source videos',async()=>{
  const dialog=await openCase();
  expect(dialog.textContent).toContain('Different vehicle body structure');
  expect(dialog.textContent).toContain('Colour supports the body mismatch');
  expect(dialog.textContent).toContain('Raw OCR disagrees');
  expect(dialog.textContent).toContain('No impossible-travel claim');
  expect(dialog.querySelector('[data-provenance="generated"]')).not.toBeNull();
  expect(dialog.textContent).toContain('gemini_generated_video_bdab81d9.mp4');
  expect(dialog.textContent).not.toContain('Night dark sedan');
  const videos=[...dialog.querySelectorAll('video')];
  expect(videos.map(v=>v.getAttribute('src'))).toEqual(['/real/user/user-vehicle-a.mp4','/real/user/user-vehicle-c.mp4']);
  await act(async()=>videos.forEach(v=>v.dispatchEvent(new Event('loadedmetadata'))));
  expect(videos[0].currentTime).toBeCloseTo(evidence.clips[0].evidence.time_s);
  expect(videos[1].currentTime).toBeCloseTo(136/24);
  expect(dialog.textContent).toContain(evidence.clips[2].sha256);
  expect(dialog.querySelector('video[src$="user-vehicle-c.mp4"]')?.hasAttribute('poster')).toBe(false);
  expect([...dialog.querySelectorAll('img')].every(img=>!img.src.includes('undefined'))).toBe(true);
  expect(testState.record).toHaveBeenCalledWith('real.alert.evidence_viewed',{id:'clone-ai07204',clip_ids:['user-vehicle-a','user-vehicle-c']});
 });
 it('masks confirmed and raw plate text for a viewer and restricts footage',async()=>{
  testState.role='viewer';const dialog=await openCase();
  expect(dialog.textContent).not.toContain('AI 0720-4');
  expect(dialog.textContent).not.toContain('A1 0720-4');
  expect(dialog.textContent).not.toContain('OA0720');
  expect(dialog.getAttribute('aria-label')).not.toContain('AI 0720-4');
  expect(dialog.querySelectorAll('video')).toHaveLength(0);
  expect(dialog.querySelectorAll('img')).toHaveLength(0);
  expect(dialog.textContent).toContain('Raw footage restricted');
 });
 it('saves the review through the existing workflow',async()=>{
  const dialog=await openCase();const form=dialog.querySelector('form')!;
  await act(async()=>form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})));
  expect(testState.save).toHaveBeenCalledOnce();
  const workflowUpdate=testState.save.mock.calls[0][0];
  expect(workflowUpdate({})).toEqual({'clone-ai07204':{status:'Open',assignee:'',note:''}});
  expect(host.querySelector('dialog')).toBeNull();
 });
});
