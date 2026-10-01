"""Prepare one to three supplied clips and choose existing connected staged nodes."""
import argparse
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
import yaml
from anpr.live_cases import camera_graph
from pipeline.common import ROOT, digest


def choose(placements, cameras, edges):
    def visit(path):
        if len(path) == len(placements):
            return path
        pinned = placements[len(path)].get('camera_id', 'AUTO')
        for node in sorted(cameras):
            if node in path or pinned not in ('AUTO', node):
                continue
            if path and not 1 <= edges.get((path[-1], node), (0,))[0] <= 3:
                continue
            found = visit(path+[node])
            if found:
                return found
        return None
    chain = visit([])
    if not chain:
        raise ValueError('No connected 1–3 km chain satisfies the fixed camera placements')
    current = datetime.fromisoformat('2026-09-30T10:12:05')
    rows = []
    for i, (place, node) in enumerate(zip(placements, chain)):
        km = edges[chain[i-1], node][0] if i else 0
        gap = round(km/35*3600) if i else 0
        current += timedelta(seconds=gap)
        place.update(camera_id=node,start_ist=current.strftime('%H:%M:%S'))
        rows.append(dict(node=node,lat=cameras[node]['lat'],lon=cameras[node]['lon'],distance_km=round(km,3),gap_s=gap,speed_kmh=round(km/gap*3600,1) if gap else None))
    return rows


def prepare(paths=(), root=ROOT):
    dest=root/'frontend/public/videos/test-case';dest.mkdir(parents=True,exist_ok=True)
    # MP4 sources supplied for this task are already H.264/720p. Copy bytes unchanged.
    for source in map(Path, paths):
        target=dest/source.name
        if source.resolve()!=target.resolve():
            shutil.copyfile(source,target)
    files=sorted((p for p in dest.iterdir() if p.suffix.lower() in ('.mp4','.webm','.mov')),key=lambda p:p.name.lower())[:3]
    if not files:
        raise ValueError('Add at least one video to frontend/public/videos/test-case or pass source paths')
    config_path=root/'configs/test_case.yaml'
    config=yaml.safe_load(config_path.read_text(encoding='utf-8')) if config_path.exists() else {}
    existing={p['file']:p for p in config.get('placements',[])}
    placements=[dict(existing.get(p.name,{}),file=p.name,camera_id=existing.get(p.name,{}).get('camera_id','AUTO')) for p in files]
    cameras,edges=camera_graph(root)
    rows=choose(placements,cameras,edges)
    config.update(name=f'Same vehicle, {len(files)} cameras',expected_plate=config.get('expected_plate','DL04CT7391'),generated=True,staged=True,
                  date=config.get('date','2026-09-30'),placements=placements,clone_variant=False)
    config_path.write_text(yaml.safe_dump(config,sort_keys=False,allow_unicode=True),encoding='utf-8')
    manifest={**config,'placements':[{**p,'url':'/videos/test-case/'+p['file'],'sha256':digest(dest/p['file'])} for p in placements], 'legs':rows}
    (dest/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('Node | Latitude | Longitude | Distance km | Gap s | Speed km/h')
    for row in rows:print(' | '.join(str(v) for v in row.values()))
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('files',nargs='*');args=parser.parse_args();prepare(args.files)
