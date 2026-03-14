"""FastF1 session loading, caching, and SQLite storage."""

import os
import sqlite3
from pathlib import Path
from typing import Optional, Union

import fastf1
import pandas as pd

# Paths relative to project root
PROJECT_ROOT = Path(__file__).parent.parent
CACHE_DIR = str(PROJECT_ROOT / "data" / "f1_cache")
DB_PATH = str(PROJECT_ROOT / "data" / "f1.db")

# Constants
FUEL_CORRECTION = 0.06  # seconds per lap improvement from fuel burn


# ---------------------------------------------------------------------------
# Cache & Session Loading
# ---------------------------------------------------------------------------

def init_cache() -> None:
    """Enable FastF1 cache. Call before any session load."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    fastf1.Cache.enable_cache(CACHE_DIR)


def get_session(
    year: int,
    event: Union[str, int],
    session_type: str = "R",
) -> fastf1.core.Session:
    """Load and return a FastF1 session without telemetry."""
    init_cache()
    session = fastf1.get_session(year, event, session_type)
    session.load(telemetry=False)
    return session


def get_session_with_telemetry(
    year: int,
    event: Union[str, int],
    session_type: str = "R",
) -> fastf1.core.Session:
    """Load and return a FastF1 session with telemetry (slower)."""
    init_cache()
    session = fastf1.get_session(year, event, session_type)
    session.load(telemetry=True)
    return session


def get_event_schedule(year: int) -> pd.DataFrame:
    """Return the event schedule for a given year."""
    init_cache()
    return fastf1.get_event_schedule(year)


# ---------------------------------------------------------------------------
# Timedelta Helpers
# ---------------------------------------------------------------------------

def _timedelta_to_ms(td: Optional[pd.Timedelta]) -> Optional[int]:
    """Convert pandas Timedelta to integer milliseconds, or None."""
    if pd.isna(td):
        return None
    return int(td.total_seconds() * 1000)


# ---------------------------------------------------------------------------
# Database Setup
# ---------------------------------------------------------------------------

def get_db_connection() -> sqlite3.Connection:
    """Return a connection to the SQLite database."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    """Create all SQLite tables if they don't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS races (
            year INTEGER,
            round INTEGER,
            event_name TEXT,
            circuit_name TEXT,
            circuit_id TEXT,
            date TEXT,
            PRIMARY KEY (year, round)
        );

        CREATE TABLE IF NOT EXISTS laps (
            year INTEGER,
            round INTEGER,
            session_type TEXT,
            driver TEXT,
            lap_number INTEGER,
            lap_time_ms INTEGER,
            sector1_ms INTEGER,
            sector2_ms INTEGER,
            sector3_ms INTEGER,
            compound TEXT,
            tyre_life INTEGER,
            stint INTEGER,
            position INTEGER,
            is_accurate INTEGER,
            is_pit_in INTEGER,
            is_pit_out INTEGER,
            speed_i1 REAL,
            speed_i2 REAL,
            speed_fl REAL,
            speed_st REAL,
            track_status TEXT,
            PRIMARY KEY (year, round, session_type, driver, lap_number)
        );

        CREATE TABLE IF NOT EXISTS stints (
            year INTEGER,
            round INTEGER,
            session_type TEXT,
            driver TEXT,
            stint_number INTEGER,
            compound TEXT,
            start_lap INTEGER,
            end_lap INTEGER,
            tyre_life_start INTEGER,
            fresh_tyre INTEGER,
            PRIMARY KEY (year, round, session_type, driver, stint_number)
        );

        CREATE TABLE IF NOT EXISTS results (
            year INTEGER,
            round INTEGER,
            driver TEXT,
            driver_number INTEGER,
            team TEXT,
            grid_position INTEGER,
            finish_position INTEGER,
            status TEXT,
            points REAL,
            fastest_lap_time_ms INTEGER,
            PRIMARY KEY (year, round, driver)
        );

        CREATE TABLE IF NOT EXISTS weather (
            year INTEGER,
            round INTEGER,
            session_type TEXT,
            timestamp TEXT,
            air_temp REAL,
            track_temp REAL,
            humidity REAL,
            pressure REAL,
            rainfall INTEGER,
            wind_speed REAL,
            wind_direction INTEGER
        );

        CREATE TABLE IF NOT EXISTS pit_stops (
            year INTEGER,
            round INTEGER,
            driver TEXT,
            stop_number INTEGER,
            lap INTEGER,
            duration_ms INTEGER,
            PRIMARY KEY (year, round, driver, stop_number)
        );

        CREATE TABLE IF NOT EXISTS driver_standings (
            year INTEGER,
            round INTEGER,
            driver TEXT,
            points REAL,
            position INTEGER,
            wins INTEGER,
            PRIMARY KEY (year, round, driver)
        );

        CREATE TABLE IF NOT EXISTS constructor_standings (
            year INTEGER,
            round INTEGER,
            constructor TEXT,
            points REAL,
            position INTEGER,
            wins INTEGER,
            PRIMARY KEY (year, round, constructor)
        );
    """)

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Store Functions
# ---------------------------------------------------------------------------

def _session_already_loaded(
    year: int,
    round_num: int,
    table: str,
    session_type: Optional[str] = None,
) -> bool:
    """Check if data for this race/session is already in the DB."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if session_type and table not in ("races", "results", "pit_stops"):
        cursor.execute(
            f"SELECT COUNT(*) FROM {table} WHERE year = ? AND round = ? AND session_type = ?",
            (year, round_num, session_type),
        )
    else:
        cursor.execute(
            f"SELECT COUNT(*) FROM {table} WHERE year = ? AND round = ?",
            (year, round_num),
        )
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0


def store_race_info(
    session: fastf1.core.Session,
    year: int,
    round_num: int,
) -> None:
    """Store race metadata in the races table."""
    if _session_already_loaded(year, round_num, "races"):
        return

    event = session.event
    conn = get_db_connection()
    conn.execute(
        "INSERT OR IGNORE INTO races (year, round, event_name, circuit_name, circuit_id, date) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            year,
            round_num,
            event["EventName"],
            event.get("Location", ""),
            event.get("Location", "").lower().replace(" ", "_"),
            str(event.get("EventDate", "")),
        ),
    )
    conn.commit()
    conn.close()


def store_race_results(
    session: fastf1.core.Session,
    year: int,
    round_num: int,
) -> None:
    """Extract results from a loaded session and insert into SQLite."""
    if _session_already_loaded(year, round_num, "results"):
        return

    results = session.results
    if results is None or results.empty:
        return

    rows = []
    for _, r in results.iterrows():
        rows.append((
            year,
            round_num,
            r.get("Abbreviation", ""),
            int(r.get("DriverNumber", 0)) if pd.notna(r.get("DriverNumber")) else None,
            r.get("TeamName", ""),
            int(r["GridPosition"]) if pd.notna(r.get("GridPosition")) else None,
            int(r["Position"]) if pd.notna(r.get("Position")) else None,
            r.get("Status", ""),
            float(r["Points"]) if pd.notna(r.get("Points")) else 0.0,
            _timedelta_to_ms(r.get("FastestLapTime")),
        ))

    conn = get_db_connection()
    conn.executemany(
        "INSERT OR IGNORE INTO results "
        "(year, round, driver, driver_number, team, grid_position, "
        "finish_position, status, points, fastest_lap_time_ms) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()


def store_laps(
    session: fastf1.core.Session,
    year: int,
    round_num: int,
    session_type: str,
) -> None:
    """Extract lap data and store in SQLite."""
    if _session_already_loaded(year, round_num, "laps", session_type):
        return

    laps = session.laps
    if laps is None or laps.empty:
        return

    rows = []
    for _, lap in laps.iterrows():
        rows.append((
            year,
            round_num,
            session_type,
            lap.get("Driver", ""),
            int(lap["LapNumber"]) if pd.notna(lap.get("LapNumber")) else None,
            _timedelta_to_ms(lap.get("LapTime")),
            _timedelta_to_ms(lap.get("Sector1Time")),
            _timedelta_to_ms(lap.get("Sector2Time")),
            _timedelta_to_ms(lap.get("Sector3Time")),
            lap.get("Compound", ""),
            int(lap["TyreLife"]) if pd.notna(lap.get("TyreLife")) else None,
            int(lap["Stint"]) if pd.notna(lap.get("Stint")) else None,
            int(lap["Position"]) if pd.notna(lap.get("Position")) else None,
            1 if lap.get("IsAccurate") else 0,
            1 if pd.notna(lap.get("PitInTime")) else 0,
            1 if pd.notna(lap.get("PitOutTime")) else 0,
            float(lap["SpeedI1"]) if pd.notna(lap.get("SpeedI1")) else None,
            float(lap["SpeedI2"]) if pd.notna(lap.get("SpeedI2")) else None,
            float(lap["SpeedFL"]) if pd.notna(lap.get("SpeedFL")) else None,
            float(lap["SpeedST"]) if pd.notna(lap.get("SpeedST")) else None,
            str(lap.get("TrackStatus", "")) if pd.notna(lap.get("TrackStatus")) else "",
        ))

    conn = get_db_connection()
    conn.executemany(
        "INSERT OR IGNORE INTO laps "
        "(year, round, session_type, driver, lap_number, lap_time_ms, "
        "sector1_ms, sector2_ms, sector3_ms, compound, tyre_life, stint, "
        "position, is_accurate, is_pit_in, is_pit_out, "
        "speed_i1, speed_i2, speed_fl, speed_st, track_status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()


def store_stints(
    session: fastf1.core.Session,
    year: int,
    round_num: int,
    session_type: str,
) -> None:
    """Extract stint boundaries and store in SQLite."""
    if _session_already_loaded(year, round_num, "stints", session_type):
        return

    laps = session.laps
    if laps is None or laps.empty:
        return

    # Group by driver and stint to find boundaries
    stint_groups = laps.groupby(["Driver", "Stint"])
    rows = []
    for (driver, stint_num), group in stint_groups:
        if pd.isna(stint_num):
            continue
        rows.append((
            year,
            round_num,
            session_type,
            driver,
            int(stint_num),
            group.iloc[0].get("Compound", ""),
            int(group["LapNumber"].min()),
            int(group["LapNumber"].max()),
            int(group["TyreLife"].min()) if pd.notna(group["TyreLife"].min()) else 0,
            1 if group.iloc[0].get("FreshTyre", False) else 0,
        ))

    conn = get_db_connection()
    conn.executemany(
        "INSERT OR IGNORE INTO stints "
        "(year, round, session_type, driver, stint_number, compound, "
        "start_lap, end_lap, tyre_life_start, fresh_tyre) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()


def store_weather(
    session: fastf1.core.Session,
    year: int,
    round_num: int,
    session_type: str,
) -> None:
    """Store weather data for the session."""
    if _session_already_loaded(year, round_num, "weather", session_type):
        return

    weather = session.weather_data
    if weather is None or weather.empty:
        return

    rows = []
    for _, w in weather.iterrows():
        rows.append((
            year,
            round_num,
            session_type,
            str(w.get("Time", "")),
            float(w["AirTemp"]) if pd.notna(w.get("AirTemp")) else None,
            float(w["TrackTemp"]) if pd.notna(w.get("TrackTemp")) else None,
            float(w["Humidity"]) if pd.notna(w.get("Humidity")) else None,
            float(w["Pressure"]) if pd.notna(w.get("Pressure")) else None,
            1 if w.get("Rainfall") else 0,
            float(w["WindSpeed"]) if pd.notna(w.get("WindSpeed")) else None,
            int(w["WindDirection"]) if pd.notna(w.get("WindDirection")) else None,
        ))

    conn = get_db_connection()
    conn.executemany(
        "INSERT INTO weather "
        "(year, round, session_type, timestamp, air_temp, track_temp, "
        "humidity, pressure, rainfall, wind_speed, wind_direction) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()


def store_pit_stops(
    session: fastf1.core.Session,
    year: int,
    round_num: int,
) -> None:
    """Extract pit stop data from lap data and store in SQLite."""
    if _session_already_loaded(year, round_num, "pit_stops"):
        return

    laps = session.laps
    if laps is None or laps.empty:
        return

    # Find laps where driver pitted (PitInTime is not NaT)
    pit_laps = laps[laps["PitInTime"].notna()].copy()
    if pit_laps.empty:
        return

    rows = []
    for driver in pit_laps["Driver"].unique():
        drv_laps = laps[laps["Driver"] == driver].sort_values("LapNumber")
        drv_pit_ins = drv_laps[drv_laps["PitInTime"].notna()]
        drv_pit_outs = drv_laps[drv_laps["PitOutTime"].notna()]

        for stop_num, (_, pit_in) in enumerate(drv_pit_ins.iterrows(), start=1):
            pit_in_lap = int(pit_in["LapNumber"])
            # PitOutTime is recorded on the out-lap (the lap after pitting),
            # not the in-lap — find the first out-lap after this in-lap.
            next_out = drv_pit_outs[drv_pit_outs["LapNumber"] > pit_in_lap]

            duration = None
            if not next_out.empty:
                pit_out_time = next_out.iloc[0]["PitOutTime"]
                if pd.notna(pit_out_time) and pd.notna(pit_in["PitInTime"]):
                    duration = _timedelta_to_ms(pit_out_time - pit_in["PitInTime"])

            rows.append((
                year,
                round_num,
                driver,
                stop_num,
                pit_in_lap,
                duration,
            ))

    conn = get_db_connection()
    conn.executemany(
        "INSERT OR IGNORE INTO pit_stops "
        "(year, round, driver, stop_number, lap, duration_ms) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()


def store_weekend(
    year: int,
    round_num: int,
    session_types: Optional[list] = None,
) -> None:
    """Load and store all sessions for a race weekend."""
    if session_types is None:
        session_types = ["FP1", "FP2", "FP3", "Q", "R"]

    for st in session_types:
        try:
            print(f"  Loading {year} R{round_num:02d} {st}...")
            session = get_session(year, round_num, st)

            # Store race info from the first successful session
            store_race_info(session, year, round_num)

            # Store laps, stints, weather for all sessions
            store_laps(session, year, round_num, st)
            store_stints(session, year, round_num, st)
            store_weather(session, year, round_num, st)

            # Results and pit stops only from race session
            if st == "R":
                store_race_results(session, year, round_num)
                store_pit_stops(session, year, round_num)

            print(f"    {st} stored successfully")
        except Exception as e:
            print(f"    {st} skipped: {e}")


# ---------------------------------------------------------------------------
# Load Functions (read from DB)
# ---------------------------------------------------------------------------

def load_laps_from_db(
    year: int,
    round_num: int,
    session_type: str = "R",
) -> pd.DataFrame:
    """Load lap data from SQLite for a given race and session type."""
    conn = get_db_connection()
    df = pd.read_sql_query(
        "SELECT * FROM laps WHERE year = ? AND round = ? AND session_type = ?",
        conn,
        params=(year, round_num, session_type),
    )
    conn.close()
    return df


def load_results_from_db(
    year: Optional[int] = None,
    round_num: Optional[int] = None,
) -> pd.DataFrame:
    """Load results, optionally filtered by year and/or round."""
    conn = get_db_connection()
    query = "SELECT * FROM results"
    params: list = []
    conditions = []

    if year is not None:
        conditions.append("year = ?")
        params.append(year)
    if round_num is not None:
        conditions.append("round = ?")
        params.append(round_num)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


def load_stints_from_db(
    year: int,
    round_num: int,
    session_type: str = "R",
) -> pd.DataFrame:
    """Load stint data from SQLite."""
    conn = get_db_connection()
    df = pd.read_sql_query(
        "SELECT * FROM stints WHERE year = ? AND round = ? AND session_type = ?",
        conn,
        params=(year, round_num, session_type),
    )
    conn.close()
    return df


def load_pit_stops_from_db(
    year: Optional[int] = None,
    round_num: Optional[int] = None,
) -> pd.DataFrame:
    """Load pit stop data from SQLite."""
    conn = get_db_connection()
    query = "SELECT * FROM pit_stops"
    params: list = []
    conditions = []

    if year is not None:
        conditions.append("year = ?")
        params.append(year)
    if round_num is not None:
        conditions.append("round = ?")
        params.append(round_num)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


_SESSION_ORDER = ["R", "Q", "FP3", "FP2", "FP1"]


def load_available_sessions_from_db(year: int, round_num: int) -> list[str]:
    """Return distinct session types ingested for a given year/round, in race-weekend order."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT DISTINCT session_type FROM laps WHERE year = ? AND round = ?",
        (year, round_num),
    )
    found = {row[0] for row in cursor.fetchall()}
    conn.close()
    return [s for s in _SESSION_ORDER if s in found] or _SESSION_ORDER


def load_available_years_from_db() -> list[int]:
    """Return distinct years that have race data in the DB, descending."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT year FROM races ORDER BY year DESC")
    years = [row[0] for row in cursor.fetchall()]
    conn.close()
    return years


def load_races_from_db(
    year: Optional[int] = None,
) -> pd.DataFrame:
    """Load race metadata from SQLite."""
    conn = get_db_connection()
    if year is not None:
        df = pd.read_sql_query(
            "SELECT * FROM races WHERE year = ?", conn, params=(year,)
        )
    else:
        df = pd.read_sql_query("SELECT * FROM races", conn)
    conn.close()
    return df
