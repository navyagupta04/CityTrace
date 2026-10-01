# Live OCR and operations interface plan

Implementation plan (recorded before implementation):

1. Add `pipeline/engines/`, `pipeline/live.py`, `pipeline/live_metrics.py`, and `configs/lab.yaml`. Reuse normalization, quality scoring, line splitting, voting, detection/tracking and evaluation math. Preserve offline defaults and metrics exports.
2. Add `anpr/ocr_live.py` for authenticated, bounded temporary upload jobs, cancellation, expiry, audit and labels. Mount from the existing frontend router using its officer dependency.
3. Add `frontend/src/real/LiveOCRRun/` and a direct authenticated API adapter. Mount above the existing OCR sections. Never route live processing through the seeded adapter.
4. Add centralized provenance, camera health scoring/measurements and Camera Health Intelligence. Add focus support to the existing map; replace wall with a redirect; remove only the density page's footage tab.
5. Add a reproducible video preparation script and five recorded feed tiles, sharing browser measurement subscriptions with camera health. Keep the previous sources collapsed below them.
6. Add backend/frontend regression tests, update wording and run the complete Python/Vitest/type/build checks. Document measurements, limits, known gaps and all changed files.

Defaults: localhost service; CPU RapidOCR 1.4.4 / PP-OCRv4; no runtime model downloads; one heavy worker; 20 files, 10 MiB/image, 200 MiB/video, 60 seconds/video; 30-minute in-memory result TTL. File labels score only unambiguous single-plate files; multi-track labels use filename#track_id to prevent assigning one identity to unrelated vehicles.

## Install and run

From the repository root, with Python 3.11 and Node 22 or later:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt -r pipeline/requirements.txt
.\.venv\Scripts\python.exe -m uvicorn anpr.api:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173/#/ocr`. The default access-profile console remains available. Expand **Sign in to local OCR service** and use the existing backend officer account (`officer` / `CityTrace@26127`, seeded only when `ANPR_DEMO_MODE=true`). This is a real password/JWT check, separate from the in-memory access profile. The Viewer role cannot open the OCR workspace or call any job route. An Officer/Admin can access only jobs created by the same backend username. Signing out clears the separate in-memory OCR access token.

Alternatively set `$env:VITE_USE_MOCK='false'` before starting Vite and sign in through the existing backend authentication screen. Access tokens expire after 15 minutes; reauthenticate if the service reports a session error. None of the live endpoints use the seeded adapter. A service/network/engine error displays an unavailable/error state, never fallback plates.

| Environment variable | Default / purpose |
|---|---|
| `VITE_OCR_API_BASE` | Existing `VITE_API_BASE_URL`, otherwise `/api`; include the `/api` prefix |
| `VITE_API_BASE_URL` | `/api`, existing general adapter |
| `VITE_USE_MOCK` | Existing default `true`; `false` enables backend sign-in for the entire console |
| `OCR_LAB_CONFIG` | Absolute or working-directory-relative path to `configs/lab.yaml` |
| `OCR_CORS_ORIGINS` | Comma-separated exact origins; defaults to `http://127.0.0.1:5173,http://localhost:5173` |
| `ANPR_DEMO_MODE` | Existing backend account-seeding setting |
| `ANPR_JWT_SECRET` | Existing backend JWT secret; absent means process-local random key |

Vite proxies `/api` to port 8000. For separate test ports set `VITE_OCR_API_BASE=http://127.0.0.1:8001/api` and include the frontend origin in `OCR_CORS_ORIGINS`. The service run command deliberately binds to loopback. No hosted deployment was performed.

Verify status after signing in:

```powershell
$login = Invoke-RestMethod http://127.0.0.1:8000/api/auth/login -Method Post -ContentType application/json -Body '{"username":"officer","password":"CityTrace@26127"}'
$headers = @{ Authorization = "Bearer $($login.access_token)" }
Invoke-RestMethod http://127.0.0.1:8000/api/ocr/status -Headers $headers
```

Expected installed-engine identity: `RapidOCR`, `1.4.4 / PP-OCRv4`, `CPU`, `available: true`. Status reports the actual installed version, not a constant representing an uninstalled model. Unauthenticated status returns 401; Viewer returns 403. Install models before running offline. RapidOCR's wheel bundles its ONNX models. The optional Paddle adapter requires locally supplied detection and recognition directories and the existing PaddleOCR 2.x dependency environment. It is not exercised by the RapidOCR tests.

## Inference and results

The upload router is additive to the existing FastAPI app. Existing `configs/demo.yaml`, offline stages, `metrics.json`, crop preview, voting endpoint, benchmark and review queue remain available. Live inference never writes offline benchmark files.

Auto image mode selects crop only when width/height is between 1.2 and 5.5, width ≤1200 and height ≤400 pixels; otherwise it uses scene. Choose Scene manually if a small full image happens to match this heuristic. Crop mode imports the existing line splitter, CLAHE/upscaling, quality function, normalization/Indian grammar and vote aggregator. Scene mode uses configured local Ultralytics weights, or RapidOCR text boxes with plausible aspect ratios, neighbouring two-line unions, padded re-reading and grammar filtering. This heuristic is not a trained plate detector, and can miss oblique, small, occluded or non-Indian plates. Valid text may still abstain below the configured 0.8 vote threshold; raw OCR and the reason remain visible.

Videos always use scene localization within vehicle tracks. Frame sampling is deterministic (`stride`, `max_seconds`); detection imports the existing YOLOX Detector and tracking uses the existing Supervision ByteTrack configuration. Best-K frames are ranked by the existing crop-quality function, with frame index breaking ties. Only the best plate candidate per vehicle frame participates in that track's vote. Reads from separate track IDs are never pooled. Source coordinates use pixel `[x,y,width,height]`; the UI seeks to a selected track's best-read frame. Stage timings include decode, detection, tracking, localization, OCR and voting. OCR text detection time belongs to localization. Models and actual engine/device identities accompany each successful result.

Vehicle inference needs local `pipeline/models/yolox.onnx` (already present on this workstation). Missing or unloadable tracking/detection dependencies cause a per-file error. Other files continue. No model is downloaded during a job. `mode: crop` applies only to images; video localization stays track-based to avoid voting unrelated vehicles together.

## Ground truth and accuracy

Use a plate crop whose ground truth you know. Enter **Expected plate** before clicking Run to mark that run blind. A filename label is used only if that file has one result. Multi-plate images use `filename#0`, `filename#1`, etc.; videos use `filename#track_id`. These keys can be imported in CSV (`filename,plate`) before a reproducible rerun, or entered per row after the first run. After-run label editing always sets `blind: false`, even when a label is unchanged. Emptying a per-track label removes it from scoring. Labels are held separately and never passed to inference.

For a useful evaluation, assemble at least 100 independently labelled plates across distinct videos, conditions and plate sizes. Avoid repeated near-identical frames as separate independent samples. Fix eligibility and sampling before running. Normalize expected and predicted text by uppercase and removal of spaces/hyphens only; do not use model predictions to correct ground truth. Labelled abstentions count as incorrect and contribute full expected length to CER. Unlabelled files/tracks never enter accuracy. The existing metric implementation supplies edit distance, length-weighted CER, coverage, selective accuracy and 95% Wilson intervals. Reliability bins include labelled accepted reads and compare model scores with actual correctness. The threshold curve uses format-valid voted candidates, including those below the configured acceptance threshold.

Verdict rules follow the requested N boundaries exactly: N≥100 and accuracy≥90% → **Meets target (point estimate)**; N≥30 and accuracy<90% → **Below target**; otherwise **Inconclusive: too few labelled samples**. Always read the interval alongside the point estimate. Upload results are **LIVE RUN (this upload)** and never a frozen held-out test. The optional benchmark buttons were not added; existing CLI evaluation and frozen-test locks remain unchanged.

## Storage, limits, security and audit

- Multipart signatures, decoded image validity/pixel count, file sizes and video duration are checked. Limits: 20 files, 10 MiB/image, 200 MiB/video, 60 seconds/video, 40 million image pixels. Duplicate sanitized filenames are rejected because labels would be ambiguous.
- Files use numeric private paths under the operating system temp folder's `citytrace-ocr-lab/job-<random id>` directory, never a user-controlled path or public web directory. SHA-256 identifies bytes, not legal chain of custody.
- One heavy inference worker; eight active/queued jobs maximum; cooperative 900-second processing timeout. Checks run between frame/model operations. A native model invocation cannot be interrupted mid-call; cancellation completes and deletes its open file after that call releases it (especially on Windows). Results immediately stop exposing rows on cancellation.
- Upload originals are removed on completion, failure, cancellation or expiry. A five-second sweep expires the in-memory result and retries pending purge. Default TTL is 30 minutes from job creation. Startup removes stale job directories older than TTL. Graceful shutdown cancels and purges jobs. An abrupt OS termination relies on the next startup sweep.
- No crops are retained by this service, including exports; result thumbnails/boxes use local browser object URLs, released when the panel is cleared or unmounted. Navigating away requests server cancellation/purge. Original user-supplied desktop videos are never deleted.
- Existing officer guard and required purpose are enforced server-side. All accepted roles may view full plates under the existing convention; Viewer and other unauthorized requests return 403 with no plate data. Jobs are scoped to their creator. Export helpers additionally mask raw, normalized, voted, expected and error-case strings when unauthorized.
- Existing hash-chained SQLite audit records `ocr_job_started` (username, role, purpose, count, sanitized filenames, types, sizes, SHA-256), `ocr_job_completed` (state/count/duration), and `ocr_job_purged`. The new audit records contain no OCR plate text.
- Client-side masking/access profiles are UI controls, not a security boundary. Static recorded feeds remain local public assets, as in the existing app. Keep this evaluation workspace on localhost; no claim of production authorization or government integration is made.

## Live feeds and Camera Health

Prepare the supplied filenames in lexical order:

```powershell
.\.venv\Scripts\python.exe -m scripts.prepare_live_videos path\to\first.mp4 path\to\second.mp4 path\to\third.mp4 path\to\fourth.mp4 path\to\fifth.mp4
```

The script checks decoder/codec metadata, keeps H.264 when suitable, otherwise transcodes using bundled ffmpeg to H.264 yuv420p at ≤720p, strips audio and writes fast-start MP4. The generated editable `frontend/src/real/liveFeeds.config.ts` assigns C01–C05, records duration/resolution/fps, and records both original and output hashes. These assignments are **Staged placement**, not filming locations. Fewer files produce fewer tiles. Nothing is downloaded. Original filenames and source bytes remain unchanged on the desktop. Getty-branded clips have no assumed public redistribution license.

Grid/Focus, individual pause, Pause all, full-size viewer and Locate operate on these files. IntersectionObserver gates autoplay; page visibility pauses video; unmount releases decoder resources. Optional `/real/analysis/<id>.json` provides actual frame/track overlays through a renderer shared with the existing recorded player. None of the five supplied recordings has a supplied detection JSON, so their default overlays correctly say **No detections loaded**.

`cameraHealth.ts` is the single scoring function. Connectivity contributes 30, FPS `20*clamp(fps/25)`, latency `15*clamp(1-ms/1000)`, image quality `10*clamp(1-|brightness-128|/128)+10*clamp(sharpness/250)`, read rate `15*clamp(rate)`. Total rounds to 0–100 only with all five inputs. ≥85 Online; 60–84 Degraded; <60 or observed no signal Offline. Missing inputs stay null, making total Unmeasured. This is preferable to inventing a score from missing network/read data.

Browser video samples every three seconds use `requestVideoFrameCallback`, 160×90 grayscale brightness and Laplacian variance, stall checks, decoder processing time where supported, and `getVideoPlaybackQuality` dropped frames. One owner per camera performs pixel sampling; overlapping previews do not duplicate sampling. FPS without frame callbacks is unavailable. Browser dropped frames are **not packet loss**; decoder time is **not network latency**. Actual plate-read rate/mean confidence need loaded track analysis with an explicit denominator, so currently remain Not measured for these five feeds. Current-session uptime refers to sampled playback, not camera hardware. Stored samples are marked paused/stale after leaving Live; a detail preview can sample again.

The remaining 35 nodes have separately labelled seeded health inputs. Their KPIs and 24-hour scenario curve never combine with measured playback values. Issue flags are deterministic threshold heuristics, not verified incidents; obstruction/tamper suspicion requires human review. No hardware/network telemetry service is claimed. The detail view offers component scores, available history, coordinates, preview and navigation. `/wall` redirects to `/camera-health`; it retains the old wall's ordinary signed-in access scope. `/map?camera=Cxx&focus=1` selects and animates focus in both roads modes, respects reduced motion, and leaves Reset/zoom/pan usable.

Density analytics no longer mounts RealAnalytics or its tab. Its shared implementation is retained on disk; the other analytics tabs, DeepDive, Video analysis, Trajectory and OCR sections remain available. Former live sources are under **Additional sources** with Intel attribution preserved.

## Troubleshooting and verification

401 → sign in to the local service; 403 → use an authorized officer account; connection failure → start FastAPI and check base URL/CORS; missing RapidOCR → install the pinned requirements; missing vehicle model → install the documented local YOLOX weights before video OCR. Some Windows application-control environments block native tracking DLL loading in sandboxed shells; the actual video check succeeded in the approved local execution context. Do not substitute results if dependencies remain unavailable.

The repository's pre-existing `.venv` pointed at a missing Python installation on this workstation. A workspace-local Python 3.11.15 runtime was installed and the ignored venv launcher repaired for testing; these machine-local paths are not requirements for other installations.

```powershell
.\.venv\Scripts\python.exe -m pytest tests pipeline/tests -q --basetemp=output/pytest-live-check
cd frontend
npm test
npx tsc -b
npm run build
```

The rendered PIL plate test is a **test fixture, not accuracy evidence**. Actual-browser verification covers service sign-in, upload, real raw text/timing, threshold abstention, label recomputation, purge, all five decoders, Pause all, map focus and responsive screens. The actual two-second traffic smoke run produced seven vehicle tracks with seven abstentions and zero scored samples (no labels). This is execution evidence only, not an accuracy claim.

## Final verification record — 2026-10-01

- `python -m pytest tests pipeline/tests -q --basetemp=output/pytest-final`: **93 passed**, one upstream Starlette/httpx deprecation warning.
- `npm test`: **49 passed across five files**. The existing `frontend/src/real/real.test.tsx` test changes only the expected provenance labels to Recorded footage / Staged placement; no existing test was deleted.
- `npm run build`: **passed**, including strict `tsc -b` and Vite production bundling. Tracked `frontend/dist` was rebuilt.
- Browser: real local officer login, rendered image upload, actual OCR and timings, threshold abstention, post-run label save and source purge; five supplied videos decoded and played; Pause all paused all five; Locate focused the correct map node; 390×844 single-column layout had no horizontal overflow. The StrictMode source-cleanup regression and region-reset Locate regression have dedicated tests.
- Actual image smoke result: raw and normalized `DL01AB1234`, abstained below the 0.8 vote threshold. This rendered fixture is not a representative accuracy sample.
- Actual two-second traffic video smoke result: seven tracks, seven abstentions, N=0. No 90% accuracy claim is supported or made.
- The optional Paddle adapter was not runtime-tested. Five feed analysis JSONs were not supplied, so detection overlays and plate-read telemetry remain unavailable for those recordings. Network latency and packet loss cannot be measured from local MP4 playback.

The existing offline OCR preprocessing was extracted into `prepare_piece` and reused by the live path; its CLAHE/upscaling algorithm and offline defaults remain unchanged. The original uploaded Desktop source files are unchanged. The complete source, prepared media and generated distribution change list is in [OCR_LAB_LIVE_FILES.md](OCR_LAB_LIVE_FILES.md).


## Plain OCR and the two supplied test clips — update

The current request supplies **two** 10-second, 1280×720 clips. The test case uses exactly these two, in filename order, rather than duplicating footage to create a third stop. Their bytes are copied unchanged into `frontend/public/videos/test-case/`; the Desktop originals remain unchanged. Both are labelled **Generated test footage** and **Staged placement**. The earlier five-feed monitoring grid and all prior trajectory presets remain intact.

Step 1 is **Upload and run**, with **No labels needed.** Pick files, enter a purpose of at least five characters and run when the local engine is ready. Step 2 is a collapsed **Measure accuracy (optional)** accordion containing expected plates and the CSV importer. With no entered labels the request omits both `expected` and `blind`. The response has `scored: false`, per-row `scored: false`, and `metrics: {scored: false}` with no verdict. Expected/Match/CER columns remain hidden. Summary cards and actual OCR results still appear. **Measure accuracy** opens Step 2; saving post-run labels recomputes metrics as non-blind.

### Prepare camera placements

From `D:\127`:

```powershell
.\.venv\Scripts\python.exe -m scripts.choose_test_cameras
```

To import the original two files into a fresh checkout first:

```powershell
.\.venv\Scripts\python.exe -m scripts.choose_test_cameras "C:\Users\Navya gupta\OneDrive\Desktop\gemini_generated_video_4835b244.mp4" "C:\Users\Navya gupta\OneDrive\Desktop\WhatsApp Video 2026-10-01 at 2.14.46 PM.mp4"
```

`configs/test_case.yaml` and the public manifest contain C01 (Connaught Place) at 10:12:05 IST and C05 (New Delhi Railway Station) at 10:15:02 IST, 30 September 2026. Road length: 1.718512 km; assigned gap: 177 seconds; implied speed: 35.0 km/h. Coordinates come from the existing road-snapped nodes, not filming locations. The chooser reads the existing frontend graph, uses existing road routes when present, otherwise straight-line distance ×1.3, preserves explicit non-AUTO camera IDs and never edits camera data. It handles one to three files, but rejects impossible graph constraints: the current road graph has no distinct three-node chain with every direct leg within 1–3 km. The requested two-node chain is valid. Existing fixed nodes are never silently replaced.

### Test A — one upload without CSV

1. Start FastAPI and Vite using the commands above; open `/ocr` and authenticate with the local OCR service.
2. Upload one video, leave Step 2 closed, and enter a purpose.
3. Press **Run OCR pipeline**. Confirm real progress, tracks, raw/normalized/voted text, confidence and timings.
4. Confirm **Not scored. Add expected plates to measure accuracy.** No CSV is needed.
5. A video without a readable accepted plate must return abstentions; raw candidates below threshold are not promoted to a voted read.
6. Optional: open Step 2, label the appropriate track and save. It must be marked non-blind.

The automated moving-rectangle video fixture renders `DL04CT7391` with PIL and sends an actual video through `/api/ocr/jobs`. A test-only geometric rectangle locator replaces vehicle detection because a rectangle is not a learned car class; video decoding, ByteTrack, text localization, OCR and voting are real. This is a component integration fixture, **not full YOLOX accuracy evidence**. Separate checks use the unchanged detector on the supplied clips.

### Test B — two clips to Plate Trajectory

1. Run the camera chooser, open `/ocr`, and choose **Load test case**. Exactly two files load with C01/C05 placements.
2. Leave labels empty, enter a purpose and run the same upload pipeline. Expected text in the YAML is only a configurable scoring reference; it is never given to inference.
3. Review voted reads. **Create trajectory** groups only accepted normalized plates; abstentions are excluded. Matching raw text below the vote threshold cannot create a shared journey.
4. For accepted reads, inspect **Place on map**, its searchable camera node and IST timestamp, then click **Create trajectory**. Each plate gets one strongest accepted track per distinct clip, sorted by placement time. A single sighting is permitted and explicitly identified.
5. Choose **Open in Plate Trajectory** and its new test-case preset. Existing presets, date searches and exports remain available.
6. Scrub/replay at 1×–8×, select each stop, verify its video seeks to the first tracked appearance and use **Seek track** for the best measured OCR frame/box. Boxes are intentionally visible only around their actual evidence timestamp; they are not stretched across unanalysed video frames.
7. Confirm generated/staged chips on header and stops, file-computed SHA-256, road distance, assigned speed and plausible travel. Dwell remains Not measured: a visible track duration does not establish stationary dwell.
8. Export GeoJSON or print the case file; generated/staged properties and provenance remain present. Viewer output masks plate strings and withholds video pixels containing readable plates.

A new owner-scoped officer endpoint `/api/ocr/jobs/{job_id}/trajectories` derives stops from the server's completed job, never client-provided plate predictions. It writes `trajectory_created` into the existing audit chain with user, purpose, plate token, stop count and clip hashes, without raw plate text. The browser stores up to twenty live cases and independent local video object URLs in memory; reload/sign-out releases them. Leaving OCR still purges its job; the deliberately retained case references continue to play locally. Cases never write seeded sightings, benchmark files or held-out metrics.

Scoring is opt-in. The supplied clips may contain multiple vehicles, so filename labels are deliberately not assigned to every detected track: label the intended track explicitly when ambiguous. At most two independently labelled intended vehicle observations cannot establish real-world accuracy, even if both match. The generated test scoring panel stays separate from held-out results. The optional cloned-plate variant remains off and is not implemented in this update.

### Verified result for the two supplied clips

The actual browser-started job used RapidOCR 1.4.4 / PP-OCRv4 on CPU, unchanged YOLOX + ByteTrack, stride **15**, no expected labels, and the complete two videos (10 seconds each). Both returned an accepted voted plate of `DL04CT7391`. Gemini clip: **0.8763** vote confidence, 5 reads; WhatsApp clip: **0.8662** vote confidence. The run finished with `scored: false`, no accuracy verdict and `purged: true`. There were 16 vehicle tracks in total; only the two accepted intended-vehicle reads entered the case. The earlier denser stride-5 diagnostic was interrupted before completion and is not the final result.

The completed-job trajectory endpoint returned two stops, C01 then C05, 1.719 km and 35.0 km/h with no impossible-travel flag. First tracked appearances and best OCR evidence times are taken from the actual tracks. Vote confidence is not plate accuracy or proof that the clips depict one physical vehicle.

Final regression commands: `python -m pytest tests pipeline/tests -q --basetemp=output/pytest-two-clips-regression` (**96 passed**, one upstream deprecation warning); `npm test` (**56 passed**, five files); `npm run build` (strict `tsc -b` plus Vite, passed). Existing test assertions were retained; `operations.test.tsx` gained additional cases and live-store cleanup. See [this update's complete file list](OCR_TWO_CLIP_FILES.md).

Browser verification additionally confirmed the actual two-stop case header/timeline, generated/staged chips, file hashes, first appearance at 1.25 seconds, second clip's best-frame seek at 4.375 seconds, and its measured overlay. At 390×844 the page's scroll width was 390 pixels. The existing route is `/trajectories`; the new case link targets it and has a regression assertion. Both supplied files played successfully in Chrome. The complete real job took 240.375 seconds on this workstation; runtime depends on available CPU and sampled vehicle count.
