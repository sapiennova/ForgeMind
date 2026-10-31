"""Focused unit tests for independently callable sensor-health rules."""

from datetime import datetime, timedelta, timezone

from backend.app.services.sensor_health.config import SensorHealthPolicy
from backend.app.services.sensor_health.rules import (
    detect_abnormal_rate_of_change,
    detect_excessive_spike,
    detect_frozen_value,
    detect_missing_or_stale,
)
from backend.app.services.sensor_health.schemas import HealthState, ReasonCode


def test_missing_reading_rule_reports_no_readings():
    condition = detect_missing_or_stale([], datetime(2026, 10, 31, tzinfo=timezone.utc),
                                        SensorHealthPolicy())
    assert condition is not None
    assert condition.reason_code is ReasonCode.NO_READINGS
    assert condition.health_state is HealthState.DISCONNECTED


def test_frozen_rule_does_not_flag_short_sequence(make_readings):
    condition = detect_frozen_value(make_readings([3.0, 3.0, 3.0]), SensorHealthPolicy())
    assert condition is None


def test_spike_rule_is_disabled_without_sensor_specific_threshold(make_readings):
    assert detect_excessive_spike(make_readings([1.0, 1000.0]), SensorHealthPolicy()) is None


def test_rate_rule_skips_non_positive_elapsed_time(make_readings):
    readings = make_readings([1.0, 100.0], interval_seconds=0)
    policy = SensorHealthPolicy(max_rate_of_change_per_second=0.01)
    assert detect_abnormal_rate_of_change(readings, policy) is None


def test_stale_rule_uses_explicit_evaluation_time(make_readings):
    evaluated = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
    readings = make_readings([1.0], start=evaluated - timedelta(seconds=600))
    condition = detect_missing_or_stale(readings, evaluated, SensorHealthPolicy(
        freshness_threshold_seconds=300
    ))
    assert condition is not None
    assert condition.reason_code is ReasonCode.STALE_READING



def test_spike_rule_orders_readings_chronologically(make_readings):
    readings = list(reversed(make_readings([1.0, 2.0, 20.0])))
    condition = detect_excessive_spike(
        readings, SensorHealthPolicy(spike_threshold=10.0)
    )
    assert condition is not None
    assert condition.evidence["events"][0]["previous_value"] == 2.0
    assert condition.evidence["events"][0]["current_value"] == 20.0
