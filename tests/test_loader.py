"""Tests for src/loader.py — stationary duration extraction from synthetic telemetry."""

import pandas as pd

from src.loader import _find_stationary_duration_ms


def _make_telemetry(times_sec: list, speeds: list) -> pd.DataFrame:
    """Create synthetic telemetry DataFrame."""
    return pd.DataFrame(
        {
            "SessionTime": [pd.Timedelta(seconds=t) for t in times_sec],
            "Speed": speeds,
        }
    )


class TestFindStationaryDuration:
    def test_finds_stationary_period(self):
        telemetry = _make_telemetry(
            times_sec=[0, 1, 2, 3, 4, 5, 6, 7, 8],
            speeds=[80, 80, 80, 1, 1, 1, 80, 80, 80],
        )
        result = _find_stationary_duration_ms(
            telemetry,
            pit_in_time=pd.Timedelta(seconds=2),
            pit_out_time=pd.Timedelta(seconds=6),
        )
        assert result == 2000  # 2 seconds stationary (3-5 sec in window)

    def test_returns_none_when_too_short(self):
        telemetry = _make_telemetry(
            times_sec=[0, 1, 2],
            speeds=[80, 1, 80],
        )
        result = _find_stationary_duration_ms(
            telemetry,
            pit_in_time=pd.Timedelta(seconds=0),
            pit_out_time=pd.Timedelta(seconds=2),
        )
        assert result is None  # Less than 500ms

    def test_returns_none_when_too_long(self):
        telemetry = _make_telemetry(
            times_sec=list(range(32)),
            speeds=[80] * 10 + [1] * 17 + [80] * 5,
        )
        result = _find_stationary_duration_ms(
            telemetry,
            pit_in_time=pd.Timedelta(seconds=0),
            pit_out_time=pd.Timedelta(seconds=31),
        )
        assert result is None  # More than 15 seconds (17 seconds)

    def test_returns_none_empty_telemetry(self):
        result = _find_stationary_duration_ms(
            pd.DataFrame(),
            pit_in_time=pd.Timedelta(seconds=0),
            pit_out_time=pd.Timedelta(seconds=2),
        )
        assert result is None

    def test_returns_none_no_stationary(self):
        telemetry = _make_telemetry(
            times_sec=[0, 1, 2, 3, 4],
            speeds=[80, 60, 40, 20, 80],
        )
        result = _find_stationary_duration_ms(
            telemetry,
            pit_in_time=pd.Timedelta(seconds=0),
            pit_out_time=pd.Timedelta(seconds=4),
        )
        assert result is None

    def test_threshold_respected(self):
        telemetry = _make_telemetry(
            times_sec=[0, 1, 2, 3, 4],
            speeds=[80, 0.5, 0.5, 0.5, 80],
        )
        result = _find_stationary_duration_ms(
            telemetry,
            pit_in_time=pd.Timedelta(seconds=0),
            pit_out_time=pd.Timedelta(seconds=4),
            speed_threshold=1.0,
        )
        assert result == 2000

    def test_handles_window_outside_range(self):
        telemetry = _make_telemetry(
            times_sec=[10, 11, 12, 13, 14],
            speeds=[1, 1, 1, 1, 1],
        )
        result = _find_stationary_duration_ms(
            telemetry,
            pit_in_time=pd.Timedelta(seconds=0),
            pit_out_time=pd.Timedelta(seconds=5),
        )
        assert result is None  # No data in window
