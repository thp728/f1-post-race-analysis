# F1 Post-Race Analysis — Implementation Plan

## Context

This is a greenfield learning project with only documentation scaffolding (CLAUDE.md, AGENTS.md, README.md, docs/research.md). No source code, pyproject.toml, or Python environment exists yet. The goal is to build the full analysis toolkit described in the docs: data loading, metrics computation, prediction model, Streamlit dashboard, and blog export pipeline.

**Key decisions made during planning**:
- **SQLite only** — no Parquet files. One storage layer is simpler and sufficient.
- **Full weekend sessions** — ETL loads R + Q + FP1/FP2/FP3, not just race + qualifying.
- **Race-by-race workflow** — no bulk backfill initially. ETL processes one weekend at a time.

---

## Phase -1: Copy Plan to Repo

Copy this finalized plan to `docs/implementation-plan.md` so it lives in the repo alongside the research doc.

---

## Phase 0: Project Scaffolding & Environment

**Goal**: Working Python environment with all dependencies. Verify with `uv run python -c "import fastf1"`.

### Files to create

**`pyproject.toml`**
```toml
[project]
name = "f1-post-race-analysis"
version = "0.1.0"
description = "Post-race Formula 1 analysis toolkit"
requires-python = ">=3.9"
dependencies = [
    "fastf1>=3.8",
    "pandas>=2.0",
    "numpy>=1.24",
    "matplotlib>=3.7",
    "seaborn>=0.12",
    "plotly>=5.15",
    "scipy>=1.10",
    "scikit-learn>=1.3",
    "streamlit>=1.30",
    "jupyterlab>=4.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

**Directory structure** — create all dirs + `__init__.py` files:
- `src/__init__.py` (empty)
- `dashboard/components/__init__.py` (empty)
- `dashboard/pages/` (empty dir)
- `scripts/` (empty dir)
- `notebooks/` (empty dir)

**`.python-version`** — run `uv python pin 3.12`

**Commands**: `uv sync` → generates `uv.lock` (commit it)

---

## Phase 1: Data Loading & Storage — `src/loader.py`

**Goal**: Load any F1 session (R/Q/FP1/FP2/FP3), store processed data in SQLite. Verify by loading 2024 Bahrain race and querying the DB.

This is the critical-path foundation — everything depends on it.

### Key functions

| Function | Purpose |
|----------|---------|
| `init_cache()` | Enable FastF1 cache at `data/f1_cache` |
| `get_session(year, event, session_type)` | Load session without telemetry |
| `get_session_with_telemetry(...)` | Load session with telemetry (for deep dives) |
| `get_event_schedule(year)` | Return event schedule DataFrame |
| `init_db()` | Create all SQLite tables if not exist |
| `store_race_results(session, year, round)` | Insert results into SQLite |
| `store_laps(session, year, round, session_type)` | Insert laps into SQLite |
| `store_stints(session, year, round, session_type)` | Insert stint boundaries |
| `store_weather(session, year, round, session_type)` | Insert weather data |
| `store_pit_stops(session, year, round)` | Insert pit stop data (race only) |
| `load_laps_from_db(year, round, session_type)` | Read laps from SQLite |
| `load_results_from_db(year, round)` | Read results from SQLite |
| `get_db_connection()` | Return SQLite connection |

### SQLite schema (8 tables)

All lap/stint/weather tables include a `session_type` column (R/Q/FP1/FP2/FP3) to distinguish data from different sessions within the same weekend.

- **races** — year, round, event_name, circuit_name, circuit_id, date
- **laps** — year, round, session_type, driver, lap_number, lap_time_ms, sector times (ms), compound, tyre_life, stint, position, is_accurate, pit flags, speed traps, track_status
- **stints** — year, round, session_type, driver, stint_number, compound, start_lap, end_lap, fresh_tyre
- **results** — year, round, driver, driver_number, team, grid_position, finish_position, status, points, fastest_lap_time_ms
- **weather** — year, round, session_type, timestamp, air_temp, track_temp, humidity, pressure, rainfall, wind
- **pit_stops** — year, round, driver, stop_number, lap, duration_ms
- **driver_standings** — year, round, driver, points, position, wins
- **constructor_standings** — year, round, constructor, points, position, wins

**Key decision**: Store lap/sector times as INTEGER milliseconds (not float seconds or timedelta strings) to avoid precision issues. Convert at boundaries: `_timedelta_to_ms()` and `ms / 1000.0`.

### Verification
- Load 2024 Bahrain race into DB, query `results` table → 20 rows
- Query `laps` with `session_type='R'` returns race laps

---

## Phase 2: Core Metrics — `src/metrics.py`

**Goal**: Implement 4 of the 6 analysis techniques. Verify by computing degradation + consistency for a real race.

**Depends on**: Phase 1 (loader)

### Key functions

**Tyre degradation**:
- `calculate_degradation(laps, driver, compound)` → dict with slope, r², fuel-corrected slope
- `calculate_all_degradation(laps)` → DataFrame of all driver/compound combos
- `detect_tyre_cliff(laps, driver, compound)` → tyre_life where cliff begins (or None)

**Sector breakdown**:
- `sector_comparison(laps, drivers)` → best sectors, theoretical best, actual best, gap
- `speed_trap_comparison(laps, drivers)` → max speeds at each trap per driver

**Pace delta**:
- `lap_by_lap_delta(laps, driver1, driver2)` → lap-by-lap delta + cumulative gap
- `stint_adjusted_pace(laps, drivers)` → mean pace per driver per stint (excluding pit laps)

**Consistency**:
- `consistency_metrics(laps, drivers)` → std, IQR, CV%, clean_laps per driver

**Shared helpers**:
- `filter_clean_laps(laps)` → remove pit/inaccurate/outlier laps (replicates `pick_quicklaps` logic on plain DataFrames from SQLite)
- `pct_gap_to_leader(laps)` → percentage gap for cross-race normalisation

### Verification
- MEDIUM degradation for 2024 Bahrain: ~0.05–0.12 s/lap before fuel correction
- Top drivers std < 1.0s
- Cumulative gap between VER and LEC matches known race gap

---

## Phase 3: Strategy Analysis — `src/strategy.py`

**Goal**: Pit strategy data + undercut/SC detection. Verify by detecting known events from a real race.

**Depends on**: Phase 1 (loader)

### Key functions

| Function | Purpose |
|----------|---------|
| `get_stint_summary(laps)` | Driver, stint, compound, start/end lap, length |
| `detect_undercuts(laps, results)` | Find position swaps from early pitting |
| `detect_overcuts(laps, results)` | Find position swaps from staying out |
| `detect_safety_car_periods(laps)` | SC/VSC periods from track_status ('4'/'6') |
| `sc_beneficiaries(laps, sc_periods)` | Who pitted during each SC period |
| `pit_stop_analysis(pit_stops)` | Mean/std duration per driver/team |

---

## Phase 4: Circuit Classification — `src/circuit.py`

**Goal**: Static circuit cluster lookup. No ML — manually maintained mapping.

**Depends on**: Nothing (can be built in parallel with Phases 2–3)

### Key elements

- `CircuitCluster` enum: `NIGHT_DESERT`, `FAST_STREET`, `TIGHT_LOW_OVERTAKING`, `CLASSIC_HIGH_SPEED`, `STRAIGHT_LINE_DOMINANT`
- `CIRCUIT_CLUSTERS` dict: maps circuit_id → cluster (covers all current calendar circuits)
- `get_cluster(circuit_id)` → cluster enum
- `get_circuits_in_cluster(cluster)` → list of circuit IDs
- `normalize_circuit_id(event_name)` → convert FastF1 event name to lookup key

---

## Phase 5: Prediction Model — `src/prediction.py`

**Goal**: Weighted scoring model ranking drivers for next race. Verify by predicting a past race and comparing.

**Depends on**: Phases 1, 2, 4

### Key functions

**Feature engineering** (each returns a score component):
- `compute_rolling_form(results, driver, as_of_round, n=5)` → rolling avg finish
- `compute_circuit_history(results, driver, circuit_id, n=3)` → avg finish at this circuit
- `compute_cluster_form(results, driver, cluster, year)` → avg finish at same cluster type
- `compute_pit_consistency(pit_stops, driver, year)` → 0–1 score from pit stop std
- `compute_quali_conversion(results, driver, n=5)` → 0–1 score centered at 0.5

**Scoring**:
- `predict_race(year, next_round, circuit_id, weights)` → ranked DataFrame with score + component breakdown

**Elo ratings**:
- `compute_elo_ratings(results)` → dict of driver → rating (processes all races chronologically)
- `update_elo_after_race(ratings, race_results)` → updated ratings after one race

**Default weights**: recent_form=0.40, circuit_history=0.25, cluster_form=0.15, pit_consistency=0.10, quali_conversion=0.10

---

## Phase 6: Dashboard — `dashboard/`

**Goal**: Working multi-page Streamlit app. Verify with `uv run streamlit run dashboard/app.py`.

**Depends on**: All src/ modules (Phases 1–5)

### `dashboard/components/charts.py` — all visualisation functions

Each function returns a figure object (matplotlib or plotly). Dashboard calls `st.pyplot(fig)` / `st.plotly_chart(fig)`. Export script calls `fig.savefig()`. This dual-use pattern is key.

| Function | Type | Purpose |
|----------|------|---------|
| `plot_lap_time_distribution(laps, drivers)` | matplotlib | Violin/box plot |
| `plot_tyre_strategy(stint_summary)` | matplotlib | Horizontal bar timeline by compound |
| `plot_degradation_curves(laps, drivers, compound)` | matplotlib | Scatter + regression lines |
| `plot_pace_delta(delta_df, d1, d2)` | matplotlib | Cumulative gap line chart |
| `plot_sector_comparison(sector_df)` | matplotlib | Grouped bar chart |
| `plot_consistency_bars(consistency_df)` | matplotlib | CV% bar chart |
| `plot_position_chart_interactive(laps, drivers)` | plotly | Position over laps |
| `plot_prediction_table(predictions)` | plotly | Styled prediction breakdown |

### `dashboard/app.py` — entry point
- `st.set_page_config(layout="wide")`
- Sidebar: season, event, session type selectors
- Session state for passing selection to pages
- Home page with overview

### `dashboard/pages/1_race_analysis.py`
Thin page calling src/ → charts.py: results table, degradation curves, strategy chart, pace delta, sector comparison, consistency, SC/undercut info

### `dashboard/pages/2_predictions.py`
Next-race prediction table with component breakdown, Elo ratings, circuit cluster info

### `dashboard/pages/3_season_trends.py`
Championship progressions, rolling form, Elo trends, pit stop consistency trends

**Caching**: Dashboard reads from SQLite (fast), not FastF1 directly (slow). Use `@st.cache_data` for DB queries.

---

## Phase 7: Scripts — `scripts/`

**Goal**: Automation for weekly content pipeline. Verify by running ETL for one race.

**Depends on**: Phases 1, 6

### `scripts/post_race_etl.py`
- Args: `--year`, `--round` (or auto-detect latest completed race)
- Loads **all sessions** for the weekend: FP1, FP2, FP3, Q, R
- Calls all `store_*` functions from loader for each session
- Skips sessions that are already in the DB (idempotent)
- Prints summary per session

### `scripts/export_blog_charts.py`
- Args: `--year`, `--round`
- Creates `exports/{year}_R{round:02d}/`
- Generates all standard charts via charts.py → saves as PNG

**Note**: `backfill_season.py` is deferred — not needed initially. The race-by-race `post_race_etl.py` is the primary workflow. Backfill can be added later by iterating the schedule and calling the same store functions.

---

## Phase 8: Export Helpers — `src/export.py`

**Goal**: Chart export utilities for the blog pipeline.

### Key functions
- `get_export_path(year, round)` → creates and returns export dir
- `save_figure(fig, filename, year, round)` → saves matplotlib figure as PNG
- `export_race_charts(year, round)` → orchestrates all chart generation + saving

---

## Phase 9: Notebook + Tests

### `notebooks/scratch.ipynb`
Minimal notebook: imports from src/, cache init, example session load, placeholder cells.

### `tests/` (optional, recommended)
- Add pytest as dev dependency
- `tests/test_metrics.py` — test math on synthetic DataFrames (no FastF1 needed)
- `tests/test_circuit.py` — test cluster lookups
- `tests/test_prediction.py` — test scoring on synthetic data

---

## Phase 10: Update Project Documentation

**Goal**: Update CLAUDE.md and AGENTS.md to reflect all decisions made during implementation.

**Depends on**: All prior phases

### Updates to `CLAUDE.md`
- Remove Parquet references from architecture and data conventions sections
- Update repo structure to reflect actual files created
- Add `session_type` to data conventions (laps/stints/weather tables)
- Update any code examples that reference Parquet
- Note that `backfill_season.py` is deferred / not yet implemented
- Document any new conventions discovered during development

### Updates to `AGENTS.md`
- Update build/test commands if any changed
- Add any new common workflows discovered
- Update data storage section (SQLite only, no Parquet)
- Add notes on full weekend session loading (FP1–FP3 + Q + R)

---

## Build Order & Dependencies

```
Phase -1 (copy plan to docs/)
  │
  ▼
Phase 0 (scaffolding)
  │
  ▼
Phase 1 (loader) ◄── critical path, largest phase
  │
  ├──► Phase 2 (metrics) ──┐
  ├──► Phase 3 (strategy)   ├──► Phase 5 (prediction)
  └──► Phase 4 (circuit) ──┘         │
                                      ▼
                              Phase 6 (dashboard + charts)
                                      │
                              Phase 7 (scripts)
                                      │
                              Phase 8 (export)
                                      │
                              Phase 9 (tests + notebook)
                                      │
                              Phase 10 (update CLAUDE.md + AGENTS.md)
```

Phases 2, 3, 4 are independent and can be built in parallel.

---

## Potential Blockers

1. **Timedelta ↔ SQLite boundary**: FastF1 returns `pd.Timedelta`; SQLite needs integers. Every conversion point is a bug risk. Centralise in `_timedelta_to_ms()` / `ms / 1000.0`.

2. **Import paths**: Project isn't an installable package. Dashboard/scripts need `sys.path.insert(0, project_root)` to resolve `from src import loader`.

3. **FastF1 download speed**: First-time session loads are slow. Cache prevents re-downloads. ETL should load with `telemetry=False` by default.

4. **Streamlit caching**: Dashboard must read from SQLite (fast), not FastF1 (slow). ETL scripts populate the DB; dashboard reads it. Use `@st.cache_data` aggressively.

5. **FastF1 colour helpers**: `get_compound_color()` and `get_driver_color_mapping()` need a loaded session. Charts should accept optional session param with manual fallback colours.

---

## Verification Milestones

| After Phase | Test |
|-------------|------|
| -1 | `docs/implementation-plan.md` exists in repo |
| 0 | `uv run python -c "import fastf1"` succeeds |
| 1 | Load 2024 Bahrain → query SQLite → 20 result rows |
| 2 | Compute degradation slopes for one race |
| 3 | Detect SC periods from a race with known SC |
| 4 | `get_cluster("monza")` → STRAIGHT_LINE_DOMINANT |
| 5 | Predict a past race, compare to actual results |
| 6 | `uv run streamlit run dashboard/app.py` shows charts |
| 7 | `post_race_etl.py --year 2024 --round 1` populates DB |
| 8 | PNGs generated in `exports/2024_R01/` |
| 9 | `uv run pytest` passes on synthetic data tests |
| 10 | CLAUDE.md and AGENTS.md reflect all implementation decisions |
