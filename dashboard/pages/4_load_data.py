"""Load race weekend data into the database from the dashboard."""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st

from src.loader import find_latest_race, init_cache, init_db, store_weekend

st.title("Load Data")
st.markdown("Fetch race weekend data from FastF1 and store it in the local database.")

# ---------------------------------------------------------------------------
# Round selection
# ---------------------------------------------------------------------------

col1, col2 = st.columns([1, 1])

with col1:
    year = st.number_input(
        "Season",
        min_value=2018,
        max_value=datetime.now().year,
        value=datetime.now().year,
        step=1,
    )

with col2:
    round_num = st.number_input(
        "Round",
        min_value=1,
        max_value=30,
        step=1,
        value=st.session_state.get("etl_detected_round", 1),
    )

if st.button("Auto-detect latest completed round"):
    with st.spinner("Fetching schedule..."):
        try:
            init_cache()
            st.session_state["etl_detected_round"] = find_latest_race(int(year))
            st.rerun()
        except Exception as e:
            st.error(f"Could not detect latest round: {e}")

# ---------------------------------------------------------------------------
# Session selection
# ---------------------------------------------------------------------------

ALL_SESSIONS = ["FP1", "FP2", "FP3", "SQ", "S", "Q", "R"]

selected_sessions = st.multiselect(
    "Sessions",
    ALL_SESSIONS,
    default=ALL_SESSIONS,
    help="Select which sessions to load. Defaults to the full weekend.",
)

# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

st.divider()

if st.button("Load Data", type="primary", disabled=not selected_sessions):
    init_db()
    label = ", ".join(selected_sessions)
    with st.status(f"Loading {year} Round {int(round_num)} ({label})...", expanded=True) as status:
        try:
            store_weekend(
                int(year),
                int(round_num),
                session_types=selected_sessions,
                on_progress=st.write,
            )
            status.update(label="Done! Reload any analysis page to see the new data.", state="complete")
        except Exception as e:
            status.update(label=f"Failed: {e}", state="error")
            st.error(str(e))
