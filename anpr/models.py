"""Validated request contracts, shared by ingestion and API documentation."""
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class PlateRead(StrictModel):
    text: str = Field(min_length=1, max_length=40)
    confidence: float = Field(ge=0, le=1)
    quality: float = Field(default=1, ge=0, le=1)


class IngestEvent(StrictModel):
    event_id: str = Field(min_length=1, max_length=200)
    camera_id: str = Field(pattern=r'^C0[1-8]$')
    timestamp: datetime
    vehicle_type: Literal['car', 'truck', 'bus', 'motorcycle', 'unknown'] = 'car'
    reads: list[PlateRead] = Field(min_length=1, max_length=120)
    source: str = Field(default='api', max_length=200)

    @field_validator('timestamp')
    @classmethod
    def require_timezone(cls, value):
        if value.tzinfo is None:
            raise ValueError('Timestamp requires an explicit timezone')
        return value.astimezone(timezone.utc)


class SimulationRequest(StrictModel):
    vehicles: int = Field(default=320, ge=1, le=1000)
    seed: int = Field(default=26127, ge=0, le=2147483647)


class TrafficEvent(StrictModel):
    event_id: str = Field(min_length=1, max_length=200)
    camera_id: str = Field(pattern=r'^C0[1-8]$')
    timestamp: datetime
    vehicle_type: Literal['car', 'truck', 'bus', 'motorcycle', 'unknown'] = 'unknown'
    source: str = Field(default='video', max_length=200)

    @field_validator('timestamp')
    @classmethod
    def require_timezone(cls, value):
        if value.tzinfo is None:
            raise ValueError('Timestamp requires an explicit timezone')
        return value.astimezone(timezone.utc)


class WatchRequest(StrictModel):
    plate: str = Field(min_length=5, max_length=20)
    reason: str = Field(min_length=3, max_length=300)


class PurgeRequest(StrictModel):
    before: datetime

    @field_validator('before')
    @classmethod
    def require_timezone(cls, value):
        if value.tzinfo is None:
            raise ValueError('Timestamp requires an explicit timezone')
        return value.astimezone(timezone.utc)
