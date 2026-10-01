"""FastAPI entry point: uvicorn anpr.api:app --host 127.0.0.1."""
import asyncio
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import hmac
from pathlib import Path
from fastapi import FastAPI, Depends, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from .config import Settings, ROADS
from .models import IngestEvent, SimulationRequest, WatchRequest, PurgeRequest, TrafficEvent
from .platform import Platform
from .simulator import run
from .alerts import list_alerts
from .auth import Auth
from .frontend_api import register_frontend_api

ROLES = {'viewer': 0, 'officer': 1, 'admin': 2}


def create_app(database: str | None = None, settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    if not settings.demo_mode and not settings.api_key:
        raise RuntimeError('ANPR_API_KEY is required when ANPR_DEMO_MODE=false')
    platform = Platform(database or settings.database)
    auth_service = Auth(platform.db, settings.demo_mode)
    clients: dict[WebSocket, asyncio.Queue] = {}
    simulation_lock = asyncio.Lock()

    @asynccontextmanager
    async def lifespan(app):
        yield
        if hasattr(app.state, 'ocr_jobs'):
            await asyncio.to_thread(app.state.ocr_jobs.close)
        platform.db.close()

    app = FastAPI(title='NEXUS · City Traffic Intelligence', version='1.0.0', lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.platform = platform
    import os
    from fastapi.middleware.cors import CORSMiddleware
    origins = os.getenv('OCR_CORS_ORIGINS', 'http://127.0.0.1:5173,http://localhost:5173').split(',')
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True,
                       allow_methods=['GET','POST','DELETE'], allow_headers=['Authorization','Content-Type'])

    def require(minimum):
        def dependency(x_role: str = Header(default='viewer'), x_api_key: str = Header(default=''), authorization: str = Header(default='')):
            if authorization:
                user = auth_service.authenticate(authorization)
                if ROLES[user['role']] < ROLES[minimum]:
                    raise HTTPException(403, f'{minimum} role required')
                return user['role']
            if settings.api_key and not hmac.compare_digest(x_api_key, settings.api_key):
                raise HTTPException(401, 'Invalid API key')
            if x_role not in ROLES or ROLES[x_role] < ROLES[minimum]:
                raise HTTPException(403, f'{minimum} role required')
            return x_role
        return dependency

    async def publish(alerts):
        for alert in alerts:
            for queue in list(clients.values()):
                if queue.full():
                    queue.get_nowait()  # reconnect/REST feed is the authoritative backfill
                queue.put_nowait({'type': 'alert', 'alert': alert})

    @app.get('/', include_in_schema=False)
    def dashboard():
        built = Path(__file__).parent.parent / 'frontend' / 'dist' / 'index.html'
        return FileResponse(built if built.exists() else Path(__file__).parent / 'static' / 'index.html')

    build_dir = Path(__file__).parent.parent / 'frontend' / 'dist'
    if build_dir.exists():
        app.mount('/assets', StaticFiles(directory=build_dir / 'assets'), name='assets')

    @app.get('/favicon.svg', include_in_schema=False)
    def favicon():
        return FileResponse(Path(__file__).parent.parent / 'frontend' / 'public' / 'favicon.svg')

    @app.get('/docs', include_in_schema=False)
    def docs():
        return FileResponse(Path(__file__).parent / 'static' / 'docs.html')

    @app.get('/api/health')
    def health():
        return {'status': 'ok', 'mode': 'demo' if settings.demo_mode else 'gateway', 'version': '1.0.0', 'timezone': 'Asia/Kolkata'}

    @app.get('/api/cameras')
    def cameras(role=Depends(require('viewer'))):
        return {'cameras': [asdict(c) for c in platform.graph.cameras.values()],
                'roads': [{'from': a, 'to': b, 'distance_km': km, 'free_flow_kmh': free} for a, b, km, free in ROADS]}

    @app.post('/api/ingest')
    async def ingest(event: IngestEvent, role=Depends(require('officer'))):
        try:
            result = await run_in_threadpool(platform.ingest, event.model_dump(mode='json'))
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        await publish(result['alerts'])
        return result

    @app.post('/api/simulate')
    async def simulate(request: SimulationRequest, role=Depends(require('admin'))):
        if simulation_lock.locked():
            raise HTTPException(409, 'A simulation is already running')
        async with simulation_lock:
            start = datetime.now(timezone.utc).replace(hour=3, minute=0, second=0, microsecond=0)
            result = await run_in_threadpool(run, platform, request.vehicles, request.seed, start)
            await publish(result['new_alerts'])
            return result

    @app.post('/api/traffic')
    def traffic(event: TrafficEvent, role=Depends(require('officer'))):
        with platform.db.transaction():
            result = platform.db.conn.execute('INSERT OR IGNORE INTO traffic VALUES (?,?,?,?,?)',
                (event.event_id, event.camera_id, event.timestamp.isoformat(), event.vehicle_type, event.source))
            return {'accepted': True, 'duplicate': result.rowcount == 0, 'identified': False}

    @app.get('/api/trajectory')
    def trajectory(plate: str = Query(min_length=1, max_length=40), role=Depends(require('officer'))):
        return platform.search(plate, role)

    @app.get('/api/analytics/summary')
    def summary(role=Depends(require('viewer'))):
        result = platform.analytics()
        return {k: result[k] for k in ('summary', 'corridors', 'vehicles_per_minute')}

    @app.get('/api/analytics/origin-destination')
    def od(role=Depends(require('viewer'))):
        return platform.analytics()['origin_destination']

    @app.get('/api/analytics/heatmap')
    def heatmap(role=Depends(require('viewer'))):
        return platform.analytics()['heatmap']

    @app.get('/api/alerts')
    def alerts(limit: int = Query(default=100, ge=1, le=500), role=Depends(require('officer'))):
        return list_alerts(platform.db, limit)

    @app.get('/api/watchlist')
    def watchlist(role=Depends(require('officer'))):
        return platform.db.rows('SELECT * FROM watchlist ORDER BY created_at DESC')

    @app.post('/api/watchlist')
    def watch(request: WatchRequest, role=Depends(require('officer'))):
        try:
            return platform.watch(request.plate, request.reason)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.get('/api/audit')
    def audit(limit: int = Query(default=100, ge=1, le=1000), role=Depends(require('admin'))):
        return platform.db.rows('SELECT * FROM audit ORDER BY id DESC LIMIT ?', (limit,))

    @app.get('/api/integrity')
    def integrity(role=Depends(require('viewer'))):
        return platform.db.verify()

    @app.post('/api/purge')
    def purge(request: PurgeRequest, role=Depends(require('admin'))):
        try:
            return platform.db.purge(request.before.isoformat())
        except ValueError as error:
            raise HTTPException(409, str(error)) from error

    @app.websocket('/ws/alerts')
    async def websocket(ws: WebSocket):
        # Browsers cannot set X-Role on WebSocket; authenticate in the first
        # message instead of exposing API keys in URLs/logs.
        await ws.accept()
        try:
            auth = await asyncio.wait_for(ws.receive_json(), timeout=10)
            if not isinstance(auth, dict):
                await ws.close(code=1008)
                return
            role, key = auth.get('role', 'viewer'), auth.get('api_key', '')
            token = auth.get('token')
            if token:
                try:
                    role = auth_service.authenticate('Bearer ' + token)['role']
                except (HTTPException, TypeError):
                    await ws.close(code=1008)
                    return
            if role not in ('officer', 'admin') or not isinstance(key, str) or (not token and settings.api_key and not hmac.compare_digest(key, settings.api_key)):
                await ws.close(code=1008)
                return
            queue = asyncio.Queue(maxsize=500)
            clients[ws] = queue
            await ws.send_json({'type': 'connected'})

            async def sender():
                while True:
                    try:
                        message = await asyncio.wait_for(queue.get(), timeout=20)
                    except asyncio.TimeoutError:
                        message = {'type': 'heartbeat'}
                    if token:
                        try:
                            auth_service.authenticate('Bearer ' + token)
                        except HTTPException:
                            await ws.close(code=1008)
                            return
                    await ws.send_json(message)

            async def receiver():
                while True:
                    await ws.receive_text()

            tasks = [asyncio.create_task(sender()), asyncio.create_task(receiver())]
            try:
                done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    task.result()
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
        except (WebSocketDisconnect, asyncio.TimeoutError, asyncio.CancelledError, ValueError, TypeError):
            pass
        finally:
            clients.pop(ws, None)

    video_public = Path(__file__).resolve().parent.parent / 'frontend' / 'dist' / 'videos'
    if video_public.is_dir():
        app.mount('/videos', StaticFiles(directory=video_public), name='demo-videos')
    real_public = Path(__file__).resolve().parent.parent / 'frontend' / 'dist' / 'real'
    if real_public.is_dir():
        app.mount('/real', StaticFiles(directory=real_public), name='real-footage')
    from .gis import register_gis
    register_gis(app)
    register_frontend_api(app, platform, auth_service, settings)
    return app


app = create_app()
