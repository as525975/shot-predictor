import json
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import log_loss, top_k_accuracy_score

import zones
from features import FORMATS, LENGTHS, LINES, build_features, load_all

HERE = Path(__file__).parent
DATA = sys.argv[1] if len(sys.argv) > 1 else str(HERE / 'data')

df = load_all(DATA)
d = df.dropna(subset=['bat', 'line', 'length', 'shot']).reset_index(drop=True)
del df
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
m = lgb.train(params, lgb.Dataset(X[tr], y[tr]), 1000, valid_sets=[lgb.Dataset(X[va], y[va])],
              callbacks=[lgb.early_stopping(30), lgb.log_evaluation(50)])


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
final = lgb.train(params, lgb.Dataset(X, y), m.best_iteration)
final.save_model(str(HERE / 'model.txt'))

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
}
(HERE / 'meta.json').write_text(json.dumps(meta))
print('saved model.txt + meta.json')
zones.write(d)
