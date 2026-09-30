import json
from pathlib import Path
import pytest
from anpr.plates import normalize
from anpr.vision import Read
from pipeline.stages.vote import aggregate
from pipeline.stages.counting import crossing,count_tracks
from pipeline.eval.metrics import compute,edit_distance,wilson
from pipeline.eval.split import split_videos
from pipeline.stages.export import purge

def test_vote_and_grammar():
    assert normalize('DL O1 AB 1234').text=='DL01AB1234'
    assert normalize('22BH1234AB').valid
    assert not normalize('XX01AB1234').valid
    assert aggregate([Read('DL01AB1234',.99)]*3)['text']=='DL01AB1234'
    assert aggregate([Read('DL01AB1234',.2)]*3)['status']=='abstain'
    assert aggregate([])['text'] is None

def test_finite_line_counting():
    assert crossing((.5,.2),(.5,.8),(.1,.5),(.9,.5))=='A→B'
    assert crossing((1,.2),(1,.8),(.1,.5),(.9,.5)) is None
    track={'track_id':1,'class':'car','dwell_s':3,'expires_at':'2099-01-01','frames':[{'frame':0,'box':[.4,0,.6,.2]},{'frame':30,'box':[.4,.6,.6,.8]},{'frame':60,'box':[.4,0,.6,.2]},{'frame':90,'box':[.4,.6,.6,.8]}]}
    result=count_tracks([track],[{'id':'line','start':[.1,.5],'end':[.9,.5]}],30)
    assert len(result['crossings'])==2 # one per direction, no jitter inflation

def test_metrics_abstain_counts_as_error():
    rows=[{'clip_id':'a','track_id':i,'plate':'DL01AB1234','prediction':'DL01AB1234' if i==0 else '', 'readable':'true','plate_height_px':30,'confidence':.95 if i==0 else 0,'condition':'day'} for i in range(2)]
    m=compute(rows);assert m['plate_accuracy_all']['value']==.5
    assert m['plate_accuracy_readable']['value']==.5
    assert m['coverage']==.5 and m['cer']==.5 and m['selective_accuracy']['value']==1
    assert wilson(1,2)==pytest.approx([.0945312,.9054688],abs=1e-6)
    assert edit_distance('ABC','ADC')==1

def test_video_split_disjoint():
    s=split_videos(['a','b','c','d','a']);assert s==split_videos(['d','c','b','a'])
    assert set(s['train']).isdisjoint(s['test']) and set(s['dev']).isdisjoint(s['test'])
    assert sum(map(len,s.values()))==4

def test_purge_only_expired(tmp_path):
    (tmp_path/'events.json').write_text(json.dumps([{'id':1,'expires_at':'2000-01-01'},{'id':2,'expires_at':'2999-01-01'}]))
    purge(tmp_path);assert json.loads((tmp_path/'events.json').read_text())==[{'id':2,'expires_at':'2999-01-01'}]
    assert json.loads((tmp_path/'purge-log.json').read_text())['removed_records']==1

def test_two_line_layout_and_hmac():
    from pipeline.stages.ocr import split_lines
    from pipeline.privacy import plate_token
    class Crop:
        shape=(40,60,3)
        def __getitem__(self,s):return s
    pieces=split_lines(Crop());assert pieces[0].stop==20 and pieces[1].start==20
    assert plate_token('DL-01 AB1234','secret')==plate_token('DL01AB1234','secret')
    assert plate_token('DL01AB1234','secret')!=plate_token('DL01AB1234','other')

def test_shared_frontend_voting_fixtures():
    from anpr.vision import vote
    for case in json.loads((Path(__file__).parent/'vote-parity.json').read_text()):
        text,confidence=vote([Read(**r) for r in case['reads']])
        assert text==case['text'] and confidence==case['confidence']

def test_staged_alert_arithmetic_and_empty_plates(tmp_path):
    from pipeline.stages.events import events_and_trajectories
    watch=tmp_path/'watch.yaml';watch.write_text('plates: [DL01AB1234]')
    clips=[{'id':'a','camera_id':'C10','start_ist':'2026-09-30T09:00:00+05:30','fps':10,'staged':True},{'id':'b','camera_id':'C34','start_ist':'2026-09-30T09:03:00+05:30','fps':10,'staged':True}]
    payload={c['id']:{'tracks':[{'track_id':1,'first_frame':0,'plate':{'text':'DL01AB1234','status':'read','vote_confidence':.95}}]} for c in clips}
    events,trajectories=events_and_trajectories(clips,payload,{'watchlist':str(watch),'privacy_settings':{'evidence_days':365},'clone_speed_limit_kmh':110})
    assert len(events)==3 and len(trajectories[0]['stops'])==2
    clone=next(e for e in events if e['type']=='clone_suspect')
    assert clone['staged'] and clone['elapsed_s']==180 and clone['implied_kmh']>110
    assert sum(f['points'] for f in clone['factors'])==85
    payload['a']['tracks'][0]['plate']['status']='abstain';payload['b']['tracks'][0]['plate']['status']='abstain'
    assert events_and_trajectories(clips,payload,{'watchlist':str(watch),'privacy_settings':{'evidence_days':365},'clone_speed_limit_kmh':110})==([],[])
