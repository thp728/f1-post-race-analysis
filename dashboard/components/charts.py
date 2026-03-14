"""Shared visualisation functions for dashboard and PNG export.

Each function returns a matplotlib Figure or plotly Figure object.
Dashboard calls st.pyplot(fig) / st.plotly_chart(fig).
Export script calls fig.savefig().
"""

from typing import List, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import seaborn as sns

# Default compound colours (fallback when no FastF1 session available)
COMPOUND_COLORS = {
    "SOFT": "#FF3333",
    "MEDIUM": "#FFC300",
    "HARD": "#F0F0EC",
    "INTERMEDIATE": "#43B02A",
    "WET": "#0067AD",
    "UNKNOWN": "#999999",
}


# ---------------------------------------------------------------------------
# Matplotlib Charts (static — used for both dashboard and PNG export)
# ---------------------------------------------------------------------------

def plot_lap_time_distribution(
    laps: pd.DataFrame,
    drivers: List[str],
) -> plt.Figure:
    """Violin/box plot of lap time distributions per driver."""
    filtered = laps[laps["driver"].isin(drivers)].copy()
    filtered["lap_time_sec"] = filtered["lap_time_ms"] / 1000.0

    fig, ax = plt.subplots(figsize=(12, 5))
    sns.violinplot(
        data=filtered,
        x="driver",
        y="lap_time_sec",
        order=drivers,
        inner="box",
        density_norm="area",
        ax=ax,
    )
    ax.set_title("Lap Time Distribution")
    ax.set_xlabel("Driver")
    ax.set_ylabel("Lap Time (s)")
    plt.tight_layout()
    return fig


def plot_tyre_strategy(
    stint_summary: pd.DataFrame,
    drivers: Optional[List[str]] = None,
) -> plt.Figure:
    """Horizontal bar chart of stint timelines, colored by compound."""
    if drivers is None:
        drivers = stint_summary["driver"].unique().tolist()

    fig, ax = plt.subplots(figsize=(10, max(4, len(drivers) * 0.5)))

    for driver in drivers:
        drv_stints = stint_summary[stint_summary["driver"] == driver]
        for _, row in drv_stints.iterrows():
            color = COMPOUND_COLORS.get(row["compound"], COMPOUND_COLORS["UNKNOWN"])
            ax.barh(
                driver,
                row["stint_length"],
                left=row["start_lap"] - 1,
                color=color,
                edgecolor="black",
                linewidth=0.5,
            )

    ax.set_xlabel("Lap Number")
    ax.set_title("Tyre Strategy")
    ax.invert_yaxis()
    plt.tight_layout()
    return fig


def plot_degradation_curves(
    laps: pd.DataFrame,
    drivers: List[str],
    compound: str,
) -> plt.Figure:
    """Scatter + regression line of lap time vs tyre age per driver."""
    fig, ax = plt.subplots(figsize=(10, 6))

    for driver in drivers:
        drv = laps[
            (laps["driver"] == driver) & (laps["compound"] == compound)
        ].copy()
        if drv.empty:
            continue
        drv["lap_time_sec"] = drv["lap_time_ms"] / 1000.0

        ax.scatter(
            drv["tyre_life"], drv["lap_time_sec"],
            alpha=0.5, label=driver, s=20,
        )

        # Regression line
        if len(drv) >= 3:
            from scipy import stats
            slope, intercept, _, _, _ = stats.linregress(
                drv["tyre_life"].astype(float), drv["lap_time_sec"],
            )
            x_line = np.linspace(drv["tyre_life"].min(), drv["tyre_life"].max(), 50)
            ax.plot(x_line, slope * x_line + intercept, linewidth=1.5)

    ax.set_xlabel("Tyre Life (laps)")
    ax.set_ylabel("Lap Time (s)")
    ax.set_title(f"Degradation Curves — {compound}")
    ax.legend()
    plt.tight_layout()
    return fig


def plot_pace_delta(
    delta_df: pd.DataFrame,
    driver1: str,
    driver2: str,
) -> plt.Figure:
    """Line chart of cumulative gap evolution between two drivers."""
    fig, ax = plt.subplots(figsize=(12, 5))

    ax.plot(delta_df["lap_number"], delta_df["cumulative_gap_ms"] / 1000.0, linewidth=1.5)
    ax.axhline(y=0, color="gray", linestyle="--", linewidth=0.5)
    ax.fill_between(
        delta_df["lap_number"],
        delta_df["cumulative_gap_ms"] / 1000.0,
        0,
        alpha=0.15,
    )

    ax.set_xlabel("Lap")
    ax.set_ylabel("Gap (s)")
    ax.set_title(f"Pace Delta: {driver1} vs {driver2} (positive = {driver1} faster)")
    plt.tight_layout()
    return fig


def plot_sector_comparison(sector_df: pd.DataFrame) -> plt.Figure:
    """Grouped bar chart of sector times per driver."""
    drivers = sector_df["driver"].tolist()
    fig, ax = plt.subplots(figsize=(10, 5))

    x = np.arange(len(drivers))
    width = 0.25

    s1 = sector_df["best_s1_ms"] / 1000.0
    s2 = sector_df["best_s2_ms"] / 1000.0
    s3 = sector_df["best_s3_ms"] / 1000.0

    ax.bar(x - width, s1, width, label="S1")
    ax.bar(x, s2, width, label="S2")
    ax.bar(x + width, s3, width, label="S3")

    ax.set_xlabel("Driver")
    ax.set_ylabel("Sector Time (s)")
    ax.set_title("Best Sector Times Comparison")
    ax.set_xticks(x)
    ax.set_xticklabels(drivers)
    ax.legend()
    plt.tight_layout()
    return fig


def plot_consistency_bars(consistency_df: pd.DataFrame) -> plt.Figure:
    """Bar chart of CV% per driver, sorted."""
    sorted_df = consistency_df.sort_values("cv_pct")
    fig, ax = plt.subplots(figsize=(10, 5))

    ax.barh(sorted_df["driver"], sorted_df["cv_pct"])
    ax.set_xlabel("Coefficient of Variation (%)")
    ax.set_title("Lap Time Consistency (lower = more consistent)")
    plt.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Plotly Charts (interactive — dashboard only)
# ---------------------------------------------------------------------------

def plot_position_chart_interactive(
    laps: pd.DataFrame,
    drivers: List[str],
) -> go.Figure:
    """Interactive position-over-laps chart."""
    fig = go.Figure()

    for driver in drivers:
        drv = laps[laps["driver"] == driver].sort_values("lap_number")
        if drv.empty:
            continue
        fig.add_trace(go.Scatter(
            x=drv["lap_number"],
            y=drv["position"],
            mode="lines",
            name=driver,
            line=dict(width=2),
        ))

    fig.update_layout(
        title="Position Chart",
        xaxis_title="Lap",
        yaxis_title="Position",
        yaxis=dict(autorange="reversed"),
        hovermode="x unified",
    )
    return fig


def plot_prediction_table(predictions: pd.DataFrame) -> go.Figure:
    """Styled table of prediction scores with component breakdown."""
    display = predictions[
        ["rank", "driver", "score", "recent_form", "circuit_history",
         "cluster_form", "pit_consistency", "quali_conversion"]
    ].copy()

    # Round scores for display
    for col in display.columns:
        if col not in ("rank", "driver"):
            display[col] = display[col].round(3)

    fig = go.Figure(data=[go.Table(
        header=dict(
            values=list(display.columns),
            fill_color="rgb(40, 40, 40)",
            font=dict(color="white", size=12),
            align="center",
        ),
        cells=dict(
            values=[display[col] for col in display.columns],
            fill_color="rgb(250, 250, 250)",
            font=dict(size=11),
            align="center",
        ),
    )])

    fig.update_layout(title="Race Prediction Breakdown")
    return fig
