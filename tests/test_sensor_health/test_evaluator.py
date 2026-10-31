"""Unit tests for sensor-health evaluation and state resolution."""

from datetime import datetime, timedelta, timezone

import pytest

from backend.app.services.sensor_health import (
    HealthState,
    ReasonCode,
    SensorHealthPolicy,
    evaluate_sensor_health,
)


EVALUATED_AT = datetime(2026, 10, 31, 12, 1, tzinfo=timezone.utc)


def codes(result):
    return {condition.reason_code for condition in result.detected_conditions}


def test_normal_sensor_readings_are_normal(sensor, make_readings):
    readings = make_readings([10.0, 10.2, 10.1])
    result = evaluate_sensor_health(sensor, readings, EVALUATED_AT)
    assert result.health_state is HealthState.NORMAL
    assert result.detected_conditions == ()
    assert result.supporting_evidence == {}


def test_sensor_without_readings_is_disconnected(sensor):
    result = evaluate_sensor_health(sensor, [], EVALUATED_AT)
    assert result.health_state is HealthState.DISCONNECTED
    assert codes(result) == {ReasonCode.NO_READINGS}
    assert result.supporting_evidence["NO_READINGS"]["reading_count"] == 0


def test_stale_reading_is_disconnected(sensor, make_readings):
    readings = make_readings([1.0], start=EVALUATED_AT - timedelta(seconds=301))
    result = evaluate_sensor_health(
        sensor, readings, EVALUATED_AT, SensorHealthPolicy(freshness_threshold_seconds=300)
    )
    assert result.health_state is HealthState.DISCONNECTED
    assert codes(result) == {ReasonCode.STALE_READING}


def test_reading_at_freshness_boundary_is_fresh(sensor, make_readings):
    readings = make_readings([1.0], start=EVALUATED_AT - timedelta(seconds=300))
    result = evaluate_sensor_health(sensor, readings, EVALUATED_AT)
    assert result.health_state is HealthState.NORMAL


def test_fresh_readings_remain_normal(sensor, make_readings):
    readings = make_readings([2.0, 2.1, 2.2], start=EVALUATED_AT - timedelta(seconds=2))
    result = evaluate_sensor_health(sensor, readings, EVALUATED_AT)
    assert result.health_state is HealthState.NORMAL


def test_frozen_consecutive_readings_are_suspected(sensor, make_readings):
    readings = make_readings([7.0] * 5)
    result = evaluate_sensor_health(sensor, readings, EVALUATED_AT)
    assert result.health_state is HealthState.SUSPECTED
    condition = next(item for item in result.detected_conditions if item.reason_code is ReasonCode.FROZEN_VALUE)
    assert condition.evidence["repeated_value"] == 7.0
    assert condition.evidence["consecutive_reading_count"] == 5


def test_insufficient_frozen_evidence_is_not_fault(sensor, make_readings):
    result = evaluate_sensor_health(sensor, make_readings([7.0] * 4), EVALUATED_AT)
    assert result.health_state is HealthState.NORMAL
    assert ReasonCode.FROZEN_VALUE not in codes(result)


def test_frozen_detection_uses_numeric_tolerance(sensor, make_readings):
    readings = make_readings([1.0, 1.0 + 1e-7, 1.0 - 1e-7, 1.0, 1.0 + 2e-7])
    policy = SensorHealthPolicy(frozen_min_consecutive_readings=5, frozen_tolerance=1e-6)
    result = evaluate_sensor_health(sensor, readings, EVALUATED_AT, policy)
    assert ReasonCode.FROZEN_VALUE in codes(result)


def test_excessive_spike_is_suspected(sensor, make_readings):
    readings = make_readings([1.0, 2.0, 20.0])
    result = evaluate_sensor_health(
        sensor, readings, EVALUATED_AT, SensorHealthPolicy(spike_threshold=10.0)
    )
    assert result.health_state is HealthState.SUSPECTED
    condition = next(item for item in result.detected_conditions if item.reason_code is ReasonCode.EXCESSIVE_SPIKE)
    event = condition.evidence["events"][0]
    assert event["previous_value"] == 2.0
    assert event["current_value"] == 20.0
    assert event["difference"] == 18.0


def test_change_below_spike_threshold_is_not_flagged(sensor, make_readings):
    result = evaluate_sensor_health(
        sensor, make_readings([1.0, 9.0]), EVALUATED_AT,
        SensorHealthPolicy(spike_threshold=10.0),
    )
    assert ReasonCode.EXCESSIVE_SPIKE not in codes(result)


def test_abnormal_rate_of_change_is_suspected(sensor, make_readings):
    readings = make_readings([0.0, 4.0], interval_seconds=2)
    result = evaluate_sensor_health(
        sensor, readings, EVALUATED_AT,
        SensorHealthPolicy(max_rate_of_change_per_second=1.5),
    )
    assert ReasonCode.ABNORMAL_RATE_OF_CHANGE in codes(result)
    event = result.supporting_evidence["ABNORMAL_RATE_OF_CHANGE"]["events"][0]
    assert event["rate_per_second"] == 2.0
    assert event["elapsed_seconds"] == 2.0


def test_zero_elapsed_time_is_skipped_for_rate(sensor, make_readings):
    timestamp = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
    readings = make_readings([1.0, 100.0], start=timestamp, interval_seconds=0)
    result = evaluate_sensor_health(
        sensor, readings, EVALUATED_AT,
        SensorHealthPolicy(max_rate_of_change_per_second=0.1),
    )
    assert ReasonCode.ABNORMAL_RATE_OF_CHANGE not in codes(result)


def test_multiple_conditions_are_preserved_and_precedence_is_deterministic(sensor, make_readings):
    old = EVALUATED_AT - timedelta(hours=1)
    readings = make_readings([1.0, 100.0, 100.0, 100.0, 100.0, 100.0], start=old)
    policy = SensorHealthPolicy(
        freshness_threshold_seconds=60,
        frozen_min_consecutive_readings=5,
        spike_threshold=10.0,
        max_rate_of_change_per_second=0.1,
    )
    result = evaluate_sensor_health(sensor, readings, EVALUATED_AT, policy)
    assert result.health_state is HealthState.DISCONNECTED
    assert ReasonCode.STALE_READING in codes(result)
    assert ReasonCode.FROZEN_VALUE in codes(result)
    assert ReasonCode.EXCESSIVE_SPIKE in codes(result)
    assert ReasonCode.ABNORMAL_RATE_OF_CHANGE in codes(result)


def test_frozen_and_spike_conditions_resolve_to_suspected(sensor, make_readings):
    readings = make_readings([1.0, 30.0, 30.0, 30.0, 30.0, 30.0],
                             start=EVALUATED_AT - timedelta(seconds=5))
    policy = SensorHealthPolicy(
        frozen_min_consecutive_readings=5,
        spike_threshold=10.0,
    )
    result = evaluate_sensor_health(sensor, readings, EVALUATED_AT, policy)
    assert result.health_state is HealthState.SUSPECTED
    assert ReasonCode.EXCESSIVE_SPIKE in codes(result)
    assert ReasonCode.FROZEN_VALUE in codes(result)


def test_utc_timestamp_is_normalized(sensor, make_readings):
    local_offset = timezone(timedelta(hours=5, minutes=30))
    evaluated = datetime(2026, 10, 31, 17, 31, tzinfo=local_offset)
    result = evaluate_sensor_health(sensor, make_readings([1.0]), evaluated)
    assert result.evaluated_at == EVALUATED_AT
    assert result.evaluated_at.utcoffset() == timedelta(0)


def test_naive_evaluation_timestamp_is_interpreted_as_utc(sensor, make_readings):
    naive = datetime(2026, 10, 31, 12, 1)
    result = evaluate_sensor_health(sensor, make_readings([1.0]), naive)
    assert result.evaluated_at == EVALUATED_AT


def test_invalid_evaluation_timestamp_type_is_rejected(sensor):
    with pytest.raises(TypeError):
        evaluate_sensor_health(sensor, [], "2026-10-31T12:00:00")  # type: ignore[arg-type]


def test_empty_input_is_deterministically_disconnected(sensor):
    result = evaluate_sensor_health(sensor, [], EVALUATED_AT)
    assert result.health_state is HealthState.DISCONNECTED


@pytest.mark.parametrize(
    "kwargs",
    [
        {"freshness_threshold_seconds": 0},
        {"freshness_threshold_seconds": float("inf")},
        {"frozen_min_consecutive_readings": 1},
        {"frozen_min_consecutive_readings": 2.5},
        {"frozen_tolerance": -1.0},
        {"frozen_tolerance": float("nan")},
        {"spike_threshold": 0},
        {"max_rate_of_change_per_second": -1},
    ],
)
def test_invalid_policy_parameters_are_rejected(kwargs):
    with pytest.raises(ValueError):
        SensorHealthPolicy(**kwargs)



def test_historical_frozen_run_does_not_override_recovered_latest_readings(sensor, make_readings):
    readings = make_readings([5.0] * 5 + [6.0, 7.0])
    result = evaluate_sensor_health(sensor, readings, EVALUATED_AT)
    assert ReasonCode.FROZEN_VALUE not in codes(result)
    assert result.health_state is HealthState.NORMAL

def test_future_reading_does_not_hide_an_old_legitimate_reading(sensor, make_readings):
    old_reading = make_readings(
        [12.0], start=EVALUATED_AT - timedelta(seconds=301)
    )
    future_reading = make_readings(
        [999.0], start=EVALUATED_AT + timedelta(seconds=60)
    )

    result = evaluate_sensor_health(
        sensor,
        old_reading + future_reading,
        EVALUATED_AT,
        SensorHealthPolicy(freshness_threshold_seconds=300),
    )

    assert result.health_state is HealthState.DISCONNECTED
    assert codes(result) == {ReasonCode.STALE_READING}
    assert result.supporting_evidence["STALE_READING"]["latest_recorded_at"] == (
        old_reading[0].recorded_at.isoformat()
    )


def test_future_readings_cannot_influence_any_detection_rule(sensor, make_readings):
    fresh_readings = make_readings(
        [1.0, 2.0, 3.0], start=EVALUATED_AT - timedelta(seconds=2)
    )
    future_repeated_readings = make_readings(
        [1000.0] * 5, start=EVALUATED_AT + timedelta(seconds=1)
    )
    policy = SensorHealthPolicy(
        freshness_threshold_seconds=300,
        frozen_min_consecutive_readings=5,
        spike_threshold=10.0,
        max_rate_of_change_per_second=1.0,
    )

    result = evaluate_sensor_health(
        sensor,
        fresh_readings + future_repeated_readings,
        EVALUATED_AT,
        policy,
    )

    assert result.health_state is HealthState.NORMAL
    assert result.detected_conditions == ()
    assert result.supporting_evidence == {}


def test_only_future_readings_are_treated_as_no_readings(sensor, make_readings):
    future_readings = make_readings(
        [4.0, 4.0, 4.0, 4.0, 4.0],
        start=EVALUATED_AT + timedelta(seconds=1),
    )

    result = evaluate_sensor_health(sensor, future_readings, EVALUATED_AT)

    assert result.health_state is HealthState.DISCONNECTED
    assert codes(result) == {ReasonCode.NO_READINGS}
    assert result.supporting_evidence["NO_READINGS"]["reading_count"] == 0

