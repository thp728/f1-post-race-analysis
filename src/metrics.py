"""Degradation, consistency, pace delta, and sector breakdown calculations."""

from typing import List, Optional

import numpy as np
import pandas as pd
from scipy import stats

from src.loader import FUEL_CORRECTION

# Threshold for pick_quicklaps equivalent
QUICK_LAP_THRESHOLD = 1.07


# ---------------------------------------------------------------------------
# Lap Filtering
# ---------------------------------------------------------------------------

def filter_clean_laps(laps: pd.DataFrame) -> pd.DataFrame:
    """Remove pit in/out laps, inaccurate laps, and outliers (>107% of fastest).

    Works on DataFrames from SQLite (lap_time_ms column), not FastF1 objects.
    """
    clean = laps.copy()

    # Remove pit in/out laps
    clean = clean[
        (clean["is_pit_in"] == 0) & (clean["is_pit_out"] == 0)
    ]

    # Remove inaccurate laps
    clean = clean[clean["is_accurate"] == 1]

    # Remove laps with no time
    clean = clean[clean["lap_time_ms"].notna()]

    if clean.empty:
        return clean

    # Remove outliers: slower than 107% of fastest
    fastest = clean["lap_time_ms"].min()
    threshold = fastest * QUICK_LAP_THRESHOLD
    clean = clean[clean["lap_time_ms"] <= threshold]

    return clean


def pct_gap_to_leader(laps: pd.DataFrame) -> pd.DataFrame:
    """Calculate percentage gap to session leader for cross-race normalisation.

    Adds a 'pct_gap' column to the DataFrame.
    """
    result = laps.copy()
    if result.empty or "lap_time_ms" not in result.columns:
        return result

    leader_time = result["lap_time_ms"].min()
    if leader_time and leader_time > 0:
        result["pct_gap"] = 100 * (result["lap_time_ms"] - leader_time) / leader_time
    else:
        result["pct_gap"] = np.nan

    return result


# ---------------------------------------------------------------------------
# Tyre Degradation
# ---------------------------------------------------------------------------

def calculate_degradation(
    laps: pd.DataFrame,
    driver: str,
    compound: str,
    fuel_correct: bool = True,
) -> Optional[dict]:
    """Linear regression of lap time vs tyre age for one driver/compound.

    Returns dict with slope, intercept, r_squared, fuel_corrected_slope, n_laps.
    Returns None if insufficient data (< 3 laps).
    """
    clean = filter_clean_laps(laps)
    drv_laps = clean[
        (clean["driver"] == driver) & (clean["compound"] == compound)
    ].copy()

    if len(drv_laps) < 3:
        return None

    drv_laps["lap_time_sec"] = drv_laps["lap_time_ms"] / 1000.0

    slope, intercept, r_value, p_value, std_err = stats.linregress(
        drv_laps["tyre_life"].astype(float),
        drv_laps["lap_time_sec"],
    )

    fuel_corrected_slope = slope + FUEL_CORRECTION if fuel_correct else slope

    return {
        "driver": driver,
        "compound": compound,
        "slope": slope,
        "intercept": intercept,
        "r_squared": r_value ** 2,
        "fuel_corrected_slope": fuel_corrected_slope,
        "n_laps": len(drv_laps),
    }


def calculate_all_degradation(
    laps: pd.DataFrame,
    fuel_correct: bool = True,
) -> pd.DataFrame:
    """Compute degradation for every driver/compound combination.

    Returns DataFrame with columns: driver, compound, slope, r_squared,
    fuel_corrected_slope, n_laps.
    """
    clean = filter_clean_laps(laps)
    if clean.empty:
        return pd.DataFrame()

    results = []
    for (driver, compound), _ in clean.groupby(["driver", "compound"]):
        deg = calculate_degradation(laps, driver, compound, fuel_correct)
        if deg is not None:
            results.append(deg)

    return pd.DataFrame(results)


def detect_tyre_cliff(
    laps: pd.DataFrame,
    driver: str,
    compound: str,
    window: int = 3,
    threshold_multiplier: float = 2.0,
) -> Optional[int]:
    """Detect the tyre life where performance cliff begins.

    Uses rolling window comparison against linear degradation rate.
    Returns tyre_life value where cliff starts, or None if no cliff detected.
    """
    deg = calculate_degradation(laps, driver, compound, fuel_correct=False)
    if deg is None:
        return None

    clean = filter_clean_laps(laps)
    drv_laps = clean[
        (clean["driver"] == driver) & (clean["compound"] == compound)
    ].sort_values("tyre_life").copy()

    if len(drv_laps) < window * 2:
        return None

    drv_laps["lap_time_sec"] = drv_laps["lap_time_ms"] / 1000.0
    rolling_avg = drv_laps["lap_time_sec"].rolling(window=window).mean()
    rolling_diff = rolling_avg.diff()

    cliff_threshold = deg["slope"] * threshold_multiplier
    cliff_points = drv_laps[rolling_diff > cliff_threshold]

    if cliff_points.empty:
        return None

    return int(cliff_points.iloc[0]["tyre_life"])


# ---------------------------------------------------------------------------
# Sector Breakdown
# ---------------------------------------------------------------------------

def sector_comparison(
    laps: pd.DataFrame,
    drivers: List[str],
) -> pd.DataFrame:
    """Compare best sector times for given drivers.

    Returns DataFrame: driver, best_s1_ms, best_s2_ms, best_s3_ms,
    theoretical_best_ms, actual_best_ms, gap_ms.
    """
    clean = filter_clean_laps(laps)
    results = []

    for driver in drivers:
        drv = clean[clean["driver"] == driver]
        if drv.empty:
            continue

        best_s1 = drv["sector1_ms"].min()
        best_s2 = drv["sector2_ms"].min()
        best_s3 = drv["sector3_ms"].min()

        theoretical = best_s1 + best_s2 + best_s3 if all(
            pd.notna(x) for x in [best_s1, best_s2, best_s3]
        ) else None

        actual = drv["lap_time_ms"].min()

        gap = (actual - theoretical) if theoretical and actual else None

        results.append({
            "driver": driver,
            "best_s1_ms": best_s1,
            "best_s2_ms": best_s2,
            "best_s3_ms": best_s3,
            "theoretical_best_ms": theoretical,
            "actual_best_ms": actual,
            "gap_ms": gap,
        })

    return pd.DataFrame(results)


def speed_trap_comparison(
    laps: pd.DataFrame,
    drivers: List[str],
) -> pd.DataFrame:
    """Compare max speed trap values across drivers.

    Returns DataFrame with max speeds at SpeedI1, SpeedI2, SpeedFL, SpeedST per driver.
    """
    clean = filter_clean_laps(laps)
    results = []

    for driver in drivers:
        drv = clean[clean["driver"] == driver]
        if drv.empty:
            continue

        results.append({
            "driver": driver,
            "max_speed_i1": drv["speed_i1"].max() if "speed_i1" in drv else None,
            "max_speed_i2": drv["speed_i2"].max() if "speed_i2" in drv else None,
            "max_speed_fl": drv["speed_fl"].max() if "speed_fl" in drv else None,
            "max_speed_st": drv["speed_st"].max() if "speed_st" in drv else None,
        })

    return pd.DataFrame(results)


# ---------------------------------------------------------------------------
# Pace Delta
# ---------------------------------------------------------------------------

def lap_by_lap_delta(
    laps: pd.DataFrame,
    driver1: str,
    driver2: str,
) -> pd.DataFrame:
    """Lap-by-lap time difference between two drivers.

    Returns DataFrame: lap_number, delta_ms (positive = driver1 faster),
    cumulative_gap_ms.
    """
    d1 = laps[laps["driver"] == driver1][["lap_number", "lap_time_ms"]].copy()
    d2 = laps[laps["driver"] == driver2][["lap_number", "lap_time_ms"]].copy()

    merged = d1.merge(d2, on="lap_number", suffixes=("_d1", "_d2"))

    # Remove laps where either driver has no time
    merged = merged.dropna(subset=["lap_time_ms_d1", "lap_time_ms_d2"])

    # Positive delta = driver1 was faster (driver2 took longer)
    merged["delta_ms"] = merged["lap_time_ms_d2"] - merged["lap_time_ms_d1"]
    merged["cumulative_gap_ms"] = merged["delta_ms"].cumsum()

    return merged[["lap_number", "delta_ms", "cumulative_gap_ms"]]


def stint_adjusted_pace(
    laps: pd.DataFrame,
    drivers: Optional[List[str]] = None,
) -> pd.DataFrame:
    """Mean lap time per driver per stint, excluding pit in/out laps.

    Returns DataFrame: driver, stint, compound, mean_pace_ms, n_laps.
    """
    clean = filter_clean_laps(laps)

    if drivers is not None:
        clean = clean[clean["driver"].isin(drivers)]

    if clean.empty:
        return pd.DataFrame()

    results = []
    for (driver, stint), group in clean.groupby(["driver", "stint"]):
        if pd.isna(stint):
            continue
        compound = group["compound"].iloc[0] if not group["compound"].empty else ""
        results.append({
            "driver": driver,
            "stint": int(stint),
            "compound": compound,
            "mean_pace_ms": group["lap_time_ms"].mean(),
            "n_laps": len(group),
        })

    return pd.DataFrame(results)


# ---------------------------------------------------------------------------
# Consistency
# ---------------------------------------------------------------------------

def consistency_metrics(
    laps: pd.DataFrame,
    drivers: Optional[List[str]] = None,
) -> pd.DataFrame:
    """Standard deviation, IQR, CV% of clean laps per driver.

    Returns DataFrame: driver, mean_ms, std_ms, iqr_ms, cv_pct, clean_laps.
    """
    clean = filter_clean_laps(laps)

    if drivers is not None:
        clean = clean[clean["driver"].isin(drivers)]

    if clean.empty:
        return pd.DataFrame()

    results = []
    for driver, group in clean.groupby("driver"):
        times = group["lap_time_ms"].dropna()
        if len(times) < 2:
            continue

        mean_val = times.mean()
        std_val = times.std()
        q1 = times.quantile(0.25)
        q3 = times.quantile(0.75)

        results.append({
            "driver": driver,
            "mean_ms": mean_val,
            "std_ms": std_val,
            "iqr_ms": q3 - q1,
            "cv_pct": (std_val / mean_val) * 100 if mean_val > 0 else 0,
            "clean_laps": len(times),
        })

    return pd.DataFrame(results).sort_values("mean_ms")


# ---------------------------------------------------------------------------
# Qualifying Analysis
# ---------------------------------------------------------------------------

def qualifying_progression(
    laps: pd.DataFrame,
    grid_size: int = 20,
    q1_eliminated: int = 5,
    q2_eliminated: int = 5,
) -> pd.DataFrame:
    """Best lap per driver ranked into Q1/Q2/Q3 segments by elimination position.

    Returns DataFrame: driver, best_lap_ms, best_s1_ms, best_s2_ms, best_s3_ms,
    position, segment, eliminated_in.
    """
    valid = laps[(laps["is_accurate"] == 1) & (laps["lap_time_ms"].notna())].copy()
    if valid.empty:
        return pd.DataFrame()

    # Best lap per driver (row with minimum lap_time_ms)
    best_idx = valid.groupby("driver")["lap_time_ms"].idxmin()
    best = valid.loc[best_idx, ["driver", "lap_time_ms", "sector1_ms", "sector2_ms", "sector3_ms"]].copy()
    best.columns = ["driver", "best_lap_ms", "best_s1_ms", "best_s2_ms", "best_s3_ms"]
    best = best.sort_values("best_lap_ms").reset_index(drop=True)
    best["position"] = range(1, len(best) + 1)

    n_drivers = len(best)
    q1_cutoff = n_drivers - q1_eliminated + 1
    q2_cutoff = q1_cutoff - q2_eliminated

    def _assign_segment(pos: int) -> str:
        if pos >= q1_cutoff:
            return "Q1"
        elif pos >= q2_cutoff:
            return "Q2"
        return "Q3"

    def _assign_eliminated(pos: int) -> Optional[str]:
        if pos >= q1_cutoff:
            return "Q1"
        elif pos >= q2_cutoff:
            return "Q2"
        return None

    best["segment"] = best["position"].apply(_assign_segment)
    best["eliminated_in"] = best["position"].apply(_assign_eliminated)

    return best


def lap_improvement_delta(
    laps: pd.DataFrame,
    driver: str,
) -> pd.DataFrame:
    """Time gained between qualifying attempts for a single driver.

    Returns DataFrame: attempt, lap_number, lap_time_ms, delta_ms,
    cumulative_improvement_ms.
    """
    drv = laps[
        (laps["driver"] == driver)
        & (laps["is_accurate"] == 1)
        & (laps["lap_time_ms"].notna())
    ].sort_values("lap_number").copy()

    if drv.empty:
        return pd.DataFrame()

    drv = drv.reset_index(drop=True)
    drv["attempt"] = range(1, len(drv) + 1)

    first_time = drv["lap_time_ms"].iloc[0]
    drv["delta_ms"] = drv["lap_time_ms"].diff()
    drv["cumulative_improvement_ms"] = drv["lap_time_ms"] - first_time

    return drv[["attempt", "lap_number", "lap_time_ms", "delta_ms", "cumulative_improvement_ms"]]


def gap_to_pole(laps: pd.DataFrame) -> pd.DataFrame:
    """Each driver's gap to the fastest qualifier.

    Returns DataFrame: driver, best_lap_ms, gap_ms, gap_pct, position.
    """
    valid = laps[(laps["is_accurate"] == 1) & (laps["lap_time_ms"].notna())].copy()
    if valid.empty:
        return pd.DataFrame()

    best = valid.groupby("driver")["lap_time_ms"].min().reset_index()
    best.columns = ["driver", "best_lap_ms"]
    best = best.sort_values("best_lap_ms").reset_index(drop=True)

    pole_time = best["best_lap_ms"].iloc[0]
    best["gap_ms"] = best["best_lap_ms"] - pole_time
    best["gap_pct"] = 100.0 * best["gap_ms"] / pole_time
    best["position"] = range(1, len(best) + 1)

    return best


# ---------------------------------------------------------------------------
# Practice Analysis
# ---------------------------------------------------------------------------

def long_run_pace(
    laps: pd.DataFrame,
    min_stint_laps: int = 5,
) -> pd.DataFrame:
    """Average pace per stint, flagged as long run or short run.

    Returns DataFrame: driver, stint, compound, mean_pace_ms, n_laps, is_long_run.
    """
    clean = filter_clean_laps(laps)
    if clean.empty:
        return pd.DataFrame()

    groups = clean.groupby(["driver", "stint", "compound"])
    rows = []
    for (driver, stint, compound), group in groups:
        n = len(group)
        rows.append({
            "driver": driver,
            "stint": stint,
            "compound": compound,
            "mean_pace_ms": group["lap_time_ms"].mean(),
            "n_laps": n,
            "is_long_run": n >= min_stint_laps,
        })

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).sort_values(["compound", "mean_pace_ms"])
