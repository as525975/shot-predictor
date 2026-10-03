from features import recency_weight
from app import Ball, CompareRequest, PlanRequest, SimilarRequest, compare, meta, plan, predict, similar_players

base = dict(format='ODI', batter='Virat Kohli', bowl_style='right-arm fast', over=20, balls_faced=30, bat_runs=25, runs=110, wkts=2)

short = predict(Ball(**base, line='ON_THE_STUMPS', length='SHORT'))['shots']
assert abs(sum(short.values()) - 100) < 1, short
assert short['pull_hook'] > short['cover_drive'], short

full = predict(Ball(**base, line='OUTSIDE_OFFSTUMP', length='FULL'))['shots']
assert full['cover_drive'] > full['pull_hook'], full

wide = predict(Ball(**base, line='WIDE_OUTSIDE_OFFSTUMP', length='GOOD_LENGTH'))['shots']
assert wide['cut'] > wide['flick'], wide  # wide outside off -> off-side shots

# format matters: same ball, T20 death over vs Test morning
ball = dict(batter='Virat Kohli', bowl_style='right-arm fast', line='OUTSIDE_OFFSTUMP', length='GOOD_LENGTH', balls_faced=30, bat_runs=40)
t20 = predict(Ball(**ball, format='T20', over=19, runs=160, wkts=4))['shots']
test = predict(Ball(**ball, format='Test', over=19, runs=50, wkts=1))['shots']
assert t20['slog'] > test['slog'] and test['leave'] > t20['leave'], (t20, test)

unknown = predict(Ball(**{**base, 'batter': 'Nobody McNoname'}, line='ON_THE_STUMPS', length='GOOD_LENGTH'))
assert unknown['batter_known'] is False

# bowling plan
for fmt in ['ODI', 'T20']:
    pl = plan(PlanRequest(batter='Virat Kohli', format=fmt))
    assert [p['name'] for p in pl['phases']] == ['powerplay', 'middle', 'death']
    for ph in pl['phases']:
        for case, key in [('fewest_runs', 'rpo'), ('runs_wickets', 'net_rpo')]:
            c = ph[case]
            assert len(c['bowlers']) == len(meta['bowl_styles'])
            scores = [b['score'] for b in c['bowlers']]
            assert scores == sorted(scores), scores
            assert c['bowl_style'] == c['recommended'] == c['bowlers'][0]['bowl_style']
            assert len(c['grid']) == 25 and len(c['best']) == 3 and len(c['worst']) == 3
            assert max(x[key] for x in c['best']) < min(x[key] for x in c['worst']), (fmt, ph['name'], case)
        # adding wicket value can only make the best cells' net cost lower than their plain runs
        assert all(x['net_rpo'] <= x['rpo'] for x in ph['runs_wickets']['best'])
    by = {p['name']: p for p in pl['phases']}
    assert by['death']['fewest_runs']['best'][0]['rpo'] > by['middle']['fewest_runs']['best'][0]['rpo'], fmt

# picking a bowler type gives that type's plan
spin = plan(PlanRequest(batter='Virat Kohli', format='ODI', bowl_style='off spin'))
assert all(ph[c]['bowl_style'] == 'off spin' for ph in spin['phases'] for c in ('fewest_runs', 'runs_wickets'))

# similar players
sp = similar_players(SimilarRequest(batter='Virat Kohli', format='ODI', k=10))['similar']
assert len(sp) == 10 and all(x['batter'] != 'Virat Kohli' for x in sp)
assert [x['score'] for x in sp] == sorted((x['score'] for x in sp), reverse=True)
assert all(0 <= x['score'] <= 100 and x['balls'] >= 300 and 'grade' not in x for x in sp)
top = sp[0]['batter']
c = compare(CompareRequest(a='Virat Kohli', b=top, format='ODI'))
assert abs(c['score'] - sp[0]['score']) < 0.2, (c['score'], sp[0])  # report agrees with the list
back = compare(CompareRequest(a=top, b='Virat Kohli', format='ODI'))
assert abs(back['score'] - c['score']) < 0.2  # symmetric
assert c['same'] and c['different'] and len(c['cells']) == 60
# a classical accumulator is more like his nearest match than like a big hitter
assert c['score'] > compare(CompareRequest(a='Virat Kohli', b='Glenn Maxwell', format='ODI'))['score']

# the bowling plan is tested on similar batters
ev = plan(PlanRequest(batter='Virat Kohli', format='ODI'))['phases'][0]['fewest_runs']['evaluation']
assert ev['judged'] > 0 and 0 <= ev['worked'] <= ev['judged'] and 0 <= ev['weighted_success'] <= 100
assert all(r['verdict'] in ('worked', 'partly', 'did not work', 'no data') for r in ev['similar'])

# recency weighting: newest ball counts 1, one half-life earlier counts half, no half-life = equal
wts = recency_weight(['2024-01-01', '2021-01-01', '2018-01-01'], 3)
assert abs(wts[0] - 1) < 1e-9 and abs(wts[1] - 0.5) < 0.01 and abs(wts[2] - 0.25) < 0.01, wts
assert (recency_weight(['2024-01-01', '2010-01-01'], None) == 1).all()

# batting hand is not an input: a request that sends one is rejected
from pydantic import ValidationError
kohli = dict(format='ODI', batter='Virat Kohli', bowl_style='right-arm fast', line='OUTSIDE_OFFSTUMP', length='GOOD_LENGTH', over=12)
try:
    Ball(**kohli, bat_hand='LHB')
    raise AssertionError('bat_hand should be rejected')
except ValidationError:
    pass

print('ok')
