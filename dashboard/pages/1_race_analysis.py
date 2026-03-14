"""Race Analysis page — results, degradation, strategy, pace, consistency."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st

from dashboard.components.charts import (
    plot_consistency_bars,
    plot_degradation_curves,
    plot_lap_time_distribution,
    plot_pace_delta,
    plot_position_chart_interactive,
    plot_sector_comparison,
    plot_tyre_strategy,
)
from src.loader import (
    load_laps_from_db,
    load_pit_stops_from_db,
    load_results_from_db,
)
from src.metrics import (
    calculate_all_degradation,
    consistency_metrics,
    filter_clean_laps,
    lap_by_lap_delta,
    sector_comparison,
    stint_adjusted_pace,
)
from src.strategy import (
    detect_safety_car_periods,
    detect_undercuts,
    get_stint_summary,
    pit_stop_analysis,
    sc_beneficiaries,
)

st.set_page_config(page_title="Race Analysis", layout="wide")
st.title("Race Analysis")

# Get selection from session state
year = st.session_state.get("year")
round_num = st.session_state.get("round")
session_type = st.session_state.get("session_type", "R")
event_name = st.session_state.get("event_name", "")

if not year or not round_num:
    st.warning("Select a race from the sidebar on the home page.")
    st.stop()

st.header(f"{event_name} {year} — {session_type}")

# Load data
laps = load_laps_from_db(year, round_num, session_type)
results = load_results_from_db(year, round_num)

if laps.empty:
    st.warning(f"No lap data found for {event_name} {year} ({session_type}). Run the ETL first.")
    st.stop()

drivers = results["driver"].tolist() if not results.empty else laps["driver"].unique().tolist()
clean_laps = filter_clean_laps(laps)

# ---------------------------------------------------------------------------
# Results Table
# ---------------------------------------------------------------------------

if not results.empty:
    st.subheader("Results")
    display_results = results[
        ["driver", "team", "grid_position", "finish_position", "status", "points"]
    ].copy()
    display_results.columns = ["Driver", "Team", "Grid", "Finish", "Status", "Points"]
    st.dataframe(display_results, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Position Chart
# ---------------------------------------------------------------------------

st.subheader("Position Chart")
top_drivers = drivers[:10] if len(drivers) > 10 else drivers
fig_pos = plot_position_chart_interactive(laps, top_drivers)
st.plotly_chart(fig_pos, use_container_width=True)

# ---------------------------------------------------------------------------
# Lap Time Distribution
# ---------------------------------------------------------------------------

st.subheader("Lap Time Distribution")
if not clean_laps.empty:
    fig_dist = plot_lap_time_distribution(clean_laps, top_drivers)
    st.pyplot(fig_dist)

# ---------------------------------------------------------------------------
# Tyre Strategy
# ---------------------------------------------------------------------------

st.subheader("Tyre Strategy")
stint_summary = get_stint_summary(laps)
if not stint_summary.empty:
    fig_strat = plot_tyre_strategy(stint_summary, drivers)
    st.pyplot(fig_strat)

# ---------------------------------------------------------------------------
# Degradation
# ---------------------------------------------------------------------------

st.subheader("Tyre Degradation")
compounds = clean_laps["compound"].unique().tolist() if not clean_laps.empty else []
if compounds:
    selected_compound = st.selectbox("Compound", compounds)
    deg_drivers = st.multiselect(
        "Drivers", drivers, default=drivers[:5] if len(drivers) >= 5 else drivers
    )
    if deg_drivers:
        fig_deg = plot_degradation_curves(clean_laps, deg_drivers, selected_compound)
        st.pyplot(fig_deg)

    deg_table = calculate_all_degradation(laps)
    if not deg_table.empty:
        st.dataframe(deg_table.round(4), use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Stint-Adjusted Pace
# ---------------------------------------------------------------------------

st.subheader("Stint-Adjusted Pace")
pace = stint_adjusted_pace(laps, drivers[:10])
if not pace.empty:
    pace_display = pace.copy()
    pace_display["mean_pace_sec"] = (pace_display["mean_pace_ms"] / 1000.0).round(3)
    st.dataframe(
        pace_display[["driver", "stint", "compound", "mean_pace_sec", "n_laps"]],
        use_container_width=True,
        hide_index=True,
    )

# ---------------------------------------------------------------------------
# Pace Delta
# ---------------------------------------------------------------------------

st.subheader("Pace Delta")
col1, col2 = st.columns(2)
with col1:
    d1 = st.selectbox("Driver 1", drivers, index=0, key="delta_d1")
with col2:
    d2 = st.selectbox("Driver 2", drivers, index=min(1, len(drivers) - 1), key="delta_d2")
if d1 != d2:
    delta = lap_by_lap_delta(laps, d1, d2)
    if not delta.empty:
        fig_delta = plot_pace_delta(delta, d1, d2)
        st.pyplot(fig_delta)

# ---------------------------------------------------------------------------
# Sector Comparison
# ---------------------------------------------------------------------------

st.subheader("Sector Comparison")
sector_drivers = st.multiselect(
    "Drivers for sector comparison", drivers,
    default=drivers[:5] if len(drivers) >= 5 else drivers,
    key="sector_drivers",
)
if sector_drivers:
    sectors = sector_comparison(laps, sector_drivers)
    if not sectors.empty:
        fig_sector = plot_sector_comparison(sectors)
        st.pyplot(fig_sector)

# ---------------------------------------------------------------------------
# Consistency
# ---------------------------------------------------------------------------

st.subheader("Consistency Metrics")
cons = consistency_metrics(laps, drivers[:10])
if not cons.empty:
    fig_cons = plot_consistency_bars(cons)
    st.pyplot(fig_cons)

# ---------------------------------------------------------------------------
# Safety Car
# ---------------------------------------------------------------------------

st.subheader("Safety Car / VSC")
sc_periods = detect_safety_car_periods(laps)
if sc_periods:
    for p in sc_periods:
        st.markdown(f"- **{p['type']}**: Laps {p['start_lap']}–{p['end_lap']}")
    beneficiaries = sc_beneficiaries(laps, sc_periods)
    pitted = beneficiaries[beneficiaries["pitted_during_sc"]]
    if not pitted.empty:
        st.markdown("**Drivers who pitted during SC/VSC:**")
        st.dataframe(
            pitted[["driver", "sc_type", "start_lap", "end_lap"]],
            use_container_width=True,
            hide_index=True,
        )
else:
    st.info("No safety car or VSC periods detected.")

# ---------------------------------------------------------------------------
# Undercuts
# ---------------------------------------------------------------------------

st.subheader("Undercut Detection")
undercuts = detect_undercuts(laps, results)
successful = [u for u in undercuts if u["successful"]]
if successful:
    for u in successful:
        st.markdown(
            f"- **{u['undercutter']}** undercut **{u['victim']}** "
            f"(pit lap {u['undercut_lap']}, moved P{u['position_before']} → P{u['position_after']})"
        )
else:
    st.info("No successful undercuts detected.")

# ---------------------------------------------------------------------------
# Pit Stop Analysis
# ---------------------------------------------------------------------------

st.subheader("Pit Stop Times")
pit_stops = load_pit_stops_from_db(year, round_num)
if not pit_stops.empty:
    pit_analysis = pit_stop_analysis(pit_stops)
    if not pit_analysis.empty:
        pit_display = pit_analysis.copy()
        pit_display["mean_duration_sec"] = (pit_display["mean_duration_ms"] / 1000.0).round(3)
        pit_display["best_stop_sec"] = (pit_display["best_stop_ms"] / 1000.0).round(3)
        st.dataframe(
            pit_display[["driver", "n_stops", "mean_duration_sec", "best_stop_sec"]],
            use_container_width=True,
            hide_index=True,
        )
