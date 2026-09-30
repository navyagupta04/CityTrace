import json
import os
import hmac
import hashlib
import importlib.metadata
from datetime import datetime, timezone, timedelta
from ..common import ROOT,read,write,digest,now,expiry

def export(cfg,clips,payload,runtime,blur=False):
    from .events import events_and_trajectories
    out=ROOT/cfg['output'];events,trajectories=events_and_trajectories(clips,payload,cfg)
    models={name:importlib.metadata.version(name) for name in ['onnxruntime','supervision','opencv-python']}
    models.update(detector=cfg['detector']['name'],inference_backend='OpenCV DNN CPU',weights_sha256=digest(ROOT/cfg['detector']['weights']),plate_ocr='Not configured' if not cfg['plate']['detector_weights'] else 'Local models')
    provenance={'config_hash':cfg['config_hash'],'commit':cfg['commit'],'models':models}
    for record in events+trajectories:record.update(provenance)
    if cfg['privacy_settings'].get('pseudonymise'):
        salt=os.environ.get(cfg['privacy_settings']['salt_environment_variable'])
        if not salt:raise ValueError('Pseudonymisation requires the configured secret environment variable')
        def tokenise(value):
            if isinstance(value,dict):
                plate=value.get('plate');text=plate if isinstance(plate,str) else value.get('text') if value.get('status')=='read' else None
                if text:
                    from ..privacy import plate_token
                    value['plate_token']=plate_token(text,salt)
                for v in value.values():tokenise(v)
            elif isinstance(value,list):
                for v in value:tokenise(v)
        tokenise(payload);tokenise(events);tokenise(trajectories)
    for clip in clips:
        for kind in ['analysis','tracks','counts']:
            value=payload[clip['id']][kind]
            if isinstance(value,dict):value.update(provenance)
            else:
                for record in value:record.update(provenance)
            write(out/kind/(clip['id']+'.json'),value)
        if blur:
            from .redact import preview
            clip['redacted_video']=preview(clip,cfg)
    write(out/'events.json',events);write(out/'trajectories.json',trajectories)
    metrics={'status':'Not measured: no ground-truth labels','split':None,'n_tracks':sum(len(p['tracks']) for p in payload.values()),'n_eligible':None,'plate_accuracy_readable':None,'plate_accuracy_all':None,'cer':None,'coverage':None,'selective_accuracy':None,'by_condition':{},'coverage_curve':[],'error_cases':[],'error_categories':{},'confusion_matrix':{},'generated_at':now(),'source':'real','expires_at':expiry(cfg['privacy_settings']['reads_days']),**provenance}
    existing=json.loads((out/'metrics.json').read_text(encoding='utf-8')) if (out/'metrics.json').exists() else {}
    if not existing.get('split'):write(out/'metrics.json',metrics)
    write(out/'registry.json',read(ROOT/cfg['registry'],{}));write(out/'privacy.json',cfg['privacy_settings'])
    manifest={'version':1,'generated_at_ist':datetime.now(timezone(timedelta(hours=5,minutes=30))).isoformat(),'pipeline_commit':cfg['commit'],'config_hash':cfg['config_hash'],'models':models,'runtime_s':runtime,'source':'real','expires_at':expiry(cfg['privacy_settings']['reads_days']),'clips':clips,'files':{'events':'events.json','trajectories':'trajectories.json','metrics':'metrics.json','privacy':'privacy.json','registry':'registry.json'}}
    write(out/'manifest.json',manifest)
    report=ROOT/'docs/ACCURACY_REPORT.md'
    if not (out/'evaluation-frozen.json').exists():report.write_text('# Real-footage accuracy report\n\nNot measured: no ground-truth labels. The 90% target has not been demonstrated.\n\n'+f"Processed {len(clips)} licensed clips ({sum(c['duration_s'] for c in clips):.2f} seconds). YOLOX and ByteTrack produced {metrics['n_tracks']} tracks. These are unvalidated model tracks, not a ground-truth vehicle count. Runtime for this invocation: {runtime:.2f} seconds (cached stages may be reused).\n\n"+'No plate detector/OCR weights are configured; every track abstains. No accuracy, coverage, CER or confidence interval is asserted. Obtain consented readable-plate footage, label tracks blindly, split by video, tune on dev and freeze before evaluating test once.\n\nEligibility: human-readable plate, best plate height ≥ '+str(cfg['plate']['min_plate_height_px'])+' px. All-tracks accuracy also counts unreadable tracks and abstentions as incorrect. Wilson 95% intervals accompany measured values; small N is inadequate for a reliable target claim.\n\nModels: '+json.dumps(models)+'\n\nConfig hash: '+cfg['config_hash']+'\n',encoding='utf-8')

def purge(out):
    stamp=now();removed=0
    def clean(value):
        nonlocal removed
        if isinstance(value,list):
            result=[]
            for v in value:
                if isinstance(v,dict) and v.get('expires_at','9999')<stamp:removed+=1
                else:result.append(clean(v))
            return result
        if isinstance(value,dict):return {k:clean(v) for k,v in value.items()}
        return value
    for path in out.rglob('*.json'):
        if path.name=='purge-log.json':continue
        write(path,clean(json.loads(path.read_text())))
    manifest=out/'manifest.json'
    if manifest.exists():
        live={c.get(k) for c in json.loads(manifest.read_text()).get('clips',[]) for k in ['video','redacted_video']}
        for path in (out/'videos').glob('*.mp4'):
            if 'videos/'+path.name not in live:path.unlink()
    write(out/'purge-log.json',{'at':stamp,'removed_records':removed,'source':'real'});print(f'Purged {removed} expired records')
