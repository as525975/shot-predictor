import json
from pathlib import Path
from typing import List, Literal, Optional

import lightgbm as lgb
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from features import MAX_BALLS, SOURCE_FOR_FORMAT, build_features

HERE = Path(__file__).parent
model = lgb.Booster(model_file=str(HERE / 'model.txt'))
meta = json.loads((HERE / 'meta.json').read_text())
zones = json.loads((HERE / 'zones.json').read_text())


def scoring_zones(batter, shot, a=40):
    """Share of this batter's runs from this shot in each zone, smoothed toward everyone's (a = prior weight in runs)."""
    prior = zones['prior'].get(shot, [0] * len(zones['zones']))
    own = zones['batters'].get(batter, {}).get(shot, [0] * len(prior))
    pt, n = sum(prior) or 1, sum(own)
    share = [(c + a * p / pt) / (n + a) for c, p in zip(own, prior)]
    return {'runs': n, 'share': dict(zip(zones['zones'], (round(x, 3) for x in share)))}


class Prev(BaseModel):
    line: Optional[str] = None
    length: Optional[str] = None
    shot: Optional[str] = None
    runs: int = Field(0, ge=0, le=7)


class Ball(BaseModel):
    format: Literal['T20', 'ODI', 'Test']
    batter: str
    bowl_style: str
    line: str
    length: str
    over: int = Field(ge=1, le=200)
    variation: Optional[str] = None  # swing/seam/spin/slower etc. Only T20 training data has it.
    balls_faced: int = Field(0, ge=0)
    bat_runs: int = Field(0, ge=0)
    prev: List[Prev] = Field(default_factory=list, max_length=5)  # earlier balls this over, oldest first
    inns: int = Field(1, ge=1, le=4)
    runs: int = Field(0, ge=0)
    wkts: int = Field(0, ge=0, le=9)
    target: Optional[int] = Field(None, ge=1)
    bat_hand: Optional[Literal['RHB', 'LHB']] = None  # defaults to the batter's known hand
    ground: Optional[str] = None
    daynight: Optional[str] = None


def check(value, allowed, field):
    if value is not None and value not in allowed:
        raise HTTPException(422, f'{field} must be one of {allowed}')


def predict(b: Ball):
    check(b.bowl_style, meta['bowl_styles'], 'bowl_style')
    check(b.line, meta['lines'], 'line')
    check(b.length, meta['lengths'], 'length')
    check(b.variation, meta['variations'], 'variation')
    for p in b.prev:
        check(p.line, meta['lines'], 'prev.line')
        check(p.length, meta['lengths'], 'prev.length')
        check(p.shot, meta['classes'], 'prev.shot')
    max_balls = MAX_BALLS.get(b.format)
    if max_balls and b.over > max_balls // 6:
        raise HTTPException(422, f'{b.format} has only {max_balls // 6} overs')
    if b.inns > (4 if b.format == 'Test' else 2):
        raise HTTPException(422, f'{b.format} has only 2 innings')
    source = SOURCE_FOR_FORMAT[b.format]
    # the ODI/Test data has no variation column, so a variation there would be a combination never seen in training
    variation = (b.variation or 'stock') if source == 'odata' else None
    known = meta['batters'].get(b.batter)
    balls = (b.over - 1) * 6 + len(b.prev)  # ponytail: assumes earlier balls this over were legal
    row = dict(format=b.format, source=source, bat=b.batter, bat_hand=b.bat_hand or (known or {}).get('hand', 'RHB'),
               bowl_style=b.bowl_style, variation=variation, line=b.line, length=b.length, over=b.over,
               ball_no=len(b.prev) + 1, bat_bf=b.balls_faced, bat_runs=b.bat_runs, inns=b.inns, runs=b.runs,
               wkts=b.wkts, balls=balls, balls_rem=max_balls - balls if max_balls else None,
               target=b.target if b.inns == 2 else None, ground=b.ground, daynight=b.daynight)
    for k, p in enumerate(reversed(b.prev), 1):  # p1 = most recent ball
        row.update({f'p{k}_line': p.line, f'p{k}_length': p.length, f'p{k}_shot': p.shot, f'p{k}_score': p.runs})
    for k in range(len(b.prev) + 1, 6):
        row.update({f'p{k}_line': None, f'p{k}_length': None, f'p{k}_shot': None, f'p{k}_score': None})
    probs = model.predict(build_features(pd.DataFrame([row])))[0]
    shots = sorted(zip(meta['classes'], probs), key=lambda s: -s[1])
    return {'shots': {s: round(float(p) * 100, 1) for s, p in shots},
            'top': [{'shot': s, 'pct': round(float(p) * 100, 1), **scoring_zones(b.batter, s)} for s, p in shots[:3]],
            'batter_known': known is not None, 'batter_balls_in_data': (known or {}).get('balls', 0),
            'variation_used': variation is not None}


app = FastAPI(title='Shot predictor')
app.post('/predict')(predict)
app.get('/options')(lambda: {k: v for k, v in meta.items() if k != 'batters'}
                    | {'batters': [[n, v['hand'], v['balls']] for n, v in meta['batters'].items()]})
app.get('/')(lambda: FileResponse(HERE / 'index.html'))
