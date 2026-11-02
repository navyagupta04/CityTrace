# Two video, two camera demo

This workflow runs OCR through the authenticated OCR Lab API, then ingests its accepted reads through `Platform.ingest`. SQLite remains the application system of record. When `DATABASE_URL` is configured, `scripts/sync_to_postgres.py` refreshes a clearly labeled, one-way PostgreSQL proof mirror named `citytrace`.

The video files are real footage. OCR candidates and votes are model estimates. Camera coordinates and event timestamps are staged/illustrative and do not identify filming locations. Patel Nagar and Moti Nagar coordinates are approximate. Investigative alerts require human review.

Current local authenticated OCR run: both files returned accepted `DL04CT7391`. Gemini-named clip: 5 candidates, vote confidence 0.8757, best frame 135 at 5.625 s (OCR confidence 0.9876). WhatsApp-named clip: 6 candidates, vote confidence 0.8662, best frame 105 at 4.375 s (OCR confidence 0.9935). These are confidence scores, not accuracy figures. Best crops and full result are under `output/two_video_evidence/` and `output/two_video_ocr_result.json` (ignored local artifacts).

## 1. PostgreSQL setup (one time)

PostgreSQL 18 is installed and its Windows service is running on this workstation. If it is stopped, open an elevated PowerShell and run `Start-Service postgresql-x64-18`. Do not install another server. If PostgreSQL is unavailable on another machine, Docker can run an isolated server instead:

```powershell
docker run --name citytrace-postgres -e POSTGRES_DB=citytrace -e POSTGRES_USER=citytrace_user -e POSTGRES_PASSWORD=<choose-a-local-password> -p 5432:5432 -d postgres:18
```

Use a PostgreSQL superuser password available in your local environment. In PowerShell, enter the supplied database commands interactively so the password does not appear in shell history:

```powershell
psql -U postgres -h localhost -d postgres
```

At the `postgres=#` prompt, create the demo role and database using the requested commands:

```sql
CREATE USER citytrace_user WITH PASSWORD '<placeholder>';
CREATE DATABASE citytrace OWNER citytrace_user;
\q
```

Replace `<placeholder>` with a local password. To keep it out of psql history, you can instead run `CREATE USER citytrace_user LOGIN;`, create the database, then use `\password citytrace_user` at the psql prompt; psql asks for the password without recording it as SQL.

Apply the mirror schema (use the PostgreSQL `bin` directory for `psql.exe` if it is not on `PATH`):

```powershell
psql -U citytrace_user -h localhost -d citytrace -f db/postgres_schema.sql
```

The app does not connect to Postgres. Create an ignored local `.env` from a hidden prompt; the password is not echoed or typed in the command history. The mirror script reads only `DATABASE_URL` and `ANPR_DATABASE` from this file. `.env` is ignored by Git; keep it local and do not commit it.

```powershell
$secret = Read-Host 'citytrace_user password' -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
try {
  $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
  $encoded = [uri]::EscapeDataString($plain)
  $url = "postgresql://citytrace_user:$encoded@localhost:5432/citytrace"
  Set-Content -LiteralPath .env -Value @("DATABASE_URL=$url",'ANPR_DATABASE=data/two_video_demo.sqlite3')
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
  Remove-Variable plain,encoded,url,secret,ptr
}
```

Keep `.env` local; `.env.example` contains placeholders only. The optional driver is installed with `python -m pip install -r requirements-postgres.txt`; the core backend does not import it unless a mirror sync is requested.

## 2. Start the backend and create the two OCR observations

From the repository root, in PowerShell terminal 1:

```powershell
$env:ANPR_DATABASE='data/two_video_demo.sqlite3'
.\.venv\Scripts\python.exe -m uvicorn anpr.api:app --host 127.0.0.1 --port 8002
```

In terminal 2, submit both exact files in one authenticated OCR Lab job. The command prompts for the local demo officer password without echoing it. Do not set a password in the command line.

```powershell
$env:CITYTRACE_API_BASE='http://127.0.0.1:8002/api'
.\.venv\Scripts\python.exe -m scripts.run_two_video_ocr
```

The runner reports each actual voted read, per-frame candidate and confidence. It saves the complete result and best-frame crop evidence to `output/two_video_ocr_result.json`. Review the reads before seeding. If either video has no accepted read, **stop here** and inspect the candidate frames/crops in that result; do not enter an expected or guessed plate.

## 3. Seed, verify, and refresh the Postgres mirror

Only run this after both video results show an accepted OCR read and the two accepted reads resolve to one canonical plate:

```powershell
.\.venv\Scripts\python.exe -m scripts.seed_two_video_demo
```

The first file is placed at the staged Patel Nagar node; the second is placed at Moti Nagar 15 minutes later. Stable event IDs make repeated runs idempotent. Both records go through `Platform.ingest`, preserving the OCR candidates, model confidence, evidence crop/frame, and provenance in the hash-chained evidence payload. If `DATABASE_URL` is set, this command refreshes the Postgres mirror and verifies its copied chain. With it unset, the script explicitly reports SQLite-only operation.

## 4. Open the UI

The two videos are bundled in the OCR Lab's test-case media directory and are byte-identical to the files under `videos/`. Both can also be played on the OCR Lab page while reviewing results.

For the full frontend in connected mode, start Vite in terminal 3:

```powershell
cd frontend
$env:VITE_USE_MOCK='false'
npm run dev
```

Open:

- Frontend: http://127.0.0.1:5173/#/ocr
- Backend API: http://127.0.0.1:8002/docs
- OpenAPI JSON: http://127.0.0.1:8002/openapi.json

Sign in as the documented local `officer` demo user. Click **OCR Lab**, upload or load the two video files, run the pipeline, inspect each per-frame candidate and best crop, then assign Video 1 to `CAM-PN-01` and Video 2 to `CAM-MN-01` in **Place on map**. Use the staged time values about 15 minutes apart and click **Create trajectory**. The route opens under Plate Trajectory with two markers and evidence. Each marker is labeled as staged; the OCR result is labeled as a model estimate.

With the connected-mode local configuration, Plate Trajectory searches the SQLite system of record served by the backend and renders saved sightings, staged camera placements, OCR evidence crops, and per-frame candidates. The video OCR job itself still needs a manual **Create trajectory** action in OCR Lab to make its temporary live case. SQLite remains the application system of record; PostgreSQL `citytrace` is the one-way proof mirror, not the API runtime database.

## 5. PostgreSQL proof queries

Connect with `psql -U citytrace_user -h localhost -d citytrace`. These queries use the schema's actual columns.

Two detections with camera/location and provenance:

```sql
SELECT d.plate, c.name AS camera_name, c.latitude, c.longitude,
       d.observed_at, d.confidence,
       d.payload::jsonb->>'source' AS source,
       d.payload::jsonb#>>'{metadata,provenance}' AS provenance,
       c.coordinate_accuracy, c.provenance AS camera_provenance
FROM detections d
JOIN cameras c USING (camera_id)
ORDER BY d.observed_at, d.id;
```

The observed Patel Nagar → Moti Nagar hop:

```sql
SELECT plate, previous_camera_id, camera_id, direction, observed_at,
       leg_distance_km, travel_seconds, speed_kmh, confidence, provenance
FROM trajectory_hops h
JOIN detections d ON d.id=h.detection_id
WHERE previous_camera_id='CAM-PN-01' AND camera_id='CAM-MN-01'
ORDER BY hop_order;
```

Latest full hash-chain verification recorded by the mirror refresh (the sync command recomputes each SHA-256 payload hash, link, count, and head):

```sql
SELECT value::jsonb AS mirror_hash_chain_verification
FROM metadata WHERE key='mirror_integrity';
```

## Reset and rerun

The OCR runner uses a temporary job upload and the OCR Lab purges it on completion. To reset only the isolated demo's SQLite data, stop the backend, then remove `data/two_video_demo.sqlite3` and its `-wal`/`-shm` companions. To reset the mirror, re-run the seed/mirror script after a fresh SQLite seed; the sync replaces the mirror snapshot atomically. Keep the Postgres database separate from synthetic seed data.

## Checks

Requested checks after implementation:

```powershell
.\.venv\Scripts\python.exe -m pytest tests pipeline/tests -q
cd frontend
npm test
npm run build
```

