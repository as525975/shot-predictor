import json
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import log_loss, mean_absolute_error, mean_poisson_deviance, roc_auc_score, top_k_accuracy_score

import similar
import zones
from features import FORMATS, LENGTHS, LINES, PHASES, build_features, load_all, recency_weight

HERE = Path(__file__).parent
DATA = sys.argv[1] if len(sys.argv) > 1 else str(HERE / 'data')

df = load_all(DATA)
d = df.dropna(subset=['bat', 'line', 'length', 'shot']).reset_index(drop=True)
classes = sorted(d.shot.unique())
y = d.shot.map({c: i for i, c in enumerate(classes)}).to_numpy()
X = build_features(d)

# time split by match date: oldest 70% train, next 10% early-stopping, newest 20% test
order = d.groupby('p_match').date.first().sort_values().index
n = len(order)
split = pd.Series(np.select([np.arange(n) < n * .7, np.arange(n) < n * .8], ['train', 'val'], 'test'), index=order)
part = d.p_match.map(split).to_numpy()
tr, va, te = part == 'train', part == 'val', part == 'test'
print(f'{len(d):,} balls, {len(classes)} shots | train {tr.sum():,} val {va.sum():,} test {te.sum():,}')


params = dict(objective='multiclass', num_class=len(classes), learning_rate=0.1, num_leaves=63,
              min_data_in_leaf=100, feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1,
              cat_l2=10, cat_smooth=20, min_data_per_group=50, verbose=-1)

# recency: recent balls count more, weight halving every HALF_LIFE years. The shot model picks the half-life itself:
# one fit per candidate, scored on the (later) validation matches. The best fit is kept as the shot model.
trials = {}
for hl in (None, 2, 3, 5):
    mm = lgb.train(params, lgb.Dataset(X[tr], y[tr], weight=recency_weight(d.date, hl)[tr]), 1000,
                   valid_sets=[lgb.Dataset(X[va], y[va])], callbacks=[lgb.early_stopping(30, verbose=False)])
    trials[hl] = (log_loss(y[va], mm.predict(X[va]), labels=range(len(classes))), mm)
HALF_LIFE = min(trials, key=lambda h: trials[h][0])
m = trials[HALF_LIFE][1]
print('recency half-life (val log-loss): ' + ', '.join(f"{'none' if h is None else f'{h}y'} {v[0]:.4f}" for h, v in trials.items())
      + f" -> {'no weighting' if HALF_LIFE is None else f'{HALF_LIFE} years'}")
w = recency_weight(d.date, HALF_LIFE)  # 1 for the newest ball; used by every model and batter table below
zones.write(df, recency_weight(df.date, HALF_LIFE))
del df, trials

def baseline(trn, tst, a=20):
    """Batter's shot mix for this line+length, smoothed toward everyone's mix for it."""
    prior = pd.crosstab([trn.format, trn.line, trn.length], trn.shot, normalize='index').reindex(columns=classes, fill_value=0)
    cnt = pd.crosstab([trn.format, trn.bat, trn.line, trn.length], trn.shot).reindex(columns=classes, fill_value=0)
    p = prior.reindex(pd.MultiIndex.from_frame(tst[['format', 'line', 'length']])).fillna(1 / len(classes)).to_numpy()
    c = cnt.reindex(pd.MultiIndex.from_frame(tst[['format', 'bat', 'line', 'length']])).fillna(0).to_numpy()
    return (c + a * p) / (c.sum(1, keepdims=True) + a)


def report(name, p, yt):
    labels = range(len(classes))
    print(f'  {name:9} logloss {log_loss(yt, p, labels=labels):.3f}  '
          f'top1 {top_k_accuracy_score(yt, p, k=1, labels=labels):.3f}  '
          f'top3 {top_k_accuracy_score(yt, p, k=3, labels=labels):.3f}')


p_model = m.predict(X[te])
p_base = baseline(d[tr | va], d[te])
fmt_te = d.format[te].to_numpy()
for f in ['all'] + FORMATS:
    k = np.ones(len(fmt_te), bool) if f == 'all' else fmt_te == f
    print(f'{f} ({k.sum():,} test balls)')
    report('baseline', p_base[k], y[te][k])
    report('model', p_model[k], y[te][k])

# calibration: does "60% confident" come true ~60% of the time?
conf, hit = p_model.max(1), p_model.argmax(1) == y[te]
bins = pd.cut(conf, np.linspace(0, 1, 11))
cal = pd.DataFrame({'conf': conf, 'hit': hit}).groupby(bins, observed=True).agg(n=('hit', 'size'), conf=('conf', 'mean'), acc=('hit', 'mean'))
print(cal.round(3).to_string())
print(f'ECE {(cal.n * (cal.conf - cal.acc).abs()).sum() / cal.n.sum():.3f}')

# final model: refit on everything with the chosen round count so the newest seasons count
final = lgb.train(params, lgb.Dataset(X, y, weight=w), m.best_iteration)
final.save_model(str(HERE / 'model.txt'))

# ---- outcome models for the bowling plan: runs off the ball, and the batter getting out ----
lim = d.format.isin(PHASES).to_numpy()  # plans cover ODI/T20
base = {k: v for k, v in params.items() if k not in ('objective', 'num_class')}


def cell_rate(trn, tst, col, a=50):
    """Baseline: batter's mean for this format+line+length, smoothed toward everyone's."""
    k = ['format', 'line', 'length']
    prior = trn.groupby(k)[col].mean()
    g = trn.groupby(['bat'] + k)[col].agg(['sum', 'size'])
    p = prior.reindex(pd.MultiIndex.from_frame(tst[k])).fillna(trn[col].mean()).to_numpy()
    c = g.reindex(pd.MultiIndex.from_frame(tst[['bat'] + k])).fillna(0).to_numpy()
    return (c[:, 0] + a * p) / (c[:, 1] + a)


outcome = {}
for name, col, obj in [('runs', 'bowl_run', 'poisson'), ('wicket', 'bat_out', 'binary')]:
    yo = d[col].fillna(0).to_numpy(float)
    mo = lgb.train(dict(base, objective=obj), lgb.Dataset(X[tr], yo[tr], weight=w[tr]), 1000, valid_sets=[lgb.Dataset(X[va], yo[va])],
                   callbacks=[lgb.early_stopping(30), lgb.log_evaluation(0)])
    k = te & lim
    pm, pb = mo.predict(X[k]), cell_rate(d[tr | va].assign(**{col: yo[tr | va]}), d[k], col)
    if name == 'runs':
        for lab, p_ in [('baseline', pb), ('model', pm)]:
            print(f'runs    {lab:9} poisson dev {mean_poisson_deviance(yo[k], np.clip(p_, 1e-6, None)):.4f}  MAE {mean_absolute_error(yo[k], p_):.4f}')
    else:
        for lab, p_ in [('baseline', pb), ('model', pm)]:
            print(f'wicket  {lab:9} logloss {log_loss(yo[k], np.clip(p_, 1e-6, 1 - 1e-6)):.4f}  AUC {roc_auc_score(yo[k], p_):.3f}')
    outcome[name] = (mo, yo, obj)

# plan check on held-out matches: do the cells the model rates best actually concede fewer runs?
k = te & lim
t = d.loc[k, ['bat', 'format', 'line', 'length']].assign(pred=outcome['runs'][0].predict(X[k]), act=outcome['runs'][1][k])
t = t[t.groupby(['bat', 'format']).bat.transform('size') >= 300]
c = t.groupby(['bat', 'format', 'line', 'length']).agg(pred=('pred', 'mean'), act=('act', 'mean'), n=('act', 'size'))
c = c[c.n >= 15]
g = c.groupby(level=[0, 1]).pred
c = c.assign(r=g.rank(method='first'), size=g.transform('size'))
c = c[c['size'] >= 8]
best, worst = c[c.r <= 5], c[c.r > c['size'] - 5]
print(f'plan check ({c.index.droplevel([2, 3]).nunique()} batter-formats): actual runs/ball in model-best 5 cells '
      f'{best.act.mean():.3f} vs model-worst 5 {worst.act.mean():.3f}')

for name, (mo, yo, obj) in outcome.items():
    lgb.train(dict(base, objective=obj), lgb.Dataset(X, yo, weight=w), mo.best_iteration).save_model(str(HERE / f'{name}_model.txt'))
print('saved runs_model.txt + wicket_model.txt')

# typical first-innings match state per phase, used as the plan's assumed situation
phase_state = {f: {name: {c: float(d.loc[(d.format == f) & (d.inns == 1) & d.over.between(lo, hi), c].median())
                          for c in ['over', 'runs', 'wkts', 'bat_bf', 'bat_runs']}
                   for name, lo, hi in ph} for f, ph in PHASES.items()}
# batter average (runs per dismissal) per format, smoothed toward the format average: the value of a wicket
ga = d[lim].assign(r=d.bat_run.fillna(0) * w, o=d.bat_out * w).groupby(['format', 'bat'])[['r', 'o']].sum()  # recent form counts more
fmt_avg = ga.groupby(level=0).r.sum() / ga.groupby(level=0).o.sum()
avg = (ga.r + 3 * fmt_avg.reindex(ga.index.get_level_values(0)).to_numpy()) / (ga.o + 3)
bat_avg = {f: {'_all': round(float(fmt_avg[f]), 1), **{b: round(float(v), 1) for b, v in avg[f].items()}} for f in PHASES}

# where each bowler type usually pitches it (share of balls per line|length), to score a bowler type on a realistic mix
mix = d[lim & (d.length != 'FULL_TOSS').to_numpy()].groupby(['format', 'bowl_style', 'line', 'length']).size()
mix = mix / mix.groupby(level=[0, 1]).transform('sum')
style_mix = {}
for (f, st, line, length), v in mix.items():
    style_mix.setdefault(f, {}).setdefault(st, {})[f'{line}|{length}'] = round(float(v), 4)

bf = d.groupby('bat').agg(hand=('bat_hand', 'first'), balls=('bat', 'size'))
bf['hand'] = bf.hand.fillna('RHB')
meta = {
    'classes': classes,
    'batters': {b: {'hand': r.hand, 'balls': int(r.balls)} for b, r in bf.sort_values('balls', ascending=False).iterrows()},
    'formats': FORMATS,
    'bowl_styles': sorted(d.bowl_style.dropna().unique().tolist()),
    'variations': d.variation.value_counts().index.tolist(),
    'lines': LINES,
    'lengths': LENGTHS,
    'grounds': sorted(d.ground.dropna().unique().tolist()),
    'daynight': sorted(d.daynight.dropna().unique().tolist()),
    'phase_state': phase_state,
    'bat_avg': bat_avg,
    'style_mix': style_mix,
    'half_life_years': HALF_LIFE,
}
(HERE / 'meta.json').write_text(json.dumps(meta))
print('saved model.txt + meta.json')
similar.build(d.assign(w=w), classes)
