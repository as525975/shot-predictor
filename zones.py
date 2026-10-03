"""Where each batter scores their runs with each shot -> zones.json (for the scoring-region diagrams).
Run standalone after changing data (`python zones.py`); train.py also calls it."""
import json
import sys
from pathlib import Path

from features import PHASES, ZONES, load_all, recency_weight

HERE = Path(__file__).parent


def zone_table(d, w=None):
    """w: recency weight per ball (recent runs count more in the zone shares). Balls-faced counts stay raw."""
    d = d.assign(wr=d.bat_run * (1 if w is None else w))
    r = d[(d.bat_run > 0) & d.zone.notna() & d.shot.notna() & d.bat.notna()]
    by_bat = r.pivot_table(index=['bat', 'shot'], columns='zone', values='wr', aggfunc='sum', fill_value=0)
    by_bat = by_bat.reindex(columns=ZONES, fill_value=0)
    prior = r.pivot_table(index='shot', columns='zone', values='wr', aggfunc='sum', fill_value=0)
    prior = prior.reindex(columns=ZONES, fill_value=0)
    batters = {}
    for (bat, shot), row in by_bat.iterrows():
        batters.setdefault(bat, {})[shot] = [round(float(v), 1) for v in row]
    # balls each batter has faced per format/line/length, so the bowling plan can flag cells it is guessing at
    f = d[d.format.isin(PHASES) & d.bat.notna() & d.line.notna() & d.length.notna()]
    faced = {}
    for (bat, fmt, line, length), n in f.groupby(['bat', 'format', 'line', 'length']).size().items():
        faced.setdefault(bat, {}).setdefault(fmt, {})[f'{line}|{length}'] = int(n)
    return {'zones': ZONES, 'prior': {s: [round(float(v), 1) for v in row] for s, row in prior.iterrows()}, 'batters': batters,
            'faced': faced}


def write(d, w=None):
    t = zone_table(d, w)
    (HERE / 'zones.json').write_text(json.dumps(t, separators=(',', ':')))
    print(f"saved zones.json ({len(t['batters']):,} batters)")


if __name__ == '__main__':
    df = load_all(sys.argv[1] if len(sys.argv) > 1 else HERE / 'data', log=lambda *a: None)
    hl = json.loads((HERE / 'meta.json').read_text()).get('half_life_years')
    write(df, recency_weight(df.date, hl))
