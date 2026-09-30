import json
from datetime import datetime, timezone
import pytest
from anpr.plates import normalize, weighted_distance
from anpr.vision import Read, vote, TrackAggregator
from anpr.simulator import run
from tools.process_video import ocr_candidates


@pytest.mark.parametrize('raw,expected,valid', [
    ('dl o1 ab i234', 'DL01AB1234', True), ('22 8H 12S4 AA', '22BH1254AA', True),
    ('XX01AB1234', 'XX01AB1234', False), ('DL1CAB1234', 'DL1CAB1234', True),
    ('not-a-plate', 'NOTAPLATE', False), ('DL01A1234', 'DL01A1234', True),
    ('20BH1234AA', '20BH1234AA', False), ('23BH1234AA', '23BH1234AA', True)])
def test_plate(raw, expected, valid):
    plate = normalize(raw)
    assert (plate.text, plate.valid) == (expected, valid)


@pytest.mark.parametrize('a,b,distance', [('O','0',.3), ('I','1',.3), ('B','8',.3), ('G','6',.3), ('D','0',.3), ('A','Q',1), ('ABC','AC',1), ('','ABC',3), ('AB','AB',0)])
def test_distance(a,b,distance):
    assert weighted_distance(a,b) == distance
    assert weighted_distance(b,a) == distance


def test_voting_and_low_quality():
    reads = [Read('DL01AB1234', .98)] * 4 + [Read('DL01AB1239', .5, .4)] * 2
    assert vote(reads)[0] == 'DL01AB1234'
    assert vote([Read('DL01AB1234', .5, .2)] * 6)[1] < .8
    assert vote([]) == ('', 0)
    assert vote([Read('!!', .9)]) == ('', 0)


def test_track_aggregator_one_pass():
    tracks = TrackAggregator()
    for i in range(6):
        tracks.add('5', i / 10, 'car', Read('DL01AB1234', .95))
    assert not tracks.flush(1)
    ready = tracks.flush(3)
    assert len(ready) == 1 and len(ready[0][1].reads) == 6
    assert not tracks.flush(5, True)


def test_graph(platform):
    assert platform.graph.shortest('C01','C08') == (13, ['C01','C04','C06','C08'])
    assert not platform.graph.possible('C01','C08',240)
    assert platform.graph.possible('C01','C08',600)
    with pytest.raises(ValueError):
        platform.graph.shortest('BAD','C08')


def test_fuzzy_link_upgrade_and_raw_evidence(platform,event):
    a = platform.ingest(event('DL01AB1239', confidence=.6))['detection']
    b = platform.ingest(event('DL01AB1234', camera='C04', minutes=8, confidence=.7))['detection']
    assert a['identity_id'] == b['identity_id']
    assert b['resolution']['method'] == 'fuzzy'
    assert platform.search('DL01AB1239')['plate'] == 'DL01AB1234'
    evidence = json.loads(platform.db.rows('SELECT payload FROM detections WHERE id=?',(a['id'],))[0]['payload'])
    assert evidence['reads'][0]['text'] == 'DL01AB1239'
    assert platform.db.verify()['valid']


@pytest.mark.parametrize('minutes,kind,confidence', [(1,'car',.6),(8,'truck',.6),(8,'car',.95),(60,'car',.6)])
def test_fuzzy_reject_speed_type_high_confidence_and_stale(platform,event,minutes,kind,confidence):
    a=platform.ingest(event())['detection']
    b=platform.ingest(event('DL01AB1239',camera='C04',minutes=minutes,vehicle_type=kind,confidence=confidence))['detection']
    assert a['identity_id'] != b['identity_id']


def test_late_event_checked_against_both_neighbors(platform,event):
    platform.ingest(event(camera='C01',minutes=0))
    first=platform.ingest(event(camera='C08',minutes=30))['detection']
    later=platform.ingest(event('DL01AB1239',camera='C01',minutes=29,confidence=.6))['detection']
    assert later['identity_id'] != first['identity_id']


@pytest.mark.parametrize('confidence,severity',[(.98,'HIGH'),(.6,'MEDIUM')])
def test_clone(platform,event,confidence,severity):
    platform.ingest(event(confidence=confidence))
    result=platform.ingest(event(camera='C08',minutes=4))
    alert=next(a for a in result['alerts'] if a['kind']=='cloned_plate')
    assert alert['severity']==severity
    assert alert['evidence']['distance_km']==13
    assert alert['evidence']['implied_speed_kmh']==195


def test_watchlist_exact_lookalike_and_restricted(platform,event):
    platform.watch('DL01AB1234','Case reference')
    assert platform.ingest(event())['alerts'][0]['severity']=='HIGH'
    platform.watch('DL01AO1234','Lookalike test')
    a=platform.ingest(event('DL01AD1234',camera='C04',minutes=8))
    # O/D are not directly a confusion pair; use letter slot invalid value for 0/O.
    assert not any(x['kind']=='watchlist' for x in a['alerts'])
    platform.watch('DL01AB1238','Second case')
    # Positional normalization can make a confusion exact; test preserved invalid string.
    b=platform.ingest(event('XL01AB1238',camera='C01',minutes=10))
    assert not b['alerts']
    restricted=platform.ingest(event('22BH1234AA',camera='C08',minutes=900))['alerts']
    assert restricted[0]['kind']=='restricted_zone'
    assert restricted[0]['evidence']['local_hour']==23


def test_lookalike_watchlist_rule_direct(platform,event):
    platform.watch('DL01AB1234','Case reference')
    # Invalid state stays raw; 0/D remains a 0.3 look-alike comparison.
    alerts=platform.ingest(event('0L01AB1234'))['alerts']
    assert alerts[0]['severity']=='MEDIUM' and 'verify visually' in alerts[0]['explanation']


def test_trajectory_inference_and_od_split(platform,event):
    platform.ingest(event())
    platform.ingest(event(camera='C08',minutes=20))
    platform.ingest(event(camera='C08',minutes=60))
    platform.ingest(event(camera='C06',minutes=70))
    t=platform.search('DL01AB1239')
    assert t['found'] and t['hops'][1]['inferred_cameras']==['C04','C06']
    assert t['total_distance_km']==19
    assert len(t['geojson']['coordinates'])==5
    data=platform.analytics()
    assert len(data['origin_destination'])==2
    assert data['summary']['speed_samples']==1


def test_congestion_and_empty(platform,event):
    assert platform.analytics()['summary']['network_average_speed_kmh'] is None
    platform.ingest(event(camera='C04'))
    platform.ingest(event(camera='C06',minutes=18))
    data=platform.analytics()
    corridor=next(c for c in data['corridors'] if c['from']=='C04' and c['to']=='C06')
    assert corridor['median_speed_kmh']==10 and corridor['level']=='congested'
    assert sum(c['count'] for c in data['heatmap'])==2
    assert sum(c['count'] for c in data['vehicles_per_minute'])==2


@pytest.mark.parametrize('mutation', ["UPDATE detections SET confidence=0 WHERE id=1", "UPDATE detections SET payload='{}' WHERE id=1", 'DELETE FROM detections WHERE id=2', 'DELETE FROM detections WHERE id=1'])
def test_tampering(platform,event,mutation):
    platform.ingest(event());platform.ingest(event(minutes=1))
    assert platform.db.verify()['valid']
    with platform.db.transaction():
        platform.db.conn.execute(mutation)
    assert not platform.db.verify()['valid']
    with pytest.raises(ValueError):
        platform.db.purge('2027-01-01T00:00:00+00:00')


def test_retention_prefix_append_and_out_of_order(platform,event):
    platform.ingest(event(minutes=0));platform.ingest(event(minutes=20));platform.ingest(event(minutes=1))
    result=platform.db.purge('2026-09-30T03:10:00+00:00')
    assert result['deleted']==1 and result['integrity']['valid']
    platform.ingest(event(minutes=30))
    assert platform.db.verify()['valid']
    result=platform.db.purge('2027-01-01T00:00:00+00:00')
    assert result['deleted']==3 and result['integrity']['valid']
    platform.ingest(event(minutes=40))
    assert platform.db.verify()['valid']


def test_idempotent_ingestion(platform,event):
    payload=event()
    a=platform.ingest(payload);b=platform.ingest(payload)
    assert b['duplicate'] and a['detection']['id']==b['detection']['id']
    assert platform.db.verify()['checked']==1


def test_seeded_simulation(platform):
    report=run(platform, vehicles=25, seed=12)
    assert report['integrity']['valid']
    assert len(report['accuracy'])==5
    assert report['summary']['active_cameras']==8
    assert {'watchlist','cloned_plate','restricted_zone'} <= {a['kind'] for a in report['new_alerts']}
    repeat=run(platform, vehicles=25, seed=12)
    assert not repeat['new_alerts']
    assert repeat['summary']==report['summary']


def test_paddle_result_adapter():
    assert ('DL01AB1234', .8) in ocr_candidates([{'rec_texts':['DL01','AB1234'],'rec_scores':[.9,.8]}])
    assert not ocr_candidates([{'rec_texts':['Hi'],'rec_scores':[.9]}])
