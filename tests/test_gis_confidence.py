from datetime import datetime, timedelta
import pytest
from anpr.config import IST
from anpr.gis import GISStore, sample_line
from anpr.vision import Read
from pipeline.live import LivePipeline


def test_local_density_is_road_aligned_time_sensitive_and_repeatable(tmp_path):
    store=GISStore(tmp_path)
    day=datetime(2026,10,1,tzinfo=IST)
    night=store.density(day+timedelta(hours=2),day+timedelta(hours=3))
    evening=store.density(day+timedelta(hours=18),day+timedelta(hours=19))
    assert evening['total_vehicles']>night['total_vehicles']*2
    assert evening['peak_hour']=='18:00'
    assert evening['storage']=='Local JSON files'
    assert evening==store.density(day+timedelta(hours=18),day+timedelta(hours=19))
    allowed=set()
    for road in store.routes['links'].values():
        allowed.update((round(lat,5),round(lon,5)) for lon,lat in sample_line(road['coordinates']))
    allowed.update((round(c['lat'],5),round(c['lon'],5)) for c in store.cameras)
    assert all((lat,lon) in allowed for lat,lon,_ in evening['points'])
    assert len(evening['cameras'])==40
    assert sum(c['vehicles'] for c in evening['cameras'])==evening['total_vehicles']
    assert store.density(day,day+timedelta(hours=1),'East Delhi')['total_vehicles']<night['total_vehicles']
    with pytest.raises(ValueError):store.density(day,day-timedelta(hours=1))
    route=store.route('C01','C34')
    assert route['cached'] is True and len(route['coordinates'])>2
    assert all(len(store.route('C01',c['id'])['coordinates'])>2 for c in store.cameras if c['id']!='C01')
    with pytest.raises(ValueError):store.route('unknown','C01')


def test_confidence_fields_preserve_engine_scores_and_raw_characters():
    class Engine:
        pass
    pipeline=LivePipeline(Engine(),{'plate':{'vote_threshold':.8,'detector_weights':None}})
    reading=Read('DLO1AB1234',.73,1.,({'character':'O','confidence':.42},),.67)
    result=pipeline.voted([([4,8,100,30],reading)],{'vote':0.})
    assert result['ocr_confidence']==.73
    assert result['plate_detection_confidence']==.67
    assert result['character_confidences']==[{'character':'O','confidence':.42}]
    assert result['low_confidence'] is True
    assert result['confidence_basis']=='per_detection_not_accuracy'


def test_same_plate_at_distinct_image_locations_is_not_deduplicated():
    import numpy as np
    class Engine:
        def read(self,image):
            return [{'text':'DL01AB1234','confidence':.91,'box':[[10,10],[110,10],[110,40],[10,40]]},
                    {'text':'DL01AB1234','confidence':.91,'box':[[200,10],[300,10],[300,40],[200,40]]}]
    pipeline=LivePipeline(Engine(),{'plate':{'detector_weights':None,'two_line_aspect_ratio':2.}})
    pipeline.crop=lambda *_:Read('DL01AB1234',.91,1.)
    candidates,_=pipeline.localise(np.zeros((400,600,3),dtype=np.uint8),'scene',{'localise':0.},lambda:None)
    assert len(candidates)==2
