# Shot Predictor

Predicts which shot a batter is likely to play to a given delivery, and shows where that batter scores their runs with each shot.

Set the format, batter, bowler type, and where the ball pitched (click the pitch map or use the arrow keys). The app returns a confidence % for 15 shot types, plus a scoring wheel for each of the top 3 shots, built from that batter's ball-by-ball history.

Covers **T20, ODI and Test** cricket. It is trained on about 1.6M balls with line, length and shot recorded.

The **Similar players** tab finds batters who play the same shots to the same deliveries, scores how alike they are (0–100), and explains where they match and where they differ.

The **Bowling plan** tab turns this around. For a batter, it recommends where to bowl in each phase (powerplay, middle, death) of an ODI or T20, and shows where not to bowl: the areas where he's strongest.

## How it works

- **Model:** a LightGBM multiclass classifier. Its predicted probabilities are the confidence % for each shot, and they're well calibrated (expected calibration error 0.025).
- **Inputs:**
  - **Delivery:** format, batter, batting hand, bowler type, line, length, and the earlier balls in the over (line, length, shot and runs for each).
  - **Situation:** over, innings, score, wickets, target, the batter's runs and balls faced.
  - **Conditions:** ground, day/night.
  - **Variation** (slower ball, googly, out-swinger…) is recorded only in the T20 data, so it's used only for T20.
- **Scoring wheels:** each shows the batter's runs from that shot across 8 fielding zones. When a batter has few runs from a shot, the wheel leans towards the average for all batters.

### Accuracy

Tested on the newest 20% of matches, which were held out of training (split by date):

| Format | Top-1 | Top-3 | Log-loss | Baseline top-3 |
|---|---|---|---|---|
| T20 | 33.6% | 65.3% | 1.995 | 61.4% |
| ODI | 37.3% | 73.4% | 1.787 | 70.8% |
| Test | 45.5% | 79.3% | 1.608 | 77.0% |

Top-3 means the actual shot was one of the model's three highest-rated shots. The baseline is the batter's historical shot mix for that line and length, smoothed towards the mix for all batters.

## Bowling plan

For each phase, the planner scores every combination of bowler type, line and length (8 × 5 × 5; full tosses excluded) with two extra models:
- **Runs model:** expected runs conceded off the ball, counting batter runs, wides and no-balls. It uses a LightGBM Poisson objective.
- **Wicket model:** the chance the ball dismisses the batter. Run-outs are excluded, because they aren't earned by the delivery.

There are two plans, each with a best and a worst case:

| Plan | Ranked by |
|---|---|
| **Fewest runs** | expected runs per over |
| **Runs + wickets** | net runs per over = runs conceded − (batter's average × wicket chance), i.e. counting the runs a wicket saves |

- **Bowler types** are ranked by the runs per over each type concedes against this batter when bowling its usual mix of lines and lengths. The top one is the recommendation, and any other type can be picked instead.
- **Best and worst deliveries** come from cells the batter has faced at least 20 times. Cells with less data are shown faded, since the model is mostly guessing there.
- **Situation assumed:** the typical first-innings state for each phase (median score, wickets, batter's runs and balls faced).

### Plan accuracy (held-out matches, ODI + T20)

| Model | Metric | Baseline | Model |
|---|---|---|---|
| Runs | Poisson deviance | 1.791 | **1.732** |
| Wicket | AUC | 0.610 | **0.642** |

The wicket model's AUC is well below 1 because wickets are hard to predict from a single ball.

**Plan check:** for batters with 300+ balls in the test period, the cells the model rated best actually conceded 1.16 runs a ball, against 1.43 in its worst cells (74 batter–format pairs). In a separate run on an earlier version of the runs model (batter runs only), best was lower than worst for 100% of ODI batters and 88% of T20 batters.

## Similar players

**Profile.** Each batter is described by his shot mix against 60 kinds of delivery: pace or spin × 5 lines × 6 lengths. Lines are relative to the batter, so left- and right-handers compare directly.

**Similarity.**
- For each delivery kind, take how the batter's shot mix differs from the average batter's (square-root / Hellinger scale, so rare shots like the sweep or ramp still count).
- Weight each delivery kind by how common it is and how much the batter has faced it.
- Similarity is the cosine between two batters' vectors, shown ×100.
- **Format segments.** The data is split into five segments: T20, ODI overs 1–10, 11–30 and 31–50, and Test. Each is centred on its own average before mixing, because the two data sources tag shots differently.
- **How much one segment counts toward another.** Segments of the same format pool fully. Across formats:

  | | T20 | ODI 1–10 | ODI 11–30 | ODI 31–50 | Test |
  |---|---|---|---|---|---|
  | **T20** | 1 | 0.85 | 0.30 | 0.80 | 0 |
  | **Test** | 0 | 0 | 0.15 | 0 | 1 |

  Other cross-format overlap, such as the same weakness in every format, already shows up in each format's own data.
- **Building a format's profile.** Each of the format's own segments borrows from the others by these weights. The pieces are then joined together, weighted by each segment's share of balls, so ODI death overs lean on T20 much more than ODI middle overs do.
- A batter is listed only with 300+ balls in that format, and profiled only with 200+ labelled balls overall.

**Similarity is a single number from 0 to 100.** To give it meaning, the app shows where a score sits among all pairs of batters in that format:

| Reference point | T20 | ODI | Test |
|---|---|---|---|
| Top 1% of all pairs | 42 | 43 | 43 |
| Top 5% of all pairs | 32 | 33 | 32 |
| Top 10% of all pairs | 26 | 27 | 27 |

**Validation:** each batter's matches are split at random into two halves. Does one half pick out the other?

| Format | Batters | Median rank | Closest match | Top 5 |
|---|---|---|---|---|
| T20 | 249 | 2 | 47% | 69% |
| ODI | 278 | 3 | 41% | 62% |
| Test | 244 | 3 | 41% | 59% |

**The report** for a pair covers:
- similarity against pace and spin separately;
- where they play alike (tendencies both have that differ from the average batter);
- where they differ (on balls both face often, the shot one plays more);
- a pitch-map heatmap of how differently they play each ball;
- runs per over and balls per wicket against pace and spin.

**Testing the bowling plan.** For each phase, the plan's best deliveries are checked against up to 8 similar batters (similarity at least the top-10% level for the format), using what actually happened when they faced those deliveries.

| Verdict | Condition |
|---|---|
| worked | ≤85% of his usual runs per over in that phase, or (in runs + wickets) a dismissal rate 1.3× his usual |
| didn't work | at or above his usual runs per over |
| partly worked | in between |

When a plan didn't work, the report names the shot that batter plays in those areas far more than the target batter does. Phase data falls back to all phases when a batter has fewer than 15 balls in those areas in that phase.

## Recency weighting

Recent balls count more, with a ball's weight halving every *half-life* years. The half-life is chosen by the data on each retrain: the shot model is fitted with no weighting and with 2, 3 and 5 years, and the fit that predicts the (later) validation matches best is kept.

| Half-life | Validation log-loss |
|---|---|
| none | 1.7285 |
| 2 years | 1.7245 |
| **3 years (chosen)** | **1.7229** |
| 5 years | 1.7241 |

The same weights are then used everywhere a batter is described:
- **All three models:** as sample weights.
- **Scoring zones and batting averages:** recent balls count more.
- **Similarity profiles:** weighted *within* each batter's career. His recent seasons shape his style, but his total evidence stays his real ball count, so retired players remain valid comparisons.
- **Balls-faced counts** (the "little data" warnings) stay raw.

Against the unweighted models on held-out matches:
- **Shot model:** log-loss improved from 1.820 to 1.815 (T20 2.005 → 1.995, Test 1.612 → 1.608).
- **Runs and wicket models:** within noise (1.728 → 1.732 and 0.645 → 0.642).

A 1-year half-life was tried too. It helped a simple per-batter check but made the models worse, because it effectively discards data older than a few seasons.

## Quick start

Requires Python 3.9+.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Put the three data files in `data/` (see below), then train:

```bash
.venv/bin/python train.py
```

This takes about 10 minutes. It writes `model.txt`, `runs_model.txt`, `wicket_model.txt`, `meta.json`, `zones.json` and `profiles.npz`, and prints accuracy for each format along with a calibration table.

Run the app:

```bash
.venv/bin/uvicorn app:app --port 8000
```

Then open http://localhost:8000.

Run the checks:

```bash
.venv/bin/python test_predict.py

node --test static/js/logic.test.mjs   # frontend helpers; needs Node 22+, no packages
```

## Data

| File | Formats | Notes |
|---|---|---|
| `data/odi_bbb-25.csv` | ODI, 2005–2025 | Ball by ball with line, length, shot and wagon zone. Line and length are recorded from 2014 on. |
| `data/test_bbb - 25.csv` | Test, 2005–2025 | Same schema as the ODI file. |
| `data/odata_full.csv` | T20, ODI, Test, domestic | Built from commentary. It has variation and fielding area. Its line/length/shot wording is mapped onto the vocabulary of the other two files. |

The data files are not in the repo (`data/` is gitignored). The trained `model.txt`, `meta.json` and `zones.json` are committed, so the app runs without the data. You only need the data to retrain.

### Cleaning

This runs every time the data is loaded (`features.load_all`):

- **Exact duplicates:** rows identical in every column are dropped (1,031 ODI, 596 Test, 5 `odata`).
- **Matches in two files:** `odata` fixtures that are already in the ODI/Test files are dropped (777 fixtures). They're matched on teams, format and start date. The ODI/Test version is kept because its match state is exact.
- **Undated rows:** `odata` rows with no date are dropped, because they can't be checked for duplicates or placed in the time split.
- **Innings with missing overs** are dropped, because the running totals rebuilt from them would be wrong.
- **Placeholder rows** in the Test file (only match/over/ball filled) are kept as unknown earlier balls in the over, but never trained on.
- **Running totals:** the source files' totals include the current ball, so they're converted to the state before the ball to avoid leaking the outcome.
- **Excluded from the model:** columns that describe what happened on the ball (runs, footwork, control, wagon zone). Wagon zone is used only for the scoring wheels.

### Replacing or adding a data source

Everything after loading works on one common table, so a new source only needs a loader:

1. **Write a loader** in `features.py`, next to `load_bbb` and `load_odata`. It maps the source's columns and wording onto the shared layout (`KEEP`):

   | Group | Columns |
   |---|---|
   | Match | `p_match`, `date`, `teams`, `format`, `source` |
   | Delivery | `line`, `length`, `bowl_style`, `variation` |
   | Batter | `bat`, `bat_hand` |
   | Pre-ball situation | `over`, `ball_no`, `runs`, `wkts`, `balls`, `balls_rem`, `target`, `bat_bf`, `bat_runs`, `inns` |
   | Outcomes | `shot`, `bat_run`, `bowl_run`, `bat_out`, `zone` |

   Vocabulary is mapped with small dicts, as `O_LINE`, `O_LENGTH` and `O_SHOT` do for `odata`. Earlier balls in the over come from `add_prev`.
2. **Add it to `load_all`,** and decide which source wins when the same match appears in two. The teams + format + date matcher in `load_odata` can be reused.
3. **Run `python train.py`.** Everything learned from data is recomputed and printed with its check:
   - recency half-life;
   - early stopping;
   - per-format accuracy against baselines, and the calibration table;
   - the plan check;
   - typical match state per phase, bowler-type delivery mixes, batting averages;
   - scoring zones, similarity profiles, reference points and the self-match validation.

   Then run `python test_predict.py`.

**Hand-set values** that stay the same unless you change them:
- the cross-format weights (`CROSS` in `similar.py`);
- the phase boundaries (`PHASES`);
- minimum-data thresholds (`MIN_BALLS`, `LOW_DATA`, …).

**New kinds of information** need more than a loader. Examples are ball speed, swing, exact pitch coordinates, over/around the wicket, or field settings. Each needs to be added to the feature lists (`CAT`/`NUM`), to `serve_row`, to the API request, and to the inputs on the page. Two parts also need a deliberate choice:
- **`plan.py`:** whether the plan searches over the new dimension, e.g. speed bands.
- **`similar.py`:** whether delivery types should be split by it.

Rough effort:

| New data | Effort |
|---|---|
| Another ball-by-ball file with line/length/shot | half a day for the loader, plus a 15-minute retrain |
| Ball-tracking data | a few days, including the UI |
| A live API such as Sportradar | 1–2 weeks: fetch and cache jobs plus a history backfill |

## Project layout

```
features.py      loading, cleaning, vocabulary mapping, feature building (shared by train and serve)
train.py         time-split training, per-format metrics, calibration check, writes the model
zones.py         per-batter scoring zones for each shot, and balls faced per cell -> zones.json
plan.py          the bowling plan search and scoring
similar.py       batter style profiles, similarity, reports, plan evaluation -> profiles.npz
app.py           FastAPI: POST /predict, /plan, /similar, /compare, GET /options, serves the page
static/          the frontend: plain HTML, CSS and ES modules. No build step, no dependencies
  index.html       markup
  styles.css       theme tokens and components
  js/logic.js      constants, state, pure helpers (no DOM, so it runs under node)
  js/ui.js         element builders, tooltip, batter picker
  js/charts.js     pitch map, wagon wheel, radar, difference map
  js/predict.js    Shot predictor tab
  js/plan.js       Bowling plan tab
  js/similar.js    Similar players tab
  js/main.js       startup and tab switching
  js/logic.test.mjs  tests for the pure helpers
test_predict.py  checks that predictions behave like cricket
```

## API

`POST /predict`

```json
{
  "format": "ODI",
  "batter": "Virat Kohli",
  "bowl_style": "right-arm fast",
  "line": "OUTSIDE_OFFSTUMP",
  "length": "GOOD_LENGTH",
  "over": 12,
  "runs": 68, "wkts": 1,
  "prev": [{"line": "ON_THE_STUMPS", "length": "FULL", "shot": "on_drive", "runs": 1}]
}
```

The response contains:
- `shots`: every shot with its %.
- `top`: the 3 most likely shots, each with its scoring-zone shares.
- `batter_known`: false if the batter isn't in the data. The prediction is then for a typical right-hander. Batting hand is never an input: it comes from the data, and a request that sends `bat_hand` is rejected.
- `variation_used`: whether the variation input was applied (T20 only).

`POST /plan` with `{"batter": "Virat Kohli", "format": "ODI", "bowl_style": null}` returns 3 phases. Each phase has both cases (`fewest_runs`, `runs_wickets`), and each case has:
- `bowlers`: the bowler types, ranked.
- `bowl_style`: the chosen type (the recommended one unless you pass `bowl_style`).
- `best` and `worst`: 3 cells each.
- `grid`: all 25 cells, with runs per over, wicket %, net runs per over, his usual shot, and balls faced there.

`POST /similar` with `{"batter", "format", "k"}` returns the most similar batters with score and balls, plus the format's `reference` points. `POST /compare` with `{"a", "b", "format"}` returns the full report. `/plan` responses also include `similar` and, per case, an `evaluation` against those batters.

`GET /options` lists the allowed values for each field, and the batters with their batting hand.

## Deploy (Google Cloud Run)

The `Dockerfile` serves the app with only the trained files (no training code, no raw data). Retraining means rebuilding and redeploying, because the models are baked into the image.

```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
gcloud run deploy shot-predictor --source . --region europe-west1 \
  --memory 1Gi --cpu 1 --min-instances 0 --max-instances 1 --cpu-boost --allow-unauthenticated
```

`--max-instances 1` caps cost and `--min-instances 0` means no charge while idle. Drop `--allow-unauthenticated` to keep the service private.

## Limitations

- **Bowling plans are ODI and T20 only** so far.
- **Plans assume a well-executed ball.** A planned yorker that goes wrong is recorded as a full toss, so yorkers look cheaper than they are in practice.
- **Plans use a typical situation** rather than a specific chase.

- **No ball speed or swing/turn amount:** none of the sources record them. Bowler type (8 groups) stands in for them.
- **No field placements.**
- **Different taggers:** the two sources describe deliveries differently. A `source` feature absorbs this. For prediction, T20 uses `odata` and ODI/Test use the ball-by-ball files.
- **Variation for T20 only.**
- **Over logging in the app** keeps the same batter on strike after an odd number of runs, and has no wicket button.
