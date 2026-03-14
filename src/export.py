"""Chart export helpers for blog PNG generation."""

import os
from pathlib import Path
from typing import Any, List

EXPORT_DIR = Path(__file__).parent.parent / "exports"


def get_export_path(year: int, round_num: int) -> Path:
    """Return and create the export directory for a race: exports/{year}_R{round:02d}/"""
    path = EXPORT_DIR / f"{year}_R{round_num:02d}"
    os.makedirs(path, exist_ok=True)
    return path


def save_figure(
    fig: Any,
    filename: str,
    year: int,
    round_num: int,
    dpi: int = 150,
) -> str:
    """Save a matplotlib figure to the export directory. Returns the full path."""
    export_path = get_export_path(year, round_num)
    filepath = export_path / filename
    fig.savefig(str(filepath), dpi=dpi, bbox_inches="tight")
    return str(filepath)


def export_race_charts(year: int, round_num: int) -> List[str]:
    """Generate and save all standard charts for a race.

    Returns list of exported file paths.
    """
    from dashboard.components.charts import (
        plot_consistency_bars,
        plot_degradation_curves,
        plot_lap_time_distribution,
        plot_pace_delta,
        plot_sector_comparison,
        plot_tyre_strategy,
    )
    from src.loader import load_laps_from_db, load_results_from_db
    from src.metrics import (
        calculate_all_degradation,
        consistency_metrics,
        filter_clean_laps,
        lap_by_lap_delta,
        sector_comparison,
    )
    from src.strategy import get_stint_summary

    laps = load_laps_from_db(year, round_num, "R")
    results = load_results_from_db(year, round_num)

    if laps.empty:
        print(f"No lap data for {year} R{round_num:02d}")
        return []

    drivers = results["driver"].tolist() if not results.empty else laps["driver"].unique().tolist()
    top_drivers = drivers[:10] if len(drivers) > 10 else drivers
    clean_laps = filter_clean_laps(laps)
    exported = []

    # 1. Lap time distribution
    if not clean_laps.empty:
        fig = plot_lap_time_distribution(clean_laps, top_drivers)
        exported.append(save_figure(fig, "lap_distribution.png", year, round_num))
        import matplotlib.pyplot as plt
        plt.close(fig)

    # 2. Tyre strategy
    stint_summary = get_stint_summary(laps)
    if not stint_summary.empty:
        fig = plot_tyre_strategy(stint_summary, drivers)
        exported.append(save_figure(fig, "tyre_strategy.png", year, round_num))
        plt.close(fig)

    # 3. Degradation curves (one per compound)
    compounds = clean_laps["compound"].unique().tolist() if not clean_laps.empty else []
    for compound in compounds:
        fig = plot_degradation_curves(clean_laps, top_drivers[:5], compound)
        exported.append(save_figure(
            fig, f"degradation_{compound.lower()}.png", year, round_num
        ))
        plt.close(fig)

    # 4. Pace delta (top 2 drivers)
    if len(drivers) >= 2:
        delta = lap_by_lap_delta(laps, drivers[0], drivers[1])
        if not delta.empty:
            fig = plot_pace_delta(delta, drivers[0], drivers[1])
            exported.append(save_figure(fig, "pace_delta.png", year, round_num))
            plt.close(fig)

    # 5. Sector comparison
    sectors = sector_comparison(laps, top_drivers[:5])
    if not sectors.empty:
        fig = plot_sector_comparison(sectors)
        exported.append(save_figure(fig, "sector_comparison.png", year, round_num))
        plt.close(fig)

    # 6. Consistency
    cons = consistency_metrics(laps, top_drivers)
    if not cons.empty:
        fig = plot_consistency_bars(cons)
        exported.append(save_figure(fig, "consistency.png", year, round_num))
        plt.close(fig)

    return exported
