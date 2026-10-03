import json
from pathlib import Path
from typing import List, Literal, Optional

import lightgbm as lgb
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from features import MAX_BALLS, build_features, serve_row
from plan import bowling_plan
from similar import Similar

HERE = Path(__file__).parent
model = lgb.Booster(model_file=str(HERE / 'model.txt'))
runs_model = lgb.Booster(model_file=str(HERE / 'runs_model.txt'))
wicket_model = lgb.Booster(model_file=str(HERE / 'wicket_model.txt'))
meta = json.loads((HERE / 'meta.json').read_text())
zones = json.loads((HERE / 'zones.json').read_text())
sim = Similar(HERE / 'profiles.npz')


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
    model_config = ConfigDict(extra='forbid')  # unknown fields (e.g. a batting hand) are rejected, not silently ignored
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
    known = meta['batters'].get(b.batter)
    hand = known['hand'] if known else 'RHB'  # batting hand comes from the data; an unknown batter is a typical right-hander
    row = serve_row(b.format, b.batter, hand, b.bowl_style, b.line, b.length,
                    b.over, [p.model_dump() for p in b.prev], b.balls_faced, b.bat_runs, b.inns, b.runs, b.wkts,
                    b.target, b.variation, b.ground, b.daynight)
    probs = model.predict(build_features(pd.DataFrame([row])))[0]
    shots = sorted(zip(meta['classes'], probs), key=lambda s: -s[1])
    return {'shots': {s: round(float(p) * 100, 1) for s, p in shots},
            'top': [{'shot': s, 'pct': round(float(p) * 100, 1), **scoring_zones(b.batter, s)} for s, p in shots[:3]],
            'batter_known': known is not None, 'batter_balls_in_data': (known or {}).get('balls', 0),
            'variation_used': row['variation'] is not None}


class PlanRequest(BaseModel):
    batter: str
    format: Literal['T20', 'ODI']  # Test plans come later
    bowl_style: Optional[str] = None  # None -> the recommended bowler type per phase


def plan(r: PlanRequest):
    check(r.bowl_style, meta['bowl_styles'], 'bowl_style')
    p = bowling_plan(model, runs_model, wicket_model, meta, zones, r.batter, r.format, r.bowl_style, scoring_zones)
    # test the plan on batters who play like him: at least as similar as the top 10% of all pairs
    similars = [x for x in sim.similar(r.batter, r.format, 8) if x['score'] >= sim.reference(r.format)['top10']]
    p['similar'] = similars
    return sim.evaluate_plan(p, similars, r.format)


class SimilarRequest(BaseModel):
    batter: str
    format: Literal['T20', 'ODI', 'Test']
    k: int = Field(10, ge=1, le=30)


def similar_players(r: SimilarRequest):
    if r.batter not in sim.idx:
        raise HTTPException(404, f'{r.batter} has too little data to profile (needs 200+ labelled balls)')
    return {'batter': r.batter, 'format': r.format, 'hand': sim.hands[sim.idx[r.batter]],
            'reference': sim.reference(r.format),  # similarity of the top 1% / 5% / 10% of all pairs
            'similar': sim.similar(r.batter, r.format, r.k)}


class CompareRequest(BaseModel):
    a: str
    b: str
    format: Literal['T20', 'ODI', 'Test']


def compare(r: CompareRequest):
    for n in (r.a, r.b):
        if n not in sim.idx:
            raise HTTPException(404, f'{n} has too little data to profile')
    return sim.compare(r.a, r.b, r.format)


app = FastAPI(title='Shot predictor')
app.post('/plan')(plan)
app.post('/similar')(similar_players)
app.post('/compare')(compare)
app.post('/predict')(predict)
app.get('/options')(lambda: {k: v for k, v in meta.items() if k != 'batters'}
                    | {'batters': [[n, v['hand'], v['balls']] for n, v in meta['batters'].items()],
                       'profiled': sim.names})  # batters with a style profile, i.e. valid on the Similar players tab
# no-cache: browsers re-check the page, so an update is never hidden behind a stale copy
app.get('/')(lambda: FileResponse(HERE / 'static' / 'index.html', headers={'Cache-Control': 'no-cache'}))


class Static(StaticFiles):  # no-cache: the browser re-checks every file, so an update is never hidden behind a stale copy
    async def get_response(self, path, scope):
        r = await super().get_response(path, scope)
        r.headers['Cache-Control'] = 'no-cache'
        return r


app.mount('/static', Static(directory=HERE / 'static'), name='static')
