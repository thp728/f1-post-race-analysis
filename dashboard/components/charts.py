"""Shared visualisation functions for dashboard and PNG export.

Each function returns a Plotly Figure object.
Dashboard calls st.plotly_chart(fig).
Export script calls fig.write_image().
"""

from typing import List, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Default compound colours (fallback when no FastF1 session available)
COMPOUND_COLORS = {
    "SOFT": "#FF3333",
    "MEDIUM": "#FFC300",
    "HARD": "#F0F0EC",
    "INTERMEDIATE": "#43B02A",
    "WET": "#0067AD",
    "UNKNOWN": "#999999",
}

# F1-inspired color palette for driver lines
DRIVER_PALETTE = [
    "#FF1801",  # F1 Red
    "#0090D0",  # Blue
    "#229971",  # Green
    "#F58025",  # Orange
    "#9061BC",  # Purple
    "#3671C6",  # Light Blue
    "#E8362F",  # Red
    "#37BEDD",  # Cyan
    "#6CD1C0",  # Teal
    "#BFCE43",  # Yellow-Green
    "#CAC9C9",  # Silver
    "#BABABA",  # Grey
    "#FFFFFF",  # White
]

F1_FONT = "IBM Plex Sans, sans-serif"


def get_plotly_layout(
    title: str,
    xaxis_title: str = "",
    yaxis_title: str = "",
    yaxis_reversed: bool = False,
    barmode: str = "group",
    hovermode: str = "closest",
) -> dict:
    """Create a consistent Plotly layout matching F1 theme."""
    layout = dict(
        title=dict(
            text=title,
            font=dict(size=18, color="#FAFAFA", family=F1_FONT),
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(30,30,30,0.5)",
        font=dict(color="#FAFAFA", family=F1_FONT),
        xaxis=dict(
            title=dict(text=xaxis_title, font=dict(size=12, color="#FAFAFA")),
            gridcolor="rgba(255,255,255,0.1)",
            linecolor="rgba(255,255,255,0.2)",
            tickfont=dict(color="#B0B0B0"),
            zerolinecolor="rgba(255,255,255,0.1)",
        ),
        yaxis=dict(
            title=dict(text=yaxis_title, font=dict(size=12, color="#FAFAFA")),
            gridcolor="rgba(255,255,255,0.1)",
            linecolor="rgba(255,255,255,0.2)",
            tickfont=dict(color="#B0B0B0"),
            zerolinecolor="rgba(255,255,255,0.1)",
            autorange="reversed" if yaxis_reversed else None,
        ),
        legend=dict(
            bgcolor="rgba(0,0,0,0.3)",
            bordercolor="rgba(255,255,255,0.1)",
            font=dict(color="#B0B0B0"),
        ),
        barmode=barmode,
        hovermode=hovermode,
        margin=dict(l=60, r=30, t=60, b=60),
    )
    return layout


# ---------------------------------------------------------------------------
# Interactive Charts (Plotly)
# ---------------------------------------------------------------------------


def plot_lap_time_distribution(
    laps: pd.DataFrame,
    drivers: List[str],
) -> go.Figure:
    """Box plot of lap time distributions per driver."""
    filtered = laps[laps["driver"].isin(drivers)].copy()
    filtered["lap_time_sec"] = filtered["lap_time_ms"] / 1000.0

    fig = go.Figure()
    for driver in drivers:
        drv = filtered[filtered["driver"] == driver]
        if drv.empty:
            continue
        fig.add_trace(
            go.Box(
                y=drv["lap_time_sec"],
                name=driver,
                boxpoints="outliers",
            )
        )

    fig.update_layout(
        **get_plotly_layout(
            title="Lap Time Distribution",
            xaxis_title="Driver",
            yaxis_title="Lap Time (s)",
            hovermode="closest",
        )
    )
    return fig


def plot_tyre_strategy(
    stint_summary: pd.DataFrame,
    drivers: Optional[List[str]] = None,
) -> go.Figure:
    """Horizontal bar chart of stint timelines, colored by compound."""
    if drivers is None:
        drivers = stint_summary["driver"].unique().tolist()

    fig = go.Figure()

    # Track which compounds have been added to the legend
    legend_shown = set()

    for driver in drivers:
        drv_stints = stint_summary[stint_summary["driver"] == driver]
        for _, row in drv_stints.iterrows():
            compound = row["compound"]
            color = COMPOUND_COLORS.get(compound, COMPOUND_COLORS["UNKNOWN"])
            show_legend = compound not in legend_shown
            legend_shown.add(compound)

            fig.add_trace(
                go.Bar(
                    y=[driver],
                    x=[row["stint_length"]],
                    base=row["start_lap"] - 1,
                    orientation="h",
                    marker=dict(
                        color=color,
                        line=dict(color="black", width=0.5),
                    ),
                    name=compound,
                    legendgroup=compound,
                    showlegend=show_legend,
                    hovertemplate=(
                        f"<b>{driver}</b><br>"
                        f"Compound: {compound}<br>"
                        f"Laps: {row['start_lap']}–{row['end_lap']}<br>"
                        f"Length: {row['stint_length']} laps"
                        "<extra></extra>"
                    ),
                )
            )

    fig.update_layout(
        **get_plotly_layout(
            title="Tyre Strategy",
            xaxis_title="Lap Number",
            yaxis_title="Driver",
            yaxis_reversed=True,
            barmode="stack",
            hovermode="closest",
        )
    )
    return fig


def plot_degradation_curves(
    laps: pd.DataFrame,
    drivers: List[str],
    compound: str,
) -> go.Figure:
    """Scatter + regression line of lap time vs tyre age per driver."""
    fig = go.Figure()

    for driver in drivers:
        drv = laps[(laps["driver"] == driver) & (laps["compound"] == compound)].copy()
        if drv.empty:
            continue
        drv["lap_time_sec"] = drv["lap_time_ms"] / 1000.0

        fig.add_trace(
            go.Scatter(
                x=drv["tyre_life"],
                y=drv["lap_time_sec"],
                mode="markers",
                name=driver,
                marker=dict(size=6, opacity=0.5),
            )
        )

        # Regression line
        if len(drv) >= 3:
            from scipy import stats

            slope, intercept, _, _, _ = stats.linregress(
                drv["tyre_life"].astype(float),
                drv["lap_time_sec"],
            )
            x_line = np.linspace(drv["tyre_life"].min(), drv["tyre_life"].max(), 50)
            fig.add_trace(
                go.Scatter(
                    x=x_line,
                    y=slope * x_line + intercept,
                    mode="lines",
                    name=f"{driver} trend",
                    line=dict(width=1.5),
                    showlegend=False,
                )
            )

    fig.update_layout(
        **get_plotly_layout(
            title=f"Degradation Curves — {compound}",
            xaxis_title="Tyre Life (laps)",
            yaxis_title="Lap Time (s)",
            hovermode="closest",
        )
    )
    return fig


def plot_pace_delta(
    delta_df: pd.DataFrame,
    driver1: str,
    driver2: str,
) -> go.Figure:
    """Line chart of cumulative gap evolution between two drivers."""
    gap_sec = delta_df["cumulative_gap_ms"] / 1000.0

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=delta_df["lap_number"],
            y=gap_sec,
            mode="lines",
            name="Gap",
            line=dict(width=2),
            fill="tozeroy",
            fillcolor="rgba(99, 110, 250, 0.15)",
        )
    )
    fig.add_hline(y=0, line_dash="dash", line_color="gray", line_width=0.5)

    fig.update_layout(
        **get_plotly_layout(
            title=f"Pace Delta: {driver1} vs {driver2} (positive = {driver1} faster)",
            xaxis_title="Lap",
            yaxis_title="Gap (s)",
            hovermode="x unified",
        )
    )
    return fig


def plot_sector_comparison(sector_df: pd.DataFrame) -> go.Figure:
    """Grouped bar chart of sector times per driver with data labels."""
    drivers = sector_df["driver"].tolist()

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=drivers,
            y=sector_df["best_s1_ms"] / 1000.0,
            name="S1",
            text=(sector_df["best_s1_ms"] / 1000.0).round(3),
            textposition="auto",
        )
    )
    fig.add_trace(
        go.Bar(
            x=drivers,
            y=sector_df["best_s2_ms"] / 1000.0,
            name="S2",
            text=(sector_df["best_s2_ms"] / 1000.0).round(3),
            textposition="auto",
        )
    )
    fig.add_trace(
        go.Bar(
            x=drivers,
            y=sector_df["best_s3_ms"] / 1000.0,
            name="S3",
            text=(sector_df["best_s3_ms"] / 1000.0).round(3),
            textposition="auto",
        )
    )

    fig.update_layout(
        **get_plotly_layout(
            title="Best Sector Times Comparison",
            xaxis_title="Driver",
            yaxis_title="Sector Time (s)",
            barmode="group",
            hovermode="closest",
        )
    )
    return fig


def plot_consistency_bars(consistency_df: pd.DataFrame) -> go.Figure:
    """Horizontal bar chart of CV% per driver, sorted."""
    sorted_df = consistency_df.sort_values("cv_pct")

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=sorted_df["driver"],
            x=sorted_df["cv_pct"],
            orientation="h",
            text=sorted_df["cv_pct"].round(3),
            textposition="auto",
            hovertemplate=("<b>%{y}</b><br>CV: %{x:.3f}%<extra></extra>"),
        )
    )

    fig.update_layout(
        **get_plotly_layout(
            title="Lap Time Consistency (lower = more consistent)",
            xaxis_title="Coefficient of Variation (%)",
            hovermode="closest",
        )
    )
    return fig


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
        fig.add_trace(
            go.Scatter(
                x=drv["lap_number"],
                y=drv["position"],
                mode="lines",
                name=driver,
                line=dict(width=2),
            )
        )

    fig.update_layout(
        **get_plotly_layout(
            title="Position Chart",
            xaxis_title="Lap",
            yaxis_title="Position",
            yaxis_reversed=True,
            hovermode="x unified",
        )
    )
    return fig


def plot_prediction_table(predictions: pd.DataFrame) -> go.Figure:
    """Styled table of prediction scores with component breakdown."""
    display = predictions[
        [
            "rank",
            "driver",
            "score",
            "recent_form",
            "circuit_history",
            "cluster_form",
            "pit_consistency",
            "quali_conversion",
        ]
    ].copy()

    # Round scores for display
    for col in display.columns:
        if col not in ("rank", "driver"):
            display[col] = display[col].round(3)

    fig = go.Figure(
        data=[
            go.Table(
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
            )
        ]
    )

    fig.update_layout(title="Race Prediction Breakdown")
    return fig


# ---------------------------------------------------------------------------
# Qualifying Charts
# ---------------------------------------------------------------------------

_SEGMENT_COLORS = {
    "Q3": "rgba(0, 180, 0, 0.25)",
    "Q2": "rgba(255, 200, 0, 0.25)",
    "Q1": "rgba(255, 0, 0, 0.25)",
    "SQ3": "rgba(0, 180, 0, 0.25)",
    "SQ2": "rgba(255, 200, 0, 0.25)",
    "SQ1": "rgba(255, 0, 0, 0.25)",
}

_SEGMENT_BAR_COLORS = {
    "Q3": "rgba(0, 180, 0, 0.7)",
    "Q2": "rgba(255, 200, 0, 0.7)",
    "Q1": "rgba(255, 60, 60, 0.7)",
    "SQ3": "rgba(0, 180, 0, 0.7)",
    "SQ2": "rgba(255, 200, 0, 0.7)",
    "SQ1": "rgba(255, 60, 60, 0.7)",
}


def _ms_to_lap_str(ms: float) -> str:
    """Format milliseconds as m:ss.xxx lap time string."""
    if pd.isna(ms):
        return ""
    total_sec = ms / 1000.0
    minutes = int(total_sec // 60)
    seconds = total_sec % 60
    return f"{minutes}:{seconds:06.3f}"


def plot_qualifying_progression(progression_df: pd.DataFrame) -> go.Figure:
    """Styled table of qualifying results color-coded by segment."""
    df = progression_df.sort_values("position").copy()

    # Format times
    lap_strs = [_ms_to_lap_str(v) for v in df["best_lap_ms"]]
    s1_strs = [_ms_to_lap_str(v) for v in df["best_s1_ms"]]
    s2_strs = [_ms_to_lap_str(v) for v in df["best_s2_ms"]]
    s3_strs = [_ms_to_lap_str(v) for v in df["best_s3_ms"]]

    # Row colors by segment
    row_colors = [_SEGMENT_COLORS.get(seg, "white") for seg in df["segment"]]

    fig = go.Figure(
        data=[
            go.Table(
                header=dict(
                    values=["Pos", "Driver", "Best Lap", "S1", "S2", "S3", "Segment"],
                    fill_color="rgb(40, 40, 40)",
                    font=dict(color="white", size=12),
                    align="center",
                ),
                cells=dict(
                    values=[
                        df["position"].tolist(),
                        df["driver"].tolist(),
                        lap_strs,
                        s1_strs,
                        s2_strs,
                        s3_strs,
                        df["segment"].tolist(),
                    ],
                    fill_color=[row_colors] * 7,
                    font=dict(size=11),
                    align="center",
                ),
            )
        ]
    )

    fig.update_layout(title="Qualifying Progression")
    return fig


def plot_gap_to_pole(gap_df: pd.DataFrame) -> go.Figure:
    """Horizontal bar chart of each driver's gap to pole, colored by segment."""
    df = gap_df.sort_values("position", ascending=False).copy()

    # Need segment info — merge from qualifying_progression if available
    colors = []
    for _, row in df.iterrows():
        seg = row.get("segment", "")
        colors.append(_SEGMENT_BAR_COLORS.get(seg, "rgba(150, 150, 150, 0.7)"))

    gap_sec = df["gap_ms"] / 1000.0
    labels = [f"+{v:.3f}s" if v > 0 else "POLE" for v in gap_sec]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=df["driver"],
            x=gap_sec,
            orientation="h",
            marker=dict(color=colors),
            text=labels,
            textposition="outside",
            hovertemplate=("<b>%{y}</b><br>Gap: %{x:.3f}s<extra></extra>"),
        )
    )

    fig.update_layout(
        **get_plotly_layout(
            title="Gap to Pole",
            xaxis_title="Gap (s)",
            yaxis_title="Driver",
            hovermode="closest",
        )
    )
    return fig


def plot_lap_improvement(
    improvement_df: pd.DataFrame,
    driver: str,
) -> go.Figure:
    """Line+scatter of qualifying attempt times with delta annotations."""
    df = improvement_df.copy()
    df["lap_time_sec"] = df["lap_time_ms"] / 1000.0

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["attempt"],
            y=df["lap_time_sec"],
            mode="lines+markers+text",
            name=driver,
            marker=dict(size=10),
            text=[f"{v / 1000.0:+.3f}s" if pd.notna(v) else "" for v in df["delta_ms"]],
            textposition="top center",
            textfont=dict(size=10),
        )
    )

    # Best lap reference line
    best = df["lap_time_sec"].min()
    fig.add_hline(
        y=best,
        line_dash="dash",
        line_color="green",
        line_width=1,
        annotation_text=f"Best: {best:.3f}s",
        annotation_position="bottom right",
    )

    fig.update_layout(
        **get_plotly_layout(
            title=f"Lap Improvement — {driver}",
            xaxis_title="Attempt",
            yaxis_title="Lap Time (s)",
            hovermode="x unified",
        )
    )
    fig.update_layout(xaxis=dict(dtick=1))
    return fig


# ---------------------------------------------------------------------------
# Practice Charts
# ---------------------------------------------------------------------------


def plot_long_run_pace(
    long_run_df: pd.DataFrame,
    drivers: List[str],
) -> go.Figure:
    """Grouped bar chart of long-run average pace by driver and compound."""
    df = long_run_df[
        (long_run_df["driver"].isin(drivers)) & (long_run_df["is_long_run"])
    ].copy()
    df["mean_pace_sec"] = df["mean_pace_ms"] / 1000.0

    compounds = df["compound"].unique().tolist()

    fig = go.Figure()
    for compound in compounds:
        comp_df = df[df["compound"] == compound].sort_values("mean_pace_sec")
        color = COMPOUND_COLORS.get(compound, COMPOUND_COLORS["UNKNOWN"])
        fig.add_trace(
            go.Bar(
                x=comp_df["driver"],
                y=comp_df["mean_pace_sec"],
                name=compound,
                marker=dict(
                    color=color,
                    line=dict(color="black", width=0.5),
                ),
                text=comp_df["mean_pace_sec"].round(3),
                textposition="auto",
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    f"Compound: {compound}<br>"
                    "Pace: %{y:.3f}s<br>"
                    "<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        **get_plotly_layout(
            title="Long Run Pace by Compound",
            xaxis_title="Driver",
            yaxis_title="Average Lap Time (s)",
            barmode="group",
            hovermode="closest",
        )
    )
    return fig


# ---------------------------------------------------------------------------
# Filterable DataFrame
# ---------------------------------------------------------------------------


def filterable_dataframe(
    df: pd.DataFrame,
    key: str,
) -> pd.DataFrame:
    """Display a DataFrame with expandable column filters.

    For object/string columns, renders a multiselect filter.
    Returns the filtered DataFrame.
    """
    if df.empty:
        return df

    with st.expander("Filter columns"):
        filtered = df.copy()
        cols_to_filter = []

        for col in filtered.columns:
            if filtered[col].dtype == "object":
                cols_to_filter.append(col)

        if not cols_to_filter:
            st.info("No filterable columns (no string columns).")
            return df

        for col in cols_to_filter:
            unique_vals = sorted(filtered[col].unique().tolist())
            selected = st.multiselect(
                f"Filter by {col}",
                options=unique_vals,
                default=unique_vals,
                key=f"{key}_{col}",
            )
            if selected:
                filtered = filtered[filtered[col].isin(selected)]

        if filtered.empty:
            st.warning("No rows match the selected filters.")

    st.dataframe(filtered, use_container_width=True, hide_index=True)
    return filtered
