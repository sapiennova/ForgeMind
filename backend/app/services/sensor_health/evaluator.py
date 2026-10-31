"""Orchestration for deterministic sensor-health assessments."""

from datetime import datetime
from typing import Sequence

from backend.app.models.sensor import Sensor
from backend.app.models.sensor_reading import SensorReading
from backend.app.services.sensor_health.config import SensorHealthPolicy
from backend.app.services.sensor_health.rules import (
    detect_abnormal_rate_of_change,
    detect_excessive_spike,
    detect_frozen_value,
    detect_missing_or_stale,
)
from backend.app.services.sensor_health.schemas import (
    DetectedCondition,
    HealthState,
    SensorHealthAssessment,
    normalize_utc,
)

_STATE_PRECEDENCE = {
    HealthState.NORMAL: 0,
    HealthState.SUSPECTED: 1,
    HealthState.FAULT: 2,
    HealthState.DISCONNECTED: 3,
}


def evaluate_sensor_health(
    sensor: Sensor,
    readings: Sequence[SensorReading],
    evaluated_at: datetime,
    policy: SensorHealthPolicy | None = None,
) -> SensorHealthAssessment:
    """Evaluate one sensor without database access or mutation.

    The caller supplies the sensor, its readings, and the evaluation timestamp.
    Naive timestamps are interpreted as UTC, matching ForgeMind's API convention.
    State precedence is DISCONNECTED > FAULT > SUSPECTED > NORMAL; all detected
    conditions remain present in the returned assessment.
    """
    if not isinstance(evaluated_at, datetime):
        raise TypeError("evaluated_at must be a datetime")

    timestamp = normalize_utc(evaluated_at)
    active_policy = policy or SensorHealthPolicy()

    conditions: list[DetectedCondition] = []
    for condition in (
        detect_missing_or_stale(readings, timestamp, active_policy),
        detect_frozen_value(readings, active_policy),
        detect_excessive_spike(readings, active_policy),
        detect_abnormal_rate_of_change(readings, active_policy),
    ):
        if condition is not None:
            conditions.append(condition)

    state = (
        max((item.health_state for item in conditions), key=_STATE_PRECEDENCE.__getitem__)
        if conditions
        else HealthState.NORMAL
    )
    explanation = (
        " ".join(item.explanation for item in conditions)
        if conditions
        else "No configured sensor reliability rule indicates a problem."
    )
    evidence = {item.reason_code.value: item.evidence for item in conditions}

    return SensorHealthAssessment(
        sensor_id=sensor.id,
        health_state=state,
        evaluated_at=timestamp,
        detected_conditions=tuple(conditions),
        explanation=explanation,
        supporting_evidence=evidence,
    )
