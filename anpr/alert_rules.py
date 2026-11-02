"""Load a small, validated JSON-compatible YAML alert rules file."""
import json
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Rule(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: bool = True
    severity: Literal['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] = 'MEDIUM'


class CloneRule(Rule):
    max_plausible_speed_kmph: float = Field(default=140, gt=0)
    min_read_confidence: float = Field(default=.8, ge=0, le=1)
    fuzzy_identity_distance: float = Field(default=.3, ge=0, le=1)
    min_gap_seconds_to_flag: float = Field(default=0, ge=0)
    require_distinct_cameras: bool = True
    lookback_window_minutes: int = Field(default=180, gt=0)


class OverspeedRule(Rule):
    default_limit_kmph: float = Field(default=50, gt=0)
    camera_limits_kmph: dict[str, float] = Field(default_factory=dict)
    zone_limits_kmph: dict[str, float] = Field(default_factory=dict)
    tolerance_kmph: float = Field(default=5, ge=0)
    method: Literal['camera_reported_speed', 'average_between_cameras'] = 'camera_reported_speed'


class WrongWayRule(Rule):
    direction_tolerance_degrees: float = Field(default=60, ge=0, le=180)
    min_read_confidence: float = Field(default=.8, ge=0, le=1)
    expected_bearings_degrees: dict[str, float] = Field(default_factory=dict)
    bearing_data_note: str = 'Configure verified expected bearings before operational use.'


class BlacklistRule(Rule):
    severity_by_reason: dict[str, Literal['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']] = Field(default_factory=lambda: {'default': 'HIGH', 'fuzzy': 'MEDIUM'})
    max_fuzzy_distance: float = Field(default=.3, ge=0, le=1)


class RestrictedRule(Rule):
    timezone: str = 'Asia/Kolkata'
    start_hour: int = Field(default=22, ge=0, le=23)
    end_hour: int = Field(default=6, ge=0, le=23)


class RepeatRule(Rule):
    count: int = Field(default=3, ge=2)
    window_minutes: int = Field(default=30, gt=0)


class AlertRules(BaseModel):
    model_config = ConfigDict(extra='forbid')
    clone_plate: CloneRule = Field(default_factory=CloneRule)
    overspeed: OverspeedRule = Field(default_factory=OverspeedRule)
    wrong_way: WrongWayRule = Field(default_factory=WrongWayRule)
    blacklist: BlacklistRule = Field(default_factory=BlacklistRule)
    restricted_hours: RestrictedRule = Field(default_factory=RestrictedRule)
    repeat_visits: RepeatRule = Field(default_factory=RepeatRule)


def load_rules(path: str | Path | None = None) -> AlertRules:
    path = Path(path or Path(__file__).resolve().parent.parent / 'configs' / 'alert_rules.yaml')
    # JSON is a strict subset of YAML, allowing the core runtime to avoid PyYAML.
    return AlertRules.model_validate(json.loads(path.read_text(encoding='utf-8')))
