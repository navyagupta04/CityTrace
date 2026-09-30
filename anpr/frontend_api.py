"""Authenticated API adapters for the CityTrace React command centre."""
from datetime import datetime
from pathlib import Path
from typing import Literal
import json
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from .auth import DEMO_USERS
from .registry import MockRegistry, AuthorizedRegistry, masked_owner
from .plates import clean, normalize, weighted_distance
from .vision import Read, vote
from .models import PlateRead
from .db import canonical
from .alerts import list_alerts


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=128)
    unit: Literal['Central District', 'North District', 'South District'] = 'Central District'
    second_factor: str = Field(default='', max_length=12)


class SearchRequest(BaseModel):
    query: str = Field(default='', max_length=40)
    reason: str = Field(min_length=5, max_length=400)
    page: int = Field(default=1, ge=1)


class ReasonRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=400)


class WorkflowRequest(BaseModel):
    status: Literal['Open', 'Acknowledged', 'Escalated', 'Closed']
    assignee: str = Field(default='', max_length=80)
    note: str = Field(default='', max_length=500)


class OCRRequest(BaseModel):
    reads: list[PlateRead] = Field(min_length=1, max_length=120)


def register_frontend_api(app, platform, auth, settings):
    router = APIRouter(prefix='/api')
    db = platform.db
    registry = MockRegistry() if settings.demo_mode else AuthorizedRegistry()
    with db.transaction():
        db.conn.executescript('''CREATE TABLE IF NOT EXISTS alert_workflow (
            alert_id INTEGER PRIMARY KEY REFERENCES alerts(id) ON DELETE CASCADE,
            status TEXT NOT NULL, assignee TEXT NOT NULL, note TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS case_notes (
            id INTEGER PRIMARY KEY, identity_id INTEGER REFERENCES identities(id) ON DELETE CASCADE,
            username TEXT NOT NULL, timestamp TEXT NOT NULL, note TEXT NOT NULL);''')

    def current(authorization: str = Header(default='')):
        return auth.authenticate(authorization)

    def officer(user=Depends(current)):
        if user['role'] not in ('officer', 'admin'):
            raise HTTPException(403, 'Officer role required')
        return user

    def admin(user=Depends(current)):
        if user['role'] != 'admin':
            raise HTTPException(403, 'Admin role required')
        return user

    def set_session(response, request, tokens):
        result, refresh = tokens
        response.set_cookie('citytrace_refresh', refresh, max_age=28800, httponly=True, secure=request.url.scheme == 'https', samesite='strict', path='/api/auth')
        response.headers['Cache-Control'] = 'no-store'
        return result

    @router.get('/auth/config')
    def auth_config(request: Request, response: Response):
        has_session = False
        if request.cookies.get('citytrace_refresh'):
            try:
                auth.decode(request.cookies['citytrace_refresh'], 'refresh')
                has_session = True
            except HTTPException:
                response.delete_cookie('citytrace_refresh', path='/api/auth')
        response.headers['Cache-Control'] = 'no-store'
        return {'demo': settings.demo_mode, 'second_factor_supported': False,
                'has_session': has_session,
                'demo_users': DEMO_USERS if settings.demo_mode else [], 'units': ['Central District', 'North District', 'South District']}

    @router.post('/auth/login')
    def login(body: LoginRequest, response: Response, request: Request):
        if body.second_factor:
            raise HTTPException(422, 'Second-factor verification is not configured; leave the optional field empty.')
        return set_session(response, request, auth.login(body.username, body.password, body.unit))

    @router.post('/auth/refresh')
    def refresh(response: Response, request: Request):
        return set_session(response, request, auth.refresh(request.cookies.get('citytrace_refresh', '')))

    @router.post('/auth/logout')
    def logout(response: Response, request: Request):
        auth.logout(request.cookies.get('citytrace_refresh', ''))
        response.delete_cookie('citytrace_refresh', path='/api/auth')
        return {'ok': True}

    @router.get('/auth/me')
    def me(user=Depends(current)):
        return user

    @router.get('/users')
    def users(user=Depends(admin)):
        return db.rows('SELECT username,name,role FROM users ORDER BY username')

    @router.post('/vehicles/search')
    def search(body: SearchRequest, user=Depends(officer)):
        query = normalize(body.query).text
        rows = db.rows('''SELECT i.*,COUNT(d.id) AS sightings,MAX(d.timestamp) AS last_seen
                          FROM identities i JOIN detections d ON d.identity_id=i.id GROUP BY i.id''')
        matches = []
        for row in rows:
            distance = weighted_distance(query, row['plate']) if query else 0
            if not query or query in row['plate'] or distance <= 1.3:
                matches.append({**row, 'match_distance': distance})
        matches.sort(key=lambda r: (r['match_distance'], -r['confidence']))
        with db.transaction():
            db.audit(user['role'], 'plate.search', {'user': user['username'], 'query': body.query, 'reason': body.reason, 'results': len(matches)})
        return {'items': matches[(body.page-1)*20:body.page*20], 'total': len(matches), 'page': body.page}

    @router.post('/vehicles/{identity_id}/profile')
    def profile(identity_id: int, body: ReasonRequest, response: Response, user=Depends(officer)):
        rows = db.rows('SELECT * FROM identities WHERE id=?', (identity_id,))
        if not rows:
            raise HTTPException(404, 'Vehicle identity not found')
        identity = rows[0]
        with db.transaction():
            db.audit(user['role'], 'vehicle.profile', {'user': user['username'], 'plate': identity['plate'], 'reason': body.reason})
        from .trajectory import search as trajectory_search
        trajectory = trajectory_search(db, platform.graph, identity['plate'])
        evidence = [json.loads(r['payload']) | {'id': r['id']} for r in db.rows('SELECT id,payload FROM detections WHERE identity_id=? ORDER BY timestamp', (identity_id,))]
        try:
            record = registry.lookup(identity['plate'])
            record['owner'] = masked_owner()
        except NotImplementedError:
            record = {'provider': 'unavailable', 'demo': False, 'registration': None, 'owner': None, 'challans': []}
        alerts = [a for a in list_alerts(db, 500) if a['plate'] == identity['plate']]
        response.headers['Cache-Control'] = 'no-store'
        return {'identity': identity, 'trajectory': trajectory, 'evidence': evidence, 'registry': record,
                'confidence': min((h['confidence'] for h in trajectory['hops']), default=0), 'alerts': alerts,
                'watchlisted': bool(db.rows('SELECT plate FROM watchlist WHERE plate=?', (identity['plate'],))),
                'integrity': db.verify(), 'notes': db.rows('SELECT * FROM case_notes WHERE identity_id=? ORDER BY id DESC', (identity_id,))}

    @router.post('/vehicles/{identity_id}/owner')
    def owner(identity_id: int, body: ReasonRequest, response: Response, user=Depends(officer)):
        rows = db.rows('SELECT plate FROM identities WHERE id=?', (identity_id,))
        if not rows:
            raise HTTPException(404, 'Vehicle not found')
        with db.transaction():
            db.audit(user['role'], 'owner.unmask', {'user': user['username'], 'plate': rows[0]['plate'], 'reason': body.reason})
        response.headers['Cache-Control'] = 'no-store'
        try:
            return registry.lookup(rows[0]['plate'])['owner']
        except NotImplementedError:
            raise HTTPException(503, 'Authorized registry provider is not configured')

    @router.post('/vehicles/{identity_id}/notes')
    def notes(identity_id: int, body: ReasonRequest, user=Depends(officer)):
        if not db.rows('SELECT id FROM identities WHERE id=?', (identity_id,)):
            raise HTTPException(404, 'Vehicle not found')
        from .db import utcnow
        with db.transaction():
            db.conn.execute('INSERT INTO case_notes(identity_id,username,timestamp,note) VALUES (?,?,?,?)', (identity_id, user['username'], utcnow(), body.reason))
            db.audit(user['role'], 'case.note', {'user': user['username'], 'identity_id': identity_id})
        return {'ok': True}

    @router.get('/attributes')
    def attributes(vehicle_class: str = '', camera: str = '', colour: str = '', plate_available: bool = True,
                   min_confidence: float = Query(default=0, ge=0, le=1), user=Depends(officer)):
        rows = db.rows('SELECT d.*,i.vehicle_type FROM detections d JOIN identities i ON i.id=d.identity_id ORDER BY d.timestamp DESC') if plate_available else []
        items = []
        for row in rows:
            if vehicle_class and row['vehicle_type'] != vehicle_class or camera and row['camera_id'] != camera or row['confidence'] < min_confidence:
                continue
            evidence = json.loads(row['payload'])
            simulated = evidence.get('source') == 'simulator'
            color = MockRegistry().lookup(row['plate'])['registration']['colour'] if simulated else None
            if colour and colour != color:
                continue
            items.append({'id': row['id'], 'identity_id': row['identity_id'], 'plate': row['plate'], 'camera_id': row['camera_id'],
                          'timestamp': row['timestamp'], 'vehicle_class': row['vehicle_type'], 'colour': color,
                          'confidence': row['confidence'], 'attribute_source': 'simulated' if simulated else 'unavailable', 'snapshot': None})
        if not plate_available:
            for row in db.rows('SELECT * FROM traffic ORDER BY timestamp DESC'):
                if vehicle_class and row['vehicle_type'] != vehicle_class or camera and row['camera_id'] != camera or colour or min_confidence > 0:
                    continue
                items.append({'id': row['event_id'], 'identity_id': None, 'plate': None, 'camera_id': row['camera_id'], 'timestamp': row['timestamp'],
                              'vehicle_class': row['vehicle_type'], 'colour': None, 'confidence': None, 'attribute_source': 'unavailable', 'snapshot': None})
        with db.transaction():
            db.audit(user['role'], 'attribute.search', {'user': user['username'], 'class': vehicle_class, 'camera': camera, 'colour': colour})
        return {'items': items[:100], 'total': len(items), 'embedding_available': False, 'make_model_available': False}

    @router.get('/alerts/workflow')
    def workflows(user=Depends(officer)):
        states = {r['alert_id']: r for r in db.rows('SELECT * FROM alert_workflow')}
        return [{**a, **states.get(a['id'], {'status': 'Open', 'assignee': '', 'note': ''})} for a in list_alerts(db, 500)]

    @router.post('/alerts/{alert_id}/workflow')
    def workflow(alert_id: int, body: WorkflowRequest, user=Depends(officer)):
        if not db.rows('SELECT id FROM alerts WHERE id=?', (alert_id,)):
            raise HTTPException(404, 'Alert not found')
        with db.transaction():
            db.conn.execute('INSERT INTO alert_workflow VALUES (?,?,?,?) ON CONFLICT(alert_id) DO UPDATE SET status=excluded.status,assignee=excluded.assignee,note=excluded.note',
                            (alert_id, body.status, body.assignee, body.note))
            db.audit(user['role'], 'alert.workflow', {'user': user['username'], 'alert_id': alert_id, **body.model_dump()})
        return {'ok': True}

    @router.delete('/watchlist/{plate}')
    def remove_watch(plate: str, user=Depends(officer)):
        with db.transaction():
            count = db.conn.execute('DELETE FROM watchlist WHERE plate=?', (normalize(plate).text,)).rowcount
            db.audit(user['role'], 'watchlist.remove', {'user': user['username'], 'plate': plate})
        return {'deleted': count}

    @router.post('/ocr/vote')
    def ocr_vote(body: OCRRequest, user=Depends(officer)):
        text, confidence = vote([Read(**r.model_dump()) for r in body.reads])
        plate = normalize(text)
        return {'plate': text, 'confidence': confidence, 'valid': plate.valid, 'format': plate.format,
                'reads': [{**r.model_dump(), 'normalized': normalize(r.text).text} for r in body.reads]}

    samples = {'car-detection.mp4': 'Intersection traffic', 'person-bicycle-car-detection.mp4': 'Mixed road users'}

    @router.get('/video/samples')
    def video_samples(user=Depends(officer)):
        return [{'name': name, 'title': title, 'license': 'CC BY 4.0 · Intel IoT DevKit', 'url': f'/api/video/samples/{name}'} for name, title in samples.items()]

    @router.get('/video/samples/{name}')
    def video_sample(name: str, user=Depends(officer)):
        if name not in samples:
            raise HTTPException(404, 'Unknown sample')
        return FileResponse(Path(__file__).parent.parent / 'samples' / name, media_type='video/mp4')

    @router.get('/video/capabilities')
    def capabilities(user=Depends(officer)):
        return {'processing_available': False, 'reason': 'Neural job service is not configured. Use the local video CLI with model weights, or import per-frame analysis JSON to inspect overlays.', 'recorded_only': True}

    app.include_router(router)
