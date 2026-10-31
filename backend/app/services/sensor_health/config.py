"""Configuration for deterministic sensor-health detection rules."""

from dataclasses import dataclass
import math


@dataclass(frozen=True, slots=True)
class SensorHealthPolicy:
    """Thresholds for one sensor evaluation.

    Rate is expressed in sensor-units per second. Spike threshold is expressed
    in the sensor's own measurement unit. These thresholds must be selected for
    the sensor/application; no universal industrial operating range is assumed.
    """

    freshness_threshold_seconds: float = 300.0
    frozen_min_consecutive_readings: int = 5
    frozen_tolerance: float = 1e-6
    spike_threshold: float | None = None
    max_rate_of_change_per_second: float | None = None

    def __post_init__(self) -> None:
        """Reject thresholds that would make evaluation ambiguous or unsafe."""
        if (
            isinstance(self.freshness_threshold_seconds, bool)
            or not math.isfinite(self.freshness_threshold_seconds)
            or self.freshness_threshold_seconds <= 0
        ):
            raise ValueError("freshness_threshold_seconds must be finite and positive")

        if (
            isinstance(self.frozen_min_consecutive_readings, bool)
            or not isinstance(self.frozen_min_consecutive_readings, int)
            or self.frozen_min_consecutive_readings < 2
        ):
            raise ValueError("frozen_min_consecutive_readings must be an integer >= 2")

        if (
            isinstance(self.frozen_tolerance, bool)
            or not math.isfinite(self.frozen_tolerance)
            or self.frozen_tolerance < 0
        ):
            raise ValueError("frozen_tolerance must be finite and non-negative")

        for name, value in (
            ("spike_threshold", self.spike_threshold),
            ("max_rate_of_change_per_second", self.max_rate_of_change_per_second),
        ):
            if value is not None and (
                isinstance(value, bool) or not math.isfinite(value) or value <= 0
            ):
                raise ValueError(f"{name} must be finite and positive when configured")
