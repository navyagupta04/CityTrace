-- CityTrace read-only proof mirror. SQLite remains the system of record.
CREATE TABLE IF NOT EXISTS identities (
    id BIGINT PRIMARY KEY,
    plate TEXT NOT NULL,
    vehicle_type TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    valid BOOLEAN NOT NULL
);
CREATE TABLE IF NOT EXISTS aliases (
    plate TEXT PRIMARY KEY,
    identity_id BIGINT NOT NULL REFERENCES identities(id)
);
CREATE TABLE IF NOT EXISTS cameras (
    camera_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    latitude NUMERIC(9,6) NOT NULL,
    longitude NUMERIC(9,6) NOT NULL,
    coordinate_accuracy TEXT NOT NULL DEFAULT 'approximate',
    provenance TEXT NOT NULL DEFAULT 'staged/illustrative placement'
);
CREATE TABLE IF NOT EXISTS detections (
    id BIGINT PRIMARY KEY,
    event_id TEXT NOT NULL UNIQUE,
    identity_id BIGINT NOT NULL REFERENCES identities(id),
    camera_id TEXT NOT NULL REFERENCES cameras(camera_id),
    observed_at TIMESTAMPTZ NOT NULL,
    plate TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    payload TEXT NOT NULL,
    prev_hash CHAR(64) NOT NULL,
    hash CHAR(64) NOT NULL
);
CREATE INDEX IF NOT EXISTS detections_plate_timestamp ON detections(plate, observed_at);
CREATE INDEX IF NOT EXISTS detections_camera_timestamp ON detections(camera_id, observed_at);
CREATE INDEX IF NOT EXISTS detections_identity_timestamp ON detections(identity_id, observed_at);
CREATE TABLE IF NOT EXISTS trajectory_hops (
    detection_id BIGINT PRIMARY KEY REFERENCES detections(id) ON DELETE CASCADE,
    identity_id BIGINT NOT NULL REFERENCES identities(id),
    hop_order INTEGER NOT NULL,
    camera_id TEXT NOT NULL REFERENCES cameras(camera_id),
    observed_at TIMESTAMPTZ NOT NULL,
    previous_camera_id TEXT REFERENCES cameras(camera_id),
    leg_distance_km DOUBLE PRECISION,
    travel_seconds DOUBLE PRECISION,
    speed_kmh DOUBLE PRECISION,
    direction TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    provenance TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS trajectory_hops_identity_order ON trajectory_hops(identity_id, hop_order);
CREATE TABLE IF NOT EXISTS alerts (
    id BIGINT PRIMARY KEY,
    detection_id BIGINT REFERENCES detections(id) ON DELETE SET NULL,
    kind TEXT NOT NULL,
    severity TEXT NOT NULL,
    plate TEXT NOT NULL,
    camera_id TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    explanation TEXT NOT NULL,
    evidence TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
    id BIGINT PRIMARY KEY,
    observed_at TIMESTAMPTZ NOT NULL,
    role TEXT NOT NULL,
    action TEXT NOT NULL,
    details TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS watchlist (
    plate TEXT PRIMARY KEY,
    reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS traffic (
    event_id TEXT PRIMARY KEY,
    camera_id TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    vehicle_type TEXT NOT NULL,
    source TEXT NOT NULL
);
