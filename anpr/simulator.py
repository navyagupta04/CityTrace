"""Seeded synthetic OCR benchmark; truth is used ONLY for evaluation."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import random
from .vision import Read, vote
from .plates import normalize
from .alerts import list_alerts

CONDITIONS = {'day': (0.04, 0.97, 0.97), 'night': (0.13, 0.82, 0.75),
              'rain': (0.16, 0.80, 0.70), 'blur': (0.22, 0.76, 0.60), 'dirty': (0.19, 0.79, 0.68)}
CONFUSIONS = {'0': 'OD', '1': 'IL', '2': 'Z', '5': 'S', '6': 'G', '8': 'B',
              'O': '0', 'I': '1', 'Z': '2', 'S': '5', 'G': '6', 'B': '8', 'D': '0'}


def noisy_frames(plate: str, condition: str, rng: random.Random, correlated=False):
    probability, certainty, quality = CONDITIONS[condition]
    base = plate
    if correlated:
        slot = rng.randrange(len(plate) - 4, len(plate))
        base = plate[:slot] + str((int(plate[slot]) + 1) % 10) + plate[slot + 1:]
        certainty = min(certainty, 0.72)
    reads = []
    for _ in range(6):
        chars = []
        for c in base:
            if rng.random() < probability:
                c = rng.choice(CONFUSIONS[c]) if c in CONFUSIONS and rng.random() < 0.7 else rng.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
            chars.append(c)
        text = ''.join(chars)
        if rng.random() < probability * 0.25:
            text = text[:-1]
        reads.append({'text': text, 'confidence': round(max(0.1, min(0.99, certainty + rng.uniform(-0.04, 0.02))), 3),
                      'quality': round(max(0.1, min(1, quality + rng.uniform(-0.05, 0.03))), 3)})
    return reads


def run(platform, vehicles=320, seed=26127, start: datetime | None = None) -> dict:
    """Replay timestamp-ordered passes; repeat seed/start is ingestion-idempotent."""
    rng = random.Random(seed)
    start = start or datetime(2026, 9, 30, 3, 0, tzinfo=timezone.utc)
    routes = [('C02', 'C08'), ('C03', 'C05'), ('C01', 'C08'), ('C07', 'C01'), ('C05', 'C02')]
    events = []
    missing = 0
    for index in range(vehicles):
        letters = ''.join(rng.choice('ACEFHKMNPRTUVWXY') for _ in range(2))
        plate = f'{rng.choice(["DL", "HR", "UP"])}{rng.randrange(1, 15):02}{letters}{1000 + index:04}'
        vehicle_type = rng.choice(['car', 'car', 'car', 'truck', 'bus', 'motorcycle'])
        origin, destination = rng.choice(routes)
        _, path = platform.graph.shortest(origin, destination)
        timestamp = start + timedelta(seconds=rng.randrange(0, 3600))
        for leg, camera in enumerate(path):
            if leg:
                a = path[leg - 1]
                km, free = platform.graph.edges[a][camera]
                speed = rng.uniform(9, 14) if {a, camera} == {'C04', 'C06'} else free * rng.uniform(0.65, 0.95)
                timestamp += timedelta(seconds=km / speed * 3600)
            if rng.random() < 0.05:
                missing += 1
                continue
            condition = rng.choice(list(CONDITIONS))
            reads = noisy_frames(plate, condition, rng, correlated=(leg > 0 and rng.random() < 0.12))
            event = {'event_id': f'sim-{seed}-{start.isoformat()}-{index}-{leg}', 'camera_id': camera,
                     'timestamp': timestamp.isoformat(), 'vehicle_type': vehicle_type, 'reads': reads, 'source': 'simulator'}
            events.append((event, plate, condition))
    platform.watch('DL01AB1234', 'Demo watchlist · authorized investigation SIH-026')
    scripts = [('DL01AB1234', [('C01', 0), ('C04', 420), ('C06', 900), ('C08', 1500)]),
               ('DL08CX9090', [('C01', 120), ('C08', 360)]),
               ('22BH4321AA', [('C08', 54000)])]
    for plate, passes in scripts:
        for leg, (camera, seconds) in enumerate(passes):
            events.append(({'event_id': f'script-{seed}-{start.isoformat()}-{plate}-{leg}', 'camera_id': camera,
                            'timestamp': (start + timedelta(seconds=seconds)).isoformat(), 'vehicle_type': 'car',
                            'reads': [{'text': plate, 'confidence': 0.98, 'quality': 0.99}] * 6, 'source': 'simulator'}, plate, 'scripted'))
    events.sort(key=lambda item: item[0]['timestamp'])
    outcomes, emitted = [], []
    for event, truth, condition in events:
        response = platform.ingest(event)
        detection = response['detection']
        emitted.extend(response['alerts'])
        outcomes.append({'truth': truth, 'condition': condition,
                         'single': normalize(event['reads'][0]['text']).text,
                         'voted': detection['plate'], 'online': detection['resolution']['canonical_plate'],
                         'identity_id': detection['identity_id']})
    identities = {row['id']: row['plate'] for row in platform.db.rows('SELECT id,plate FROM identities')}
    scores = defaultdict(lambda: {'passes': 0, 'single': 0, 'voted': 0, 'resolved': 0, 'online': 0})
    for row in outcomes:
        if row['condition'] == 'scripted':
            continue
        score = scores[row['condition']]
        score['passes'] += 1
        for stage in ('single', 'voted', 'online'):
            score[stage] += row[stage] == row['truth']
        score['resolved'] += identities[row['identity_id']] == row['truth']
    accuracy = [{'condition': condition, 'passes': score['passes'],
                 **{stage: round(100 * score[stage] / score['passes'], 2) for stage in ('single', 'voted', 'online', 'resolved')}}
                for condition, score in sorted(scores.items())]
    with platform.db.transaction():
        platform.db.audit('admin', 'simulation.run', {'seed': seed, 'vehicles': vehicles, 'passes': len(events), 'start': start.isoformat()})
    return {'vehicles_generated': vehicles + 3, 'passes': len(events), 'missed_passes': missing, 'seed': seed,
            'accuracy': accuracy, 'new_alerts': emitted, 'summary': platform.analytics()['summary'],
            'integrity': platform.db.verify(), 'example_plate': 'DL01AB1234'}
