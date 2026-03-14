"""Tests for src/metrics.py using synthetic DataFrames (no FastF1 needed)."""

import pandas as pd
import pytest

from src.metrics import (
    calculate_degradation,
    consistency_metrics,
    filter_clean_laps,
    lap_by_lap_delta,
    pct_gap_to_leader,
    sector_comparison,
    stint_adjusted_pace,
)


def _make_laps(n_laps: int = 20, driver: str = "VER") -> pd.DataFrame:
    """Create a synthetic lap DataFrame mimicking SQLite schema."""
    return pd.DataFrame({
        "driver": [driver] * n_laps,
        "lap_number": list(range(1, n_laps + 1)),
        "lap_time_ms": [90000 + i * 50 for i in range(n_laps)],  # ~90s + degradation
        "sector1_ms": [28000 + i * 10 for i in range(n_laps)],
        "sector2_ms": [32000 + i * 20 for i in range(n_laps)],
        "sector3_ms": [30000 + i * 20 for i in range(n_laps)],
        "compound": ["MEDIUM"] * n_laps,
        "tyre_life": list(range(1, n_laps + 1)),
        "stint": [1] * n_laps,
        "position": [1] * n_laps,
        "is_accurate": [1] * n_laps,
        "is_pit_in": [0] * n_laps,
        "is_pit_out": [0] * n_laps,
        "speed_i1": [310.0] * n_laps,
        "speed_i2": [290.0] * n_laps,
        "speed_fl": [320.0] * n_laps,
        "speed_st": [330.0] * n_laps,
        "track_status": ["1"] * n_laps,
    })


def _make_two_driver_laps() -> pd.DataFrame:
    """Create laps for two drivers."""
    d1 = _make_laps(20, "VER")
    d2 = _make_laps(20, "LEC")
    d2["lap_time_ms"] = d2["lap_time_ms"] + 200  # LEC is ~0.2s slower
    d2["position"] = [2] * 20
    return pd.concat([d1, d2], ignore_index=True)


class TestFilterCleanLaps:
    def test_removes_pit_laps(self):
        laps = _make_laps(10)
        laps.loc[5, "is_pit_in"] = 1
        clean = filter_clean_laps(laps)
        assert len(clean) == 9

    def test_removes_inaccurate_laps(self):
        laps = _make_laps(10)
        laps.loc[3, "is_accurate"] = 0
        clean = filter_clean_laps(laps)
        assert len(clean) == 9

    def test_removes_outliers(self):
        laps = _make_laps(10)
        laps.loc[0, "lap_time_ms"] = 200000  # Way too slow
        clean = filter_clean_laps(laps)
        assert len(clean) == 9

    def test_empty_input(self):
        laps = pd.DataFrame(columns=_make_laps(1).columns)
        clean = filter_clean_laps(laps)
        assert clean.empty


class TestDegradation:
    def test_positive_degradation(self):
        laps = _make_laps(20)
        result = calculate_degradation(laps, "VER", "MEDIUM")
        assert result is not None
        assert result["slope"] > 0  # Times get slower
        assert result["n_laps"] == 20

    def test_fuel_corrected_slope(self):
        laps = _make_laps(20)
        result = calculate_degradation(laps, "VER", "MEDIUM", fuel_correct=True)
        assert result is not None
        assert result["fuel_corrected_slope"] > result["slope"]

    def test_insufficient_data(self):
        laps = _make_laps(2)
        result = calculate_degradation(laps, "VER", "MEDIUM")
        assert result is None

    def test_wrong_driver(self):
        laps = _make_laps(20)
        result = calculate_degradation(laps, "HAM", "MEDIUM")
        assert result is None


class TestSectorComparison:
    def test_returns_correct_drivers(self):
        laps = _make_two_driver_laps()
        result = sector_comparison(laps, ["VER", "LEC"])
        assert len(result) == 2
        assert set(result["driver"]) == {"VER", "LEC"}

    def test_theoretical_best(self):
        laps = _make_laps(10)
        result = sector_comparison(laps, ["VER"])
        assert result.iloc[0]["theoretical_best_ms"] <= result.iloc[0]["actual_best_ms"]


class TestLapByLapDelta:
    def test_delta_positive_when_d1_faster(self):
        laps = _make_two_driver_laps()
        result = lap_by_lap_delta(laps, "VER", "LEC")
        assert not result.empty
        assert (result["delta_ms"] > 0).all()  # VER faster every lap

    def test_cumulative_gap_grows(self):
        laps = _make_two_driver_laps()
        result = lap_by_lap_delta(laps, "VER", "LEC")
        assert result["cumulative_gap_ms"].iloc[-1] > result["cumulative_gap_ms"].iloc[0]


class TestStintAdjustedPace:
    def test_single_stint(self):
        laps = _make_laps(20)
        result = stint_adjusted_pace(laps, ["VER"])
        assert len(result) == 1
        assert result.iloc[0]["stint"] == 1
        assert result.iloc[0]["n_laps"] == 20


class TestConsistencyMetrics:
    def test_returns_metrics(self):
        laps = _make_laps(20)
        result = consistency_metrics(laps, ["VER"])
        assert len(result) == 1
        assert result.iloc[0]["clean_laps"] == 20
        assert result.iloc[0]["cv_pct"] > 0

    def test_lower_std_for_consistent_driver(self):
        laps = _make_laps(20)
        # Make very consistent laps
        laps["lap_time_ms"] = 90000
        result = consistency_metrics(laps, ["VER"])
        assert result.iloc[0]["std_ms"] == 0.0


class TestPctGapToLeader:
    def test_leader_has_zero_gap(self):
        laps = _make_two_driver_laps()
        result = pct_gap_to_leader(laps)
        assert result["pct_gap"].min() == 0.0
