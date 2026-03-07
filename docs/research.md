# Post-race F1 analysis with Python, FastF1, and OpenF1

**FastF1 (v3.8.1) and OpenF1 together give you free access to lap times, telemetry, tyre data, pit stops, weather, and race control messages for every F1 session from 2018 onward** — enough to build serious post-race analysis and predictive models. FastF1 is the primary tool: a Python library returning extended pandas DataFrames with ~30 Hz telemetry, sector times, compound data, and built-in plotting. OpenF1 complements it as a language-agnostic REST API with unique data like overtake tracking and team radio URLs. Together with Jolpica-F1 (the Ergast replacement providing results back to 1950), these free tools cover every dimension of F1 performance analysis. This guide walks through the full pipeline — from data collection through post-race analysis to building a baseline model that predicts competitiveness at the next race.

---

## 1. FastF1 vs OpenF1: choosing the right tool

**FastF1** is the gold standard for Python-based F1 analysis. It wraps Formula 1's official live timing streams into pandas DataFrames with F1-specific helper methods like `.pick_fastest()`, `.pick_quicklaps()`, and `.pick_tyre()`. Telemetry arrives at **~30 Hz** (speed, throttle, brake, gear, DRS, RPM, plus X/Y/Z position), and the library covers **2018 to present** with full lap timing, sector times, tyre compounds, weather, and race control messages.

**OpenF1** is a REST API returning JSON or CSV. It covers **2023 onward** and samples telemetry at **~3.7 Hz** — lower resolution than FastF1 but accessible from any language without installing a Python library. OpenF1 uniquely provides **overtake data**, **team radio audio URLs**, **mini-sector segment colors** in lap data, and **championship standings endpoints** (beta). Its free tier allows **3 requests/second and 30 requests/minute** without authentication for historical data.

| Dimension           | FastF1                                              | OpenF1                                             |
| ------------------- | --------------------------------------------------- | -------------------------------------------------- |
| **Type**            | Python library (pip install)                        | REST API (JSON/CSV)                                |
| **Coverage**        | 2018–present                                        | 2023–present                                       |
| **Telemetry rate**  | ~30 Hz                                              | ~3.7 Hz                                            |
| **Tyre/stint data** | ✅ Compound, TyreLife, FreshTyre                    | ✅ Compound, stint boundaries, tyre age            |
| **Weather**         | ✅ Per-minute updates                               | ✅ Per-session                                     |
| **Race control**    | ✅ Flags, SC, penalties                             | ✅ Flags, SC, penalties                            |
| **Overtakes**       | ❌                                                  | ✅ (may be incomplete)                             |
| **Team radio**      | ❌                                                  | ✅ Audio URLs                                      |
| **Rate limits**     | Caching-based; respects Jolpica 200 req/hr          | 3 req/s, 30 req/min                                |
| **Best for**        | Deep telemetry analysis, plotting, Python workflows | Quick web apps, non-Python environments, live data |

**Additional free data sources worth integrating:**

- **Jolpica-F1** (`api.jolpi.ca/ergast/f1/`) — the drop-in replacement for the now-defunct Ergast API. Same endpoints, JSON only (no XML), **200 requests/hour**. Provides race results, qualifying, standings, lap times, and pit stops from **1950 to present**. FastF1 uses this internally since v3.5.
- **F1DB** (`github.com/f1db/f1db`) — the most comprehensive downloadable F1 database. All-time data from 1950 in CSV, JSON, and SQL formats. Updated after each race, CC BY 4.0 licensed. Ideal for building historical feature sets for ML models.
- **Kaggle datasets** — "Formula 1 World Championship (1950–2024)" by Rohan Rao remains the most popular offline dataset for machine learning projects.

**Recommended Python stack**: `fastf1` for data, `pandas` + `numpy` for processing, `matplotlib` + `seaborn` for static plots, `plotly` for interactive visualization, `scipy` for curve fitting, `scikit-learn` for modelling, and `streamlit` for dashboards.

---

## 2. Collecting and storing F1 data

### Loading a session

Every analysis begins by loading a session. FastF1's caching mechanism is critical — raw telemetry can exceed **200 MB per session**, and re-downloading is slow and strains the API.

```python
import fastf1

# Always enable caching first
fastf1.Cache.enable_cache('f1_cache')

# Load by year, GP name (or round number), and session type
session = fastf1.get_session(2024, 'Bahrain', 'R')   # Race
session.load()  # Fetches laps, telemetry, weather, messages

# Session types: 'FP1', 'FP2', 'FP3', 'Q', 'SQ' (Sprint Quali),
#                'S' (Sprint), 'R' (Race)
```

After `.load()`, the session object exposes:

- `session.laps` — all lap data (sector times, compounds, positions, pit times)
- `session.results` — finishing order, grid positions, points
- `session.weather_data` — air/track temp, humidity, wind, rainfall (1-min updates)
- `session.race_control_messages` — flags, safety car deployments, penalties
- `session.car_data` / `session.pos_data` — raw telemetry by driver number

### Fetching specific data types

**Lap times and sectors** come from `session.laps`, which contains columns for `LapTime`, `Sector1Time`, `Sector2Time`, `Sector3Time`, `Compound`, `TyreLife`, `Stint`, `PitInTime`, `PitOutTime`, `Position`, `IsAccurate`, and speed trap values (`SpeedI1`, `SpeedI2`, `SpeedFL`, `SpeedST`).

**Telemetry for a single lap** is accessed via the lap object:

```python
fastest_lap = session.laps.pick_driver('VER').pick_fastest()
telemetry = fastest_lap.get_telemetry()  # Speed, RPM, nGear, Throttle, Brake, DRS, X, Y, Z
telemetry = telemetry.add_distance()     # Adds cumulative Distance column
```

**Weather per lap** is obtained with `lap.get_weather_data()`, returning air/track temperature, humidity, pressure, rainfall, wind speed, and direction at the time of that lap.

**Pit stop data** is embedded in lap data: any lap where `PitInTime` is not NaT indicates the driver entered the pits. For detailed pit stop durations from historical data, use the Ergast interface:

```python
from fastf1.ergast import Ergast
ergast = Ergast()
pit_stops = ergast.get_pit_stops(season=2024, round=1)
```

**OpenF1 equivalent** (useful when you want REST access or non-Python integration):

```python
import requests
import pandas as pd

# Get lap data from OpenF1
laps = requests.get("https://api.openf1.org/v1/laps", params={
    "session_key": 9839, "driver_number": 44
}).json()
df = pd.DataFrame(laps)

# Get stint/tyre data
stints = requests.get("https://api.openf1.org/v1/stints", params={
    "session_key": 9839
}).json()

# Get weather
weather = requests.get("https://api.openf1.org/v1/weather", params={
    "session_key": 9839
}).json()
```

### Handling data gaps and storage

**Data quality flags**: FastF1 marks laps with `IsAccurate=False` when timing synchronization is unreliable — this includes in-laps, out-laps, safety car laps, and laps with missing data. Always filter with `.pick_quicklaps()` or `.pick_accurate()` for pace analysis. The `pick_quicklaps(threshold=1.07)` method removes laps slower than 107% of the session's fastest, which effectively strips pit laps and anomalies.

**Compound data**: FastF1 reports tyre compounds as SOFT/MEDIUM/HARD/INTERMEDIATE/WET. It does not distinguish the underlying C1–C5 Pirelli specification, so cross-race tyre comparisons require external knowledge of which compounds Pirelli allocated to each event.

**Storage strategy**: Enable FastF1 caching to a persistent directory. For reuse across analysis sessions, export processed data to **Parquet** files — they're compact, columnar, and preserve pandas types including Timedelta:

```python
# After loading and filtering
clean_laps = session.laps.pick_quicklaps()
clean_laps.to_parquet(f'data/{year}_{event}_laps.parquet')
```

For a multi-season database, consider SQLite with tables for laps, stints, results, and weather, populated by a batch script that iterates through the schedule:

```python
schedule = fastf1.get_event_schedule(2024)
for _, event in schedule.iterrows():
    session = fastf1.get_session(2024, event['RoundNumber'], 'R')
    session.load(telemetry=False)  # Skip telemetry for storage efficiency
    # Extract and store lap data, results, weather...
```

---

## 3. Six post-race analysis techniques with code

### Tyre degradation and performance curves

Tyre degradation — how lap times increase as tyres wear — is the single most important factor in race strategy. To isolate it, you must subtract the **fuel effect** (~0.06 seconds per lap of fuel burn) and remove outlier laps (safety car periods, traffic, pit laps).

```python
import numpy as np
from scipy import stats

session = fastf1.get_session(2024, 'Bahrain', 'R')
session.load()
laps = session.laps

# Analyse degradation for all drivers on MEDIUM compound
medium_laps = laps[(laps['Compound'] == 'MEDIUM') &
                   (laps['IsAccurate'] == True) &
                   (laps['PitOutTime'].isna()) &
                   (laps['PitInTime'].isna())].copy()
medium_laps['LapTimeSec'] = medium_laps['LapTime'].dt.total_seconds()

# Remove outliers using IQR
Q1, Q3 = medium_laps['LapTimeSec'].quantile([0.25, 0.75])
IQR = Q3 - Q1
medium_laps = medium_laps[
    (medium_laps['LapTimeSec'] >= Q1 - 1.5 * IQR) &
    (medium_laps['LapTimeSec'] <= Q3 + 1.5 * IQR)
]

# Linear degradation rate: slope of lap time vs tyre age
slope, intercept, r, p, se = stats.linregress(
    medium_laps['TyreLife'], medium_laps['LapTimeSec']
)
print(f"MEDIUM degradation: {slope:.3f} s/lap (R²={r**2:.3f})")

# Fuel-corrected rate (subtract ~0.06 s/lap improvement from fuel burn)
fuel_corrected_deg = slope + 0.06  # Net tyre-only degradation
```

**Cliff detection**: Monitor a rolling 3-lap average of lap times within a stint. If the increase between consecutive windows exceeds **2× the linear degradation rate**, the tyre has likely hit its performance cliff — the point where grip drops non-linearly.

**What this informs**: Circuits with high degradation (>0.10 s/lap fuel-corrected) tend to reward multi-stop strategies and good tyre management. If a team shows low relative degradation, they gain a strategic advantage at similar high-deg circuits in future races.

### Sector-level performance breakdown

Sector times reveal where a car's strengths lie — aerodynamic efficiency in high-speed sectors versus mechanical grip in slow, technical sections.

```python
from fastf1 import utils

# Compare two drivers' fastest qualifying laps
session = fastf1.get_session(2024, 'Bahrain', 'Q')
session.load()

ver = session.laps.pick_driver('VER').pick_fastest()
lec = session.laps.pick_driver('LEC').pick_fastest()

# Sector-by-sector comparison
for s in ['Sector1Time', 'Sector2Time', 'Sector3Time']:
    delta = (lec[s] - ver[s]).total_seconds()
    leader = 'VER' if delta > 0 else 'LEC'
    print(f"{s}: {leader} faster by {abs(delta):.3f}s")

# Continuous delta trace over distance (FastF1's built-in utility)
delta_time, ref_tel, comp_tel = utils.delta_time(ver, lec)
# delta_time is an array: positive means ref (VER) is ahead
```

**Theoretical best lap** — the sum of a driver's best individual sectors across all qualifying attempts — reveals untapped potential:

```python
drv_laps = session.laps.pick_driver('VER')
theoretical = (drv_laps['Sector1Time'].min() +
               drv_laps['Sector2Time'].min() +
               drv_laps['Sector3Time'].min())
actual = drv_laps.pick_fastest()['LapTime']
gap = (actual - theoretical).total_seconds()
print(f"VER theoretical best: {theoretical}, actual: {actual}, gap: {gap:.3f}s")
```

Speed trap data (`SpeedI1`, `SpeedI2`, `SpeedFL`, `SpeedST`) supplements sector analysis by indicating straight-line speed and drag/power levels.

### Pace delta and gap evolution between drivers

Tracking how the gap between two drivers evolves lap by lap reveals the dynamics of an entire race — who was pushing, who was managing, and where the decisive moments occurred.

```python
session = fastf1.get_session(2024, 'Bahrain', 'R')
session.load()

d1 = session.laps.pick_driver('VER')[['LapNumber', 'LapTime']].copy()
d2 = session.laps.pick_driver('LEC')[['LapNumber', 'LapTime']].copy()
d1['Sec'] = d1['LapTime'].dt.total_seconds()
d2['Sec'] = d2['LapTime'].dt.total_seconds()

merged = d1.merge(d2, on='LapNumber', suffixes=('_VER', '_LEC'))
merged['LapDelta'] = merged['Sec_LEC'] - merged['Sec_VER']  # Positive = VER faster
merged['CumulativeGap'] = merged['LapDelta'].cumsum()
```

**Stint-adjusted pace** is more informative than raw averages. Compute mean lap time per driver per stint, excluding pit-in and pit-out laps:

```python
for driver in ['VER', 'LEC', 'NOR']:
    drv = session.laps.pick_driver(driver)
    clean = drv[(drv['PitOutTime'].isna()) & (drv['PitInTime'].isna()) &
                (drv['IsAccurate'] == True)].copy()
    clean['Sec'] = clean['LapTime'].dt.total_seconds()
    for stint in sorted(clean['Stint'].dropna().unique()):
        stint_laps = clean[clean['Stint'] == stint]
        compound = stint_laps['Compound'].iloc[0]
        avg = stint_laps['Sec'].mean()
        print(f"{driver} Stint {int(stint)} ({compound}): {avg:.3f}s")
```

### Pit stop strategy analysis

Pit strategy determines race outcomes as much as raw pace. The key questions: when did each driver stop, what compounds did they use, and did any undercut or overcut attempts succeed?

**Visualising team strategies** (adapted from FastF1's official example):

```python
import fastf1.plotting
import matplotlib.pyplot as plt

session = fastf1.get_session(2024, 'Bahrain', 'R')
session.load()

stints = session.laps[['Driver', 'Stint', 'Compound', 'LapNumber']]
stints = stints.groupby(['Driver', 'Stint', 'Compound']).count().reset_index()
stints.rename(columns={'LapNumber': 'StintLength'}, inplace=True)

fig, ax = plt.subplots(figsize=(8, 12))
drivers = [session.get_driver(d)['Abbreviation'] for d in session.drivers]

for driver in drivers:
    drv_stints = stints[stints['Driver'] == driver]
    left = 0
    for _, row in drv_stints.iterrows():
        color = fastf1.plotting.get_compound_color(row['Compound'], session=session)
        ax.barh(driver, row['StintLength'], left=left, color=color, edgecolor='black')
        left += row['StintLength']

ax.set_xlabel('Lap Number')
ax.invert_yaxis()
plt.title('Tyre Strategy')
plt.tight_layout()
plt.show()
```

**Detecting undercuts**: An undercut occurs when a driver pits 1–3 laps before a rival and uses the fresh-tyre pace advantage on the out-lap to jump ahead. To detect this programmatically, compare pit stop laps between pairs of drivers who were close on track, then check if their relative positions changed:

```python
def detect_undercut(session, d1_code, d2_code):
    d1 = session.laps.pick_driver(d1_code)
    d2 = session.laps.pick_driver(d2_code)
    d1_pits = d1[d1['PitInTime'].notna()]['LapNumber'].tolist()
    d2_pits = d2[d2['PitInTime'].notna()]['LapNumber'].tolist()

    for p1 in d1_pits:
        for p2 in d2_pits:
            if 0 < p2 - p1 <= 3:  # d1 pitted 1-3 laps earlier
                # Check position swap
                pos_before = d1[d1['LapNumber'] == p1 - 1]['Position'].values
                pos_after = d2[d2['LapNumber'] == p2 + 1]['Position'].values
                print(f"Potential undercut by {d1_code}: "
                      f"pitted lap {p1}, {d2_code} pitted lap {p2}")
```

### Safety car and VSC impact analysis

Safety car periods compress the field and give free pit stops to well-positioned drivers. FastF1 provides two detection methods:

```python
# Method 1: Race control messages
rcm = session.race_control_messages
sc_msgs = rcm[rcm['Message'].str.contains('SAFETY CAR|VSC', na=False)]
print(sc_msgs[['Time', 'Message', 'Lap']])

# Method 2: TrackStatus codes on each lap
# '1'=Clear, '2'=Yellow, '4'=Safety Car, '5'=Red Flag, '6'=VSC, '7'=VSC Ending
sc_laps = session.laps[session.laps['TrackStatus'].str.contains('4|6', na=False)]
```

**Analysing who benefited**: During a safety car, drivers who hadn't yet pitted get a "free" stop (the time loss is greatly reduced since the field is slowed). To quantify this:

```python
def sc_beneficiaries(session, sc_lap_start, sc_lap_end):
    results = []
    for driver in session.drivers:
        drv = session.laps.pick_driver(driver)
        abbr = session.get_driver(driver)['Abbreviation']
        sc_range = drv[(drv['LapNumber'] >= sc_lap_start) &
                       (drv['LapNumber'] <= sc_lap_end)]
        pitted = sc_range['PitInTime'].notna().any()
        results.append({'Driver': abbr, 'PittedDuringSC': pitted})
    return pd.DataFrame(results)
```

Drivers who pitted during the SC window typically gain **18–22 seconds** relative to a normal green-flag stop, depending on pit lane length.

### Driver and team consistency metrics

Consistency — the ability to deliver similar lap times repeatedly — separates the best drivers and is one of the most transferable metrics across circuits.

```python
import seaborn as sns

def consistency_report(session, top_n=10):
    drivers = session.drivers[:top_n]  # Top finishers
    metrics = []
    for d in drivers:
        drv = session.laps.pick_driver(d).pick_quicklaps()
        if drv.empty:
            continue
        times = drv['LapTime'].dt.total_seconds()
        abbr = session.get_driver(d)['Abbreviation']
        metrics.append({
            'Driver': abbr,
            'Mean': times.mean(),
            'Std': times.std(),
            'IQR': times.quantile(0.75) - times.quantile(0.25),
            'CV%': (times.std() / times.mean()) * 100,
            'CleanLaps': len(times)
        })
    return pd.DataFrame(metrics).sort_values('Mean')
```

**Key benchmarks**: Elite drivers typically show a standard deviation of **0.3–0.5 seconds** on clean race laps. A coefficient of variation below **0.5%** indicates exceptional consistency. The IQR (interquartile range) is more robust to outliers than standard deviation and captures the driver's "core" pace window.

**Violin plots** overlay lap distributions per driver with compound information, making it easy to spot who was fast _and_ consistent. FastF1's official examples include a violin plot recipe using seaborn:

```python
driver_laps = session.laps.pick_drivers(session.drivers[:10]).pick_quicklaps()
driver_laps['LapTimeSec'] = driver_laps['LapTime'].dt.total_seconds()
order = [session.get_driver(d)['Abbreviation'] for d in session.drivers[:10]]

fig, ax = plt.subplots(figsize=(12, 5))
sns.violinplot(data=driver_laps, x='Driver', y='LapTimeSec',
               order=order, inner=None, density_norm='area',
               palette=fastf1.plotting.get_driver_color_mapping(session=session))
```

---

## 4. Predicting competitiveness at the next race

The shift from post-race analysis to prediction requires distinguishing **what transfers** from one race to the next and **what is circuit-specific**. No model can predict safety cars, mechanical failures, or weather — but a structured approach can establish a useful baseline ranking.

### Which signals carry forward and which don't

**Transferable across circuits** (carry-forward signals):

- Driver consistency metrics (standard deviation, CV%)
- Team pit stop execution speed and reliability
- Qualifying-to-race conversion rate (does grid position translate to points?)
- Driver Elo ratings and rolling form (last 3–5 races)
- Relative pace to teammate (indicates driver skill independent of car)

**Circuit-dependent** (must be recalibrated per track):

- Raw lap times and sector times
- Tyre degradation rates (surface, temperature, and layout all affect this)
- Top speed / straight-line performance
- DRS effectiveness and overtaking frequency
- Safety car probability (street circuits see SC in ~40–60% of races vs ~20% on permanent tracks)

**Calculating rolling form with FastF1:**

```python
def rolling_form(year, driver_code, n_races=5):
    """Compute rolling average finish position over last N races."""
    fastf1.Cache.enable_cache('f1_cache')
    schedule = fastf1.get_event_schedule(year)
    positions = []

    for _, event in schedule.iterrows():
        try:
            sess = fastf1.get_session(year, event['RoundNumber'], 'R')
            sess.load(telemetry=False, weather=False)
            drv = sess.results[sess.results['Abbreviation'] == driver_code]
            if not drv.empty:
                positions.append(float(drv['Position'].values[0]))
        except Exception:
            continue

    if len(positions) >= n_races:
        return np.mean(positions[-n_races:])
    return np.mean(positions) if positions else None
```

For cross-circuit comparisons, **normalise pace as a percentage of the leader** rather than using raw seconds. This accounts for track length and speed differences. An even more robust approach uses **symmetric percent difference**: `100 × (driver_time - leader_time) / ((driver_time + leader_time) / 2)`.

### Classifying circuits to map performance across tracks

Circuits cluster into recognisable types. A data-driven approach using features like track length, number of turns, corner speed profile, elevation change, and DRS zone count produces roughly **five clusters** when applying k-means:

- **Night/desert races** — Bahrain, Lusail, Yas Marina, Las Vegas: warm conditions, big straights, smooth surfaces
- **Fast street circuits** — Jeddah, Baku, Miami, Marina Bay: walls close, low grip, high SC probability
- **Tight/low-overtaking** — Monaco, Hungaroring: qualifying-dominant, mechanical grip critical
- **Classic high-speed** — Silverstone, Spa, Suzuka, Barcelona, COTA: flowing corners, elevation, balanced aero demands
- **Straight-line speed dominant** — Monza, Montreal, Red Bull Ring, Mexico, Albert Park: big braking zones, power-sensitive

**Using this for prediction**: If the most recent race was at Spa (Cluster 3) and the next race is Zandvoort (Cluster 4), you weight recent form heavily but discount sector-specific gains. If consecutive races share a cluster (e.g., Bahrain → Jeddah), historical performance at similar tracks becomes a stronger predictor.

To build the historical baseline for the upcoming circuit:

```python
# Get all past races at a circuit
from fastf1.ergast import Ergast
ergast = Ergast()

# Historical results at Monza
results = ergast.get_race_results(circuit='monza', limit=1000)
# Filter to recent seasons for relevance
recent = [r for r in results.content if int(r['season'].iloc[0]) >= 2020]
```

### Building a baseline prediction model

The model combines three signal types: **recent form** (rolling last N races), **circuit-specific history** (past results at the upcoming track or similar tracks), and **strategy/execution metrics** (pit stop consistency, tyre management).

**Weighted scoring approach** (no ML required):

```python
def predict_competitiveness(driver_data, next_circuit_id, next_circuit_cluster,
                            weights=None):
    """
    Score each driver's expected competitiveness for the next race.
    Returns a score from 0 to 1, where higher = more competitive.
    """
    if weights is None:
        weights = {
            'recent_form': 0.40,
            'circuit_history': 0.25,
            'cluster_form': 0.15,
            'pit_consistency': 0.10,
            'quali_conversion': 0.10,
        }

    # Recent form: rolling avg finish position (last 5 races), inverted
    recent_form = 1 - (driver_data['rolling_avg_finish_5'] / 20)

    # Circuit history: avg finish at this specific circuit (last 3 visits)
    circuit_races = driver_data[driver_data['circuit_id'] == next_circuit_id]
    if len(circuit_races) >= 2:
        circuit_history = 1 - (circuit_races['finish_position'].mean() / 20)
    else:
        circuit_history = recent_form  # Fallback if no history

    # Cluster form: avg finish at circuits in the same cluster this season
    cluster_races = driver_data[driver_data['circuit_cluster'] == next_circuit_cluster]
    cluster_form = (1 - (cluster_races['finish_position'].mean() / 20)
                    if len(cluster_races) > 0 else recent_form)

    # Pit consistency: lower std of pit stop durations = better
    pit_score = max(0, 1 - driver_data['pit_stop_std'].mean() / 2)

    # Qualifying conversion: avg(grid_pos - finish_pos), positive = gains places
    conv = driver_data['grid_pos'].mean() - driver_data['finish_position'].mean()
    quali_conversion = 0.5 + (conv / 20)  # Center at 0.5

    score = (weights['recent_form'] * recent_form +
             weights['circuit_history'] * circuit_history +
             weights['cluster_form'] * cluster_form +
             weights['pit_consistency'] * pit_score +
             weights['quali_conversion'] * quali_conversion)
    return score
```

**Gradient boosting approach** (for those wanting ML):

```python
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import cross_val_score

features = [
    'grid_position',            # If predicting post-qualifying
    'rolling_avg_finish_5',     # Recent form
    'rolling_avg_finish_3',     # Short-term form
    'circuit_avg_finish',       # Historical circuit performance
    'circuit_cluster',          # Circuit type encoding
    'constructor_points_pct',   # Constructor strength
    'quali_delta_pct',          # Qualifying gap to pole (%)
    'avg_pit_stop_time',        # Pit crew performance
    'tyre_deg_relative',        # Tyre management vs field
    'dnf_rate',                 # Reliability
]

model = GradientBoostingRegressor(
    n_estimators=200, learning_rate=0.05, max_depth=3,
    subsample=0.8, random_state=42
)
scores = cross_val_score(model, X_train[features], y_train,
                         cv=5, scoring='neg_mean_absolute_error')
print(f"MAE: {-scores.mean():.2f} positions")
```

Research shows that **~88% of variance in race results** comes from the constructor (car performance), making constructor strength the dominant feature. Grid position alone correlates at **r ≈ 0.6–0.8** with finishing position. Published models achieve roughly **60–70% accuracy** for podium prediction and a mean absolute error of **2–4 positions** for finishing order.

**Elo ratings** provide an elegant alternative. Treat each race as a round-robin tournament where every driver is compared pairwise. After each race, update ratings with a K-factor proportional to the result:

```python
def update_elo(ratings, race_results, K=32):
    drivers = race_results['driver'].tolist()
    positions = race_results['position'].tolist()
    new_ratings = ratings.copy()

    for i in range(len(drivers)):
        for j in range(i + 1, len(drivers)):
            exp_i = 1 / (1 + 10 ** ((ratings.get(drivers[j], 1500) -
                                       ratings.get(drivers[i], 1500)) / 400))
            actual_i = 1.0 if positions[i] < positions[j] else 0.0
            adj = K * (actual_i - exp_i) / len(drivers)
            new_ratings[drivers[i]] = new_ratings.get(drivers[i], 1500) + adj
            new_ratings[drivers[j]] = new_ratings.get(drivers[j], 1500) - adj
    return new_ratings
```

### What the model cannot account for

Five structural limitations bound any F1 prediction model:

- **Mid-season upgrades** can shift a team's competitiveness by 0.3–0.5 seconds in a single weekend. Rolling form assumes gradual evolution, so a step-change upgrade will be mis-estimated until the window catches up.
- **Street circuits** (Monaco, Singapore, Baku) produce outlier results due to near-impossible overtaking, higher safety car probability, and wall proximity. Models trained predominantly on permanent circuits underperform here.
- **Small sample sizes** early in the season mean rolling averages are unstable. With fewer than 3 races of data, fall back to prior-season form or preseason testing pace.
- **Driver transfers** break historical continuity. When a driver changes teams (as Hamilton did to Ferrari in 2025), their personal historical data at a circuit is less relevant because ~88% of performance comes from the car.
- **Regulation changes** (like the 2026 power unit regulations) effectively reset the competitive order. Historical constructor ratings become unreliable in year-one of a new regulation cycle.

---

## 5. A lightweight Streamlit dashboard in under 100 lines

**Streamlit** is the recommended framework for this use case. It requires zero frontend knowledge, integrates natively with pandas and matplotlib, offers **free cloud deployment** via Streamlit Cloud, and has strong community adoption in the F1 analytics space (multiple production dashboards exist).

**Plotly Dash** is the more powerful alternative if you need callback-based interactivity for many concurrent users, but it requires understanding HTML layouts and callback decorators — significantly more setup for the same result. For an educational, prototype-first workflow, Streamlit wins.

**Minimal working dashboard:**

```python
import streamlit as st
import fastf1
import fastf1.plotting
import matplotlib.pyplot as plt
import pandas as pd

st.set_page_config(page_title="F1 Race Analysis", layout="wide")
fastf1.Cache.enable_cache('f1_cache')

# Sidebar controls
st.sidebar.title("🏎️ F1 Analysis")
year = st.sidebar.selectbox("Season", [2025, 2024, 2023])
schedule = fastf1.get_event_schedule(year)
event_name = st.sidebar.selectbox("Grand Prix", schedule['EventName'].tolist())
session_type = st.sidebar.selectbox("Session", ['R', 'Q', 'FP1', 'FP2', 'FP3'])

@st.cache_data(ttl=3600)
def load_session(y, e, s):
    sess = fastf1.get_session(y, e, s)
    sess.load(telemetry=False)
    return sess

session = load_session(year, event_name, session_type)
st.header(f"{event_name} {year} — {session_type}")

# Results table
col1, col2 = st.columns(2)
with col1:
    st.subheader("Results")
    results = session.results[['Abbreviation', 'Position', 'TeamName',
                                'GridPosition', 'Status']].copy()
    st.dataframe(results, use_container_width=True)

# Lap time distribution
with col2:
    st.subheader("Lap Time Distribution")
    top_drivers = session.drivers[:10]
    laps = session.laps.pick_drivers(top_drivers).pick_quicklaps()
    laps['LapTimeSec'] = laps['LapTime'].dt.total_seconds()

    fig, ax = plt.subplots(figsize=(10, 5))
    order = [session.get_driver(d)['Abbreviation'] for d in top_drivers]
    laps.boxplot(column='LapTimeSec', by='Driver', ax=ax)
    ax.set_title('Lap Times')
    ax.set_ylabel('Seconds')
    st.pyplot(fig)

# Strategy visualization
st.subheader("Tyre Strategy")
stint_data = session.laps[['Driver', 'Stint', 'Compound', 'LapNumber']]
stint_data = stint_data.groupby(['Driver', 'Stint', 'Compound']).count().reset_index()
stint_data.rename(columns={'LapNumber': 'Length'}, inplace=True)
st.dataframe(stint_data.pivot_table(index='Driver', columns='Stint',
             values='Compound', aggfunc='first'), use_container_width=True)
```

Run locally with `streamlit run app.py`. Deploy for free by pushing to GitHub and connecting to [share.streamlit.io](https://share.streamlit.io).

**Recommended multi-page structure** for a complete analysis dashboard:

- **Page 1 — Season Overview**: Standings, team form trend lines, upcoming race info
- **Page 2 — Race Analysis**: Results, position progression, tyre strategy timeline, lap time distributions
- **Page 3 — Next Race Prediction**: Model output table, confidence ranges, circuit characteristics card, historical performance at that track
- **Page 4 — Deep Dive**: Telemetry comparison, head-to-head teammate analysis, degradation curves

For caching efficiency, the proven pattern from community projects is to create **three loader functions**: a full telemetry loader (for deep dives), a light loader without telemetry (for results and summaries), and a weather-only loader (for strategy overlays). This avoids loading 200+ MB of telemetry when you only need lap times.

---

## Conclusion

The free F1 data ecosystem has matured significantly. **FastF1 is the backbone** — its pandas-native API, 30 Hz telemetry, and built-in plotting make it the obvious starting point for any analysis. **OpenF1 fills gaps** with REST accessibility, overtake data, and team radio. **Jolpica-F1 extends the timeline** back to 1950 for historical context. Together, they're sufficient for professional-grade analysis without spending a penny.

The most actionable analytical techniques are **tyre degradation curves** (they directly inform strategy expectations), **stint-adjusted pace deltas** (they reveal true relative performance), and **consistency metrics** (they're the most circuit-agnostic signal). For prediction, a weighted scoring model combining rolling form (40%), circuit history (25%), cluster performance (15%), and execution metrics (20%) provides a strong baseline — especially when supplemented with Elo ratings that naturally capture momentum. The key insight from academic research is that **constructor strength explains ~88% of variance**, so getting the car ranking right matters far more than any individual driver metric.

Start simple. Load one race with FastF1, compute degradation slopes and pace deltas, visualise the strategy chart, and compare your findings to post-race media narratives. That feedback loop — data versus narrative — is where genuine analytical intuition develops.
