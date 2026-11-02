# Configurable alerts and database polling

CityTrace evaluates alerts immediately for `/api/ingest` observations. A background poller also scans the configured SQLite database every 2 seconds (override with `ANPR_POLL_INTERVAL_SECONDS`) for newly committed observations appended through the hash-chain-aware database API. The poller verifies the full evidence chain before evaluating anything. Raw SQL writes that break the chain are rejected from evaluation and appear as an integrity failure.

Alerts appear on the connected frontend's **Alert workspace**. `DataProvider` reloads `/api/alerts/workflow` every 30 seconds and refreshes sooner when `/ws/alerts` receives a new alert. Watchlist/restricted-hours and impossible-travel alerts use the common API feed. Alert evidence carries provenance metadata when the observation has it.

## Run the app

From the repository root, with the repository virtual environment and `.env` configured:

```powershell
.\.venv\Scripts\python.exe -m uvicorn anpr.api:app --host 127.0.0.1 --port 8001 --reload
```

Set the frontend to connected mode (`VITE_USE_MOCK=false`, API base `/api`) and open `http://127.0.0.1:5173`. Sign in with a demo officer account, then open **Alert workspace**.

## Append a database observation for the poller

The helper below appends a new hash-chained sighting for a plate that already has an identity in the configured database. It writes using the same append-chain routine as the app, not raw SQL. The running server should evaluate it within the polling interval; refresh the Alert workspace to see the resulting item.

```powershell
.\.venv\Scripts\python.exe scripts\manual_db_observation.py `
  --plate DL04CT7391 `
  --camera C01 `
  --timestamp "2026-11-03T10:00:00+05:30" `
  --confidence 0.98

.\.venv\Scripts\python.exe scripts\manual_db_observation.py `
  --plate DL04CT7391 `
  --camera C08 `
  --timestamp "2026-11-03T10:04:00+05:30" `
  --confidence 0.98
```

The second sighting is far enough away in four minutes to create a clone suspicion; the first append is a baseline. For an overspeed reading, append `--speed-kmph 92`. For wrong-way evaluation, set that camera's expected bearing in `configs/alert_rules.yaml` and pass `--direction 270` (or N/S/E/W). The bundled bearings are explicitly illustrative demo assumptions; replace them with surveyed values before operational use.

Manual observations need an existing canonical plate identity. Ingest a first sighting through the authenticated `/api/ingest` endpoint, then use the helper for an additional database observation. `/api/ingest` itself is evaluated immediately and does not wait for the poller.

## Rules

Edit `configs/alert_rules.yaml`, restart the API, and ingest/append a new observation to exercise the new values. The file is JSON syntax, which is a subset of YAML, so the core runtime needs no PyYAML package. The validated, read-only rules snapshot is available at `GET /api/alert-rules`.

For example, set `clone_plate.max_plausible_speed_kmph` from `140` to `120`, save, restart the API, then append a pair of sightings for one existing plate. `clone_plate.min_read_confidence`, `lookback_window_minutes`, overspeed limits/tolerance and wrong-way direction tolerance can be configured the same way. `overspeed.method` supports `camera_reported_speed` and `average_between_cameras`.

## Evidence and interpretation

Alerts are suspected anomalies and investigative leads for human review. They do not prove cloning, speeding, or unauthorized movement. Clone alerts include both detection IDs, camera names and coordinates, timestamps, confidence values, road distance, elapsed time, required minimum gap, and implied speed. Both detections remain in the immutable evidence chain. A low-confidence impossible leg produces a low-severity `needs_review` note rather than a clone alert.

The configured camera bearings are illustrative values for demonstrating the wrong-way rule, not verified roadway facts. Replace them with surveyed camera directions before operational use. Camera speed limits default to 50 km/h and can be overridden per camera or zone in the rules file.

## Demo alert scenarios

In connected frontend mode, sign in as the `admin` demo account and open **Alert workspace**. The demo panel is shown only when the backend reports demo mode. It writes to a separate `data/demo_injections.sqlite3` chain with provenance `simulated injection (demo)`; reset purges only that isolated chain and its watchlist entries.

The authenticated local endpoint accepts `clone`, `clone_simultaneous`, `blacklist`, `overspeed`, `wrong_way`, `restricted_hours`, `all`, and `reset`:

```powershell
$login = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8001/api/auth/login -ContentType 'application/json' -Body '{"username":"admin","password":"CityTrace@26127","unit":"Central District"}'
$token = $login.access_token
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8001/api/demo/inject -Headers @{ Authorization = "Bearer $token" } -ContentType 'application/json' -Body '{"scenario":"clone"}'
```

`clone` creates a five-minute impossible-travel pair and a separate 45-minute control pair. `overspeed` creates a 92 km/h reported-speed case plus a short average-speed pair. `wrong_way` uses the selected camera's configured bearing. Scenario responses list alert objects and detection IDs; the isolated demo database integrity result should remain valid. All items carry their simulated provenance in both the API evidence and alert workspace.

The two uploaded video observations remain in the primary database. Demo reset never removes or rewrites them.