"""SQLite persistence. Evidence is immutable and chained in ingestion order."""
from contextlib import contextmanager
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from threading import RLock
from datetime import datetime, timezone


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def digest(previous: str, payload: str) -> str:
    return sha256((previous + '\n' + payload).encode()).hexdigest()


class Database:
    def __init__(self, path: str = ':memory:'):
        if path != ':memory:':
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript('''
            PRAGMA foreign_keys=ON;
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS identities (
                id INTEGER PRIMARY KEY, plate TEXT NOT NULL, vehicle_type TEXT NOT NULL,
                confidence REAL NOT NULL, valid INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS aliases (
                plate TEXT PRIMARY KEY, identity_id INTEGER NOT NULL REFERENCES identities(id));
            CREATE TABLE IF NOT EXISTS detections (
                id INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE,
                identity_id INTEGER NOT NULL REFERENCES identities(id), camera_id TEXT NOT NULL,
                timestamp TEXT NOT NULL, plate TEXT NOT NULL, confidence REAL NOT NULL,
                payload TEXT NOT NULL, prev_hash TEXT NOT NULL, hash TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS detection_identity_time ON detections(identity_id,timestamp);
            CREATE INDEX IF NOT EXISTS detection_time ON detections(timestamp);
            CREATE TABLE IF NOT EXISTS traffic (
                event_id TEXT PRIMARY KEY, camera_id TEXT NOT NULL, timestamp TEXT NOT NULL,
                vehicle_type TEXT NOT NULL, source TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS watchlist (plate TEXT PRIMARY KEY, reason TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY, detection_id INTEGER REFERENCES detections(id),
                kind TEXT NOT NULL, severity TEXT NOT NULL, plate TEXT NOT NULL,
                camera_id TEXT NOT NULL, timestamp TEXT NOT NULL, explanation TEXT NOT NULL,
                evidence TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, role TEXT NOT NULL,
                action TEXT NOT NULL, details TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        ''')
        for key, value in [('anchor', '0' * 64), ('head', '0' * 64), ('count', '0')]:
            self.conn.execute('INSERT OR IGNORE INTO metadata VALUES (?,?)', (key, value))
        self.conn.commit()

    @contextmanager
    def transaction(self):
        """Serialize writers and commit identity, evidence, and alerts atomically."""
        with self.lock:
            with self.conn:
                yield

    def rows(self, sql: str, params=()) -> list[dict]:
        with self.lock:
            return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def meta(self, key: str) -> str:
        return self.rows('SELECT value FROM metadata WHERE key=?', (key,))[0]['value']

    def set_meta(self, key: str, value: str):
        self.conn.execute('UPDATE metadata SET value=? WHERE key=?', (value, key))

    def audit(self, role: str, action: str, details: dict):
        self.conn.execute('INSERT INTO audit(timestamp,role,action,details) VALUES (?,?,?,?)',
                          (utcnow(), role, action, canonical(details)))

    def append(self, event: dict) -> dict:
        payload = canonical(event)
        previous = self.meta('head')
        hashed = digest(previous, payload)
        cursor = self.conn.execute('''INSERT INTO detections
            (event_id,identity_id,camera_id,timestamp,plate,confidence,payload,prev_hash,hash)
            VALUES (?,?,?,?,?,?,?,?,?)''', tuple(event[k] for k in
            ('event_id', 'identity_id', 'camera_id', 'timestamp', 'plate', 'confidence')) + (payload, previous, hashed))
        self.set_meta('head', hashed)
        self.set_meta('count', str(int(self.meta('count')) + 1))
        return {**event, 'id': cursor.lastrowid, 'hash': hashed}

    def verify(self) -> dict:
        """Verify payloads, query columns, link order, retained count and tail."""
        with self.lock:
            previous = self.meta('anchor')
            rows = self.rows('SELECT * FROM detections ORDER BY id')
            for row in rows:
                try:
                    payload = json.loads(row['payload'])
                    columns_ok = all(payload[k] == row[k] for k in
                                     ('event_id', 'identity_id', 'camera_id', 'timestamp', 'plate', 'confidence'))
                    ok = columns_ok and row['prev_hash'] == previous and row['hash'] == digest(previous, row['payload'])
                except (ValueError, KeyError, TypeError):
                    ok = False
                if not ok:
                    return {'valid': False, 'checked': len(rows), 'broken_at': row['id']}
                previous = row['hash']
            ok = previous == self.meta('head') and len(rows) == int(self.meta('count'))
            return {'valid': ok, 'checked': len(rows), 'head': previous, 'anchor': self.meta('anchor')}

    def purge(self, before: str) -> dict:
        """Remove an expired ingestion prefix, preserving the boundary hash.

        Late arrivals after a nonexpired row are retained until a future purge.
        This never rewrites hashes or disguises preexisting corruption.
        """
        with self.transaction():
            if not self.verify()['valid']:
                raise ValueError('Integrity check failed; purge refused')
            expired = []
            for row in self.rows('SELECT id,timestamp,hash FROM detections ORDER BY id'):
                if row['timestamp'] >= before:
                    break
                expired.append(row)
            if expired:
                last = expired[-1]
                self.conn.execute('DELETE FROM alerts WHERE detection_id<=?', (last['id'],))
                self.conn.execute('DELETE FROM detections WHERE id<=?', (last['id'],))
                self.set_meta('anchor', last['hash'])
                self.set_meta('count', str(int(self.meta('count')) - len(expired)))
                self.conn.execute('DELETE FROM aliases WHERE identity_id NOT IN (SELECT identity_id FROM detections)')
                self.conn.execute('DELETE FROM identities WHERE id NOT IN (SELECT identity_id FROM detections)')
            traffic_deleted = self.conn.execute('DELETE FROM traffic WHERE timestamp<?', (before,)).rowcount
            self.audit('admin', 'retention.purge', {'before': before, 'deleted': len(expired), 'anchor': self.meta('anchor')})
            return {'deleted': len(expired), 'traffic_deleted': traffic_deleted, 'integrity': self.verify()}

    def close(self):
        self.conn.close()
