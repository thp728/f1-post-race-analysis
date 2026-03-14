I'm looking for changes that help the user read and understand the data easier.

---

# Completed (Phase 1)

- Results Table: color-coded rows by grid→finish position change, DNF highlighted red
- All charts converted from static matplotlib to interactive Plotly (hover, zoom, pan, legend toggle)
- All driver limits removed: charts show all drivers by default with multiselect filter
- Sector comparison chart now has data labels
- Degradation table: color-coded by fuel-corrected slope (green = low deg, red = high)
- Stint-adjusted pace table: color-coded by pace (green = fastest, red = slowest)
- Season trends heatmap converted to interactive Plotly
- Explanation text expanders added to every chart/table section (content from `docs/dashboard-guide.md`)

---

# Completed (Phase 3)

## Sprint Support & Session-Type Branching

### Sprint support

- `"S"` and `"SQ"` added to `_SESSION_ORDER` and `store_weekend()` defaults in `src/loader.py`
- `results` and `pit_stops` tables gained `session_type` column with auto-migration (no DB rebuild needed)
- Sprint results and pit stops stored separately from Race results (same tables, keyed by `session_type`)
- Prediction model explicitly filters to `session_type="R"` — sprint results don't affect predictions
- Dashboard sidebar dynamically lists S/SQ only when present in DB (sprint weekends only)

### Session-type aware analysis

`dashboard/pages/1_race_analysis.py` now branches on session type:

| Session                | What is shown                                                                                              |
| ---------------------- | ---------------------------------------------------------------------------------------------------------- |
| Race (R)               | Full analysis (results, positions, laps, tyres, deg, pace, sectors, consistency, SC, undercuts, pit stops) |
| Sprint (S)             | Same as Race                                                                                               |
| Qualifying (Q)         | Q1/Q2/Q3 progression table, gap to pole chart, lap improvement per driver, sector comparison, speed traps  |
| Sprint Qualifying (SQ) | Same as Q (labels show SQ1/SQ2/SQ3)                                                                        |
| Practice (FP1/FP2/FP3) | Long run pace chart, short run pace table, lap time distribution, tyre strategy, sector comparison         |

### New functions in `src/metrics.py`

- `qualifying_progression(laps)` — best lap per driver, Q segment assignment, elimination status
- `lap_improvement_delta(laps, driver)` — per-attempt time delta and cumulative improvement
- `gap_to_pole(laps)` — gap in ms/s/% to the session's fastest lap
- `long_run_pace(laps, min_stint_laps=5)` — stint pace with `is_long_run` flag

### New chart functions in `dashboard/components/charts.py`

- `plot_qualifying_progression()` — color-coded Plotly table (green=Q3, yellow=Q2, red=Q1)
- `plot_gap_to_pole()` — horizontal bar chart with segment colors and gap labels
- `plot_lap_improvement()` — line+scatter with delta annotations per attempt
- `plot_long_run_pace()` — grouped bar chart by compound, colored by `COMPOUND_COLORS`

---

# Remaining

## Phase 4: Data & Edge Cases

### Pit stop times

- Current data shows ~20s (pit lane duration: entry→exit), not stationary stop time (~2-3s)
- OpenF1 does NOT expose stationary time — won't help
- **Option A**: Test `fastf1.ergast.Ergast().get_pit_stops()` (Jolpica-F1) for actual stop durations
- **Option B**: Relabel as "Pit Lane Duration" and add explanatory note
- **Option C**: Infer from telemetry (detect speed=0 period) — accurate but complex

### Filters

- Is it possible to add filters to table cols for all tables in the dashboard

### Prediction edge cases

- Show warning when insufficient data (< 3 races) instead of empty table
- Add graceful messaging for 2026 R1 scenario

### Files to modify

- `src/loader.py` — potentially add Jolpica-F1 pit stop source
- `dashboard/pages/2_predictions.py` — empty state handling

## Phase 5: Visual Polish (Streamlit limits)

What we CAN improve:

- Custom theme via `.streamlit/config.toml` — F1-inspired color palette
- Consistent Plotly template across all charts (matching fonts, colors)
- Use `st.tabs()` to group related analyses instead of one long scroll
- Use `st.metric()` cards for key race summary stats (winner, fastest lap, total laps)
- Use `st.spinner()` during data loads
