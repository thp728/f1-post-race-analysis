"""F1 Post-Race Analysis Dashboard — Entry Point."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

from src.loader import init_cache, init_db, load_available_sessions_from_db, load_available_years_from_db, load_races_from_db

st.set_page_config(
    page_title="F1 Post-Race Analysis",
    page_icon="🏎️",
    layout="wide",
)

init_cache()
init_db()

# ---------------------------------------------------------------------------
# Home Page
# ---------------------------------------------------------------------------

st.title("F1 Post-Race Analysis")
st.markdown("---")

available_years = load_available_years_from_db()

if not available_years:
    st.info(
        "No data loaded yet. Go to **Load Data** to fetch a race weekend from FastF1."
    )
else:
    _, col, _ = st.columns([1, 2, 1])

    with col:
        st.subheader("Select a race")

        year = st.selectbox("Season", available_years)

        races_in_db = load_races_from_db(year)
        if not races_in_db.empty:
            event_options = races_in_db["event_name"].tolist()
            round_map = dict(zip(races_in_db["event_name"], races_in_db["round"]))
            event_name = st.selectbox("Grand Prix", event_options)
            selected_round = round_map.get(event_name, 1)
        else:
            st.warning("No races found for this season.")
            event_name = None
            selected_round = None

        available_sessions = (
            load_available_sessions_from_db(year, selected_round)
            if selected_round is not None
            else []
        )
        if available_sessions:
            session_type = st.selectbox("Session", available_sessions)
        else:
            if selected_round is not None:
                st.warning("No sessions found for this race.")
            session_type = None

        if event_name and session_type:
            st.session_state["year"] = year
            st.session_state["round"] = selected_round
            st.session_state["event_name"] = event_name
            st.session_state["session_type"] = session_type

            st.success(f"Viewing **{event_name} {year} — {session_type}**. Navigate to an analysis page.")
