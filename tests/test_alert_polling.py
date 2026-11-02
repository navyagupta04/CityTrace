"""Anomaly evaluation also catches committed, hash-valid database observations."""
import json
from datetime import datetime, timedelta, timezone


def test_external_append_is_polled_and_published_in_alert_feed(platform, event):
    first = platform.ingest(event())['detection']
    timestamp = (datetime.fromisoformat(first['timestamp']) + timedelta(minutes=4)).isoformat()
    payload = {
        'event_id': 'manual-db-observation-1', 'identity_id': first['identity_id'],
        'camera_id': 'C08', 'timestamp': timestamp, 'plate': first['plate'],
        'confidence': .98, 'vehicle_type': 'car', 'resolution': {'method': 'external'},
        'reads': [{'text': first['plate'], 'confidence': .98, 'quality': 1}],
        'source': 'manual database import', 'metadata': {'provenance': 'manual database import'}
    }
    with platform.db.transaction():
        appended = platform.db.append(payload)
    result = platform.poll_new_observations()
    clone = next(a for a in result['alerts'] if a['kind'] == 'cloned_plate')
    assert appended['id'] in clone['evidence']['detection_ids']
    assert clone['evidence']['provenance'] == 'manual database import'
    assert platform.db.verify()['valid']
    assert platform.poll_new_observations()['evaluated'] == 0


def test_invalid_chain_is_not_evaluated(platform, event):
    platform.ingest(event())
    with platform.db.transaction():
        platform.db.conn.execute("UPDATE detections SET payload='{}' WHERE id=1")
    result = platform.poll_new_observations()
    assert result['evaluated'] == 0
    assert result['error'] == 'hash-chain verification failed'


def test_fuzzy_ocr_variant_is_considered_for_clone_alert(platform, event):
    platform.ingest(event('DL01AB1234'))
    result=platform.ingest(event('DL01A81234',camera='C08',minutes=4))
    assert any(a['kind']=='cloned_plate' for a in result['alerts'])


def test_overspeed_tolerance_and_wrong_way_bearing(platform, event):
    platform.alert_engine.rules.wrong_way.expected_bearings_degrees={'C01':0}
    within=platform.ingest(event('DL02AB1234',speed_kmph=54,direction=60))['alerts']
    assert not any(a['kind'] in ('overspeed','wrong_way') for a in within)
    outside=platform.ingest(event('DL03AB1234',camera='C02',minutes=2,speed_kmph=56,direction=61))['alerts']
    assert any(a['kind']=='overspeed' for a in outside)
    platform.alert_engine.rules.wrong_way.expected_bearings_degrees={'C02':0}
    wrong=platform.ingest(event('DL05AB1234',camera='C02',minutes=4,direction=61))['alerts']
    assert any(a['kind']=='wrong_way' for a in wrong)


def test_clone_takes_precedence_over_average_speed_alert(platform, event):
    platform.alert_engine.rules.overspeed.method='average_between_cameras'
    platform.ingest(event())
    result=platform.ingest(event(camera='C08',minutes=4))
    assert any(a['kind']=='cloned_plate' for a in result['alerts'])
    assert not any(a['kind']=='overspeed' for a in result['alerts'])
