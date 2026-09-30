# Delhi synthetic-demo verification — 30 September 2026

- Strict TypeScript build: passed. Vite production bundle: passed.
- Frontend: 7 tests passed, covering deterministic seed behavior, 40-camera connectivity, chronological 18-hop/126-read lifeline, inferred segments, fuzzy OCR correction, impossible-travel arithmetic, stable regional heatmap counts, purpose checks, attribute matches, alert workflow, access audit and viewer restriction.
- Backend regression: 73 tests passed. One upstream Starlette/httpx deprecation warning remains.
- Browser: Chrome via agent-browser. Sign-in loads the in-memory dataset with zero API requests and zero external resource requests in the tested flow.
- Plate flow: DL01AB1234 produces 18 stops, 94.8 km, 8h 41m span and 280 min scripted dwell for 30 September; 17 route segments render. Replay and timeline scrub controls work.
- Fuzzy query RJ14CB22I0 offers RJ14CB2210 with distance 0.5 and opens its journey.
- Region filter: South Delhi changes the SVG viewBox and exposes 5 cameras; scope carries into analytics.
- Heatmap: 40 camera heat spots for All Delhi; time-lapse advances the hour and changes values; 30 date choices and 8 region options are available.
- Attributes: White + car gives 27 identities, DL01AB1234 is present, and 12 cards render on the first page.
- Media: both local MP4s reach readyState 4, videoWidth 768, duration 30.16 / 53.916667 seconds; no media errors. Animated synthetic feeds show synthetic labels.
- Scenario: continued after navigation and completed with 8 alerts (6 seed + 2 scripted).
- Alert detail: priority 85; Narela → Badarpur = 44.92 km / 180 seconds ≈ 898 km/h. Acknowledged workflow saves and audit records include both alert.action and trajectory.view.
- OCR: 91.8% simulated benchmark and two populated review entries render.
- Responsive: 390 × 844 journey view has scrollWidth 390 and retains all 18 stops. Desktop checked at 1440 × 1000.
- Browser error collection was empty after the completed core flow. Two test-driver timing/selection errors were corrected; they were not application errors.

Screenshots in output/: delhi-trajectory.png, delhi-heatmap.png, delhi-attributes.png, delhi-mobile.png.

This verifies a synthetic frontend demo, not real OCR accuracy, real surveillance, official registry access, legal compliance, or production authentication.

---

# Verification record

## React conversion update

The current CityTrace React frontend supersedes the original single-file dashboard below. Source and production bundles are included in `frontend/`. Strict TypeScript + Vite build passes; **73 Python tests and 2 Vitest tests pass**. `npm audit` reports zero vulnerabilities. See `FRONTEND.md` for the capability matrix and integration limits.

Browser checks on the React build confirmed sign-in, reason-based plate search, synthetic registry labels, default owner masking, trajectory controls, actual Intel MP4 playback (768-pixel source, 30.16 seconds), theme switching and no horizontal overflow at desktop/laptop/mobile widths. Default map mode loaded zero external HTTP resources. Screenshots use the `output/citytrace-*.png` prefix. Neural job execution, official registry services, classifiers and Docker execution remain unverified/unconfigured as documented.

## Original Python / single-file dashboard baseline

Verified locally on 30 September 2026 with Python 3.11.9 on Windows.

## Core and API

- `python -m pytest -q`: **56 passed**. One upstream Starlette warning reports that its httpx TestClient adapter is deprecated. No test failures.
- `python -m compileall -q anpr tools demo.py`: passed.
- `python -m tools.process_video --help`: passed without installing the optional vision stack.
- `python demo.py`: 320 generated random vehicles + 3 scripted vehicles, 1,142 observed passes, 74 missed passes; full measurements in `output/evaluation.json`.
- Dashboard after simulation: 331 resolved identities, 8 active cameras, 35.6 km/h network average, 6 alerts. The identity count exceeding the 323 physical simulated vehicles reflects unresolved OCR splits; it is not hidden or claimed as perfect association.
- Watched vehicle: 4 observed hops and 13 km inferred road distance.
- Clone: 13 km in 240 seconds, 195 km/h, HIGH confidence; inferred intermediate nodes C04 and C06.
- Restricted-zone night scenario and all watchlist crossings produced alerts.
- Evidence chain valid before the isolated tamper test; modified evidence detected afterward.

## Browser-to-database flow

An isolated Chrome session was driven using agent-browser. The local Uvicorn server returned successful REST requests and accepted the authenticated alert WebSocket.

| Check | Observed result |
|---|---|
| Initial empty page | Map and meaningful empty/loading states rendered |
| Run simulation | SQLite populated; 1,142 passes appeared in KPI strip |
| Evidence verification | Green “Evidence chain verified” badge |
| Automatic watched-plate route | Four hops and animated SVG path |
| Click cloned-plate alert | Correct camera focus, 195 km/h leg, inferred cameras marked |
| Fuzzy search `DL01AB1239` | Loaded `DL01AB1234` trajectory |
| Audit dialog | `plate.search` events visible |
| Switch to viewer | Plate input and route cleared; search/simulation disabled; alert feed restricted |
| Desktop 1440×1100 and laptop 1366×768 | Dashboard visually inspected; desktop no horizontal overflow |
| Mobile 390×844 | Responsive layout inspected; no horizontal overflow |
| External resources | Browser resource inventory returned an empty list of non-local URLs |
| Offline API reference | Local `/docs` page and generated schema loaded |
| Browser errors | agent-browser reported none |

The desktop and laptop screenshots are in `output/`. The test browser was closed; the local API server was left running for review. On a new machine use the README startup commands.

## Explicit verification limits

- Optional YOLO/PaddleOCR neural inference was **not run**: local model weights and the large optional dependency stack were not installed. The CLI, OCR-result parser and track aggregation are tested; actual video inference/OCR accuracy is not verified.
- Both requested sample MP4s were downloaded and their SHA-256 checksums recorded in `samples/README.md`. They were not used to claim OCR performance.
- Docker CLI is present but its daemon is unavailable. Dockerfile build/run was **not verified**.
- PostgreSQL/PostGIS migration, production authentication, multi-worker pub/sub, penetration tests and city-scale throughput are outside this prototype’s verified scope.
- Accuracy is from seeded simulated noise only. Final canonical updates can propagate errors; the complete table includes these regressions.


## Real-footage update — 1 October 2026

- Final strict TypeScript check and Vite build passed. No new frontend runtime dependency.
- 14 frontend tests passed (7 existing + 7 real-footage checks).
- 81 Python tests passed (73 existing + 8 pipeline tests). The existing upstream Starlette/httpx deprecation warning remains. One intermediate run collided with Vite replacing `dist/assets`; rerunning after the build passed all 81 tests.
- Actual CPU inference processed 1,024 source frames at stride 3 across two licensed clips (84.08 seconds); final RGB preprocessing follows the OpenCV reference. Runtime 624.66 seconds on this memory-constrained workstation. No detection values were hand-edited.
- Final outputs: intel-cars has 2 confirmed model tracks and 0 configured-line crossings; intel-street has 2 confirmed model tracks and 2 crossings. Sparse sampling and tracking misses materially undercount the fast road clip: these are unvalidated model outputs, not an accuracy claim.
- All four tracks abstain on plate identity. No plate detector/OCR weights or ground-truth labels were supplied. Real plate trajectories/events remain empty; `evaluate --split dev` confirms “Not measured: no ground-truth labels”. Test split has not been evaluated.
- Two clips decode in Chrome (readyState 4). Track selection seeks to the exported best frame; overlays and counting-line timecodes render. Desktop 1440×1000 recording view and mobile 390×844 analytics have no page-level horizontal overflow.
- Offline OSM roads load (10,969 road features). South Delhi selection changes the SVG viewBox and exposes five active camera nodes; heatmap shows five intensity circles. Real/schematic toggle tested.
- Viewer: zero raw video elements when no redacted preview exists; restricted message shown; no unmasked scripted plate strings; admin Privacy link absent. Role masking is not a server security boundary.
- Privacy purge and local erasure-request controls exercised. Immutable store filtering, actual erasure/purge on populated fixtures, counting-line intersection, HMAC, two-line splitting, Wilson interval, abstention metrics, video splitting and Python/TypeScript voting parity are tested.
- Real watchlist and staged clone arithmetic are exercised with isolated unit fixtures; no test plate events are injected into the published bundle. Real trajectory/alert video playback requires accepted plate output and therefore is not claimed as end-to-end verified on these samples.
- Missing-bundle fallback is covered by the loader test. No crops are retained in the normal export.

Screenshots: `output/real-video-desktop.png`, `output/real-map-region.png`, `output/real-analytics-mobile.png`. The file inventory and commands are in `docs/REAL_FOOTAGE_FILES.md` and `pipeline/README.md`.

Final browser follow-up: the preserved 30-second scenario produced eight alerts; Deep dive shows its own computed panels without the density-map panel; actual video playback advanced from 18.00 to 18.66 seconds; the mobile video view also has no horizontal overflow. No browser JavaScript errors were reported. Final targeted pipeline rerun: 8/8 passed after adding aligned character-confusion counts.
