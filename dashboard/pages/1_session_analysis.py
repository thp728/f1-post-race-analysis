"""Session Analysis — branches by session type (Race/Sprint/Qualifying/Practice)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import streamlit as st

from dashboard.components.charts import (
    filterable_dataframe,
    plot_consistency_bars,
    plot_degradation_curves,
    plot_gap_to_pole,
    plot_lap_improvement,
    plot_lap_time_distribution,
    plot_long_run_pace,
    plot_pace_delta,
    plot_position_chart_interactive,
    plot_qualifying_progression,
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
    gap_to_pole,
    lap_by_lap_delta,
    lap_improvement_delta,
    long_run_pace,
    qualifying_progression,
    sector_comparison,
    speed_trap_comparison,
    stint_adjusted_pace,
)
from src.strategy import (
    detect_safety_car_periods,
    detect_undercuts,
    get_stint_summary,
    pit_stop_analysis,
    sc_beneficiaries,
)

# Session type groups
_RACE_SESSIONS = {"R", "S"}
_QUALIFYING_SESSIONS = {"Q", "SQ"}
_PRACTICE_SESSIONS = {"FP1", "FP2", "FP3"}


# ---------------------------------------------------------------------------
# Race / Sprint Analysis
# ---------------------------------------------------------------------------


def _show_race_analysis(
    laps: pd.DataFrame,
    clean_laps: pd.DataFrame,
    selected_drivers: list[str],
    all_drivers: list[str],
    year: int,
    round_num: int,
    session_type: str,
) -> None:
    results = load_results_from_db(year, round_num, session_type=session_type)

    # --- Summary Metrics ---
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if not results.empty:
            winner = results[results["finish_position"] == 1]["driver"].values
            st.metric("Winner", winner[0] if len(winner) > 0 else "N/A")
    with col2:
        if not clean_laps.empty:
            fastest = clean_laps.loc[clean_laps["lap_time_ms"].idxmin()]
            st.metric(
                "Fastest Lap",
                f"{fastest['driver']} ({fastest['lap_time_ms'] / 1000:.3f}s)",
            )
    with col3:
        total_laps = laps["lap_number"].max() if not laps.empty else 0
        st.metric("Total Laps", int(total_laps))
    with col4:
        pit_stops = load_pit_stops_from_db(year, round_num, session_type=session_type)
        n_stops = len(pit_stops) if not pit_stops.empty else 0
        st.metric("Total Pit Stops", n_stops)

    # --- Results Table ---
    if not results.empty:
        st.subheader("Results")
        with st.expander("How to read this table"):
            st.markdown("""\
| Column | What it means |
|---|---|
| Driver | Driver name |
| Team | Constructor |
| Grid | Starting position (P1 = pole) |
| Finish | Final classified position |
| Status | "Finished", or reason for retirement (e.g. "Collision", "Engine") |
| Points | Championship points scored |

**What to look for:** Large differences between Grid and Finish indicate a driver who gained or lost \
a lot of positions. A "DNF" (Did Not Finish) in Status explains a missing position in the standings.
""")
        display_results = results[
            ["driver", "team", "grid_position", "finish_position", "status", "points"]
        ].copy()
        display_results.columns = [
            "Driver",
            "Team",
            "Grid",
            "Finish",
            "Status",
            "Points",
        ]

        def _color_results(row: pd.Series) -> list[str]:
            status = str(row["Status"]).strip()
            grid = row["Grid"]
            finish = row["Finish"]
            is_classified = status == "Finished" or "lap" in status.lower()
            if not is_classified:
                return ["background-color: rgba(255, 0, 0, 0.3)"] * len(row)
            if pd.isna(grid) or pd.isna(finish) or grid == 0:
                return [""] * len(row)
            change = grid - finish
            if change > 0:
                intensity = min(change / 10, 1.0)
                return [
                    f"background-color: rgba(0, 180, 0, {0.1 + intensity * 0.4})"
                ] * len(row)
            elif change < 0:
                intensity = min(abs(change) / 10, 1.0)
                return [
                    f"background-color: rgba(255, 0, 0, {0.1 + intensity * 0.4})"
                ] * len(row)
            return [""] * len(row)

        styled_results = display_results.style.apply(_color_results, axis=1)
        st.dataframe(styled_results, use_container_width=True, hide_index=True)

    # --- Position Chart ---
    st.subheader("Position Chart")
    with st.expander("How to read this chart"):
        st.markdown("""\
A line per driver showing their **race position on every lap**.

- **X-axis:** Lap number (1 = first lap after the start)
- **Y-axis:** Position (P1 is at the top, P20 at the bottom)
- Hover over any point to see the exact lap and position.

**What to look for:**
- A sudden jump upward (toward P1) = a position gain — likely an overtake or a pit stop by a rival
- A sudden drop = a position loss — overtaken on track, or the driver pitted while others hadn't yet
- A cluster of lines converging at the same lap = everyone pitting around the same time (often a safety car)
- Flat lines = a driver is holding position, no changes happening
""")
    fig_pos = plot_position_chart_interactive(laps, selected_drivers)
    st.plotly_chart(fig_pos, use_container_width=True)

    # --- Lap Time Distribution ---
    st.subheader("Lap Time Distribution")
    with st.expander("How to read this chart"):
        st.markdown("""\
A box/violin plot showing the **spread of clean lap times** for the top 10 drivers.

- **X-axis:** Driver
- **Y-axis:** Lap time in seconds
- The thick bar in the middle of each box is the **median** — the typical lap time for that driver
- The box itself spans the middle 50% of laps (the "interquartile range")
- The lines extending out show the full range, and dots are outliers

Pit laps, out-laps, and any lap slower than 107% of the fastest lap are removed before plotting.

**What to look for:**
- A low median = fast overall pace
- A narrow box = very consistent driver (laps were similar to each other)
- A wide box or many outliers = variable pace (could be traffic, tyre issues, or pushing in certain phases)
- Two drivers with the same median but different box widths: similar speed, but one was more consistent
""")
    if not clean_laps.empty:
        fig_dist = plot_lap_time_distribution(clean_laps, selected_drivers)
        st.plotly_chart(fig_dist, use_container_width=True)

    # --- Tyre Strategy ---
    st.subheader("Tyre Strategy")
    with st.expander("How to read this chart"):
        st.markdown("""\
A horizontal bar chart showing each driver's **tyre stints** across the race.

- Each coloured bar segment = one stint on a particular tyre compound
- Bar length = how many laps that stint lasted
- **Colours:** Red = Soft, Yellow = Medium, White/Grey = Hard, Green = Intermediate, Blue = Wet

**What to look for:**
- Drivers with more segments = more pit stops (more complex strategy)
- A very long bar on one compound = that driver committed to that tyre for many laps
- If most drivers show the same pattern, there was a dominant strategy that race
- Outliers who used a different compound sequence may have been gambling on a strategy advantage
""")
    stint_summary = get_stint_summary(laps)
    if not stint_summary.empty:
        fig_strat = plot_tyre_strategy(stint_summary, selected_drivers)
        st.plotly_chart(fig_strat, use_container_width=True)

    # --- Degradation ---
    st.subheader("Tyre Degradation")
    with st.expander("How to read this chart"):
        st.markdown("""\
A scatter plot with a regression line per driver showing how **lap times get slower as tyres age**.

- **X-axis:** Tyre life — how many laps the current tyre set has been on the car
- **Y-axis:** Lap time in seconds
- Each dot = one clean lap; the line is the mathematical best-fit trend

The table below shows:

| Column | What it means |
|---|---|
| slope | How much slower (in seconds) the driver gets per lap of tyre age |
| intercept | The predicted lap time on a fresh tyre (lap 0 of the stint) |
| r_squared | How well the line fits the data (0–1; closer to 1 = cleaner trend) |
| fuel_corrected_slope | Slope after removing ~0.06 s/lap natural improvement from fuel burning off |
| n_laps | Number of clean laps used in the calculation |

**What to look for:**
- A **slope of 0.05** means the driver loses ~0.05s every lap — after 20 laps that's 1s slower than fresh
- A **steep slope** (e.g. 0.1 or worse) = high degradation, tyres fell off quickly
- A **flat slope** near 0 = very low degradation, tyres lasted well
- **r_squared below 0.5** = the trend is noisy; treat that slope with caution
- **fuel_corrected_slope** is the more accurate number: fuel weight makes the car faster as it burns off, \
so the raw slope flatters the tyres slightly
""")
    compounds = clean_laps["compound"].unique().tolist() if not clean_laps.empty else []
    if compounds:
        selected_compound = st.selectbox("Compound", compounds)
        deg_drivers = st.multiselect(
            "Drivers for degradation",
            selected_drivers,
            default=selected_drivers[:5]
            if len(selected_drivers) >= 5
            else selected_drivers,
            key="deg_drivers",
        )
        if deg_drivers:
            fig_deg = plot_degradation_curves(
                clean_laps, deg_drivers, selected_compound
            )
            st.plotly_chart(fig_deg, use_container_width=True)

        deg_table = calculate_all_degradation(laps)
        if not deg_table.empty:
            deg_display = deg_table.round(4).copy()

            def _color_degradation(val: float) -> str:
                if pd.isna(val):
                    return ""
                intensity = min(abs(val) / 0.15, 1.0)
                return f"background-color: rgba(255, 0, 0, {0.1 + intensity * 0.4})"

            styled_deg = deg_display.style.map(
                _color_degradation, subset=["fuel_corrected_slope"]
            )
            st.dataframe(styled_deg, use_container_width=True, hide_index=True)

    # --- Stint-Adjusted Pace ---
    st.subheader("Stint-Adjusted Pace")
    with st.expander("How to read this table"):
        st.markdown("""\
A table showing the **average lap time per driver per stint**, so you can compare pace across different \
tyre stints fairly.

| Column | What it means |
|---|---|
| stint | Stint number (1 = first stint, 2 = second stint, etc.) |
| compound | Tyre compound used in that stint |
| mean_pace_sec | Average clean lap time during that stint, in seconds |
| n_laps | How many clean laps are included in the average |

**What to look for:**
- Compare drivers who ran the same compound in the same stint range — this shows who had better raw pace on that tyre
- A driver with a low mean_pace on the Hard tyre but high on the Soft had compound-specific pace differences
- Low n_laps (e.g. 2 or 3) means the average isn't very reliable — that stint was short or had many excluded laps
""")
    pace = stint_adjusted_pace(laps, selected_drivers)
    if not pace.empty:
        pace_display = pace.copy()
        pace_display["mean_pace_sec"] = (pace_display["mean_pace_ms"] / 1000.0).round(3)
        display_cols = ["driver", "stint", "compound", "mean_pace_sec", "n_laps"]
        pace_styled = pace_display[display_cols].copy()

        def _color_pace(col: pd.Series) -> list[str]:
            if col.name != "mean_pace_sec":
                return [""] * len(col)
            vmin = col.min()
            vmax = col.max()
            span = vmax - vmin if vmax != vmin else 1.0
            styles = []
            for v in col:
                if pd.isna(v):
                    styles.append("")
                else:
                    ratio = (v - vmin) / span
                    r = int(ratio * 255)
                    g = int((1 - ratio) * 180)
                    styles.append(f"background-color: rgba({r}, {g}, 0, 0.3)")
            return styles

        styled_pace = pace_styled.style.apply(_color_pace)
        st.dataframe(styled_pace, use_container_width=True, hide_index=True)

    # --- Pace Delta ---
    st.subheader("Pace Delta")
    with st.expander("How to read this chart"):
        st.markdown("""\
A line chart comparing **two selected drivers' gap** lap by lap.

- **X-axis:** Lap number
- **Y-axis:** Gap in seconds (positive = Driver 1 is ahead on cumulative race time; negative = Driver 2 is ahead)

**What to look for:**
- A line moving upward = Driver 1 is pulling away from Driver 2 lap by lap
- A line moving downward = Driver 2 is catching up
- A sudden vertical jump = one driver pitted (their lap time was very long) — the gap usually recovers over the following laps
- A flat line = both drivers lapping at the same pace, the gap holding steady
- The overall shape tells you whether on-track positions were representative of actual pace, or whether \
strategy created artificial gaps
""")
    col1, col2 = st.columns(2)
    with col1:
        d1 = st.selectbox("Driver 1", all_drivers, index=0, key="delta_d1")
    with col2:
        d2 = st.selectbox(
            "Driver 2", all_drivers, index=min(1, len(all_drivers) - 1), key="delta_d2"
        )
    if d1 != d2:
        delta = lap_by_lap_delta(laps, d1, d2)
        if not delta.empty:
            fig_delta = plot_pace_delta(delta, d1, d2)
            st.plotly_chart(fig_delta, use_container_width=True)

    # --- Sector Comparison ---
    st.subheader("Sector Comparison")
    with st.expander("How to read this chart"):
        st.markdown("""\
A grouped bar chart showing the **best sector time each driver achieved** across the whole session.

- Three bars per driver: Sector 1, Sector 2, Sector 3
- **Y-axis:** Sector time in seconds (shorter = faster)

| Metric | What it means |
|---|---|
| theoretical_best | Best S1 + best S2 + best S3 combined — the fastest possible lap |
| actual_best | The driver's actual fastest lap of the session |
| gap | theoretical_best - actual_best: time "left on the table" |

**What to look for:**
- A short bar in one sector = the driver's strength (e.g. good in S1 but slower in S2)
- Compare sector profiles: two drivers with the same total lap time may have achieved it very differently
- A large **gap** value means the driver had the pace for a faster lap but never put it all together
""")
    sector_drivers = st.multiselect(
        "Drivers for sector comparison",
        selected_drivers,
        default=selected_drivers[:5]
        if len(selected_drivers) >= 5
        else selected_drivers,
        key="sector_drivers",
    )
    if sector_drivers:
        sectors = sector_comparison(laps, sector_drivers)
        if not sectors.empty:
            fig_sector = plot_sector_comparison(sectors)
            st.plotly_chart(fig_sector, use_container_width=True)

    # --- Consistency ---
    st.subheader("Consistency Metrics")
    with st.expander("How to read this chart"):
        st.markdown("""\
A horizontal bar chart showing how **consistent each driver's race pace was**.

- **X-axis:** Coefficient of Variation (CV%) — lower is more consistent
- **Y-axis:** Driver, sorted from most consistent (top) to least consistent (bottom)

**What to look for:**
- A **low CV%** (e.g. under 0.5%) = the driver was hitting very similar lap times each lap — controlled, methodical racing
- A **high CV%** = variable lap times — could be managing tyres deliberately, responding to traffic, or inconsistent driving
- Consistency is particularly valuable in long stints: a driver who laps within 0.3s of themselves every lap \
is easier for the team to strategise around
""")
    cons = consistency_metrics(laps, selected_drivers)
    if not cons.empty:
        fig_cons = plot_consistency_bars(cons)
        st.plotly_chart(fig_cons, use_container_width=True)

    # --- Safety Car ---
    st.subheader("Safety Car / VSC")
    with st.expander("How to read this section"):
        st.markdown("""\
A list of all Safety Car and Virtual Safety Car periods during the race, followed by a table of \
**drivers who pitted during those periods**.

- **SC (Safety Car):** A physical safety car enters the track, all drivers must slow and hold position. Gap between cars freezes.
- **VSC (Virtual Safety Car):** No physical car, but all drivers must meet a minimum lap time. Similar effect.

**Why pitting under a SC/VSC matters:** A pit stop normally costs about 20-25 seconds of track time. \
Under a SC/VSC, every driver is going slowly anyway — so the pit stop "costs" much less relative to \
rivals staying out. Teams that pit under SC effectively get a free (or cheap) tyre change.

**What to look for:**
- Drivers who pitted under SC and then gained positions = benefited from the timing
- Drivers who had just pitted before the SC appeared = unlucky, they paid full cost and missed the "free" stop
- If no one pitted under SC, teams may have judged their current tyres as sufficient to finish
""")
    sc_periods = detect_safety_car_periods(laps)
    if sc_periods:
        for p in sc_periods:
            st.markdown(f"- **{p['type']}**: Laps {p['start_lap']}–{p['end_lap']}")
        beneficiaries = sc_beneficiaries(laps, sc_periods)
        pitted = beneficiaries[beneficiaries["pitted_during_sc"]]
        if not pitted.empty:
            st.markdown("**Drivers who pitted during SC/VSC:**")
            filterable_dataframe(
                pitted[["driver", "sc_type", "start_lap", "end_lap"]],
                key="sc_beneficiaries",
            )
    else:
        st.info("No safety car or VSC periods detected.")

    # --- Undercuts ---
    st.subheader("Undercut Detection")
    with st.expander("How to read this section"):
        st.markdown("""\
A list of detected **undercut manoeuvres** during the race.

An **undercut** is when a driver pits *before* a rival, gets fresh tyres, sets fast laps while the rival \
is still on worn tyres, and comes out of their own pit stop *ahead* of the rival.

Each detected undercut shows:
- **Who undercut whom** (the aggressor and the victim)
- **Which lap it happened on**
- **Position change:** e.g. P4 -> P3 confirms it worked

**What to look for:**
- A successful undercut shows aggressive pit strategy paid off
- An attempted undercut that didn't change positions = either the rival covered it quickly, or the tyre delta wasn't big enough
- Multiple undercuts in one race = active strategic battle, teams reacting to each other in real time
""")
    if not results.empty:
        undercuts = detect_undercuts(laps, results)
        successful = [u for u in undercuts if u["successful"]]
        if successful:
            for u in successful:
                st.markdown(
                    f"- **{u['undercutter']}** undercut **{u['victim']}** "
                    f"(pit lap {u['undercut_lap']}, moved P{u['position_before']} -> P{u['position_after']})"
                )
        else:
            st.info("No successful undercuts detected.")

    # --- Pit Stops ---
    st.subheader("Pit Stop Times")
    with st.expander("How to read this table"):
        st.markdown("""\
A table of each driver's **pit stop performance**.

| Column | What it means |
|---|---|
| n_stops | Total number of pit stops made |
| mean_duration_sec | Average pit lane duration (entry to exit, in seconds) |
| best_stop_sec | Fastest single pit lane duration (seconds) |
| mean_stationary_sec | Average stationary time (wheel change only, seconds) — if available |
| best_stationary_sec | Fastest stationary time (seconds) — if available |

**Pit Lane Duration vs Stationary Time:**
- **Pit Lane Duration** (~20-25s): Time from entering to exiting the pit lane, includes acceleration, deceleration, and travel
- **Stationary Time** (~2-3s): Actual time the car is stationary at the pit box (wheels being changed)

**What to look for:**
- Sub-2.5 second stops = excellent crew performance
- Large difference between best and mean = one stop was great, another went wrong
- Higher n_stops = more complex strategy; this driver spent more time in the pit lane total
- Pit stop times feed into the prediction model's "pit consistency" score
""")
    pit_stops = load_pit_stops_from_db(year, round_num, session_type=session_type)
    if not pit_stops.empty:
        pit_analysis = pit_stop_analysis(pit_stops)
        if not pit_analysis.empty:
            pit_display = pit_analysis.copy()
            pit_display["mean_duration_sec"] = (
                pit_display["mean_duration_ms"] / 1000.0
            ).round(3)
            pit_display["best_stop_sec"] = (pit_display["best_stop_ms"] / 1000.0).round(
                3
            )

            cols_to_show = ["driver", "n_stops", "mean_duration_sec", "best_stop_sec"]

            if "mean_stationary_ms" in pit_display.columns:
                pit_display["mean_stationary_sec"] = (
                    pit_display["mean_stationary_ms"] / 1000.0
                ).round(3)
                pit_display["best_stationary_sec"] = (
                    pit_display["best_stationary_ms"] / 1000.0
                ).round(3)
                cols_to_show.extend(["mean_stationary_sec", "best_stationary_sec"])

            st.dataframe(
                pit_display[cols_to_show],
                use_container_width=True,
                hide_index=True,
            )


# ---------------------------------------------------------------------------
# Qualifying / Sprint Qualifying Analysis
# ---------------------------------------------------------------------------


def _show_qualifying_analysis(
    laps: pd.DataFrame,
    clean_laps: pd.DataFrame,
    selected_drivers: list[str],
    all_drivers: list[str],
    session_type: str,
) -> None:
    prefix = "SQ" if session_type == "SQ" else "Q"

    # --- Qualifying Progression ---
    st.subheader(f"{prefix} Progression")
    with st.expander("How to read this table"):
        st.markdown(f"""\
A table showing each driver's **best lap** ranked by time, with colour coding by segment.

- **Green rows** = reached {prefix}3 (top 10)
- **Yellow rows** = eliminated in {prefix}2 (P11–P15)
- **Red rows** = eliminated in {prefix}1 (P16–P20)

The sector columns show the sectors from the driver's fastest lap, not their individual best sectors.

**What to look for:**
- Large gaps between segments show where the performance "cliff" is
- Sector times reveal where on the circuit each driver is gaining or losing
""")
    prog = qualifying_progression(laps)
    if not prog.empty:
        # Relabel segments for SQ sessions
        if prefix == "SQ":
            prog["segment"] = prog["segment"].str.replace("Q", "SQ")
            prog["eliminated_in"] = prog["eliminated_in"].apply(
                lambda x: x.replace("Q", "SQ") if isinstance(x, str) else x
            )
        fig_prog = plot_qualifying_progression(prog)
        st.plotly_chart(fig_prog, use_container_width=True)

    # --- Gap to Pole ---
    st.subheader("Gap to Pole")
    with st.expander("How to read this chart"):
        st.markdown("""\
A horizontal bar chart showing each driver's **time gap to the pole-sitter**.

- Bar length = gap in seconds (longer bar = further from pole)
- Bars are coloured by qualifying segment (green = Q3, yellow = Q2, red = Q1)

**What to look for:**
- The gap between P1 and P2 shows how dominant the pole lap was
- A cluster of drivers within 0.1s = a very tight qualifying session
- A big jump from P10 to P11 shows the Q2 elimination gap
""")
    gap = gap_to_pole(laps)
    if not gap.empty:
        # Merge segment info from progression for colouring
        if not prog.empty:
            seg_map = prog.set_index("driver")["segment"]
            gap["segment"] = gap["driver"].map(seg_map).fillna("")
        else:
            gap["segment"] = ""
        fig_gap = plot_gap_to_pole(gap)
        st.plotly_chart(fig_gap, use_container_width=True)

    # --- Lap Improvement ---
    st.subheader("Lap Improvement")
    with st.expander("How to read this chart"):
        st.markdown("""\
A line chart showing how a driver's **lap time changed across qualifying attempts**.

- **X-axis:** Attempt number (each valid timed lap in the session)
- **Y-axis:** Lap time in seconds
- The green dashed line marks the driver's best lap
- Annotations show the time gained or lost compared to the previous attempt

**What to look for:**
- Consistent negative deltas = the driver kept finding time across attempts
- A big improvement on the final attempt = the driver "put it all together" when it mattered
- A slower final attempt = the driver may have made a mistake or encountered traffic
""")
    imp_driver = st.selectbox(
        "Driver for lap improvement",
        all_drivers,
        index=0,
        key="imp_driver",
    )
    imp = lap_improvement_delta(laps, imp_driver)
    if not imp.empty:
        fig_imp = plot_lap_improvement(imp, imp_driver)
        st.plotly_chart(fig_imp, use_container_width=True)

    # --- Sector Comparison ---
    st.subheader("Sector Comparison")
    with st.expander("How to read this chart"):
        st.markdown("""\
A grouped bar chart showing the **best sector time each driver achieved** across the qualifying session.

- Three bars per driver: Sector 1, Sector 2, Sector 3
- **Y-axis:** Sector time in seconds (shorter = faster)

**What to look for:**
- A short bar in one sector = the driver's strength
- Compare sector profiles to see where different cars or drivers excel
""")
    sector_drivers = st.multiselect(
        "Drivers for sector comparison",
        selected_drivers,
        default=selected_drivers[:5]
        if len(selected_drivers) >= 5
        else selected_drivers,
        key="q_sector_drivers",
    )
    if sector_drivers:
        sectors = sector_comparison(laps, sector_drivers)
        if not sectors.empty:
            fig_sector = plot_sector_comparison(sectors)
            st.plotly_chart(fig_sector, use_container_width=True)

    # --- Speed Traps ---
    st.subheader("Speed Traps")
    with st.expander("How to read this table"):
        st.markdown("""\
A table comparing **top speeds** at key points around the circuit.

| Column | What it means |
|---|---|
| speed_i1 / speed_i2 | Speed at intermediate timing points (km/h) |
| speed_fl | Finish line speed (km/h) |
| speed_st | Speed trap — the official top speed reading (km/h) |

**What to look for:**
- High speed trap values indicate low-drag setups or strong straight-line performance
- Comparing speeds across drivers reveals who is sacrificing top speed for downforce (and vice versa)
""")
    traps = speed_trap_comparison(laps, selected_drivers)
    if not traps.empty:
        filterable_dataframe(traps, key="speed_traps")


# ---------------------------------------------------------------------------
# Practice Analysis (FP1/FP2/FP3)
# ---------------------------------------------------------------------------


def _show_practice_analysis(
    laps: pd.DataFrame,
    clean_laps: pd.DataFrame,
    selected_drivers: list[str],
    all_drivers: list[str],
) -> None:
    # --- Long Run Pace ---
    st.subheader("Long Run Pace")
    with st.expander("How to read this chart"):
        st.markdown("""\
A bar chart showing **average pace on long stints** (5+ consecutive clean laps) grouped by compound.

Long runs are the best indicator of **race pace** from practice data. Teams run long stints to assess \
tyre degradation and fuel load behaviour before deciding their race strategy.

**What to look for:**
- The fastest long-run pace on each compound suggests who has the best race pace
- A driver fast on Mediums but slow on Softs may have a tyre usage issue
- Compare the gap between compounds — a small gap means the harder tyre is strong (often favoured for race strategy)
""")
    lr = long_run_pace(laps)
    if not lr.empty:
        lr_only = lr[lr["is_long_run"]]
        if not lr_only.empty:
            fig_lr = plot_long_run_pace(lr_only, selected_drivers)
            st.plotly_chart(fig_lr, use_container_width=True)
        else:
            st.info("No long runs detected (5+ clean laps in a stint).")

        # --- Short Run / Qualifying Simulation Pace ---
        st.subheader("Short Run Pace")
        with st.expander("How to read this table"):
            st.markdown("""\
Stints shorter than 5 clean laps — typically **qualifying simulation runs** or performance checks.

Shows the average pace per driver per short stint. Single-lap runs are likely qualifying simulations; \
2-4 lap runs may be aero checks or tyre warmup sequences.

**What to look for:**
- The fastest short-run time on Softs is a rough qualifying pace indicator
- Compare short-run pace to long-run pace to see qualifying vs race performance trade-offs
""")
        sr = lr[~lr["is_long_run"]]
        if not sr.empty:
            sr_display = sr.copy()
            sr_display["mean_pace_sec"] = (sr_display["mean_pace_ms"] / 1000.0).round(3)
            filterable_dataframe(
                sr_display[["driver", "stint", "compound", "mean_pace_sec", "n_laps"]],
                key="practice_short_runs",
            )
    else:
        st.info("No stint data available.")

    # --- Lap Time Distribution ---
    st.subheader("Lap Time Distribution")
    with st.expander("How to read this chart"):
        st.markdown("""\
A box plot showing the **spread of clean lap times** per driver in this practice session.

**What to look for:**
- A low median = fast overall pace
- A wide box = the driver ran a variety of programmes (different fuel loads, tyre types)
- Outliers may be installation laps, slow out-laps that weren't fully filtered, or lock-up laps
""")
    if not clean_laps.empty:
        fig_dist = plot_lap_time_distribution(clean_laps, selected_drivers)
        st.plotly_chart(fig_dist, use_container_width=True)

    # --- Tyre Strategy ---
    st.subheader("Compound Usage")
    with st.expander("How to read this chart"):
        st.markdown("""\
A horizontal bar chart showing which **tyre compounds each driver used** during the session.

**What to look for:**
- Which compounds each team explored — this hints at their race strategy thinking
- A driver who only ran Softs may be focused on qualifying pace, not race prep
- Long stints on Mediums or Hards suggest race simulation runs
""")
    stint_summary = get_stint_summary(laps)
    if not stint_summary.empty:
        fig_strat = plot_tyre_strategy(stint_summary, selected_drivers)
        st.plotly_chart(fig_strat, use_container_width=True)

    # --- Sector Comparison ---
    st.subheader("Sector Comparison")
    with st.expander("How to read this chart"):
        st.markdown("""\
A grouped bar chart showing the **best sector time each driver achieved** during practice.

**What to look for:**
- Sector strengths hint at car characteristics (e.g. strong S1 = good traction out of slow corners)
- Compare across practice sessions to track setup evolution through the weekend
""")
    sector_drivers = st.multiselect(
        "Drivers for sector comparison",
        selected_drivers,
        default=selected_drivers[:5]
        if len(selected_drivers) >= 5
        else selected_drivers,
        key="fp_sector_drivers",
    )
    if sector_drivers:
        sectors = sector_comparison(laps, sector_drivers)
        if not sectors.empty:
            fig_sector = plot_sector_comparison(sectors)
            st.plotly_chart(fig_sector, use_container_width=True)


# ===========================================================================
# Page entry point
# ===========================================================================

st.set_page_config(page_title="Session Analysis", layout="wide")
st.title("Session Analysis")

# Get selection from session state
year = st.session_state.get("year")
round_num = st.session_state.get("round")
session_type = st.session_state.get("session_type", "R")
event_name = st.session_state.get("event_name", "")

if not year or not round_num:
    st.warning("Select a race from the sidebar on the home page.")
    st.stop()

st.header(f"{event_name} {year} — {session_type}")

# Load data with spinner
with st.spinner("Loading race data..."):
    laps = load_laps_from_db(year, round_num, session_type)

if laps.empty:
    st.warning(
        f"No lap data found for {event_name} {year} ({session_type}). Run the ETL first."
    )
    st.stop()

all_drivers = laps["driver"].unique().tolist()
clean_laps = filter_clean_laps(laps)

# Driver filter
selected_drivers = st.multiselect(
    "Select drivers",
    all_drivers,
    default=all_drivers,
    key="driver_filter",
)

if not selected_drivers:
    st.warning("Select at least one driver.")
    st.stop()

# Branch by session type
if session_type in _RACE_SESSIONS:
    _show_race_analysis(
        laps, clean_laps, selected_drivers, all_drivers, year, round_num, session_type
    )
elif session_type in _QUALIFYING_SESSIONS:
    _show_qualifying_analysis(
        laps, clean_laps, selected_drivers, all_drivers, session_type
    )
elif session_type in _PRACTICE_SESSIONS:
    _show_practice_analysis(laps, clean_laps, selected_drivers, all_drivers)
else:
    st.warning(f"Unknown session type: {session_type}")
