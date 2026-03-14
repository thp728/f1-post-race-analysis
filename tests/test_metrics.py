"""Tests for src/metrics.py using synthetic DataFrames (no FastF1 needed)."""

import pandas as pd

from src.metrics import (
    calculate_degradation,
    consistency_metrics,
    filter_clean_laps,
    gap_to_pole,
    lap_by_lap_delta,
    lap_improvement_delta,
    long_run_pace,
    pct_gap_to_leader,
    qualifying_progression,
    sector_comparison,
    stint_adjusted_pace,
)


def _make_laps(n_laps: int = 20, driver: str = "VER") -> pd.DataFrame:
    """Create a synthetic lap DataFrame mimicking SQLite schema."""
    return pd.DataFrame(
        {
            "driver": [driver] * n_laps,
            "lap_number": list(range(1, n_laps + 1)),
            "lap_time_ms": [
                90000 + i * 50 for i in range(n_laps)
            ],  # ~90s + degradation
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
        }
    )


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
        assert (
            result["cumulative_gap_ms"].iloc[-1] > result["cumulative_gap_ms"].iloc[0]
        )


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


# ---------------------------------------------------------------------------
# Helpers for qualifying / practice tests
# ---------------------------------------------------------------------------

_DRIVER_CODES = [
    "VER",
    "NOR",
    "LEC",
    "PIA",
    "SAI",
    "HAM",
    "RUS",
    "ALO",
    "GAS",
    "OCO",
    "TSU",
    "RIC",
    "HUL",
    "MAG",
    "BOT",
    "ZHO",
    "ALB",
    "SAR",
    "STR",
    "DEV",
]


def _make_qualifying_laps(n_drivers: int = 20) -> pd.DataFrame:
    """Create synthetic qualifying-style laps for n_drivers.

    Each driver has 3-6 timed laps, with the fastest driver ~80s
    and the slowest ~82s.
    """
    frames = []
    for i, code in enumerate(_DRIVER_CODES[:n_drivers]):
        n_laps = 3 + (i % 4)  # 3 to 6 laps per driver
        base_time = 80000 + i * 100  # 80.0s to 81.9s spread
        driver_laps = pd.DataFrame(
            {
                "driver": [code] * n_laps,
                "lap_number": list(range(1, n_laps + 1)),
                # Each attempt gets slightly faster (qualifying improvement)
                "lap_time_ms": [base_time + 300 - j * 80 for j in range(n_laps)],
                "sector1_ms": [26000 + i * 30 + 100 - j * 20 for j in range(n_laps)],
                "sector2_ms": [28000 + i * 40 + 100 - j * 30 for j in range(n_laps)],
                "sector3_ms": [26000 + i * 30 + 100 - j * 30 for j in range(n_laps)],
                "compound": ["SOFT"] * n_laps,
                "tyre_life": list(range(1, n_laps + 1)),
                "stint": [1 + j // 2 for j in range(n_laps)],
                "position": [i + 1] * n_laps,
                "is_accurate": [1] * n_laps,
                "is_pit_in": [0] * n_laps,
                "is_pit_out": [0] * n_laps,
                "speed_i1": [310.0] * n_laps,
                "speed_i2": [290.0] * n_laps,
                "speed_fl": [320.0] * n_laps,
                "speed_st": [330.0 - i * 0.5] * n_laps,
                "track_status": ["1"] * n_laps,
            }
        )
        frames.append(driver_laps)
    return pd.concat(frames, ignore_index=True)


class TestQualifyingProgression:
    def test_returns_all_drivers(self):
        laps = _make_qualifying_laps(20)
        result = qualifying_progression(laps)
        assert len(result) == 20

    def test_positions_sequential(self):
        laps = _make_qualifying_laps(20)
        result = qualifying_progression(laps)
        assert list(result["position"]) == list(range(1, 21))

    def test_q1_eliminated(self):
        laps = _make_qualifying_laps(20)
        result = qualifying_progression(laps)
        q1 = result[result["eliminated_in"] == "Q1"]
        assert len(q1) == 5
        assert all(q1["position"] >= 16)

    def test_q2_eliminated(self):
        laps = _make_qualifying_laps(20)
        result = qualifying_progression(laps)
        q2 = result[result["eliminated_in"] == "Q2"]
        assert len(q2) == 5
        assert all(q2["position"].between(11, 15))

    def test_q3_drivers(self):
        laps = _make_qualifying_laps(20)
        result = qualifying_progression(laps)
        q3 = result[result["eliminated_in"].isna()]
        assert len(q3) == 10
        assert all(q3["position"] <= 10)

    def test_best_lap_is_minimum(self):
        laps = _make_qualifying_laps(20)
        result = qualifying_progression(laps)
        for _, row in result.iterrows():
            driver_laps = laps[
                (laps["driver"] == row["driver"]) & (laps["is_accurate"] == 1)
            ]
            assert row["best_lap_ms"] == driver_laps["lap_time_ms"].min()

    def test_fewer_than_20_drivers(self):
        laps = _make_qualifying_laps(15)
        result = qualifying_progression(laps, grid_size=15)
        assert len(result) == 15
        # With 15 drivers: Q1 eliminated = P11-P15, Q2 = P6-P10, Q3 = P1-P5
        assert len(result[result["eliminated_in"] == "Q1"]) == 5

    def test_empty_input(self):
        laps = pd.DataFrame(columns=_make_laps(1).columns)
        result = qualifying_progression(laps)
        assert result.empty


class TestLapImprovementDelta:
    def test_improving_driver(self):
        laps = _make_qualifying_laps(1)  # VER with improving times
        result = lap_improvement_delta(laps, "VER")
        assert not result.empty
        # Each attempt should be faster (negative delta after first)
        deltas = result["delta_ms"].dropna()
        assert (deltas < 0).all()

    def test_cumulative_improvement_negative(self):
        laps = _make_qualifying_laps(1)
        result = lap_improvement_delta(laps, "VER")
        # Last attempt should show cumulative improvement from first
        assert result["cumulative_improvement_ms"].iloc[-1] < 0

    def test_single_attempt(self):
        laps = _make_laps(1, "VER")
        result = lap_improvement_delta(laps, "VER")
        assert len(result) == 1
        assert pd.isna(result["delta_ms"].iloc[0])
        assert result["cumulative_improvement_ms"].iloc[0] == 0

    def test_unknown_driver(self):
        laps = _make_qualifying_laps(5)
        result = lap_improvement_delta(laps, "NOBODY")
        assert result.empty


class TestGapToPole:
    def test_pole_has_zero_gap(self):
        laps = _make_two_driver_laps()
        result = gap_to_pole(laps)
        assert result.iloc[0]["gap_ms"] == 0
        assert result.iloc[0]["gap_pct"] == 0.0

    def test_slower_driver_has_positive_gap(self):
        laps = _make_two_driver_laps()
        result = gap_to_pole(laps)
        assert result.iloc[1]["gap_ms"] > 0
        assert result.iloc[1]["gap_pct"] > 0.0

    def test_positions_correct(self):
        laps = _make_qualifying_laps(10)
        result = gap_to_pole(laps)
        assert list(result["position"]) == list(range(1, 11))

    def test_empty_input(self):
        laps = pd.DataFrame(columns=_make_laps(1).columns)
        result = gap_to_pole(laps)
        assert result.empty


class TestLongRunPace:
    def test_long_run_flagged(self):
        laps = _make_laps(15, "VER")  # 15 clean laps in one stint
        result = long_run_pace(laps)
        assert len(result) == 1
        assert result.iloc[0]["is_long_run"]
        assert result.iloc[0]["n_laps"] == 15

    def test_short_run_flagged(self):
        laps = _make_laps(3, "VER")  # 3 laps — below threshold
        result = long_run_pace(laps)
        assert len(result) == 1
        assert not result.iloc[0]["is_long_run"]

    def test_custom_threshold(self):
        laps = _make_laps(5, "VER")
        result = long_run_pace(laps, min_stint_laps=10)
        assert not result.iloc[0]["is_long_run"]

        result = long_run_pace(laps, min_stint_laps=3)
        assert result.iloc[0]["is_long_run"]

    def test_multiple_stints(self):
        laps = _make_laps(20, "VER")
        # Split into two stints
        laps.loc[laps["lap_number"] <= 10, "stint"] = 1
        laps.loc[laps["lap_number"] > 10, "stint"] = 2
        laps.loc[laps["lap_number"] > 10, "compound"] = "HARD"
        result = long_run_pace(laps)
        assert len(result) == 2
        assert all(result["is_long_run"])

    def test_empty_input(self):
        laps = pd.DataFrame(columns=_make_laps(1).columns)
        result = long_run_pace(laps)
        assert result.empty
