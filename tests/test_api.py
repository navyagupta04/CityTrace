import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from anpr.api import create_app
from anpr.config import Settings


@pytest.fixture
def client():
    with TestClient(create_app(':memory:')) as client:
        yield client


ADMIN={'X-Role':'admin'}
OFFICER={'X-Role':'officer'}


def test_public_and_viewer_endpoints(client):
    root=client.get('/')
    assert root.status_code==200 and 'NEXUS' in root.text
    assert 'cdn.' not in root.text
    for path in ['/api/health','/api/cameras','/api/analytics/summary','/api/analytics/origin-destination','/api/analytics/heatmap','/api/integrity','/openapi.json','/docs']:
        assert client.get(path).status_code==200,path


@pytest.mark.parametrize('method,path,body',[
    ('get','/api/trajectory?plate=DL01AB1234',None),('get','/api/alerts',None),('get','/api/watchlist',None),
    ('post','/api/watchlist',{'plate':'DL01AB1234','reason':'Case reference'}),('post','/api/ingest',{}),
    ('post','/api/traffic',{}),('post','/api/simulate',{}),('get','/api/audit',None),
    ('post','/api/purge',{'before':'2027-01-01T00:00:00Z'})])
def test_viewer_denied(client,method,path,body):
    response=getattr(client,method)(path,**({'json':body} if body is not None else {}))
    assert response.status_code==403


def test_officer_vs_admin(client):
    assert client.get('/api/audit',headers=OFFICER).status_code==403
    assert client.post('/api/simulate',headers=OFFICER,json={}).status_code==403


def test_demo_scenario_isolated_alert_feed_and_reset(client):
    real = {'event_id':'real-main-db','camera_id':'C01','timestamp':'2026-11-03T10:00:00+05:30',
            'vehicle_type':'car','reads':[{'text':'DL01AB1234','confidence':.98}]}
    assert client.post('/api/ingest',headers=OFFICER,json=real).status_code==200
    result=client.post('/api/demo/inject',headers=ADMIN,json={'scenario':'clone'})
    assert result.status_code==200, result.text
    alerts=client.get('/api/alerts',headers=OFFICER).json()
    simulated=[a for a in alerts if a['evidence'].get('provenance')=='simulated injection (demo)']
    assert any(a['kind']=='cloned_plate' for a in simulated)
    assert result.json()['integrity']['valid']
    token=client.post('/api/auth/login',json={'username':'admin','password':'CityTrace@26127','unit':'Central District'}).json()['access_token']
    assert client.get('/api/alerts/workflow',headers={'Authorization':'Bearer '+token}).status_code==200
    reset=client.post('/api/demo/inject',headers=ADMIN,json={'scenario':'reset'})
    assert reset.status_code==200 and reset.json()['integrity']['valid']
    remaining=client.get('/api/alerts',headers=OFFICER).json()
    assert all(a['evidence'].get('provenance')!='simulated injection (demo)' for a in remaining)
    assert client.get('/api/trajectory?plate=DL01AB1234',headers=OFFICER).json()['found']


def test_all_scenarios_emit_configured_anomaly_types(client):
    response=client.post('/api/demo/inject',headers=ADMIN,json={'scenario':'all'})
    assert response.status_code==200, response.text
    kinds={a['kind'] for a in response.json()['alerts']}
    assert {'cloned_plate','watchlist','overspeed','wrong_way','restricted_zone'} <= kinds
    assert response.json()['integrity']['valid']
    assert client.post('/api/purge',headers=OFFICER,json={'before':'2027-01-01T00:00:00Z'}).status_code==403
    assert client.get('/api/cameras',headers={'X-Role':'root'}).status_code==403


def test_full_api_flow_and_audit(client,event):
    assert client.post('/api/watchlist',headers=OFFICER,json={'plate':'DL01AB1234','reason':'Case reference'}).status_code==200
    assert len(client.get('/api/watchlist',headers=OFFICER).json())==1
    response=client.post('/api/ingest',headers=OFFICER,json=event())
    assert response.status_code==200 and response.json()['alerts'][0]['kind']=='watchlist'
    assert client.get('/api/trajectory?plate=DL01AB1234',headers=OFFICER).json()['found']
    assert not client.get('/api/trajectory?plate=XY99QQ0000',headers=OFFICER).json()['found']
    assert len(client.get('/api/alerts',headers=OFFICER).json())==1
    audit=client.get('/api/audit',headers=ADMIN).json()
    assert len([row for row in audit if row['action']=='plate.search'])==2
    assert client.post('/api/simulate',headers=ADMIN,json={'vehicles':12,'seed':1}).status_code==200
    result=client.post('/api/purge',headers=ADMIN,json={'before':'2027-01-01T00:00:00Z'})
    assert result.status_code==200 and result.json()['integrity']['valid']


def test_frontend_watchlist_plate_alerts_on_next_sighting(client,event):
    token=client.post('/api/auth/login',json={'username':'officer','password':'CityTrace@26127','unit':'Central District'}).json()['access_token']
    headers={'Authorization':'Bearer '+token}
    saved=client.post('/api/watchlist',headers=headers,json={'plate':'DL5CQ5466','reason':'User requested watchlist test'} )
    assert saved.status_code==200, saved.text
    assert any(row['plate']=='DL5CQ5466' for row in client.get('/api/watchlist',headers=headers).json())
    result=client.post('/api/ingest',headers=headers,json=event('DL5CQ5466',camera='C07',minutes=2))
    assert result.status_code==200, result.text
    alert=next(a for a in result.json()['alerts'] if a['kind']=='watchlist')
    assert alert['severity']=='HIGH' and 'Suspected' in alert['explanation']
    feed=client.get('/api/alerts/workflow',headers=headers).json()
    assert any(a['id']==alert['id'] and a['plate']=='DL5CQ5466' for a in feed)
    assert client.get('/api/integrity',headers={'X-Role':'viewer'}).json()['valid']


def test_validation(client,event):
    payload=event();payload['reads'][0]['confidence']=2
    assert client.post('/api/ingest',headers=OFFICER,json=payload).status_code==422
    payload=event();payload['timestamp']='2026-01-01T00:00:00'
    assert client.post('/api/ingest',headers=OFFICER,json=payload).status_code==422
    payload=event();payload['camera_id']='C99'
    assert client.post('/api/ingest',headers=OFFICER,json=payload).status_code==422
    assert client.post('/api/simulate',headers=ADMIN,json={'vehicles':1001}).status_code==422
    assert client.post('/api/watchlist',headers=OFFICER,json={'plate':'nonsense','reason':'Case ref'}).status_code==422
    assert client.get('/api/alerts?limit=10000',headers=OFFICER).status_code==422
    assert client.post('/api/purge',headers=ADMIN,json={'before':'2026-01-01'}).status_code==422


def test_anonymous_traffic(client,event):
    payload=event();payload.pop('reads')
    assert client.post('/api/traffic',headers=OFFICER,json=payload).json()['identified'] is False
    assert client.post('/api/traffic',headers=OFFICER,json=payload).json()['duplicate'] is True
    summary=client.get('/api/analytics/summary').json()['summary']
    assert summary['detections']==1 and summary['unique_vehicles']==0 and summary['unidentified_passes']==1


def test_websocket_delivery_and_role(client,event):
    with client.websocket_connect('/ws/alerts') as ws:
        ws.send_json({'role':'officer'})
        assert ws.receive_json()['type']=='connected'
        client.post('/api/watchlist',headers=OFFICER,json={'plate':'DL01AB1234','reason':'Case reference'})
        client.post('/api/ingest',headers=OFFICER,json=event())
        assert ws.receive_json()['alert']['plate']=='DL01AB1234'
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect('/ws/alerts') as ws:
            ws.send_json({'role':'viewer'})
            ws.receive_json()


def test_gateway_key():
    with TestClient(create_app(':memory:',Settings(database=':memory:',api_key='test-only-value',demo_mode=False))) as client:
        assert client.get('/api/cameras').status_code==401
        assert client.get('/api/cameras',headers={'X-API-Key':'test-only-value'}).status_code==200
        assert client.get('/api/alerts',headers={'X-API-Key':'test-only-value'}).status_code==403
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect('/ws/alerts') as ws:
                ws.send_json({'role':'officer','api_key':'wrong'})
                ws.receive_json()
    with pytest.raises(RuntimeError):
        create_app(':memory:',Settings(database=':memory:',api_key='',demo_mode=False))
