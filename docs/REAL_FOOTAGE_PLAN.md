# Real footage implementation plan

1. Preserve seed 26127, all four scripted plates, the existing scenario, API contracts and tests. Replace the word “synthetic” only in visible UI and human-facing documentation with “synthetic”, “demo” or “simulated”; keep internal compatibility names where necessary.
2. Use the two already-bundled licensed Intel videos. Do not download new videos. Add a reproducible offline detector/tracker/counting exporter with file/model/config hashes. Export no invented plate reads; accuracy stays unmeasured without labels and configured plate models.
3. Add pipeline config, resumable stages, optional plate detector/OCR support, blind labeling, held-out video splits, honest metrics, retention and pseudonymisation utilities. Run the actual detector on both clips.
4. Add a separate real-footage loader/store and shared video/overlay component, then embed source-labeled panels in Video, Live, Trajectory, Alerts, Profile, Search, OCR and Analytics. Make recorded videos the default testing view. Keep generated identities independent of those recordings.
5. Add offline OSM roads and route preprocessing without changing seeded coordinates, deeper analytics, synthetic registry extensions and an admin Privacy & DPDP workspace.
6. Validate types/build, existing tests, new pipeline/loader/analytics tests and browser playback, including mobile. Document unavailable OCR/ground-truth outcomes, source licenses and all changed files.

Existing files touched: frontend pages and App/main for additive panels/providers/routes; NetworkMap for optional OSM layers; UI labels for terminology; anpr/api.py only to serve /real assets; documentation. No changes to seeded numeric data or existing tests.
