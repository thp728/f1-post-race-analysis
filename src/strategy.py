"""Stint analysis, undercut/overcut detection, and safety car impact."""

from typing import List

import pandas as pd


# ---------------------------------------------------------------------------
# Stint Timeline
# ---------------------------------------------------------------------------


def get_stint_summary(laps: pd.DataFrame) -> pd.DataFrame:
    """Build stint summary: driver, stint, compound, start_lap, end_lap, stint_length.

    Works on DataFrames from SQLite (column names: driver, stint, compound, lap_number).
    """
    if laps.empty:
        return pd.DataFrame()

    results = []
    for (driver, stint), group in laps.groupby(["driver", "stint"]):
        if pd.isna(stint):
            continue
        results.append(
            {
                "driver": driver,
                "stint": int(stint),
                "compound": group["compound"].iloc[0] if not group.empty else "",
                "start_lap": int(group["lap_number"].min()),
                "end_lap": int(group["lap_number"].max()),
                "stint_length": len(group),
            }
        )

    return pd.DataFrame(results)


# ---------------------------------------------------------------------------
# Undercut / Overcut Detection
# ---------------------------------------------------------------------------


def _get_pit_laps(laps: pd.DataFrame, driver: str) -> List[int]:
    """Get lap numbers where a driver pitted (pit_in)."""
    drv = laps[(laps["driver"] == driver) & (laps["is_pit_in"] == 1)]
    return sorted(drv["lap_number"].tolist())


def detect_undercuts(
    laps: pd.DataFrame,
    results: pd.DataFrame,
    gap_threshold_laps: int = 3,
) -> List[dict]:
    """Detect undercut attempts between drivers.

    An undercut: driver A pits 1-N laps before driver B and gains position.
    Returns list of dicts with undercut details.
    """
    drivers = laps["driver"].unique()
    undercuts = []

    for d1 in drivers:
        d1_pits = _get_pit_laps(laps, d1)
        for d2 in drivers:
            if d1 == d2:
                continue
            d2_pits = _get_pit_laps(laps, d2)

            for p1 in d1_pits:
                for p2 in d2_pits:
                    if 0 < p2 - p1 <= gap_threshold_laps:
                        # d1 pitted before d2 — check for position swap
                        d1_pos_before = laps[
                            (laps["driver"] == d1) & (laps["lap_number"] == p1 - 1)
                        ]["position"].values
                        d2_pos_before = laps[
                            (laps["driver"] == d2) & (laps["lap_number"] == p1 - 1)
                        ]["position"].values

                        d1_pos_after = laps[
                            (laps["driver"] == d1) & (laps["lap_number"] == p2 + 1)
                        ]["position"].values
                        d2_pos_after = laps[
                            (laps["driver"] == d2) & (laps["lap_number"] == p2 + 1)
                        ]["position"].values

                        if (
                            len(d1_pos_before) > 0
                            and len(d2_pos_before) > 0
                            and len(d1_pos_after) > 0
                            and len(d2_pos_after) > 0
                        ):
                            was_behind = d1_pos_before[0] > d2_pos_before[0]
                            now_ahead = d1_pos_after[0] < d2_pos_after[0]
                            successful = was_behind and now_ahead

                            undercuts.append(
                                {
                                    "undercutter": d1,
                                    "victim": d2,
                                    "undercut_lap": p1,
                                    "victim_pit_lap": p2,
                                    "position_before": int(d1_pos_before[0]),
                                    "position_after": int(d1_pos_after[0]),
                                    "successful": successful,
                                }
                            )

    return undercuts


def detect_overcuts(
    laps: pd.DataFrame,
    results: pd.DataFrame,
    gap_threshold_laps: int = 3,
) -> List[dict]:
    """Detect overcut attempts (driver stays out longer and gains position).

    An overcut: driver A pits 1-N laps after driver B and gains position.
    """
    drivers = laps["driver"].unique()
    overcuts = []

    for d1 in drivers:
        d1_pits = _get_pit_laps(laps, d1)
        for d2 in drivers:
            if d1 == d2:
                continue
            d2_pits = _get_pit_laps(laps, d2)

            for p1 in d1_pits:
                for p2 in d2_pits:
                    if 0 < p1 - p2 <= gap_threshold_laps:
                        # d1 pitted after d2 (overcutting)
                        d1_pos_before = laps[
                            (laps["driver"] == d1) & (laps["lap_number"] == p2 - 1)
                        ]["position"].values
                        d2_pos_before = laps[
                            (laps["driver"] == d2) & (laps["lap_number"] == p2 - 1)
                        ]["position"].values

                        d1_pos_after = laps[
                            (laps["driver"] == d1) & (laps["lap_number"] == p1 + 1)
                        ]["position"].values
                        d2_pos_after = laps[
                            (laps["driver"] == d2) & (laps["lap_number"] == p1 + 1)
                        ]["position"].values

                        if (
                            len(d1_pos_before) > 0
                            and len(d2_pos_before) > 0
                            and len(d1_pos_after) > 0
                            and len(d2_pos_after) > 0
                        ):
                            was_behind = d1_pos_before[0] > d2_pos_before[0]
                            now_ahead = d1_pos_after[0] < d2_pos_after[0]
                            successful = was_behind and now_ahead

                            overcuts.append(
                                {
                                    "overcutter": d1,
                                    "victim": d2,
                                    "overcutter_pit_lap": p1,
                                    "victim_pit_lap": p2,
                                    "position_before": int(d1_pos_before[0]),
                                    "position_after": int(d1_pos_after[0]),
                                    "successful": successful,
                                }
                            )

    return overcuts


# ---------------------------------------------------------------------------
# Safety Car Analysis
# ---------------------------------------------------------------------------


def detect_safety_car_periods(laps: pd.DataFrame) -> List[dict]:
    """Identify SC/VSC periods from track_status column.

    Track status codes: '4' = Safety Car, '6' = VSC.
    Returns list of dicts: {type, start_lap, end_lap}.
    """
    if laps.empty or "track_status" not in laps.columns:
        return []

    # Get unique laps with SC or VSC status
    sc_laps = laps[laps["track_status"].str.contains("4", na=False)][
        "lap_number"
    ].unique()

    vsc_laps = laps[laps["track_status"].str.contains("6", na=False)][
        "lap_number"
    ].unique()

    periods = []

    # Group consecutive laps into periods
    for status_type, lap_nums in [("SC", sc_laps), ("VSC", vsc_laps)]:
        if len(lap_nums) == 0:
            continue
        lap_nums = sorted(lap_nums)
        start = lap_nums[0]
        prev = lap_nums[0]

        for lap in lap_nums[1:]:
            if lap - prev > 1:
                periods.append(
                    {
                        "type": status_type,
                        "start_lap": int(start),
                        "end_lap": int(prev),
                    }
                )
                start = lap
            prev = lap

        periods.append(
            {
                "type": status_type,
                "start_lap": int(start),
                "end_lap": int(prev),
            }
        )

    return sorted(periods, key=lambda p: p["start_lap"])


def sc_beneficiaries(
    laps: pd.DataFrame,
    sc_periods: List[dict],
) -> pd.DataFrame:
    """For each SC period, identify which drivers pitted (benefited from cheap stop).

    Returns DataFrame: driver, sc_period_index, sc_type, start_lap, end_lap,
    pitted_during_sc.
    """
    if not sc_periods:
        return pd.DataFrame()

    results = []
    drivers = laps["driver"].unique()

    for idx, period in enumerate(sc_periods):
        for driver in drivers:
            drv_laps = laps[
                (laps["driver"] == driver)
                & (laps["lap_number"] >= period["start_lap"])
                & (laps["lap_number"] <= period["end_lap"])
            ]
            pitted = (drv_laps["is_pit_in"] == 1).any() if not drv_laps.empty else False

            results.append(
                {
                    "driver": driver,
                    "sc_period_index": idx,
                    "sc_type": period["type"],
                    "start_lap": period["start_lap"],
                    "end_lap": period["end_lap"],
                    "pitted_during_sc": pitted,
                }
            )

    return pd.DataFrame(results)


# ---------------------------------------------------------------------------
# Pit Stop Analysis
# ---------------------------------------------------------------------------


def pit_stop_analysis(pit_stops: pd.DataFrame) -> pd.DataFrame:
    """Summary statistics of pit stop durations per driver.

    Returns DataFrame: driver, n_stops, mean_duration_ms, std_duration_ms,
    best_stop_ms, and optionally mean_stationary_ms, std_stationary_ms,
    best_stationary_ms if stationary_ms data is available.
    """
    if pit_stops.empty:
        return pd.DataFrame()

    results = []
    for driver, group in pit_stops.groupby("driver"):
        durations = group["duration_ms"].dropna()
        if durations.empty:
            continue

        result = {
            "driver": driver,
            "n_stops": len(group),
            "mean_duration_ms": durations.mean(),
            "std_duration_ms": durations.std() if len(durations) > 1 else 0.0,
            "best_stop_ms": durations.min(),
        }

        if "stationary_ms" in group.columns:
            stationary = group["stationary_ms"].dropna()
            if len(stationary) >= 2:
                result["mean_stationary_ms"] = stationary.mean()
                result["std_stationary_ms"] = stationary.std()
                result["best_stationary_ms"] = stationary.min()
            elif len(stationary) == 1:
                result["mean_stationary_ms"] = stationary.iloc[0]
                result["std_stationary_ms"] = 0.0
                result["best_stationary_ms"] = stationary.iloc[0]

        results.append(result)

    if not results:
        return pd.DataFrame()
    return pd.DataFrame(results).sort_values("mean_duration_ms")
