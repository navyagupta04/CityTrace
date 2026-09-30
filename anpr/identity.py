"""Conservative, explainable identity linking using OCR and road topology."""
from datetime import datetime
from .config import RECENT_SECONDS
from .plates import normalize, weighted_distance


class IdentityResolver:
    def __init__(self, db, graph):
        self.db, self.graph = db, graph

    def resolve(self, plate: str, confidence: float, vehicle_type: str, camera: str, timestamp: str) -> dict:
        normalized = normalize(plate)
        exact = self.db.rows('SELECT i.* FROM identities i JOIN aliases a ON a.identity_id=i.id WHERE a.plate=?', (normalized.text,))
        if exact:
            return self._accept(exact[0], normalized, confidence, 'exact', 1.0)
        now = datetime.fromisoformat(timestamp)
        limit = 1.3 if confidence < 0.8 or not normalized.valid else 0.35
        candidates = []
        for identity in self.db.rows('SELECT * FROM identities WHERE vehicle_type=?', (vehicle_type,)):
            distance = weighted_distance(normalized.text, identity['plate'])
            if distance > limit:
                continue
            detections = self.db.rows('SELECT * FROM detections WHERE identity_id=? ORDER BY timestamp', (identity['id'],))
            previous = [d for d in detections if d['timestamp'] <= timestamp]
            following = [d for d in detections if d['timestamp'] > timestamp]
            neighbors = (previous[-1:] + following[:1])
            if not neighbors or min(abs((now - datetime.fromisoformat(d['timestamp'])).total_seconds()) for d in neighbors) > RECENT_SECONDS:
                continue
            if not all(self.graph.possible(camera, d['camera_id'], abs((now - datetime.fromisoformat(d['timestamp'])).total_seconds())) for d in neighbors):
                continue
            text_score = max(0, 1 - distance / max(len(normalized.text), len(identity['plate']), 1))
            score = 0.75 * text_score + 0.10 + 0.15  # matching type and feasible topology
            if score >= 0.88:
                candidates.append((score, identity))
        candidates.sort(key=lambda item: item[0], reverse=True)
        # Do not silently merge near-tied candidates.
        if candidates and (len(candidates) == 1 or candidates[0][0] - candidates[1][0] >= 0.025):
            score, identity = candidates[0]
            return self._accept(identity, normalized, confidence, 'fuzzy', score)
        cursor = self.db.conn.execute('INSERT INTO identities(plate,vehicle_type,confidence,valid) VALUES (?,?,?,?)',
                                      (normalized.text, vehicle_type, confidence, normalized.valid))
        self.db.conn.execute('INSERT INTO aliases VALUES (?,?)', (normalized.text, cursor.lastrowid))
        return {'identity_id': cursor.lastrowid, 'canonical_plate': normalized.text, 'method': 'new', 'score': 1.0}

    def _accept(self, identity, plate, confidence, method, score):
        canonical_plate = identity['plate']
        if plate.valid and (not identity['valid'] or confidence > identity['confidence'] + 0.03):
            canonical_plate = plate.text
            self.db.conn.execute('UPDATE identities SET plate=?,confidence=?,valid=1 WHERE id=?', (plate.text, confidence, identity['id']))
        self.db.conn.execute('INSERT OR IGNORE INTO aliases VALUES (?,?)', (plate.text, identity['id']))
        return {'identity_id': identity['id'], 'canonical_plate': canonical_plate, 'method': method, 'score': round(score, 4)}
