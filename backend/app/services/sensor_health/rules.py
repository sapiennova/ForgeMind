"""Independently testable deterministic sensor reliability rules."""

from datetime import datetime
import math
from typing import Sequence

from backend.app.models.sensor_reading import SensorReading
from backend.app.services.sensor_health.config import SensorHealthPolicy
from backend.app.services.sensor_health.schemas import (
    DetectedCondition,
    HealthState,
    ReasonCode,
    normalize_utc,
)


def _ordered_readings(
    readings: Sequence[SensorReading],
) -> list[tuple[datetime, SensorReading]]:
    """Return readings in chronological order with deterministic tie-breaking."""
    normalized = [(normalize_utc(item.recorded_at), item) for item in readings]
    return sorted(normalized, key=lambda pair: (pair[0], str(pair[1].id)))


def detect_missing_or_stale(
    readings: Sequence[SensorReading],
    evaluated_at: datetime,
    policy: SensorHealthPolicy,
) -> DetectedCondition | None:
    """Detect absent history or a latest reading beyond the freshness window."""
    if not readings:
        return DetectedCondition(
            reason_code=ReasonCode.NO_READINGS,
            health_state=HealthState.DISCONNECTED,
            explanation="No readings have ever been received from this sensor.",
            evidence={"reading_count": 0},
        )

    latest_at, _ = max(
        ((normalize_utc(item.recorded_at), item) for item in readings),
        key=lambda pair: (pair[0], str(pair[1].id)),
    )
    age_seconds = (normalize_utc(evaluated_at) - latest_at).total_seconds()
    if age_seconds > policy.freshness_threshold_seconds:
        return DetectedCondition(
            reason_code=ReasonCode.STALE_READING,
            health_state=HealthState.DISCONNECTED,
            explanation="The latest sensor reading is older than the configured freshness threshold.",
            evidence={
                "latest_recorded_at": latest_at.isoformat(),
                "age_seconds": age_seconds,
                "freshness_threshold_seconds": policy.freshness_threshold_seconds,
            },
        )
    return None


def detect_frozen_value(
    readings: Sequence[SensorReading],
    policy: SensorHealthPolicy,
) -> DetectedCondition | None:
    """Detect a sufficiently long trailing run of values equal within tolerance."""
    if not readings:
        return None

    ordered = _ordered_readings(readings)
    longest_count = 1
    longest_value = float(ordered[0][1].value)
    run_count = 1
    run_value = float(ordered[0][1].value)

    for _, reading in ordered[1:]:
        value = float(reading.value)
        if math.isclose(value, run_value, rel_tol=0.0, abs_tol=policy.frozen_tolerance):
            run_count += 1
        else:
            if run_count >= longest_count:
                longest_count, longest_value = run_count, run_value
            run_count, run_value = 1, value

    if run_count >= longest_count:
        longest_count, longest_value = run_count, run_value

    if longest_count < policy.frozen_min_consecutive_readings:
        return None

    return DetectedCondition(
        reason_code=ReasonCode.FROZEN_VALUE,
        health_state=HealthState.FAULT,
        explanation="Consecutive readings are effectively unchanged for longer than the configured evidence threshold.",
        evidence={
            "repeated_value": longest_value,
            "consecutive_reading_count": longest_count,
            "minimum_consecutive_readings": policy.frozen_min_consecutive_readings,
            "numeric_tolerance": policy.frozen_tolerance,
        },
    )


def detect_excessive_spike(
    readings: Sequence[SensorReading],
    policy: SensorHealthPolicy,
) -> DetectedCondition | None:
    """Detect adjacent reading differences exceeding an explicitly configured limit."""
    if policy.spike_threshold is None:
        return None

    ordered = _ordered_readings(readings)
    events = []
    for (_, previous), (_, current) in zip(ordered, ordered[1:]):
        difference = abs(float(current.value) - float(previous.value))
        if difference > policy.spike_threshold:
            events.append(
                {
                    "previous_value": float(previous.value),
                    "current_value": float(current.value),
                    "difference": difference,
                    "threshold": policy.spike_threshold,
                }
            )

    if not events:
        return None

    return DetectedCondition(
        reason_code=ReasonCode.EXCESSIVE_SPIKE,
        health_state=HealthState.SUSPECTED,
        explanation="One or more consecutive readings changed by more than the configured spike threshold.",
        evidence={"events": events, "event_count": len(events)},
    )


def detect_abnormal_rate_of_change(
    readings: Sequence[SensorReading],
    policy: SensorHealthPolicy,
) -> DetectedCondition | None:
    """Detect rapid changes measured in sensor-units per elapsed second.

    Pairs with zero or negative elapsed time are skipped because a rate cannot
    be calculated reliably without a strictly positive time interval.
    """
    if policy.max_rate_of_change_per_second is None:
        return None

    ordered = _ordered_readings(readings)
    events = []
    for (previous_at, previous), (current_at, current) in zip(ordered, ordered[1:]):
        elapsed_seconds = (current_at - previous_at).total_seconds()
        if elapsed_seconds <= 0:
            continue

        difference = abs(float(current.value) - float(previous.value))
        rate = difference / elapsed_seconds
        if rate > policy.max_rate_of_change_per_second:
            events.append(
                {
                    "previous_value": float(previous.value),
                    "current_value": float(current.value),
                    "difference": difference,
                    "elapsed_seconds": elapsed_seconds,
                    "rate_per_second": rate,
                    "maximum_rate_per_second": policy.max_rate_of_change_per_second,
                }
            )

    if not events:
        return None

    return DetectedCondition(
        reason_code=ReasonCode.ABNORMAL_RATE_OF_CHANGE,
        health_state=HealthState.SUSPECTED,
        explanation="One or more readings changed faster than the configured maximum rate of change.",
        evidence={"events": events, "event_count": len(events)},
    )
