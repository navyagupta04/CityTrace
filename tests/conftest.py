from datetime import datetime, timedelta, timezone
import uuid
import pytest
from anpr.platform import Platform


@pytest.fixture
def platform():
    service = Platform()
    yield service
    service.db.close()


@pytest.fixture
def event():
    def make(plate='DL01AB1234', camera='C01', minutes=0, confidence=.98, vehicle_type='car', **extras):
        return {'event_id': uuid.uuid4().hex, 'camera_id': camera,
                'timestamp': (datetime(2026, 9, 30, 3, tzinfo=timezone.utc) + timedelta(minutes=minutes)).isoformat(),
                'vehicle_type': vehicle_type, 'reads': [{'text': plate, 'confidence': confidence, 'quality': 1}] * 6, **extras}
    return make
