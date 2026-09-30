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
