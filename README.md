# Shot Predictor

Predicts which shot a batter is likely to play to a given delivery, and shows where that batter scores their runs with each shot.

Set the format, batter, bowler type, and where the ball pitched (click the pitch map or use the arrow keys). The app returns a confidence % for 15 shot types, plus a scoring wheel for each of the top 3 shots, built from that batter's ball-by-ball history.

Covers **T20, ODI and Test** cricket. It is trained on about 1.6M balls with line, length and shot recorded.

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
| T20 | 33.8% | 65.1% | 2.005 | 61.4% |
| ODI | 37.3% | 73.4% | 1.788 | 70.8% |
| Test | 45.3% | 79.2% | 1.612 | 77.0% |

Top-3 means the actual shot was one of the model's three highest-rated shots. The baseline is the batter's historical shot mix for that line and length, smoothed towards the mix for all batters.

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

This takes a few minutes. It writes `model.txt`, `meta.json` and `zones.json`, and prints accuracy for each format along with a calibration table.

Run the app:

```bash
.venv/bin/uvicorn app:app --port 8000
```

Then open http://localhost:8000.

Run the checks:

```bash
.venv/bin/python test_predict.py
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

## Project layout

```
features.py      loading, cleaning, vocabulary mapping, feature building (shared by train and serve)
train.py         time-split training, per-format metrics, calibration check, writes the model
zones.py         per-batter scoring zones for each shot -> zones.json
app.py           FastAPI: POST /predict, GET /options, serves the page
index.html       the single-page frontend (no build step, no dependencies)
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
- `batter_known`: false if the batter isn't in the data. The prediction is then for a typical batter of that hand.
- `variation_used`: whether the variation input was applied (T20 only).

`GET /options` lists the allowed values for each field, and the batters with their batting hand.

## Limitations

- **No ball speed or swing/turn amount:** none of the sources record them. Bowler type (8 groups) stands in for them.
- **No field placements.**
- **Different taggers:** the two sources describe deliveries differently. A `source` feature absorbs this. For prediction, T20 uses `odata` and ODI/Test use the ball-by-ball files.
- **Variation for T20 only.**
- **Over logging in the app** keeps the same batter on strike after an odd number of runs, and has no wicket button.
