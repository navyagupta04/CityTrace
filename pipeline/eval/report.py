import csv,json
from ..common import ROOT,write,now,digest
from .split import split_videos
from .metrics import compute
def evaluate(cfg,split):
    out=ROOT/cfg['output'];paths=sorted((ROOT/cfg['ground_truth']).glob('*.csv'));rows=[]
    if not paths:print('Not measured: no ground-truth labels. No test evaluation performed.');return
    for path in paths:
        with path.open(encoding='utf-8-sig',newline='') as stream:rows.extend(csv.DictReader(stream))
    split_path=ROOT/cfg['ground_truth']/'video-splits.json'
    if split_path.exists():splits=json.loads(split_path.read_text())
    else:splits=split_videos([r['clip_id'] for r in rows],cfg['seed']);write(split_path,splits)
    selected=[r for r in rows if r['clip_id'] in splits[split]]
    if not selected:print(f'No labelled tracks in {split}; not evaluated.');return
    freeze=out/'evaluation-frozen.json'
    if split=='test' and freeze.exists():raise ValueError('Held-out test evaluation is already frozen. Do not tune or rerun it; acquire an independent test set.')
    seen=set()
    for row in selected:
        key=(row['clip_id'],row['track_id'])
        if key in seen:raise ValueError('Duplicate ground-truth track')
        seen.add(key)
        tracks=json.loads((out/'tracks'/(row['clip_id']+'.json')).read_text(encoding='utf-8'));track=next((t for t in tracks if str(t['track_id'])==row['track_id']),None)
        row['prediction']=track['plate']['text'] if track and track['plate']['status']=='read' else '';row['confidence']=track['plate']['vote_confidence'] if track else 0
    metrics=compute(selected,cfg['plate']['min_plate_height_px']);previous=json.loads((out/'metrics.json').read_text(encoding='utf-8'));metrics={**previous,**metrics,'split':split,'config_hash':cfg['config_hash'],'commit':cfg['commit'],'generated_at':now(),'status':'Measured on labelled '+split+' videos'}
    metrics['target_met']=bool(metrics['plate_accuracy_readable'] and metrics['plate_accuracy_readable']['value']>=.9)
    if split=='test':write(freeze,{'config_hash':cfg['config_hash'],'labels':{p.name:digest(p) for p in paths},'at':now(),'splits':splits})
    write(out/'metrics.json',metrics)
    (ROOT/'docs/ACCURACY_REPORT.md').write_text('# Real-footage accuracy report\n\n'+('90% point-estimate target met. Examine N and the Wilson confidence interval before making reliability claims.' if metrics['target_met'] else '90% target not met. Tune only on dev; acquire more labelled consented footage.')+'\n\nEligibility: readable by a human and plate height >= '+str(cfg['plate']['min_plate_height_px'])+'px. Abstentions count as incorrect. Split unit is video. All-tracks accuracy includes every labelled track.\n\n```json\n'+json.dumps(metrics,indent=2)+'\n```\n',encoding='utf-8')
    print(json.dumps(metrics,indent=2))
