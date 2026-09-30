import pytest
from fastapi.testclient import TestClient
from anpr.api import create_app
from anpr.config import Settings


@pytest.fixture
def client():
    with TestClient(create_app(':memory:')) as client:
        yield client


def login(client, username='admin'):
    response = client.post('/api/auth/login', json={'username':username,'password':'CityTrace@26127','unit':'Central District'})
    assert response.status_code == 200
    return {'Authorization':'Bearer '+response.json()['access_token']}


def test_login_refresh_logout(client):
    config = client.get('/api/auth/config').json()
    assert config['demo'] and len(config['demo_users']) == 3 and not config['has_session']
    headers = login(client)
    assert client.get('/api/auth/me', headers=headers).json()['role'] == 'admin'
    assert client.get('/api/auth/config').json()['has_session']
    original = client.cookies.get('citytrace_refresh')
    refreshed = client.post('/api/auth/refresh')
    assert refreshed.status_code == 200
    assert client.cookies.get('citytrace_refresh') != original
    assert client.get('/api/users', headers=headers).status_code == 200
    client.post('/api/auth/logout')
    assert client.get('/api/auth/me', headers=headers).status_code == 401
    assert client.post('/api/auth/refresh').status_code == 401


def test_login_failure_audit_and_lockout(client):
    for _ in range(5):
        assert client.post('/api/auth/login', json={'username':'officer','password':'wrong'}).status_code == 401
    assert client.post('/api/auth/login', json={'username':'officer','password':'CityTrace@26127'}).status_code == 429
    headers = login(client)
    events = client.get('/api/audit',headers=headers).json()
    assert len([e for e in events if e['action']=='auth.login_failed']) == 6


@pytest.mark.parametrize('method,path,body',[
    ('get','/api/users',None),('post','/api/vehicles/search',{'reason':'Test case'}),
    ('post','/api/vehicles/1/profile',{'reason':'Test case'}),('post','/api/vehicles/1/owner',{'reason':'Test case'}),
    ('post','/api/vehicles/1/notes',{'reason':'Test note'}),('get','/api/attributes',None),
    ('get','/api/alerts/workflow',None),('post','/api/alerts/1/workflow',{'status':'Open'}),
    ('delete','/api/watchlist/DL01AB1234',None),('post','/api/ocr/vote',{'reads':[{'text':'DL01AB1234','confidence':.9}]}),
    ('get','/api/video/samples',None),('get','/api/video/samples/car-detection.mp4',None),('get','/api/video/capabilities',None)])
def test_new_endpoints_require_session_and_role(client,method,path,body):
    args = {'json':body} if body is not None else {}
    assert client.request(method,path,**args).status_code == 401
    headers=login(client,'viewer')
    assert client.request(method,path,headers=headers,**args).status_code == 403


def test_full_profile_workflow(client,event):
    headers=login(client,'officer')
    client.post('/api/watchlist',headers=headers,json={'plate':'DL01AB1234','reason':'Approved case'})
    client.post('/api/ingest',headers=headers,json=event())
    assert client.post('/api/vehicles/search',headers=headers,json={'query':'DL01'}).status_code == 422
    results=client.post('/api/vehicles/search',headers=headers,json={'query':'DL01','reason':'Approved case'}).json()
    identity=results['items'][0]['id']
    response=client.post(f'/api/vehicles/{identity}/profile',headers=headers,json={'reason':'Approved case'})
    profile=response.json()
    assert profile['registry']['demo'] and '••' in profile['registry']['owner']['name']
    assert response.headers['cache-control']=='no-store'
    unmasked=client.post(f'/api/vehicles/{identity}/owner',headers=headers,json={'reason':'Verify case owner'})
    assert unmasked.status_code==200 and unmasked.json()['name']=='Demo Registered Owner'
    assert client.post(f'/api/vehicles/{identity}/notes',headers=headers,json={'reason':'Checked recorded evidence'}).status_code==200
    alerts=client.get('/api/alerts/workflow',headers=headers).json()
    assert client.post(f'/api/alerts/{alerts[0]["id"]}/workflow',headers=headers,json={'status':'Acknowledged','assignee':'officer','note':'Review started'}).status_code==200
    assert client.get('/api/alerts/workflow',headers=headers).json()[0]['status']=='Acknowledged'
    assert client.delete('/api/watchlist/DL01AB1234',headers=headers).json()['deleted']==1
    assert client.get('/api/attributes?vehicle_class=car',headers=headers).json()['total']==1
    assert client.get('/api/attributes?vehicle_class=bus',headers=headers).json()['total']==0
    assert client.get('/api/attributes?colour=Red',headers=headers).json()['total']==0  # no fabricated real-video colours
    result=client.post('/api/ocr/vote',headers=headers,json={'reads':[{'text':'DL O1 AB I234','confidence':.95}]}).json()
    assert result['valid'] and result['plate']=='DL01AB1234'
    assert len(client.get('/api/video/samples',headers=headers).json())==2
    sample=client.get('/api/video/samples/car-detection.mp4',headers=headers)
    assert sample.status_code==200 and sample.headers['content-type']=='video/mp4'
    assert client.get('/api/video/samples/not-a-sample.mp4',headers=headers).status_code==404
    assert not client.get('/api/video/capabilities',headers=headers).json()['processing_available']
    with client.websocket_connect('/ws/alerts') as ws:
        ws.send_json({'token':headers['Authorization'][7:]})
        assert ws.receive_json()['type']=='connected'
    admin_headers=login(client)
    events=client.get('/api/audit',headers=admin_headers).json()
    assert any(e['action']=='owner.unmask' and 'Verify case owner' in e['details'] for e in events)
    assert not any('Demo Registered Owner' in e['details'] for e in events)


def test_gateway_hides_demo_accounts():
    with TestClient(create_app(':memory:',Settings(api_key='test-only',demo_mode=False))) as client:
        assert client.get('/api/auth/config').json()['demo_users']==[]
