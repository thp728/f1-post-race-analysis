"""Season Trends page — championship progressions, rolling form, Elo trends."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import matplotlib.pyplot as plt
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.loader import load_pit_stops_from_db, load_races_from_db, load_results_from_db
from src.prediction import compute_rolling_form

st.set_page_config(page_title="Season Trends", layout="wide")
st.title("Season Trends")

year = st.session_state.get("year")
if not year:
    st.warning("Select a season from the sidebar on the home page.")
    st.stop()

results = load_results_from_db(year)
races = load_races_from_db(year)

if results.empty:
    st.warning("No results data for this season. Run the ETL first.")
    st.stop()

st.header(f"{year} Season")

# ---------------------------------------------------------------------------
# Championship Standings Progression
# ---------------------------------------------------------------------------

st.subheader("Championship Points Progression")

# Cumulative points per driver across rounds
drivers = results["driver"].unique()
rounds = sorted(results["round"].unique())

fig_points = go.Figure()
for driver in drivers:
    drv = results[results["driver"] == driver].sort_values("round")
    drv["cumulative_points"] = drv["points"].cumsum()
    fig_points.add_trace(go.Scatter(
        x=drv["round"],
        y=drv["cumulative_points"],
        mode="lines+markers",
        name=driver,
        line=dict(width=2),
    ))

fig_points.update_layout(
    xaxis_title="Round",
    yaxis_title="Cumulative Points",
    hovermode="x unified",
)
st.plotly_chart(fig_points, use_container_width=True)

# ---------------------------------------------------------------------------
# Constructor Standings
# ---------------------------------------------------------------------------

st.subheader("Constructor Points Progression")

# Sum points per team per round
team_results = results.groupby(["round", "team"])["points"].sum().reset_index()
teams = team_results["team"].unique()

fig_constructors = go.Figure()
for team in teams:
    t = team_results[team_results["team"] == team].sort_values("round")
    t["cumulative_points"] = t["points"].cumsum()
    fig_constructors.add_trace(go.Scatter(
        x=t["round"],
        y=t["cumulative_points"],
        mode="lines+markers",
        name=team,
        line=dict(width=2),
    ))

fig_constructors.update_layout(
    xaxis_title="Round",
    yaxis_title="Cumulative Points",
    hovermode="x unified",
)
st.plotly_chart(fig_constructors, use_container_width=True)

# ---------------------------------------------------------------------------
# Rolling Form
# ---------------------------------------------------------------------------

st.subheader("Rolling Average Finish Position (Last 5 Races)")

all_results = load_results_from_db()
fig_form = go.Figure()

top_drivers = (
    results.groupby("driver")["points"].sum()
    .sort_values(ascending=False)
    .head(10)
    .index.tolist()
)

for driver in top_drivers:
    form_by_round = []
    for r in rounds:
        form = compute_rolling_form(all_results, driver, r + 1, year, n_races=5)
        if form is not None:
            form_by_round.append({"round": r, "rolling_avg": form})

    if form_by_round:
        form_df = pd.DataFrame(form_by_round)
        fig_form.add_trace(go.Scatter(
            x=form_df["round"],
            y=form_df["rolling_avg"],
            mode="lines+markers",
            name=driver,
            line=dict(width=2),
        ))

fig_form.update_layout(
    xaxis_title="Round",
    yaxis_title="Avg Finish Position (last 5)",
    yaxis=dict(autorange="reversed"),
    hovermode="x unified",
)
st.plotly_chart(fig_form, use_container_width=True)

# ---------------------------------------------------------------------------
# Finishing Position Heatmap
# ---------------------------------------------------------------------------

st.subheader("Finishing Positions by Round")

pivot = results.pivot_table(
    index="driver", columns="round", values="finish_position", aggfunc="first"
)
if not pivot.empty:
    # Sort by total points
    driver_points = results.groupby("driver")["points"].sum().sort_values(ascending=False)
    pivot = pivot.reindex(driver_points.index)

    fig_heat, ax = plt.subplots(figsize=(max(8, len(rounds) * 0.8), max(6, len(drivers) * 0.3)))
    import seaborn as sns
    sns.heatmap(
        pivot,
        annot=True,
        fmt=".0f",
        cmap="RdYlGn_r",
        linewidths=0.5,
        ax=ax,
        vmin=1,
        vmax=20,
    )
    ax.set_xlabel("Round")
    ax.set_ylabel("Driver")
    ax.set_title("Finishing Positions")
    plt.tight_layout()
    st.pyplot(fig_heat)
