"""Tests for src/prediction.py — scoring math on synthetic data."""

import pandas as pd

from src.prediction import (
    compute_quali_conversion,
    compute_rolling_form,
    update_elo_after_race,
    DEFAULT_ELO,
)


def _make_results() -> pd.DataFrame:
    """Create synthetic results DataFrame."""
    rows = []
    for round_num in range(1, 6):
        for i, driver in enumerate(["VER", "LEC", "NOR", "HAM"], start=1):
            rows.append({
                "year": 2024,
                "round": round_num,
                "driver": driver,
                "driver_number": i,
                "team": f"Team{i}",
                "grid_position": i,
                "finish_position": i,  # Everyone finishes where they start
                "status": "Finished",
                "points": max(0, 26 - i * 5),
                "fastest_lap_time_ms": 90000 + i * 1000,
            })
    return pd.DataFrame(rows)


class TestRollingForm:
    def test_returns_average(self):
        results = _make_results()
        form = compute_rolling_form(results, "VER", as_of_round=6, year=2024, n_races=5)
        assert form == 1.0  # VER finished P1 every race

    def test_limited_by_n_races(self):
        results = _make_results()
        form = compute_rolling_form(results, "VER", as_of_round=6, year=2024, n_races=3)
        assert form == 1.0  # Still P1 average

    def test_no_data_returns_none(self):
        results = _make_results()
        form = compute_rolling_form(results, "ALO", as_of_round=6, year=2024)
        assert form is None

    def test_excludes_future_rounds(self):
        results = _make_results()
        form = compute_rolling_form(results, "VER", as_of_round=3, year=2024, n_races=5)
        assert form == 1.0  # Only rounds 1-2 are used


class TestQualiConversion:
    def test_no_gain_or_loss(self):
        results = _make_results()
        # Grid == Finish for all, so conversion should be 0.5
        conv = compute_quali_conversion(results, "VER", 2024, as_of_round=6)
        assert conv == 0.5

    def test_gains_places(self):
        results = _make_results()
        # Make VER start P5 but finish P1
        results.loc[results["driver"] == "VER", "grid_position"] = 5
        conv = compute_quali_conversion(results, "VER", 2024, as_of_round=6)
        assert conv > 0.5  # Positive conversion

    def test_no_data(self):
        results = _make_results()
        conv = compute_quali_conversion(results, "ALO", 2024, as_of_round=6)
        assert conv == 0.5  # Default


class TestEloRatings:
    def test_winner_gains_rating(self):
        ratings = {"VER": DEFAULT_ELO, "LEC": DEFAULT_ELO}
        race = pd.DataFrame({
            "driver": ["VER", "LEC"],
            "finish_position": [1, 2],
        })
        new_ratings = update_elo_after_race(ratings, race)
        assert new_ratings["VER"] > DEFAULT_ELO
        assert new_ratings["LEC"] < DEFAULT_ELO

    def test_ratings_are_zero_sum(self):
        ratings = {"VER": DEFAULT_ELO, "LEC": DEFAULT_ELO, "NOR": DEFAULT_ELO}
        race = pd.DataFrame({
            "driver": ["VER", "LEC", "NOR"],
            "finish_position": [1, 2, 3],
        })
        new_ratings = update_elo_after_race(ratings, race)
        total_before = sum(ratings.values())
        total_after = sum(new_ratings.values())
        assert abs(total_before - total_after) < 0.01  # Zero-sum within float precision

    def test_new_driver_gets_default(self):
        ratings = {"VER": 1600}
        race = pd.DataFrame({
            "driver": ["VER", "NEW"],
            "finish_position": [1, 2],
        })
        new_ratings = update_elo_after_race(ratings, race)
        assert "NEW" in new_ratings
