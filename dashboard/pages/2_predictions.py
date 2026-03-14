"""Predictions page — next-race predictions, Elo ratings, circuit info."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import streamlit as st

from dashboard.components.charts import filterable_dataframe, plot_prediction_table
from src.circuit import get_cluster, normalize_circuit_id
from src.loader import get_event_schedule, load_races_from_db, load_results_from_db
from src.prediction import compute_elo_ratings, predict_race

st.set_page_config(page_title="Predictions", layout="wide")
st.title("Next Race Prediction")

year = st.session_state.get("year")
if not year:
    st.warning("Select a season from the sidebar on the home page.")
    st.stop()

# ---------------------------------------------------------------------------
# Determine next race
# ---------------------------------------------------------------------------

races_in_db = load_races_from_db(year)
if races_in_db.empty:
    st.warning("No race data in DB for this season. Run the ETL first.")
    st.stop()

last_round = int(races_in_db["round"].max())
next_round = last_round + 1

# Try to get next race info from schedule
try:
    schedule = get_event_schedule(year)
    next_events = schedule[schedule["RoundNumber"] == next_round]
    if not next_events.empty:
        next_event_name = next_events.iloc[0]["EventName"]
        next_circuit_id = normalize_circuit_id(next_event_name)
    else:
        st.info(
            "No more races in the schedule. Showing prediction for last loaded race."
        )
        next_round = last_round
        last_event = races_in_db[races_in_db["round"] == last_round].iloc[0]
        next_event_name = last_event["event_name"]
        next_circuit_id = last_event["circuit_id"]
except Exception:
    last_event = races_in_db[races_in_db["round"] == last_round].iloc[0]
    next_event_name = last_event["event_name"]
    next_circuit_id = last_event["circuit_id"]

st.header(f"Prediction for R{next_round}: {next_event_name}")

# Circuit info
with st.spinner("Loading circuit info..."):
    cluster = get_cluster(next_circuit_id)
    if cluster:
        st.markdown(f"**Circuit cluster:** {cluster.value.replace('_', ' ').title()}")
    st.markdown(f"**Circuit ID:** {next_circuit_id}")

# ---------------------------------------------------------------------------
# Predictions
# ---------------------------------------------------------------------------

with st.spinner("Computing predictions..."):
    predictions = predict_race(year, next_round, next_circuit_id)

races_available = (
    predictions.attrs.get("races_available", 0) if not predictions.empty else 0
)

if next_round == 1 or races_available == 0:
    st.info(
        f"This is the first race of the {year} season. Predictions will be available after Round 3."
    )
elif races_available < 3:
    st.warning(
        f"Only {races_available} race(s) completed. Predictions are unreliable with fewer than 3 races of data."
    )

if not predictions.empty:
    st.subheader("Predicted Finishing Order")
    with st.expander("How to read this table"):
        st.markdown("""\
A table ranking drivers by their **composite prediction score** for the next race.

| Column | What it means | Weight |
|---|---|---|
| score | Overall prediction score (0–1; higher = predicted to finish higher) | — |
| recent_form | Normalised score based on average finish over last 5 races | 40% |
| circuit_history | Normalised score based on average finish at this specific circuit (last 3 visits) | 25% |
| cluster_form | Normalised score based on average finish at circuits in the same cluster this season | 15% |
| pit_consistency | How consistent the driver's pit stops have been (lower std dev = higher score) | 10% |
| quali_conversion | How many positions the driver typically gains or loses from grid to finish | 10% |

**Interpreting scores:** All component scores are normalised to 0–1 within the current driver pool, so \
a score of 0.9 means this driver is near the top of the field on that metric.

**Known limits:** The model does not account for mid-season car upgrades, driver team changes, or regulation \
resets. Early in the season (fewer than 3 races), scores are unreliable due to limited data. Street circuits \
tend to produce more unexpected results than the model predicts.
""")
    fig_table = plot_prediction_table(predictions)
    st.plotly_chart(fig_table, use_container_width=True)

    st.subheader("Rankings")
    for _, row in predictions.iterrows():
        st.markdown(
            f"**{int(row['rank'])}. {row['driver']}** — "
            f"Score: {row['score']:.3f} "
            f"(Form: {row['recent_form']:.2f}, Circuit: {row['circuit_history']:.2f}, "
            f"Cluster: {row['cluster_form']:.2f})"
        )

# ---------------------------------------------------------------------------
# Elo Ratings
# ---------------------------------------------------------------------------

with st.spinner("Computing Elo ratings..."):
    st.subheader("Elo Ratings")
with st.expander("How to read this table"):
    st.markdown("""\
Each driver's **Elo rating** — a number representing their competitive strength relative to the field.

**How Elo works:**
- Everyone starts at a baseline of **1500**
- After each race, drivers gain or lose points based on how many head-to-head matchups they won \
(finishing ahead of) versus lost (finishing behind)
- Beating a high-rated driver earns more points than beating a low-rated one
- The **K-factor of 32** controls how quickly ratings can shift per race

**What to look for:**
- Ratings above 1550 = consistently beating their peers
- Ratings below 1450 = underperforming relative to the field
- Large jumps in rating between races = a standout performance or a run of bad results
- The Elo rating is a rolling, self-correcting measure — it smooths out one-off anomalies over time
""")
    results = load_results_from_db()
    elo = compute_elo_ratings(results)

    if elo:
        elo_sorted = sorted(elo.items(), key=lambda x: x[1], reverse=True)
        elo_data = pd.DataFrame(
            [{"Driver": d, "Elo": round(r, 1)} for d, r in elo_sorted]
        )
        filterable_dataframe(elo_data, key="elo_ratings")
