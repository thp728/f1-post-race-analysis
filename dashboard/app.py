"""F1 Post-Race Analysis Dashboard — Entry Point."""

import sys
from pathlib import Path

# Add project root to path for src imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

from src.loader import get_event_schedule, init_cache, load_available_sessions_from_db, load_available_years_from_db, load_races_from_db

st.set_page_config(
    page_title="F1 Post-Race Analysis",
    page_icon="🏎️",
    layout="wide",
)

init_cache()

# ---------------------------------------------------------------------------
# Sidebar — Race Selection
# ---------------------------------------------------------------------------

st.sidebar.title("F1 Post-Race Analysis")

available_years = load_available_years_from_db() or [2026]
year = st.sidebar.selectbox("Season", available_years)

# Try to get races from DB first, fall back to FastF1 schedule
races_in_db = load_races_from_db(year)
if not races_in_db.empty:
    event_options = races_in_db["event_name"].tolist()
    round_map = dict(zip(races_in_db["event_name"], races_in_db["round"]))
else:
    try:
        schedule = get_event_schedule(year)
        event_options = schedule["EventName"].tolist()
        round_map = dict(zip(schedule["EventName"], schedule["RoundNumber"]))
    except Exception:
        event_options = []
        round_map = {}

if event_options:
    event_name = st.sidebar.selectbox("Grand Prix", event_options)
    selected_round = round_map.get(event_name, 1)
    st.session_state["year"] = year
    st.session_state["round"] = selected_round
    st.session_state["event_name"] = event_name
else:
    st.sidebar.warning("No races found. Run the ETL script to load data.")
    selected_round = None
    event_name = None

available_sessions = (
    load_available_sessions_from_db(year, selected_round)
    if selected_round is not None
    else ["R", "Q", "FP3", "FP2", "FP1"]
)
session_type = st.sidebar.selectbox("Session", available_sessions)
st.session_state["session_type"] = session_type

# ---------------------------------------------------------------------------
# Home Page
# ---------------------------------------------------------------------------

st.title("F1 Post-Race Analysis")

if event_name:
    st.header(f"{event_name} {year}")
    st.markdown(
        "Use the sidebar to select a race, then navigate to the analysis pages."
    )
else:
    st.info(
        "Welcome! To get started:\n\n"
        "1. Run `uv run python scripts/post_race_etl.py --year 2024 --round 1` "
        "to load race data\n"
        "2. Select a season and Grand Prix from the sidebar\n"
        "3. Navigate to Race Analysis, Predictions, or Season Trends"
    )

st.sidebar.markdown("---")
st.sidebar.markdown(
    "**Pages:**\n"
    "- Race Analysis\n"
    "- Predictions\n"
    "- Season Trends"
)
