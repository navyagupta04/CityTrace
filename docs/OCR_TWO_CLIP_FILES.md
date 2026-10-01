# Two-clip update file manifest

All repository deliverables created or changed for this request are listed below. The existing five-feed videos, seeded camera graph, prior trajectories, held-out metrics and original Desktop files were not changed. Removed files are obsolete hashed production bundles replaced by Vite.

Existing tests: `frontend/src/operations.test.tsx` gained seven tests plus store cleanup; its prior assertions remain. No existing tests were removed or weakened. New backend coverage is in `tests/test_live_cases.py`.

Validation: 96 Python tests and 56 frontend tests passed; strict TypeScript and the production build passed. Browser evidence and actual API result JSON are machine-local verification files under ignored `output/`, rather than application data.

## Created (32)

- [anpr/live_cases.py](../anpr/live_cases.py)
- [configs/test_case.yaml](../configs/test_case.yaml)
- [docs/OCR_TWO_CLIP_FILES.md](../docs/OCR_TWO_CLIP_FILES.md)
- [frontend/dist/assets/Attributes-DB6U41dg.js](../frontend/dist/assets/Attributes-DB6U41dg.js)
- [frontend/dist/assets/CameraHealth-BMmOGSEC.js](../frontend/dist/assets/CameraHealth-BMmOGSEC.js)
- [frontend/dist/assets/Evidence-BxCcJfLT.js](../frontend/dist/assets/Evidence-BxCcJfLT.js)
- [frontend/dist/assets/Intelligence-BD8J7xCm.js](../frontend/dist/assets/Intelligence-BD8J7xCm.js)
- [frontend/dist/assets/Live-CNX3Bzhq.js](../frontend/dist/assets/Live-CNX3Bzhq.js)
- [frontend/dist/assets/LiveFeeds-COaRexdm.js](../frontend/dist/assets/LiveFeeds-COaRexdm.js)
- [frontend/dist/assets/Profile-CXkujL--.js](../frontend/dist/assets/Profile-CXkujL--.js)
- [frontend/dist/assets/RealWorkspace-C7FxCJ-V.js](../frontend/dist/assets/RealWorkspace-C7FxCJ-V.js)
- [frontend/dist/assets/SimulatedFeed-C0Sy32mB.js](../frontend/dist/assets/SimulatedFeed-C0Sy32mB.js)
- [frontend/dist/assets/Traffic-DIry7SpI.js](../frontend/dist/assets/Traffic-DIry7SpI.js)
- [frontend/dist/assets/Trajectory-eABExvEg.js](../frontend/dist/assets/Trajectory-eABExvEg.js)
- [frontend/dist/assets/Video-5Ii5BaSx.js](../frontend/dist/assets/Video-5Ii5BaSx.js)
- [frontend/dist/assets/download-pT_CFsjB.js](../frontend/dist/assets/download-pT_CFsjB.js)
- [frontend/dist/assets/index-CLzczfBi.css](../frontend/dist/assets/index-CLzczfBi.css)
- [frontend/dist/assets/index-DbsYvGdf.js](../frontend/dist/assets/index-DbsYvGdf.js)
- [frontend/dist/assets/pause-DcdpDZ1q.js](../frontend/dist/assets/pause-DcdpDZ1q.js)
- [frontend/dist/assets/upload-k7snvSXt.js](../frontend/dist/assets/upload-k7snvSXt.js)
- [frontend/dist/videos/test-case/WhatsApp Video 2026-10-01 at 2.14.46 PM.mp4](../frontend/dist/videos/test-case/WhatsApp%20Video%202026-10-01%20at%202.14.46%20PM.mp4)
- [frontend/dist/videos/test-case/gemini_generated_video_4835b244.mp4](../frontend/dist/videos/test-case/gemini_generated_video_4835b244.mp4)
- [frontend/dist/videos/test-case/manifest.json](../frontend/dist/videos/test-case/manifest.json)
- [frontend/public/videos/test-case/WhatsApp Video 2026-10-01 at 2.14.46 PM.mp4](../frontend/public/videos/test-case/WhatsApp%20Video%202026-10-01%20at%202.14.46%20PM.mp4)
- [frontend/public/videos/test-case/gemini_generated_video_4835b244.mp4](../frontend/public/videos/test-case/gemini_generated_video_4835b244.mp4)
- [frontend/public/videos/test-case/manifest.json](../frontend/public/videos/test-case/manifest.json)
- [frontend/src/real/LiveCases/LiveCaseJourney.tsx](../frontend/src/real/LiveCases/LiveCaseJourney.tsx)
- [frontend/src/real/LiveCases/LiveCaseStore.ts](../frontend/src/real/LiveCases/LiveCaseStore.ts)
- [frontend/src/real/LiveCases/PlaceOnMap.tsx](../frontend/src/real/LiveCases/PlaceOnMap.tsx)
- [frontend/src/real/LiveOCRRun/Evidence.tsx](../frontend/src/real/LiveOCRRun/Evidence.tsx)
- [scripts/choose_test_cameras.py](../scripts/choose_test_cameras.py)
- [tests/test_live_cases.py](../tests/test_live_cases.py)

## Modified (15)

- [FRONTEND.md](../FRONTEND.md)
- [anpr/ocr_live.py](../anpr/ocr_live.py)
- [docs/OCR_LAB_LIVE.md](../docs/OCR_LAB_LIVE.md)
- [frontend/dist/index.html](../frontend/dist/index.html)
- [frontend/src/components/DataSources.tsx](../frontend/src/components/DataSources.tsx)
- [frontend/src/lib/provenance.ts](../frontend/src/lib/provenance.ts)
- [frontend/src/operations.css](../frontend/src/operations.css)
- [frontend/src/operations.test.tsx](../frontend/src/operations.test.tsx)
- [frontend/src/pages/Trajectory.tsx](../frontend/src/pages/Trajectory.tsx)
- [frontend/src/real/LiveOCRRun/AccuracyPanel.tsx](../frontend/src/real/LiveOCRRun/AccuracyPanel.tsx)
- [frontend/src/real/LiveOCRRun/LiveOCRRun.tsx](../frontend/src/real/LiveOCRRun/LiveOCRRun.tsx)
- [frontend/src/real/LiveOCRRun/export.ts](../frontend/src/real/LiveOCRRun/export.ts)
- [frontend/src/real/LiveOCRRun/ocrLiveApi.ts](../frontend/src/real/LiveOCRRun/ocrLiveApi.ts)
- [frontend/src/session.tsx](../frontend/src/session.tsx)
- [pipeline/live_metrics.py](../pipeline/live_metrics.py)

## Replaced generated bundles (16)

- [frontend/dist/assets/Attributes-DowORn0w.js](../frontend/dist/assets/Attributes-DowORn0w.js)
- [frontend/dist/assets/CameraHealth-B9jOSZ8C.js](../frontend/dist/assets/CameraHealth-B9jOSZ8C.js)
- [frontend/dist/assets/Intelligence-D1neEDRZ.js](../frontend/dist/assets/Intelligence-D1neEDRZ.js)
- [frontend/dist/assets/Live-nMXvmIrD.js](../frontend/dist/assets/Live-nMXvmIrD.js)
- [frontend/dist/assets/LiveFeeds-9CmLDM79.js](../frontend/dist/assets/LiveFeeds-9CmLDM79.js)
- [frontend/dist/assets/Profile-DvZr5anJ.js](../frontend/dist/assets/Profile-DvZr5anJ.js)
- [frontend/dist/assets/RealWorkspace-CCPo4VdM.js](../frontend/dist/assets/RealWorkspace-CCPo4VdM.js)
- [frontend/dist/assets/SimulatedFeed-BbMXO_UQ.js](../frontend/dist/assets/SimulatedFeed-BbMXO_UQ.js)
- [frontend/dist/assets/Traffic-BuS7QBV5.js](../frontend/dist/assets/Traffic-BuS7QBV5.js)
- [frontend/dist/assets/Trajectory-D75zPlCJ.js](../frontend/dist/assets/Trajectory-D75zPlCJ.js)
- [frontend/dist/assets/Video-CnbKp6wR.js](../frontend/dist/assets/Video-CnbKp6wR.js)
- [frontend/dist/assets/download-DjUUFhVN.js](../frontend/dist/assets/download-DjUUFhVN.js)
- [frontend/dist/assets/index-DZvLnIrx.js](../frontend/dist/assets/index-DZvLnIrx.js)
- [frontend/dist/assets/index-DeNrDegQ.css](../frontend/dist/assets/index-DeNrDegQ.css)
- [frontend/dist/assets/pause-NSJnpXgp.js](../frontend/dist/assets/pause-NSJnpXgp.js)
- [frontend/dist/assets/upload-BQ_-YECX.js](../frontend/dist/assets/upload-BQ_-YECX.js)

## Main local verification artifacts

- `output/two-clip-browser-result.json`: completed actual two-video OCR run.
- `output/two-clip-browser-cases.json`: actual grouped case returned by the endpoint.
- `output/two-camera-trajectory.png`, `output/two-camera-evidence-final.png`, `output/two-camera-mobile.png`: browser checks.
- Earlier stride-5 diagnostics in `output/two-clip-check.json` were interrupted; they are not the final result.

