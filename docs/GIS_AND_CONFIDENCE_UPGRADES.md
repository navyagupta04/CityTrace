# CityTrace GIS and OCR confidence upgrades

The existing navigation and interface remain in place. Delhi Map now opens a Leaflet geographic map, with the original cached schematic available as an offline fallback. Road and Satellite views, camera status popups, camera/plate search, Delhi boundary, scale, zoom and location controls share the existing map pages. Vehicle paths use cached road geometry rather than camera-to-camera straight lines.

Traffic Density uses the same geographic map and a Leaflet heat layer. Last hour, today and custom windows read deterministic camera counts in 15-minute buckets from local JSON files under `data/gis-density`. The Traffic page also connects its existing date/hour selector to these counts. Demo counts include morning and evening rush-hour peaks; points follow cached roads and camera coordinates. Totals mean camera detections, not unique vehicles across the city. Counts, camera statuses and restricted-zone areas are labelled demo or illustrative data.

No new database is required. The original application's existing SQLite storage is retained. PostgreSQL and PostGIS are not used for these upgrades, following the user's updated preference.

OCR Lab keeps its existing results and adds an annotated image, each source plate crop, OCR confidence, detector confidence, processing time and engine-provided character confidence. The video results table uses the same confidence fields. Warnings use an 80% threshold. These are per-detection scores, not measured system accuracy. The requested optional accuracy-input section has been removed.

The installed engine is RapidOCR running Paddle PP-OCRv4 ONNX models. OCR confidence uses the real recognizer output, weighted by text length when regions are combined; character scores come from the recognizer's CTC decoder. Without dedicated plate-detector weights, detection confidence is the real PP-OCR text-region detector score and is labelled accordingly. A supplied plate crop, or an engine that does not expose a detector or character score, is shown as unavailable instead of receiving an invented score. Other original result fields remain available.

## Run

From `D:\127`:

```powershell
.\.venv\Scripts\python.exe -m uvicorn anpr.api:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. The rebuilt frontend is already in `frontend/dist`. The OCR Lab uses the existing local-service sign-in when an access-profile session is selected.

For source changes, rebuild the frontend from `frontend` with `npm run build`. On this machine, if the system npm shim is unavailable, the installed runtime can build directly:

```powershell
& 'C:\Users\Navya gupta\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' node_modules\typescript\bin\tsc -b
& 'C:\Users\Navya gupta\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' node_modules\vite\bin\vite.js build
```

## Internet and cached data

- Road tiles: OpenStreetMap, with contributor attribution; tiles need internet. The existing dark theme applies a filter to Road tiles.
- Satellite tiles: Esri World Imagery, with Esri and imagery-source attribution; tiles need internet. No API key is configured.
- Routes: bundled cached OSM road geometry works offline. An optional OSRM refresh requires internet and falls back to cached roads on timeout or failure. Refresh a pair with `.\.venv\Scripts\python.exe -m tools.refresh_gis_route C01 C03`; restart the server to load the new cache. Refresh results are stored under `data/gis-density/routes`.
- Delhi boundary: the existing bundled DataMeet boundary, attributed in the map. Cached schematic, boundary, density data and installed OCR models work locally.
- Locate me: asks the browser for location permission only when clicked.

GIS endpoints are `/api/gis/density`, `/api/gis/routes` and `/api/gis/route`. Density accepts `window=last_hour`, `window=today`, or `window=custom` with timezone-qualified `start` and `end`; custom windows are limited to 31 days. Route refresh is optional with `refresh=true` and is cached locally.
