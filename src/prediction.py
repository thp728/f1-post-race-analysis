"""Scoring model, Elo ratings, and feature engineering for race predictions."""

from typing import Optional

import numpy as np
import pandas as pd

from src.circuit import CircuitCluster, get_cluster, normalize_circuit_id
from src.loader import (
    get_db_connection,
    load_pit_stops_from_db,
    load_races_from_db,
    load_results_from_db,
)

# Default weights for the prediction model
DEFAULT_WEIGHTS = {
    "recent_form": 0.40,
    "circuit_history": 0.25,
    "cluster_form": 0.15,
    "pit_consistency": 0.10,
    "quali_conversion": 0.10,
}

DEFAULT_ELO = 1500
ELO_K_FACTOR = 32


# ---------------------------------------------------------------------------
# Feature Engineering
# ---------------------------------------------------------------------------

def compute_rolling_form(
    results: pd.DataFrame,
    driver: str,
    as_of_round: int,
    year: int,
    n_races: int = 5,
) -> Optional[float]:
    """Rolling average finish position for a driver over last N races.

    Returns None if no race data available.
    """
    drv = results[
        (results["driver"] == driver)
        & (results["year"] == year)
        & (results["round"] < as_of_round)
        & (results["finish_position"].notna())
    ].sort_values("round")

    if drv.empty:
        return None

    recent = drv.tail(n_races)
    return float(recent["finish_position"].mean())


def compute_circuit_history(
    results: pd.DataFrame,
    races: pd.DataFrame,
    driver: str,
    circuit_id: str,
    n_visits: int = 3,
) -> Optional[float]:
    """Average finish position at this specific circuit over last N visits."""
    # Find all rounds at this circuit
    circuit_rounds = races[
        races["circuit_id"] == circuit_id
    ][["year", "round"]].copy()

    if circuit_rounds.empty:
        return None

    # Get driver results at those rounds
    drv_at_circuit = results.merge(circuit_rounds, on=["year", "round"])
    drv_at_circuit = drv_at_circuit[
        (drv_at_circuit["driver"] == driver)
        & (drv_at_circuit["finish_position"].notna())
    ].sort_values(["year", "round"])

    if drv_at_circuit.empty:
        return None

    recent = drv_at_circuit.tail(n_visits)
    return float(recent["finish_position"].mean())


def compute_cluster_form(
    results: pd.DataFrame,
    races: pd.DataFrame,
    driver: str,
    cluster: CircuitCluster,
    year: int,
) -> Optional[float]:
    """Average finish position at circuits in the same cluster this season."""
    # Find circuits in this cluster
    cluster_circuits = races[
        races["circuit_id"].apply(lambda cid: get_cluster(cid) == cluster)
    ]
    cluster_rounds = cluster_circuits[
        cluster_circuits["year"] == year
    ][["year", "round"]]

    if cluster_rounds.empty:
        return None

    drv_cluster = results.merge(cluster_rounds, on=["year", "round"])
    drv_cluster = drv_cluster[
        (drv_cluster["driver"] == driver)
        & (drv_cluster["finish_position"].notna())
    ]

    if drv_cluster.empty:
        return None

    return float(drv_cluster["finish_position"].mean())


def compute_pit_consistency(
    pit_stops: pd.DataFrame,
    driver: str,
    year: int,
) -> float:
    """Score from 0-1 based on pit stop duration consistency (lower std = better)."""
    drv_pits = pit_stops[
        (pit_stops["driver"] == driver)
        & (pit_stops["year"] == year)
        & (pit_stops["duration_ms"].notna())
    ]

    if len(drv_pits) < 2:
        return 0.5  # Neutral score if insufficient data

    std_ms = drv_pits["duration_ms"].std()
    # Normalize: std of 0 = score 1.0, std of 2000ms+ = score 0.0
    return float(max(0.0, 1.0 - std_ms / 2000.0))


def compute_quali_conversion(
    results: pd.DataFrame,
    driver: str,
    year: int,
    as_of_round: int,
    n_races: int = 5,
) -> float:
    """Score 0-1 centered at 0.5 based on avg positions gained grid-to-finish."""
    drv = results[
        (results["driver"] == driver)
        & (results["year"] == year)
        & (results["round"] < as_of_round)
        & (results["grid_position"].notna())
        & (results["finish_position"].notna())
    ].sort_values("round").tail(n_races)

    if drv.empty:
        return 0.5

    # Positive = gains places (lower finish than grid)
    conversion = (drv["grid_position"] - drv["finish_position"]).mean()
    # Normalize to 0-1 range centered at 0.5
    return float(np.clip(0.5 + conversion / 20.0, 0.0, 1.0))


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def predict_race(
    year: int,
    next_round: int,
    next_circuit_id: str,
    weights: Optional[dict] = None,
) -> pd.DataFrame:
    """Generate predictions for all drivers for the next race.

    Reads from SQLite database. Returns DataFrame sorted by score (descending):
    driver, score, rank, and individual component scores.
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS.copy()

    results = load_results_from_db()
    races = load_races_from_db()
    pit_stops = load_pit_stops_from_db(year=year)

    if results.empty:
        return pd.DataFrame()

    # Get cluster for next circuit
    cluster = get_cluster(next_circuit_id)

    # Get all drivers who raced this season
    season_drivers = results[
        (results["year"] == year) & (results["round"] < next_round)
    ]["driver"].unique()

    predictions = []
    for driver in season_drivers:
        # Compute each component
        rolling = compute_rolling_form(results, driver, next_round, year)
        circuit = compute_circuit_history(results, races, driver, next_circuit_id)
        cluster_f = compute_cluster_form(results, races, driver, cluster, year) if cluster else None
        pit_cons = compute_pit_consistency(pit_stops, driver, year)
        quali_conv = compute_quali_conversion(results, driver, year, next_round)

        # Convert to 0-1 scores (higher = more competitive)
        # Recent form: invert so lower avg finish = higher score
        recent_score = 1.0 - (rolling / 20.0) if rolling else 0.5
        circuit_score = 1.0 - (circuit / 20.0) if circuit else recent_score
        cluster_score = 1.0 - (cluster_f / 20.0) if cluster_f else recent_score

        # Weighted total
        score = (
            weights["recent_form"] * recent_score
            + weights["circuit_history"] * circuit_score
            + weights["cluster_form"] * cluster_score
            + weights["pit_consistency"] * pit_cons
            + weights["quali_conversion"] * quali_conv
        )

        predictions.append({
            "driver": driver,
            "score": score,
            "recent_form": recent_score,
            "circuit_history": circuit_score,
            "cluster_form": cluster_score,
            "pit_consistency": pit_cons,
            "quali_conversion": quali_conv,
            "rolling_avg_finish": rolling,
        })

    df = pd.DataFrame(predictions).sort_values("score", ascending=False)
    df["rank"] = range(1, len(df) + 1)
    return df


# ---------------------------------------------------------------------------
# Elo Ratings
# ---------------------------------------------------------------------------

def update_elo_after_race(
    current_ratings: dict,
    race_results: pd.DataFrame,
    k_factor: int = ELO_K_FACTOR,
) -> dict:
    """Update Elo ratings after a single race.

    Each finishing position pair is treated as a head-to-head matchup.
    """
    valid = race_results[race_results["finish_position"].notna()].copy()
    drivers = valid["driver"].tolist()
    positions = valid["finish_position"].astype(int).tolist()

    new_ratings = current_ratings.copy()
    n = len(drivers)

    for i in range(n):
        for j in range(i + 1, n):
            ri = current_ratings.get(drivers[i], DEFAULT_ELO)
            rj = current_ratings.get(drivers[j], DEFAULT_ELO)

            # Expected score for driver i
            exp_i = 1.0 / (1.0 + 10.0 ** ((rj - ri) / 400.0))

            # Actual score: 1 if i finished ahead of j
            actual_i = 1.0 if positions[i] < positions[j] else 0.0

            # Adjustment scaled by field size
            adj = k_factor * (actual_i - exp_i) / n
            new_ratings[drivers[i]] = new_ratings.get(drivers[i], DEFAULT_ELO) + adj
            new_ratings[drivers[j]] = new_ratings.get(drivers[j], DEFAULT_ELO) - adj

    return new_ratings


def compute_elo_ratings(
    results: Optional[pd.DataFrame] = None,
    k_factor: int = ELO_K_FACTOR,
) -> dict:
    """Compute Elo ratings for all drivers based on race results.

    Processes races chronologically, updating ratings after each.
    Returns dict: {driver_abbreviation: elo_rating}.
    """
    if results is None:
        results = load_results_from_db()

    if results.empty:
        return {}

    ratings: dict = {}

    # Process each race chronologically
    for (year, round_num), race in results.groupby(["year", "round"]):
        ratings = update_elo_after_race(ratings, race, k_factor)

    return ratings
