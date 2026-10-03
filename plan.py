"""Bowling plan: search every bowler type x line x length per phase, score each cell with the runs and wicket models.
Runs = runs the bowler concedes (batter runs + wides + no-balls), so wide lines aren't free."""
import pandas as pd

from features import LENGTHS, LINES, PHASES, build_features, serve_row

PLAN_LENGTHS = [l for l in LENGTHS if l != 'FULL_TOSS']  # nobody plans a full toss
LOW_DATA = 20  # balls faced in a cell below which the numbers are mostly the model's guess
CASES = {'fewest_runs': 'runs', 'runs_wickets': 'cost'}


def bowling_plan(shot_m, runs_m, wicket_m, meta, zones, batter, fmt, bowl_style=None, zone_fn=None):
    known = meta['batters'].get(batter)
    hand = (known or {}).get('hand', 'RHB')
    wicket_value = meta['bat_avg'][fmt].get(batter, meta['bat_avg'][fmt]['_all'])
    faced = zones['faced'].get(batter, {}).get(fmt, {})

    rows, keys = [], []
    for phase, _, _ in PHASES[fmt]:
        st = meta['phase_state'][fmt][phase]  # typical first-innings situation in this phase
        for style in meta['bowl_styles']:
            for line in LINES:
                for length in PLAN_LENGTHS:
                    rows.append(serve_row(fmt, batter, hand, style, line, length, round(st['over']),
                                          bat_bf=round(st['bat_bf']), bat_runs=round(st['bat_runs']),
                                          runs=round(st['runs']), wkts=round(st['wkts'])))
                    keys.append((phase, style, line, length))
    X = build_features(pd.DataFrame(rows))
    shots, runs, wkt = shot_m.predict(X), runs_m.predict(X), wicket_m.predict(X)
    g = pd.DataFrame(keys, columns=['phase', 'style', 'line', 'length'])
    # cost = runs conceded minus the runs a wicket saves (his average x chance of getting him out)
    g = g.assign(runs=runs, wkt=wkt, cost=runs - wicket_value * wkt,
                 shot=[meta['classes'][i] for i in shots.argmax(1)], shot_pct=shots.max(1))

    def cell(r, strongest=False):
        n = faced.get(f'{r.line}|{r.length}', 0)
        c = {'line': r.line, 'length': r.length, 'rpo': round(r.runs * 6, 2), 'wicket_pct': round(r.wkt * 100, 2),
             'net_rpo': round(r.cost * 6, 2), 'shot': r.shot, 'shot_pct': round(r.shot_pct * 100),
             'faced': n, 'low_data': n < LOW_DATA}
        if strongest and zone_fn and r.shot != 'leave':
            share = zone_fn(batter, r.shot)['share']
            c['zone'] = max(share, key=share.get)
        return c

    phases = []
    for phase, lo, hi in PHASES[fmt]:
        p = g[g.phase == phase]
        # rank and pick from cells he has actually faced enough, unless there are too few (e.g. an unknown batter)
        seen = [faced.get(f'{l}|{n}', 0) >= LOW_DATA for l, n in zip(p.line, p.length)]
        ps = p[seen] if sum(seen) >= 6 * p['style'].nunique() else p
        out = {'name': phase, 'overs': [lo, hi], 'state': meta['phase_state'][fmt][phase]}
        for case, col in CASES.items():
            # matchup: this batter against each bowler type's usual mix of lines and lengths
            mix = meta['style_mix'][fmt]
            w = [mix.get(st, {}).get(f'{l}|{n}', 0) for st, l, n in zip(p['style'], p.line, p.length)]
            rank = (p[col] * w).groupby(p['style']).sum().div(pd.Series(w, index=p.index).groupby(p['style']).sum()).sort_values()
            style = bowl_style or rank.index[0]
            q, pick = p[p.style == style], ps[ps.style == style]
            out[case] = {
                'bowlers': [{'bowl_style': s, 'score': round(v * 6, 2)} for s, v in rank.items()],
                'recommended': rank.index[0], 'bowl_style': style,
                'best': [cell(r) for r in pick.nsmallest(3, col).itertuples()],
                'worst': [cell(r, strongest=True) for r in pick.nlargest(3, col).itertuples()],
                'grid': [cell(r) for r in q.itertuples()],
            }
        phases.append(out)
    return {'batter': batter, 'format': fmt, 'bat_hand': hand, 'batter_known': known is not None,
            'wicket_value': wicket_value, 'phases': phases}
