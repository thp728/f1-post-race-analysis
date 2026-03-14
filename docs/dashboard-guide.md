# Dashboard Reading Guide

How to interpret every chart, table, and metric in the F1 Post-Race Analysis dashboard.

---

## Navigation

The dashboard has **three pages**, accessible from the left sidebar:

1. **Race Analysis** — deep-dive into a single race
2. **Predictions** — predicted finishing order for the next race
3. **Season Trends** — how the season has unfolded so far

The **sidebar** lets you select a season, Grand Prix, and session type (Race, Qualifying, FP1/FP2/FP3). All pages respond to these selectors.

---

## Page 1: Race Analysis

### Results Table

| Column | What it means |
|---|---|
| Driver | Driver name |
| Team | Constructor |
| Grid | Starting position (P1 = pole) |
| Finish | Final classified position |
| Status | "Finished", or reason for retirement (e.g. "Collision", "Engine") |
| Points | Championship points scored |

**What to look for:** Large differences between Grid and Finish indicate a driver who gained or lost a lot of positions. A "DNF" (Did Not Finish) in Status explains a missing position in the standings.

---

### Position Chart

A line per driver showing their **race position on every lap**.

- **X-axis:** Lap number (1 = first lap after the start)
- **Y-axis:** Position (P1 is at the top, P20 at the bottom)
- Hover over any point to see the exact lap and position.

**What to look for:**
- A sudden jump upward (toward P1) = a position gain — likely an overtake or a pit stop by a rival
- A sudden drop = a position loss — overtaken on track, or the driver pitted while others hadn't yet
- A cluster of lines converging at the same lap = everyone pitting around the same time (often a safety car)
- Flat lines = a driver is holding position, no changes happening

---

### Lap Time Distribution

A box/violin plot showing the **spread of clean lap times** for the top 10 drivers.

- **X-axis:** Driver
- **Y-axis:** Lap time in seconds
- The thick bar in the middle of each box is the **median** — the typical lap time for that driver
- The box itself spans the middle 50% of laps (the "interquartile range")
- The lines extending out show the full range, and dots are outliers

Pit laps, out-laps, and any lap slower than 107% of the fastest lap are removed before plotting, so you're seeing representative race pace only.

**What to look for:**
- A low median = fast overall pace
- A narrow box = very consistent driver (laps were similar to each other)
- A wide box or many outliers = variable pace (could be traffic, tyre issues, or pushing in certain phases)
- Two drivers with the same median but different box widths: similar speed, but one was more consistent

---

### Tyre Strategy

A horizontal bar chart showing each driver's **tyre stints** across the race.

- Each coloured bar segment = one stint on a particular tyre compound
- Bar length = how many laps that stint lasted
- **Colours:** Red = Soft, Yellow = Medium, White/Grey = Hard, Green = Intermediate, Blue = Wet

**What to look for:**
- Drivers with more segments = more pit stops (more complex strategy)
- A very long bar on one compound = that driver committed to that tyre for many laps
- If most drivers show the same pattern, there was a dominant strategy that race
- Outliers who used a different compound sequence may have been gambling on a strategy advantage

---

### Tyre Degradation

A scatter plot with a regression line per driver showing how **lap times get slower as tyres age**.

- **X-axis:** Tyre life — how many laps the current tyre set has been on the car (lap 1 of a stint = fresh tyre)
- **Y-axis:** Lap time in seconds
- Each dot = one clean lap; the line is the mathematical best-fit trend

Below the chart, a table shows the calculated numbers:

| Column | What it means |
|---|---|
| driver | Driver name |
| compound | Tyre type (SOFT/MEDIUM/HARD) |
| slope | How much slower (in seconds) the driver gets per lap of tyre age |
| intercept | The predicted lap time on a fresh tyre (lap 0 of the stint) |
| r_squared | How well the line fits the data (0–1; closer to 1 = cleaner trend) |
| fuel_corrected_slope | Slope after removing ~0.06 s/lap natural improvement from fuel burning off |
| n_laps | Number of clean laps used in the calculation |

**What to look for:**
- A **slope of 0.05** means the driver loses ~0.05 seconds every lap — after 20 laps that's 1 second slower than fresh
- A **steep negative slope** (e.g. -0.1 or worse) = high degradation, tyres fell off quickly
- A **flat slope** near 0 = very low degradation, tyres lasted well
- **r_squared below 0.5** means the trend is noisy — maybe traffic, safety car laps, or variable pace disrupted the pattern; treat that slope with caution
- **fuel_corrected_slope** is the more accurate number: fuel weight makes the car faster as it burns off, so the raw slope flatters the tyres slightly. The corrected slope isolates true tyre wear.

---

### Stint-Adjusted Pace

A table showing the **average lap time per driver per stint**, so you can compare pace across different tyre stints fairly.

| Column | What it means |
|---|---|
| driver | Driver name |
| stint | Stint number (1 = first stint, 2 = second stint, etc.) |
| compound | Tyre compound used in that stint |
| mean_pace_sec | Average clean lap time during that stint, in seconds |
| n_laps | How many clean laps are included in the average |

**What to look for:**
- Compare drivers who ran the same compound in the same stint range — this shows who had better raw pace on that tyre
- A driver with a low mean_pace on the Hard tyre but high on the Soft had compound-specific pace differences
- Low n_laps (e.g. 2 or 3) means the average isn't very reliable — that stint was short or had many excluded laps

---

### Pace Delta

A line chart comparing **two selected drivers' gap** lap by lap.

- **X-axis:** Lap number
- **Y-axis:** Gap in seconds (positive = Driver 1 is ahead on cumulative race time; negative = Driver 2 is ahead)
- The line shows how the gap between the two drivers evolved over the entire race

**What to look for:**
- A line moving upward = Driver 1 is pulling away from Driver 2 lap by lap
- A line moving downward = Driver 2 is catching up
- A sudden vertical jump = one driver pitted (their lap time for that lap was very long) — this is normal; the gap will usually recover over the following laps
- A flat line = both drivers lapping at the same pace, the gap holding steady
- The overall shape tells you whether the on-track positions were representative of their actual pace, or whether strategy (pit timing) created artificial gaps

---

### Sector Comparison

A grouped bar chart showing the **best sector time each driver achieved** across the whole session.

- Three bars per driver: Sector 1, Sector 2, Sector 3
- **Y-axis:** Sector time in seconds (shorter = faster)

Below the chart or alongside it you'll also see:

| Metric | What it means |
|---|---|
| theoretical_best | If a driver had combined their best S1, best S2, and best S3 in one single lap, this is how fast that lap would have been |
| actual_best | The driver's actual fastest lap of the session |
| gap | theoretical_best − actual_best: how much time the driver "left on the table" by not achieving all three best sectors in one lap |

**What to look for:**
- A short bar in one sector = the driver's strength (e.g. good in S1 but slower in S2)
- Compare sector profiles: two drivers with the same total lap time may have achieved it very differently (one strong in high-speed S1, the other in twisty S3)
- A large **gap** value means the driver had the pace for a faster lap but never put it all together in one lap (traffic, errors, or just didn't need to)

---

### Consistency Metrics

A horizontal bar chart showing how **consistent each driver's race pace was**.

- **X-axis:** Coefficient of Variation (CV%) — lower is more consistent
- **Y-axis:** Driver, sorted from most consistent (top) to least consistent (bottom)

The underlying table also shows:

| Column | What it means |
|---|---|
| mean_ms | Average clean lap time (milliseconds) |
| std_ms | Standard deviation — average amount each lap varied from the mean |
| iqr_ms | Interquartile range — the spread of the middle 50% of laps |
| cv_pct | CV% = (std_dev ÷ mean) × 100 — normalised consistency measure |
| clean_laps | Number of laps included |

**What to look for:**
- A **low CV%** (e.g. under 0.5%) = the driver was hitting very similar lap times each lap — controlled, methodical racing
- A **high CV%** = variable lap times — could be managing tyres deliberately, responding to traffic, or simply inconsistent driving
- Consistency is particularly valuable in long stints: a driver who laps within 0.3 s of themselves every lap is easier for the team to strategise around

---

### Safety Car / VSC

A text list of all Safety Car and Virtual Safety Car periods during the race, followed by a table of **drivers who pitted during those periods**.

- **SC (Safety Car):** A physical safety car enters the track, all drivers must slow and hold position. Gap between cars freezes.
- **VSC (Virtual Safety Car):** No physical car, but all drivers must meet a minimum lap time. Similar effect.

**Why pitting under a SC/VSC matters:** A pit stop normally costs about 20–25 seconds of track time. Under a SC/VSC, every driver is going slowly anyway — so the pit stop "costs" much less relative to rivals staying out. Teams that pit under SC effectively get a free (or cheap) tyre change.

**What to look for:**
- Drivers who pitted under SC and then gained positions = benefited from the timing
- Drivers who had just pitted before the SC appeared = unlucky, they paid full cost and missed the "free" stop
- If no one pitted under SC, teams may have judged their current tyres as sufficient to finish

---

### Undercut Detection

A list of detected **undercut manoeuvres** during the race.

An **undercut** is when a driver pits *before* a rival, gets fresh tyres, sets fast laps while the rival is still on worn tyres, and comes out of their own pit stop *ahead* of the rival. The rival then has to pit shortly after, but by that point the position has flipped.

Each detected undercut shows:
- **Who undercut whom** (the aggressor and the victim)
- **Which lap it happened on**
- **Position change:** e.g. P4 → P3 confirms it worked

**What to look for:**
- A successful undercut shows aggressive pit strategy paid off
- An attempted undercut that didn't change positions = either the rival pitted quickly enough to cover it, or the tyre delta wasn't big enough
- Multiple undercuts in one race = active strategic battle, teams reacting to each other in real time

---

### Pit Stop Times

A table of each driver's **pit stop performance**.

| Column | What it means |
|---|---|
| driver | Driver name |
| n_stops | Total number of pit stops made |
| mean_duration_sec | Average pit stop duration across all stops (seconds) |
| best_stop_sec | Fastest single pit stop (seconds) |

**What to look for:**
- Sub-2.5 second stops = excellent crew performance
- Large difference between best and mean = one stop was great, another went wrong (dropped wheel, slow lollipop, etc.)
- Higher n_stops = more complex strategy; this driver spent more time in the pit lane total
- Pit stop times feed into the prediction model's "pit consistency" score

---

## Page 2: Predictions

### Circuit Info

Shows the **circuit cluster** for the current race venue — a category used to group similar circuits together.

| Cluster | Circuits |
|---|---|
| Night/Desert | Bahrain, Saudi Arabia, Abu Dhabi, Las Vegas, Qatar |
| Fast Street | Baku, Miami, Singapore |
| Tight/Low Overtaking | Monaco, Hungary, Zandvoort |
| Classic High-Speed | Silverstone, Spa, Suzuka, Barcelona, COTA, Imola |
| Straight-Line Dominant | Monza, Montreal, Austria, Mexico City, Australia, Brazil |

**Why it matters:** Drivers tend to have characteristic strengths at certain circuit types. A driver who always does well in Monaco's narrow, technical layout often repeats that at Zandvoort. The cluster form score captures this pattern.

---

### Predicted Finishing Order

A table ranking drivers by their **composite prediction score** for the next race.

| Column | What it means | Weight |
|---|---|---|
| rank | Predicted finishing position | — |
| driver | Driver name | — |
| score | Overall prediction score (0–1; higher = predicted to finish higher) | — |
| recent_form | Normalised score based on average finish over last 5 races | 40% |
| circuit_history | Normalised score based on average finish at this specific circuit (last 3 visits) | 25% |
| cluster_form | Normalised score based on average finish at circuits in the same cluster this season | 15% |
| pit_consistency | How consistent the driver's pit stops have been (lower std dev = higher score) | 10% |
| quali_conversion | How many positions the driver typically gains or loses from grid to finish | 10% |

**Interpreting scores:** All component scores are normalised to 0–1 within the current driver pool, so a score of 0.9 means this driver is near the top of the field on that metric. The overall score is a weighted sum.

**Known limits:** The model does not account for mid-season car upgrades, driver team changes, or regulation resets. Early in the season (fewer than 3 races), scores are unreliable due to limited data. Street circuits tend to produce more unexpected results than the model predicts.

---

### Elo Ratings

A table showing each driver's **Elo rating** — a number representing their competitive strength relative to the field.

**How Elo works:**
- Everyone starts at a baseline of **1500**
- After each race, drivers gain or lose points based on how many head-to-head matchups they won (finishing ahead of) versus lost (finishing behind)
- Beating a high-rated driver earns more points than beating a low-rated one
- The **K-factor of 32** controls how quickly ratings can shift per race — higher K = faster adaptation

**What to look for:**
- Ratings above 1550 = consistently beating their peers
- Ratings below 1450 = underperforming relative to the field
- Large jumps in rating between races = a standout performance or a run of bad results
- The Elo rating is a rolling, self-correcting measure — it smooths out one-off anomalies over time

---

## Page 3: Season Trends

### Championship Points Progression

A line chart showing **cumulative championship points** for each driver across the season.

- **X-axis:** Round number (1 = first race, 2 = second, etc.)
- **Y-axis:** Total points accumulated so far
- Each line = one driver

**What to look for:**
- A steep upward slope = consistently scoring big points
- A flat section = a run of retirements or poor results
- Crossing lines = a driver overtaking another in the championship
- The gap between the top two lines at the rightmost point is the current championship margin

---

### Constructor Points Progression

Same as above, but each line represents a **team** (both drivers' points combined per round).

**What to look for:**
- The constructor championship is often decided by reliability as much as pace — a team that scores points from both drivers every race will pull away from a team relying on one star driver
- A sudden plateau for a team often means one driver had a run of DNFs

---

### Rolling Form

A line chart showing each driver's **5-race rolling average finishing position**.

- **X-axis:** Round number
- **Y-axis:** Average finish position over the previous 5 races (note: lower number = better finish)
- Only the top 10 championship contenders are shown

**What to look for:**
- A line trending downward = the driver is on a run of improving results
- A line trending upward = recent form is deteriorating
- Sharp changes = a single dominant win or DNF skewing the short-term average
- This is the metric most predictive of near-term performance in the model (40% weight in the prediction score)

---

### Finishing Positions Heatmap

A grid showing every driver's **finishing position at every round** of the season.

- **Rows:** Drivers (sorted by total season points, highest at top)
- **Columns:** Round number
- **Cell colour:** Green = good result (P1 = darkest green), Red = bad result (P20 = darkest red); grey = DNS/DNF
- **Number inside each cell:** The actual finishing position

**What to look for:**
- Mostly green rows = consistently fast drivers
- Mostly red rows = struggling all season
- A single red cell in a green row = a one-off bad race (reliability failure or incident)
- Columns with many red cells = chaotic race (rain, first-lap incidents, safety cars causing strategy divergence)
- Consistency across a driver's row tells you more than any single result — a driver who finishes P3–P5 every race is often more valuable to a team than one who alternates P1 and P15

---

## Quick-Reference Glossary

| Term | Definition |
|---|---|
| **Stint** | A continuous run on one set of tyres between pit stops. Stint 1 = from race start to first pit, Stint 2 = first to second pit, etc. |
| **Tyre Life** | How many laps the current tyres have been on the car. Lap 1 of a stint = fresh tyres. |
| **Clean Lap** | A lap used in analysis — pit laps, out-laps (first lap of a stint), in-laps (last lap before pitting), and laps over 107% of the fastest are excluded. |
| **Degradation Slope** | How many seconds per lap a driver gets slower as the tyres age. E.g. 0.07 s/lap = 1.4 s slower after 20 laps. |
| **Fuel Correction** | Cars burn ~1.5 kg of fuel per lap. Lighter cars are faster. We subtract ~0.06 s/lap improvement from raw degradation to isolate true tyre wear. |
| **Theoretical Best Lap** | The sum of a driver's best Sector 1, best Sector 2, and best Sector 3 times — even if they weren't in the same lap. It's the fastest they could theoretically have gone. |
| **CV% (Coefficient of Variation)** | Standard deviation ÷ mean × 100. A normalised consistency measure that allows comparison across drivers regardless of their raw pace. Lower = more consistent. |
| **Elo Rating** | A competitive ranking that adjusts based on head-to-head race outcomes. Starting baseline is 1500. Higher = stronger performer relative to field. |
| **Circuit Cluster** | A grouping of circuits with similar characteristics (e.g. tight street circuits, high-speed tracks). Used to find form patterns at similar venues. |
| **Undercut** | When a driver pits before a rival, uses fresh-tyre speed to lap faster, and emerges from their own pit stop ahead of the rival. |
| **Overcut** | The opposite: staying out longer than a rival who has pitted, using the fresh-tyre phase they're now in to go faster and emerge ahead when you eventually do pit. |
| **SC (Safety Car)** | A physical safety car deployed on track after an incident. All cars must slow and hold position. Gaps between cars freeze. |
| **VSC (Virtual Safety Car)** | Like a safety car but managed electronically — no physical car. Drivers must meet a minimum lap time. |
| **r² (R-Squared)** | A measure of how well a regression line fits the data. Range 0–1; values above 0.7 indicate a clear trend; below 0.4 the relationship is noisy and the slope should be treated cautiously. |
| **Grid** | The starting position on the grid, determined by qualifying. P1 = pole position. |
