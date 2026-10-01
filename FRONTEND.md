# Current operations update · 1 October 2026

The OCR Lab now includes a local authenticated upload/job panel above all existing panels. Camera Health Intelligence replaces the wall (`/wall` redirects), five supplied recordings play in Live Monitoring, and density analytics no longer has a footage tab. Compact provenance chips and Data sources distinguish modelled, sample, recorded, measured, and live-upload results.

See [live OCR setup, limits, privacy and exact commands](docs/OCR_LAB_LIVE.md) and [changed files](docs/OCR_LAB_LIVE_FILES.md). The frontend still defaults to its existing in-memory access profile; the OCR panel can separately sign in to the local backend. OCR never runs in the browser. Five-stream playback metrics cannot supply network latency, camera hardware uptime or plate-read success without their source data, so those values remain unmeasured.

The following historical implementation notes are retained for context; where they describe the old wall, footage analytics tab or preview-only OCR, this current update takes precedence.

# CityTrace Delhi command console

The current build is a **frontend-only React demo**. `VITE_USE_MOCK` defaults to `true`; the typed adapter resolves deterministic in-memory data with 180 ms simulated latency. No production authentication, registry connector or browser OCR is provided. A separate offline pipeline now exports real recorded-video detections. The existing Python implementation is retained separately below.


## Real footage update · 1 October 2026

Open **Live monitoring** or **Video analysis** for the default real recording workspace. It loads `/real/manifest.json`, plays the licensed clips, draws model boxes and counting lines, and seeks to each track’s best frame. Counting, colour and dwell are unvalidated model estimates from recorded clips, not city traffic. No new frontend runtime dependency was added.

The new **Real footage** analytics tab, **Measured on real footage** OCR panel, **Deep dive**, **Privacy & DPDP**, and synthetic registry extension are available. Existing seed 26127, 1,842 sightings, scripted plates and 30-second scenario remain unchanged. Human-facing placeholder wording was replaced with explicit synthetic/simulated source labels. Internal adapter names and environment flags remain compatible.

The samples contain no supplied readable-plate labels or configured plate models. Accepted real plates, identity alerts and real plate trajectories are therefore empty. Real trajectory, search-match, profile and alert evidence components consume those exports when populated; they do not manufacture a plate to demonstrate the flow. Use **DL01AB1234** in the synthetic trajectory section to test a full Delhi route.

Offline real roads are on by default: 3.1 MB OSM extract, snapped illustrative cameras and 119/130 directed route geometries. Eleven links retain fallback geometry. Region zoom, heatmaps and the schematic toggle remain available. Road routing does not model turn restrictions and is not a navigation system.

The privacy page is an admin demo workspace. Raw video is blocked for Viewer unless a redacted preview is supplied. Masking does not secure the static data. Rights requests, audit and frontend erasure/purge are in memory; permanent local bundle purge is a pipeline command. Keep the app bound to localhost.

See [pipeline commands and limitations](pipeline/README.md), [measured report](docs/ACCURACY_REPORT.md), [data licences](docs/DATA_AND_LICENSES.md), [privacy controls](docs/PRIVACY_DPDP.md), and [complete changed-file list](docs/REAL_FOOTAGE_FILES.md). The older gateway/CLI notes below describe the retained legacy implementation, not the default frontend adapter.

## Try it now

Open http://127.0.0.1:8000/?v=delhi-final#/trajectories and click **Sign in to command centre**. `admin` / `demo` is pre-filled; these are demo labels and no credentials are validated. Use the Demo access panel to try Officer or Viewer. Viewer sees masked plate badges and cannot open investigation pages.

1. Enter **DL01AB1234**, keep the demo case reference, and click **Track trajectory**. On 30 September 2026 this shows 18 stops, a 94.8 km route, 280 minutes of scripted dwell, and an 8h 41m observation span. Click **Replay journey**, scrub the slider, choose a speed, click timeline stops and inspect the synthetic CCTV scene below.
2. **RJ14CB2210** is the second route. **RJ14CB22I0** deliberately tests an OCR look-alike: accept the 0.5-distance suggestion. **UP16AX9912** is the scripted watchlist scenario. **DL08CX9090** is the impossible-travel example.
3. Select a region in the map or scope control. All Delhi shows the full NCT boundary; regional views zoom to five camera nodes. These eight operational regions are illustrative groupings, not official district boundaries.
4. Open **Density & analytics**. Play the 24-hour heatmap time-lapse, choose a region/date, inspect speed colours, the OD matrix, ranked hotspots, or daily Trends. Counts are generated from a separate seeded traffic model, not an accuracy benchmark or counts extracted from the clips.
5. Open **Attribute search** and choose **White cars**: 27 synthetic identities match, including DL01AB1234. Combine class, colour, make, region, camera and confidence filters. Results are paginated and link to trajectories. When the selected date has no readings, trajectory search switches to that vehicle's latest demo date.
6. Open **Live monitoring**. **Recorded traffic samples** is now the default, with pipeline overlays. Animated Delhi scenes remain available under **Simulated Delhi CCTV**. There are two real, locally bundled Intel clips (30.16 seconds and 53.92 seconds). These clips are not Delhi footage and are not evidence for the generated number plates.
7. Run the 30-second demo scenario, navigate to Alerts, and review the new watchlist and impossible-travel alerts. The review dialog shows additive priority factors and distance / elapsed-time arithmetic. Save a workflow change, then inspect Audit log.
8. OCR Lab contains a simulated accuracy benchmark and a small Confirm / Correct / Reject queue, plus the existing text-read voting playground. Control room wall combines the map, four feeds, rotating historical reads and alerts; Full screen works through the browser Fullscreen API.

## Dataset and state

- 40 cameras, 65 undirected synthetic road links, 160 identities, 1,842 sightings.
- Searchable observation dates: 24–30 September 2026; 720 modeled hourly traffic buckets across September.
- DL01AB1234 has 126 sightings across seven days. Number plates, owners, appearances, scores, OCR performance and forecasts are synthetic.
- `src/demo/model.ts` is the seeded source of truth, using seed 26127. `src/demo/api.ts` provides search, profile, registry, watchlist, audit, notes, workflow and sample-video responses.
- synthetic authentication, theme, interactions and datasets are held in memory. Reload resets all demo state. **Reset scenario** restores only seeded alerts, preserving the session and audit history.
- Trajectories support GeoJSON download and browser print/PDF. Traffic CSV downloads include a UTF-8 BOM.
- Shared scenario/ticker timers and animated feeds pause when the document is hidden. CSS respects reduced motion.

## Run without Python

```sh
cd frontend
npm ci
npm run dev
```

The Vite server supplies the app and videos. For a static build: `npm run build` then `npm run preview`. The included FastAPI server also serves `frontend/dist` and `/videos` at port 8000. The original backend APIs still run independently; set `VITE_USE_MOCK=false` only when deliberately testing the legacy adapter. Newly added Delhi trajectory, traffic and attribute workspaces are demonstration modules, not production integrations.

## Sources and licensing

The original Delhi boundary is bundled unchanged in `frontend/src/demo/delhi-boundary.json`. Source: [DataMeet Delhi Municipal Spatial Data](https://github.com/datameet/Municipal_Spatial_Data/blob/master/Delhi/Delhi_Boundary.geojson), under the Delhi-specific [CC BY-SA 2.5 India](https://creativecommons.org/licenses/by-sa/2.5/in/) license. The data provider's Delhi notice takes precedence over its repository-wide license default. Projection, camera nodes and schematic road links are added for the demo. Attribution is displayed on every map and included in `src/demo/ATTRIBUTION.txt`.

The two original clips are from [Intel IoT DevKit sample-videos](https://github.com/intel-iot-devkit/sample-videos), under CC BY 4.0. Full license and source attribution ship in `frontend/public/videos/` and `samples/`. No outside network is needed during the demo.

## Files changed for this update

Created:

- `frontend/.env.example`
- `frontend/src/constants/city.ts`
- `frontend/src/demo/model.ts`, `model.test.ts`, `api.ts`, `context.tsx`, `delhi-boundary.json`, `ATTRIBUTION.txt`
- `frontend/src/router.tsx`, `frontend/src/demo.css`
- `frontend/src/components/SimulatedFeed.tsx`, `AlertEvidence.tsx`, `OCRDemo.tsx`
- `frontend/src/pages/Trajectory.tsx`, `Traffic.tsx`, `Attributes.tsx`, `Live.tsx`
- `frontend/public/MAP-ATTRIBUTION.txt`
- `frontend/public/videos/car-detection.mp4`, `person-bicycle-car-detection.mp4`, `ATTRIBUTION.md`, `LICENSE-CC-BY-4.0.txt`

Updated:

- `frontend/src/App.tsx`, `main.tsx`, `api.ts`, `data.tsx`, `types.ts`, `utils.ts`, `utils.test.ts`
- `frontend/src/components/NetworkMap.tsx`, `UI.tsx`
- `frontend/src/pages/Overview.tsx`, `SignIn.tsx`, `Search.tsx`, `Profile.tsx`, `Intelligence.tsx`
- `frontend/package.json`, `package-lock.json`, `vite.config.ts`
- `frontend/dist/` (regenerated production assets and bundled videos)
- `anpr/api.py` (local static video mount)
- `FRONTEND.md`, `README.md`, `VERIFICATION.md`

No dependency was added. Leaflet, React Router and Leaflet type declarations were removed; SVG rendering and a small history router now handle those features. Existing React, Vite, TypeScript, Tailwind, Framer Motion, Lucide and Recharts remain.

---

# Previous backend-connected frontend reference

The section below documents the previous adapter and real Python APIs. Its authentication and model-integration details do **not** describe the current in-memory demo mode.

# CityTrace React frontend

The current application is **React + TypeScript + Vite**, with Tailwind CSS, Framer Motion, locally bundled Leaflet, Recharts and Lucide icons. Source lives in `frontend/src`; the production build in `frontend/dist` is served by FastAPI at `/`. Hash-based routing supports direct links without an SPA catch-all intercepting API requests.

## Start

The production build is included. Install Python requirements and start FastAPI:

```sh
python -m pip install -r requirements-dev.txt
python -m uvicorn anpr.api:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. In demo mode the sign-in screen's **Demo access** panel can fill any of the three credentials:

| User ID | Password | Role |
|---|---|---|
| `admin` | `CityTrace@26127` | Admin |
| `officer` | `CityTrace@26127` | Officer |
| `viewer` | `CityTrace@26127` | Viewer |

These are public **demo credentials**, not deployment secrets. New accounts are seeded only when `ANPR_DEMO_MODE=true`. The Unit selector records the chosen demo unit; it does not imply deployment-level regional authorization.

Sign in as admin and click **Run simulation** if the dataset is empty. Search `DL01AB1234` with a reason to see the watched vehicle profile, or `DL08CX9090` for the cloning scenario.

## Frontend development

Requires Node.js 22 or later. Install dependencies once; the runtime UI uses only locally served bundles unless Streets mode is explicitly selected.

```sh
cd frontend
npm ci
npm run dev
```

Vite serves http://127.0.0.1:5173 and proxies `/api` and `/ws` to FastAPI on port 8000. Keep the API running in another terminal. For a production build:

```sh
npm run build
npm test
```

Restart FastAPI after the first build so its asset mount is registered. Subsequent rebuilds update the files it serves. `npm run build` type-checks before bundling. `npm run preview` previews static files only; use FastAPI for the complete production application.

The Dockerfile now builds React in a Node stage and copies the result into the Python image. Docker execution remains unverified on this machine because its daemon is unavailable.

## Implemented workspaces

| Screen | Connected behavior |
|---|---|
| Sign in | scrypt passwords, signed JWT access tokens, rotating refresh cookie, failed-login audit, five-failure lockout, show/hide password, demo access panel |
| Shell | Role-aware navigation, Ctrl/Cmd+K search, alert count, session-expiry warning, light/dark themes, sign out, responsive sidebar |
| Overview | API-backed KPIs, count-up animation, camera network, recent alerts, hourly chart, density ranking, evidence status, simulation control |
| Map | Local Leaflet grid, road topology, density rings, camera selection, corridor colours, optional online OpenStreetMap tiles |
| Vehicle search | Partial and fuzzy candidates, required reason, pagination, audited requests |
| Vehicle profile | Plate validation/confidence, watchlist state, explicitly synthetic registration/owner/challans, reason-audited owner unmasking, sightings filters, raw OCR evidence, alerts, case notes |
| Trajectory | Numbered hops, inferred segments, route playback, moving marker, scrubber, 1×/2×/4×/8× speed, trips split by dwell time |
| Attribute search | Class/camera/read-confidence/plate-availability filters; explicitly simulated colour attributes for simulator events; unidentified traffic tracks |
| Video analysis | Authenticated Intel samples, local video playback, camera selection, real imported per-frame JSON overlays, confidence/class/ID toggles, speed and frame stepping, track counts and highlighting |
| Analytics | Recharts volume/density charts, corridor speed/congestion table, OD matrix |
| Alerts | Status and severity filters; persisted Open/Acknowledged/Escalated/Closed workflow, assignee and note |
| Watchlist | Add, remove and bulk text import with an investigation reason |
| OCR Lab | Local image preview, actual API positional normalization and multi-frame voting on supplied reads |
| Audit | Admin-only filterable access history including searches, login attempts and owner-detail access |
| Administration | User-role inventory and evidence verification; local API reference |

Case-file export uses the browser print dialog's **Save as PDF**. It includes the evidence-chain status/head and the observed hop list. It is not a server-generated signed PDF. Owner details are visually masked in print and the synthetic-record disclaimer is included.

## Recorded video overlays

The UI never invents plate text, bounding boxes or detection counts. The included clips have mostly unreadable plates. Without actual analysis results, the player shows the original video and an explicit empty state.

The existing optional CLI can now emit normalized, smoothed per-frame detections:

```sh
python -m tools.process_video samples/car-detection.mp4 --camera C04 --vehicle-model models/yolo11n.pt --detect-only --analysis-json output/car-analysis.json
```

Use **Import analysis JSON** on the Video Analysis page with the same source clip. The JSON format is:

```json
{"fps":30,"frames":[{"frame":0,"timestamp":0,"detections":[{"track_id":12,"class":"car","confidence":0.91,"box":[0.1,0.2,0.3,0.5]}]}]}
```

`box` is normalized `[x1,y1,x2,y2]`. Frame indices begin at zero and the file must match the video's constant frame rate. Optional `colour`, `plate` and `plate_confidence` come from actual analysis. A plate is drawn only when its supplied read confidence is at least 0.8. Playback uses `requestVideoFrameCallback` with a `requestAnimationFrame` fallback, scaling overlays to the actual video content area. Import accepts at most 50 MB / 100,000 frames.

The CLI uses confidence ≥0.4, EMA box smoothing, and excludes tiny boxes / tracks observed fewer than three times from its overlay export. Its neural processing still requires optional dependencies and local model weights and has not been executed here. The React player and included MP4 playback were verified.

## Clearly bounded integrations

This change implements the **React frontend**, plus API adapters needed by its supported screens. The expanded product brief also describes services that are not installed or configured. The UI does not fake their results:

- The local authenticated OCR upload/job service now exists. The retained offline pipeline provides recorded-clip counting lines, track dwell, hashes and static JSON overlays; it does not provide live city surveillance.
- OCR Lab now runs RapidOCR on the local service. Browser-side OCR remains unimplemented. The separate legacy crop control remains preview-only, and its voting playground still accepts supplied reads.
- No official registry/e-Challan connectivity, satellite tile provider, geofence polygons or hardware camera heartbeat service. Registry data is explicitly synthetic in demo mode.
- No trained colour/make/model classifier, appearance embeddings, cross-camera appearance re-identification or saved-search alert service. Demo colour is deterministic synthetic metadata, not a prediction. Attribute confidence is not substituted with a made-up value.
- No week-on-week delta without historical data. KPI notes explicitly state the retained-data scope.
- No user-provisioning UI, watchlist categories/expiry scheduler or MFA identity-provider integration. The optional second-factor field explains that it is not configured and the server rejects nonempty codes rather than pretending to validate them.

The existing plain SQLite core and its algorithm limitations still apply. See `README.md` for simulated accuracy and evidence retention details.

## Security and state

Access tokens stay in memory. Refresh JWTs are in an HttpOnly, SameSite=Strict cookie scoped to `/api/auth`; HTTPS also sets Secure. Refresh tokens rotate, session revocation invalidates access, and tokens require HS256 with the expected access/refresh type. Passwords use unique salts and scrypt. Set a strong `ANPR_JWT_SECRET` for stable controlled deployments; without it a random process-local key safely invalidates sessions on restart.

New profile, owner, attribute, workflow, video and OCR endpoints require bearer sessions and enforce roles server-side. API inputs require search and unmask reasons. Unmasked owner values are returned with `Cache-Control: no-store`; audit logs contain the reason and actor rather than owner PII.

**Legacy compatibility:** the original demo ingestion/analytics/trajectory APIs still support the earlier `X-Role` interface. In demo mode it is self-selected, so the whole demo must remain bound to localhost. JWT sign-in is not a claim that the legacy demo API is production-secure. Gateway mode requires `ANPR_API_KEY` for legacy access; place that interface behind a trusted authenticated gateway, disable public demo accounts, and add proper identity provisioning for a deployment. Neither this frontend nor the previous backend is a certified government system.

Theme preference is the only application data stored in localStorage. Plate searches, owner details and credentials are not persisted there. Routes carry plate query text only when explicitly searching; never expose this local demo publicly. No analytics or remote fonts are loaded. All charts/icons are bundled locally. The map uses offline OSM vectors with an optional schematic fallback; no raster tile requests are needed.

## Verification

- 73 Python tests passed, including new auth/session/masking/workflow/role tests and the previous algorithm suite.
- 2 Vitest transformation tests passed.
- TypeScript strict checking and Vite production build passed.
- `npm audit`: zero reported vulnerabilities after updating Vitest to 4.1.11.
- Browser: sign-in, API-backed overview, reason-based search, full vehicle profile, masked owner data, trajectory controls and actual Intel MP4 loading verified. See `output/citytrace-*.png`.
- Backend tests retain one upstream Starlette/httpx deprecation warning; it is not a test failure.
