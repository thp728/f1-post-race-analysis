"""Season Trends page — championship progressions, rolling form, Elo trends."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.loader import load_races_from_db, load_results_from_db
from src.prediction import compute_rolling_form

st.set_page_config(page_title="Season Trends", layout="wide")
st.title("Season Trends")

year = st.session_state.get("year")
if not year:
    st.warning("Select a season from the sidebar on the home page.")
    st.stop()

with st.spinner("Loading season data..."):
    results = load_results_from_db(year)
    races = load_races_from_db(year)

if results.empty:
    st.warning("No results data for this season. Run the ETL first.")
    st.stop()

st.header(f"{year} Season")

# ---------------------------------------------------------------------------
# Championship Standings Progression
# ---------------------------------------------------------------------------

with st.spinner("Generating championship progression chart..."):
    st.subheader("Championship Points Progression")
with st.expander("How to read this chart"):
    st.markdown("""\
A line chart showing **cumulative championship points** for each driver across the season.

- **X-axis:** Round number (1 = first race, 2 = second, etc.)
- **Y-axis:** Total points accumulated so far
- Each line = one driver

**What to look for:**
- A steep upward slope = consistently scoring big points
- A flat section = a run of retirements or poor results
- Crossing lines = a driver overtaking another in the championship
- The gap between the top two lines at the rightmost point is the current championship margin
""")

# Cumulative points per driver across rounds
drivers = results["driver"].unique().tolist()
rounds = sorted(results["round"].unique())

fig_points = go.Figure()
for driver in drivers:
    drv = results[results["driver"] == driver].sort_values("round")
    drv["cumulative_points"] = drv["points"].cumsum()
    fig_points.add_trace(
        go.Scatter(
            x=drv["round"],
            y=drv["cumulative_points"],
            mode="lines+markers",
            name=driver,
            line=dict(width=2),
        )
    )

fig_points.update_layout(
    xaxis_title="Round",
    yaxis_title="Cumulative Points",
    hovermode="x unified",
)
st.plotly_chart(fig_points, use_container_width=True)

# ---------------------------------------------------------------------------
# Constructor Standings
# ---------------------------------------------------------------------------

with st.spinner("Generating constructor standings chart..."):
    st.subheader("Constructor Points Progression")
with st.expander("How to read this chart"):
    st.markdown("""\
Same as above, but each line represents a **team** (both drivers' points combined per round).

**What to look for:**
- The constructor championship is often decided by reliability as much as pace — a team that scores points \
from both drivers every race will pull away from a team relying on one star driver
- A sudden plateau for a team often means one driver had a run of DNFs
""")

# Sum points per team per round
team_results = results.groupby(["round", "team"])["points"].sum().reset_index()
teams = team_results["team"].unique()

fig_constructors = go.Figure()
for team in teams:
    t = team_results[team_results["team"] == team].sort_values("round")
    t["cumulative_points"] = t["points"].cumsum()
    fig_constructors.add_trace(
        go.Scatter(
            x=t["round"],
            y=t["cumulative_points"],
            mode="lines+markers",
            name=team,
            line=dict(width=2),
        )
    )

fig_constructors.update_layout(
    xaxis_title="Round",
    yaxis_title="Cumulative Points",
    hovermode="x unified",
)
st.plotly_chart(fig_constructors, use_container_width=True)

# ---------------------------------------------------------------------------
# Rolling Form
# ---------------------------------------------------------------------------

with st.spinner("Computing rolling form..."):
    st.subheader("Rolling Average Finish Position (Last 5 Races)")
with st.expander("How to read this chart"):
    st.markdown("""\
A line chart showing each driver's **5-race rolling average finishing position**.

- **X-axis:** Round number
- **Y-axis:** Average finish position over the previous 5 races (lower number = better finish)
- Only the top 10 championship contenders are shown by default

**What to look for:**
- A line trending downward = the driver is on a run of improving results
- A line trending upward = recent form is deteriorating
- Sharp changes = a single dominant win or DNF skewing the short-term average
- This is the metric most predictive of near-term performance in the model (40% weight in the prediction score)
""")

all_results = load_results_from_db()

# Driver filter for rolling form — default to top 10 by points
top_drivers_by_points = (
    results.groupby("driver")["points"]
    .sum()
    .sort_values(ascending=False)
    .index.tolist()
)

rolling_drivers = st.multiselect(
    "Select drivers",
    top_drivers_by_points,
    default=top_drivers_by_points[:10]
    if len(top_drivers_by_points) > 10
    else top_drivers_by_points,
    key="rolling_form_drivers",
)

fig_form = go.Figure()

for driver in rolling_drivers:
    form_by_round = []
    for r in rounds:
        form = compute_rolling_form(all_results, driver, r + 1, year, n_races=5)
        if form is not None:
            form_by_round.append({"round": r, "rolling_avg": form})

    if form_by_round:
        form_df = pd.DataFrame(form_by_round)
        fig_form.add_trace(
            go.Scatter(
                x=form_df["round"],
                y=form_df["rolling_avg"],
                mode="lines+markers",
                name=driver,
                line=dict(width=2),
            )
        )

fig_form.update_layout(
    xaxis_title="Round",
    yaxis_title="Avg Finish Position (last 5)",
    yaxis=dict(autorange="reversed"),
    hovermode="x unified",
)
st.plotly_chart(fig_form, use_container_width=True)

# ---------------------------------------------------------------------------
# Finishing Position Heatmap (Plotly)
# ---------------------------------------------------------------------------

with st.spinner("Generating finishing positions heatmap..."):
    st.subheader("Finishing Positions by Round")
    with st.expander("How to read this chart"):
        st.markdown("""\
A grid showing every driver's **finishing position at every round** of the season.

- **Rows:** Drivers (sorted by total season points, highest at top)
- **Columns:** Round number
- **Cell colour:** Green = good result (P1 = darkest green), Red = bad result (P20 = darkest red)
- **Number inside each cell:** The actual finishing position

**What to look for:**
- Mostly green rows = consistently fast drivers
- Mostly red rows = struggling all season
- A single red cell in a green row = a one-off bad race (reliability failure or incident)
- Columns with many red cells = chaotic race (rain, first-lap incidents, safety cars)
- Consistency across a driver's row tells you more than any single result
""")

    pivot = results.pivot_table(
        index="driver", columns="round", values="finish_position", aggfunc="first"
    )
    if not pivot.empty:
        # Sort by total points
        driver_points = (
            results.groupby("driver")["points"].sum().sort_values(ascending=False)
        )
        pivot = pivot.reindex(driver_points.index)

        fig_heat = go.Figure(
            data=go.Heatmap(
                z=pivot.values,
                x=[f"R{int(c)}" for c in pivot.columns],
                y=pivot.index.tolist(),
                text=pivot.values,
                texttemplate="%{text:.0f}",
                colorscale="RdYlGn_r",
                zmin=1,
                zmax=20,
                hovertemplate=(
                    "<b>%{y}</b><br>Round: %{x}<br>Position: P%{z:.0f}<extra></extra>"
                ),
            )
        )

        fig_heat.update_layout(
            title="Finishing Positions",
            xaxis_title="Round",
            yaxis_title="Driver",
            yaxis=dict(autorange="reversed"),
        )
        st.plotly_chart(fig_heat, use_container_width=True)
