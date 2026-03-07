# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Post-race Formula 1 analysis toolkit. Loads race data, computes performance metrics, generates predictions for the next race, and serves results via a Streamlit dashboard. Blog-ready chart exports feed a separate Astro-based GitHub Pages site.

This is a learning project — educational focus, not production-grade. Prioritise clarity and correctness over abstraction.

## Architecture

### Data Source Strategy

- **FastF1 (primary)** — all session data: laps, sectors, telemetry, tyre compounds, weather, race control messages. Covers 2018–present. Already uses Jolpica-F1 internally for results/standings.
- **Jolpica-F1 (direct, only when needed)** — for pre-2018 historical data (Elo ratings, long-term trend features). API at `api.jolpi.ca/ergast/f1/`, 200 req/hr limit.
- **OpenF1** — not currently used. Only add if building a REST-based frontend or needing overtake/team radio data.
- **F1DB** — not currently used. Only add for multi-decade ML feature sets.

Do not add new data sources without a concrete use case.

### Repo Structure

```
f1-analysis/
├── src/                     # Core logic — all reusable functions live here
│   ├── loader.py            # FastF1 session loading, caching, ETL helpers
│   ├── metrics.py           # Degradation, consistency, pace delta calculations
│   ├── strategy.py          # Stint analysis, undercut/overcut detection
│   ├── prediction.py        # Scoring model, Elo ratings, feature engineering
│   ├── circuit.py           # Circuit classification, cluster mapping
│   └── export.py            # Chart export helpers (PNG for blog)
│
├── dashboard/               # Streamlit app — primary analysis interface
│   ├── app.py               # Entry point
│   ├── pages/
│   │   ├── 1_race_analysis.py
│   │   ├── 2_predictions.py
│   │   └── 3_season_trends.py
│   └── components/
│       └── charts.py        # Shared visualisation functions for dashboard
│
├── notebooks/               # Ad-hoc exploration ONLY — not per-race templates
│   └── scratch.ipynb
│
├── scripts/
│   ├── post_race_etl.py     # Run after each race to load data into DB
│   ├── backfill_season.py   # Bulk load historical season data
│   └── export_blog_charts.py # Export dashboard charts as PNGs for blog
│
├── data/                    # All local data (gitignored)
│   ├── f1_cache/            # FastF1 cache directory
│   ├── processed/           # Parquet files
│   └── f1.db               # SQLite database
│
├── exports/                 # Blog-ready PNGs per race (e.g., exports/2025_R01/)
├── pyproject.toml           # Dependencies managed by uv
├── uv.lock                  # Pinned dependency lockfile (committed to git)
├── .gitignore
├── README.md
└── CLAUDE.md
```

### Key Design Decisions

- **Dashboard is the primary analysis interface**, not notebooks. If analysis is repeatable week-to-week, it belongs in the dashboard. Notebooks are scratch space for one-off investigations only.
- **Notebooks import from `src/`** — never duplicate logic. If you copy-paste code between notebooks, extract it into `src/`.
- **If a notebook exploration pattern proves generally useful, promote it**: move the logic to `src/`, add a dashboard page, delete the notebook.
- **Own database (SQLite)** stores processed data. FastF1's cache is a download cache, not an analytical database. The SQLite DB enables cross-race queries, rolling aggregations, and pre-computed metrics without reloading sessions.
- **Parquet files** for intermediate storage when SQL isn't needed. One file per race for lap data.
- **Two-repo setup**: this repo is the analysis workbench. A separate repo (`f1-blog`) hosts the Astro-based GitHub Pages site. `exports/` in this repo contains PNGs that get copied to the blog repo's `src/assets/`.

## Common Commands

```bash
uv sync                                  # Install all dependencies from lockfile
uv run streamlit run dashboard/app.py    # Run dashboard
uv run jupyter lab                       # Run notebooks
uv add <package>                         # Add new dependency
uv run python scripts/post_race_etl.py   # Post-race data loading
uv run python scripts/backfill_season.py # Bulk historical data load
uv run python scripts/export_blog_charts.py  # Export PNGs for blog
```

## Package Management

Uses **uv** (not pip/venv/conda).

- `pyproject.toml` declares dependencies
- `uv.lock` pins exact versions (always commit this)
- `.venv/` is the local virtual environment (gitignored)
- Python version pinned via `uv python pin` in project root

## Core Dependencies

- `fastf1` — F1 data loading and session management
- `pandas`, `numpy` — data processing
- `matplotlib`, `seaborn` — static visualisation
- `plotly` — interactive charts
- `scipy` — curve fitting (degradation slopes)
- `scikit-learn` — predictive modelling
- `streamlit` — dashboard framework
- `jupyterlab` — notebook exploration

## Data Conventions

### FastF1 Caching

Always enable before any session load:

```python
fastf1.Cache.enable_cache('data/f1_cache')
```

### Lap Filtering

- Use `pick_quicklaps(threshold=1.07)` for pace analysis — removes pit laps, SC laps, outliers
- Use `pick_accurate()` for timing-critical analysis — removes laps with sync issues
- Always filter out in-laps and out-laps for degradation calculations (`PitInTime.isna() & PitOutTime.isna()`)

### Tyre Compounds

FastF1 reports SOFT/MEDIUM/HARD — not the underlying Pirelli C1–C5 specification. Cross-race tyre comparisons require external knowledge of compound allocation per event. Do not assume MEDIUM at Bahrain equals MEDIUM at Monza.

### Fuel Correction

Approximate fuel effect: **~0.06 s/lap** improvement from fuel burn. Subtract this from raw degradation slope to isolate tyre-only degradation.

### Normalisation for Cross-Race Comparison

Never compare raw lap times across circuits. Use percentage gap to session leader:

```python
pct_gap = 100 * (driver_time - leader_time) / leader_time
```

## Analysis Techniques Implemented

All implementations live in `src/`. Dashboard pages and export scripts call these — never reimplement.

1. **Tyre degradation** (`metrics.py`) — linear regression of lap time vs tyre age per compound per driver. Fuel-corrected. Cliff detection via rolling window threshold.
2. **Sector breakdown** (`metrics.py`) — sector-by-sector comparison, theoretical best lap, speed trap analysis.
3. **Pace delta** (`metrics.py`) — lap-by-lap gap evolution, stint-adjusted mean pace per driver.
4. **Pit strategy** (`strategy.py`) — stint timeline visualisation, undercut/overcut detection by comparing pit lap timing and position changes.
5. **Safety car impact** (`strategy.py`) — identify SC/VSC periods from race control messages or TrackStatus codes, flag drivers who pitted under SC.
6. **Consistency metrics** (`metrics.py`) — standard deviation, IQR, coefficient of variation of clean lap times per driver.

## Prediction Model

Weighted scoring model combining:

- Recent form — rolling avg finish position, last 5 races (weight: 0.40)
- Circuit history — avg finish at this specific circuit, last 3 visits (weight: 0.25)
- Circuit cluster form — avg finish at same circuit type this season (weight: 0.15)
- Pit stop consistency — std of pit stop durations (weight: 0.10)
- Qualifying conversion — avg positions gained/lost grid-to-finish (weight: 0.10)

Circuit clusters: night/desert, fast street, tight/low-overtaking, classic high-speed, straight-line dominant.

**Known limitations (do not try to model these):**

- Mid-season upgrades can shift competitiveness 0.3–0.5s overnight
- Street circuits produce outlier results
- Early-season predictions are unreliable (< 3 races of data)
- Driver team changes break historical continuity
- Regulation changes reset the competitive order

## Content Pipeline

Weekly cadence per race:

1. Run `scripts/post_race_etl.py` after the race
2. Open dashboard — standard analysis is auto-generated
3. Run `scripts/export_blog_charts.py` for blog PNGs
4. Write blog post in the `f1-blog` repo referencing exported charts
5. Optionally: explore specific questions in `notebooks/scratch.ipynb`

Two content formats per race week:

- **Post-race analysis + next-race prediction** (Monday/Tuesday)
- **Prediction review** (after the next race — what the model got right/wrong)

## Code Style

- Type hints on all `src/` functions
- Docstrings on public functions (one-liner minimum)
- No logic in dashboard pages — they call `src/` and `components/charts.py`
- Prefer explicit over clever — this is a learning project

## .gitignore Must Include

```
data/
.venv/
__pycache__/
*.pyc
.ipynb_checkpoints/
exports/
```

## Reference

- `docs/research.md` — original research on FastF1, OpenF1, analysis techniques, and prediction modelling that informed this project's design
