"""Where each batter scores their runs with each shot -> zones.json (for the scoring-region diagrams).
Run standalone after changing data (`python zones.py`); train.py also calls it."""
import json
import sys
from pathlib import Path

from features import ZONES, load_all

HERE = Path(__file__).parent


def zone_table(d):
    r = d[(d.bat_run > 0) & d.zone.notna() & d.shot.notna() & d.bat.notna()]
    by_bat = r.pivot_table(index=['bat', 'shot'], columns='zone', values='bat_run', aggfunc='sum', fill_value=0)
    by_bat = by_bat.reindex(columns=ZONES, fill_value=0)
    prior = r.pivot_table(index='shot', columns='zone', values='bat_run', aggfunc='sum', fill_value=0)
    prior = prior.reindex(columns=ZONES, fill_value=0)
    batters = {}
    for (bat, shot), row in by_bat.iterrows():
        batters.setdefault(bat, {})[shot] = [int(v) for v in row]
    return {'zones': ZONES, 'prior': {s: [int(v) for v in row] for s, row in prior.iterrows()}, 'batters': batters}


def write(d):
    t = zone_table(d)
    (HERE / 'zones.json').write_text(json.dumps(t, separators=(',', ':')))
    print(f"saved zones.json ({len(t['batters']):,} batters)")


if __name__ == '__main__':
    write(load_all(sys.argv[1] if len(sys.argv) > 1 else HERE / 'data', log=lambda *a: None))
