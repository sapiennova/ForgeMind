"""Validated result types for sensor-health evaluations."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class HealthState(str, Enum):
    """Reliability state for an individual sensor, not its parent machine."""

    NORMAL = "NORMAL"
    SUSPECTED = "SUSPECTED"
    FAULT = "FAULT"
    DISCONNECTED = "DISCONNECTED"


class ReasonCode(str, Enum):
    """Stable machine-readable identifiers for detected sensor conditions."""

    NO_READINGS = "NO_READINGS"
    STALE_READING = "STALE_READING"
    FROZEN_VALUE = "FROZEN_VALUE"
    EXCESSIVE_SPIKE = "EXCESSIVE_SPIKE"
    ABNORMAL_RATE_OF_CHANGE = "ABNORMAL_RATE_OF_CHANGE"


def normalize_utc(value: datetime) -> datetime:
    """Interpret naive timestamps as UTC and convert aware timestamps to UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class DetectedCondition(BaseModel):
    """One independently detected condition and its supporting evidence."""

    model_config = ConfigDict(frozen=True)

    reason_code: ReasonCode
    health_state: HealthState
    explanation: str
    evidence: dict[str, Any]


class SensorHealthAssessment(BaseModel):
    """Deterministic sensor-health result for a single evaluation instant."""

    model_config = ConfigDict(frozen=True)

    sensor_id: UUID
    health_state: HealthState
    evaluated_at: datetime
    detected_conditions: tuple[DetectedCondition, ...]
    explanation: str
    supporting_evidence: dict[str, Any]

    @field_validator("evaluated_at", mode="before")
    @classmethod
    def normalize_evaluation_timestamp(cls, value: datetime) -> datetime:
        """Keep result timestamps consistently timezone-aware and in UTC."""
        return normalize_utc(value)
