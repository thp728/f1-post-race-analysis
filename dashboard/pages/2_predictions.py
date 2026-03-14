"""Predictions page — next-race predictions, Elo ratings, circuit info."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st

from dashboard.components.charts import plot_prediction_table
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
        st.info("No more races in the schedule. Showing prediction for last loaded race.")
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
cluster = get_cluster(next_circuit_id)
if cluster:
    st.markdown(f"**Circuit cluster:** {cluster.value.replace('_', ' ').title()}")
st.markdown(f"**Circuit ID:** {next_circuit_id}")

# ---------------------------------------------------------------------------
# Predictions
# ---------------------------------------------------------------------------

predictions = predict_race(year, next_round, next_circuit_id)

if predictions.empty:
    st.warning("Insufficient data to generate predictions.")
    st.stop()

st.subheader("Predicted Finishing Order")
fig_table = plot_prediction_table(predictions)
st.plotly_chart(fig_table, use_container_width=True)

# Simple ranked list
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

st.subheader("Elo Ratings")
results = load_results_from_db()
elo = compute_elo_ratings(results)

if elo:
    elo_sorted = sorted(elo.items(), key=lambda x: x[1], reverse=True)
    elo_data = [{"Driver": d, "Elo": round(r, 1)} for d, r in elo_sorted]
    st.dataframe(elo_data, use_container_width=True, hide_index=True)
