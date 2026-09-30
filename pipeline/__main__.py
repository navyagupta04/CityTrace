"""Offline, resumable real-footage processing. Run from the repository root."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')
import argparse
import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from .common import ROOT, config, read, write, digest, now, expiry

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['run-all','ingest','detect-track','read-plates','evaluate','export','purge-expired','build-delhi-roads','label-tracks'])
    p.add_argument('--config',default='configs/demo.yaml');p.add_argument('--split',choices=['train','dev','test'],default='dev');p.add_argument('--blur-plates',action='store_true');p.add_argument('--clip');p.add_argument('--force',action='store_true')
    args=p.parse_args();cfg=config(args.config);out=ROOT/cfg['output'];cache=ROOT/cfg['cache'];cache.mkdir(parents=True,exist_ok=True)
    if args.command=='build-delhi-roads':
        from .tools.build_delhi_roads import build
        return build(cfg)
    if args.command=='purge-expired':
        from .stages.export import purge
        return purge(out)
    if args.command=='label-tracks':
        from .tools.label_tracks import serve
        return serve(cfg,args.clip)
    if args.command=='evaluate':
        from .eval.report import evaluate
        return evaluate(cfg,args.split)
    from .stages.ingest import ingest
    started=time.perf_counter();clips=[];detector=None;payload={}
    for placement in read(ROOT/cfg['placements']).get('clips',[]):
        if not (ROOT/placement['file']).exists():
            print(f"Skipping missing clip: {placement['file']}");continue
        clip=ingest(placement,cfg);clips.append(clip)
        if args.command=='ingest':continue
        key=digest(ROOT/placement['file'])+'-'+cfg['config_hash']+'-'+digest(ROOT/cfg['detector']['weights'])
        cached=cache/(placement['id']+'.json')
        saved=json.loads(cached.read_text()) if cached.exists() else {}
        if saved.get('key')==key and not args.force:
            analysis,tracks=saved['analysis'],saved['tracks'];print(f"{clip['id']}: cached detection/tracking",flush=True)
        else:
            from .stages.detect_track import Detector,run
            detector=detector or Detector(cfg['detector']);analysis,tracks=run(clip,cfg,detector)
            write(cached,{'key':key,'analysis':analysis,'tracks':tracks})
        if args.command in ('run-all','read-plates','export'):
            from .stages.ocr import read_plates
            read_plates(clip,analysis,tracks,cfg)
        from .stages.counting import count_tracks
        lines=read(ROOT/cfg['counting_lines']).get('clips',{}).get(clip['id'],[])
        counts=count_tracks(tracks,lines,clip['fps']);counts.update(lines=lines,source='real',expires_at=expiry(cfg['privacy_settings']['reads_days']))
        payload[clip['id']]={'analysis':analysis,'tracks':tracks,'counts':counts}
    if args.command=='ingest':write(cache/'ingest.json',clips);return
    from .stages.export import export
    export(cfg,clips,payload,time.perf_counter()-started,args.blur_plates)
    print(f"Exported {len(clips)} clips to {out}",flush=True)

if __name__=='__main__':main()
