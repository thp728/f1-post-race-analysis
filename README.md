# F1 Post-Race Analysis

Post-race Formula 1 analysis toolkit. Loads race data via [FastF1](https://docs.fastf1.dev/), computes performance metrics, generates predictions for the next race, and serves results via a Streamlit dashboard. Blog-ready chart exports feed a separate Astro-based GitHub Pages site.

This is a learning project — educational focus, not production-grade.

## Setup

Requires [uv](https://docs.astral.sh/uv/) for package management.

```bash
uv sync
```

## Usage

```bash
# Run the dashboard
uv run streamlit run dashboard/app.py

# Post-race data pipeline — load full weekend (FP1, FP2, FP3, Q, R)
uv run python scripts/post_race_etl.py --year 2026 --round 2

# Load a specific session only
uv run python scripts/post_race_etl.py --year 2026 --round 2 --session FP1

# Export charts for blog
uv run python scripts/export_blog_charts.py --year 2026 --round 2
```

## Project Structure

- `src/` — Core logic: data loading, metrics, strategy analysis, predictions
- `dashboard/` — Streamlit app (primary analysis interface)
- `scripts/` — ETL and export automation
- `notebooks/` — Ad-hoc exploration only
- `data/` — Local data and caches (gitignored)
- `exports/` — Blog-ready PNGs (gitignored)
