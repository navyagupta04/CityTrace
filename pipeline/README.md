# CityTrace real-footage pipeline

Run from the repository root. No video downloads occur. Two already-bundled Intel CC BY 4.0 recordings were copied into `data/videos/`. Put additional owned/consented MP4s there and declare their camera/time assignments in `configs/placements.yaml`.

```powershell
.\.venv\Scripts\python.exe -m pip install -r pipeline/requirements.txt
.\.venv\Scripts\python.exe -m pipeline run-all --config configs/demo.yaml
.\.venv\Scripts\python.exe -m pipeline build-delhi-roads --config configs/demo.yaml
.\.venv\Scripts\python.exe -m pipeline label-tracks --clip intel-cars
.\.venv\Scripts\python.exe -m pipeline evaluate --split dev
# Only after dev tuning and freezing the eligibility/model configuration:
.\.venv\Scripts\python.exe -m pipeline evaluate --split test
.\.venv\Scripts\python.exe -m pipeline purge-expired
```

`ingest`, `detect-track`, `read-plates`, `export` are resumable entry points; downstream commands populate missing detection prerequisites. Detection caches are keyed by source SHA-256, model SHA-256 and configuration hash. Use `--force` after editing detector code. Exports are atomic JSON writes. Rebuild the frontend after exporting to update the FastAPI-served `frontend/dist/real/`; Vite dev reads `frontend/public/real/` directly.

The real run uses OpenCV Zoo YOLOX (640×640 RGB letterboxing) and Supervision ByteTrack, OpenCV DNN CPU, stride 3. Native BLAS threads are bounded for this workstation. ONNX Runtime is installed as an alternative but was not used: its model initialization hit Windows memory limits. GPU acceleration is not enabled in the supplied implementation. Outputs are **model estimates, not validated ground truth**; sampled frames and tracking misses can undercount vehicles and dwell. Colour uses a coarse HSV estimate; make/model is not inferred. Directional line counts are once per track/direction/line, at the vehicle-box bottom centre. No speed is estimated from video.

Model weights: `pipeline/models/yolox.onnx`, OpenCV's official YOLOX export. Its source, licence and SHA-256 are documented in `docs/DATA_AND_LICENSES.md`. The model is not included in Git because `models/` is ignored; it is available locally. To reproduce elsewhere, download model weights from the linked OpenCV repository; no video download is needed.

## Optional plates

Install `pipeline/requirements-plates.txt` into a separate compatible environment and supply a local Ultralytics plate detector plus local PaddleOCR 2.x detection/recognition directories in `configs/demo.yaml`. The adapter uses two-line splitting, CLAHE/upscaling, deterministic frame sampling, crop quality and character-weighted voting. It never downloads a plate model implicitly. This path is implemented but **not executed or benchmarked here** because no local plate models or labelled readable-plate footage were supplied. Existing `requirements-vision.txt` is for the separate legacy CLI and uses a different PaddleOCR API generation.

The samples abstain on all plate reads. Accuracy remains **Not measured: no ground-truth labels**. No 90% result is asserted. Fine-tuning, perspective rectification, OCR ensembles and an engine-selection benchmark are not implemented.

## Blind labels and evaluation

The loopback-only labelling tool shows temporary vehicle crops with no model plate predictions. Enter ground truth, readability, condition and measured best-frame plate height. Download CSV into `data/ground_truth/`. Optional second-labeller/second-plate columns support agreement reporting. Stop with Ctrl+C to remove temporary crops.

Required CSV columns: `clip_id,track_id,plate,readable,condition,vehicle_class,labeller,labelled_at,plate_height_px`. Missing height makes the record ineligible for the readable headline but it remains in all-tracks accuracy. Splits are by video with seed 26127; fewer than three videos stay in dev and cannot support a held-out claim. The first split is saved to `data/ground_truth/video-splits.json`.

Exact match normalizes uppercase, spaces and hyphens. Abstentions count as incorrect. CER, coverage, selective accuracy, condition/size breakdowns, Wilson intervals and threshold curves are computed. A first test evaluation writes a lock and refuses subsequent test evaluations. Do not delete the lock to tune on the same test set. Error categories are conservative: abstention/no plate read or OCR character confusion; unobserved causes such as blur are not invented.

## Privacy

No crops are retained by default. `--blur-plates` produces a conservative whole-frame low-resolution preview, because a missed plate detector must not expose a bystander plate to viewers. Without a redacted preview, the Viewer UI blocks raw recordings. This is a frontend control; static files are **not access protected**. Keep the demo on localhost.

HMAC tokens are optional via `configs/privacy.yaml` and an environment secret. Tokens are supplemental; authorised raw plate text remains in the bundle, so this is not anonymisation. Purge applies to the exported bundle, not original user video files, backups or a production evidence store. The Privacy page's purge and erasure actions apply only to the in-memory real store and reset on reload.

Roads are an offline OpenStreetMap vector extract. Routes respect represented one-way flags, but this is not a turn-restriction-aware navigation engine. Camera locations remain illustrative. Missing directed links use the existing schematic fallback.

## Live OCR Lab (additive)

`configs/lab.yaml` and `pipeline/engines/` support authenticated local uploads through the existing FastAPI app. Install `pipeline/requirements.txt`, start `python -m uvicorn anpr.api:app --host 127.0.0.1 --port 8000`, and open the OCR Lab. RapidOCR 1.4.4 / PP-OCRv4 is bundled by its wheel; `engine: auto` prefers configured Paddle directories, otherwise RapidOCR. Scene fallback uses text boxes and grammar, and videos vote within YOLOX/ByteTrack vehicle tracks. Labels never enter inference.

See [OCR_LAB_LIVE.md](../docs/OCR_LAB_LIVE.md) for limits, authentication, metrics and privacy. Existing offline defaults, evaluation splits, test lock and `metrics.json` behaviour are unchanged. Upload results do not establish held-out accuracy. Browser OCR, fine-tuning, OCR ensembles and hardware camera telemetry remain unimplemented.
