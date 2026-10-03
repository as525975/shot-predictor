"""Similar batters: who plays the same shots to the same deliveries -> profiles.npz.
Build: `python similar.py` (train.py also calls build()). Serve: Similar(path).similar / .compare / .evaluate_plan."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from features import FORMATS, LENGTHS, LINES, PHASES, load_all, recency_weight

HERE = Path(__file__).parent
SPIN = {'off spin', 'leg spin', 'left-arm orthodox', 'left-arm wrist spin'}
KINDS = ['pace', 'spin']
CELLS = [(k, l, n) for k in KINDS for l in LINES for n in LENGTHS]  # 60 delivery types
MIN_BALLS = 200            # batters with less labelled data aren't profiled
PRIOR = 10                 # balls of everyone's shot mix blended into each cell
MIN_CELL = 15              # balls in a cell before we say anything about it in a report
MIN_FORMAT_BALLS = 300     # to be listed as similar in a format, a batter must have really batted in it
# shot groups for the radar comparison in the report
SHOT_GROUPS = [('defend', ['defend']), ('leave', ['leave']), ('drive', ['cover_drive', 'on_drive', 'straight_drive', 'square_drive']),
               ('cut', ['cut']), ('pull / hook', ['pull_hook']), ('flick / glance', ['flick', 'leg_glance']),
               ('steer / dab', ['steer_dab']), ('sweep', ['sweep', 'reverse_sweep']), ('slog', ['slog']), ('ramp', ['ramp_scoop'])]
# overs bins per format (upper bounds). Fine enough for both the similarity contexts and the plan phases.
BINS = {'T20': [6, 15, 20], 'ODI': [10, 30, 40, 50], 'Test': [10 ** 4]}
NBINS = max(len(b) for b in BINS.values())
PLAN_BINS = {'T20': [[0], [1], [2]], 'ODI': [[0], [1, 2], [3]]}  # features.PHASES (powerplay, middle, death) -> bins
assert all(BINS[f][PLAN_BINS[f][i][-1]] == hi for f, ph in PHASES.items() for i, (_, _, hi) in enumerate(ph))
# format segments whose batting styles are compared (name, format, bins). Segments of one format pool fully.
CONTEXTS = [('T20', 'T20', [0, 1, 2]), ('ODI 1-10', 'ODI', [0]), ('ODI 11-30', 'ODI', [1]),
            ('ODI 31-50', 'ODI', [2, 3]), ('Test', 'Test', [0])]
# how much batting in one segment carries over to another (symmetric). Unlisted cross-format pairs: 0 -
# the rest of the overlap (e.g. the same weakness in every format) already shows up in each format's own data.
CROSS = {('T20', 'ODI 1-10'): 0.85, ('T20', 'ODI 11-30'): 0.30, ('T20', 'ODI 31-50'): 0.80, ('Test', 'ODI 11-30'): 0.15}


def carry(t, c):
    (nt, ft, _), (nc, fc, _) = CONTEXTS[t], CONTEXTS[c]
    return 1.0 if ft == fc else CROSS.get((nt, nc), CROSS.get((nc, nt), 0.0))


LEN_NAME = {'FULL_TOSS': 'full toss', 'YORKER': 'yorker', 'FULL': 'full', 'GOOD_LENGTH': 'good length',
            'SHORT_OF_A_GOOD_LENGTH': 'back of a length', 'SHORT': 'short'}
LINE_NAME = {'WIDE_OUTSIDE_OFFSTUMP': 'wide outside off', 'OUTSIDE_OFFSTUMP': 'outside off', 'ON_THE_STUMPS': 'on the stumps',
             'DOWN_LEG': 'down leg', 'WIDE_DOWN_LEG': 'wide down leg'}


def cell_name(c):
    k, l, n = CELLS[c]
    return f'{k}, {LEN_NAME[n]} {LINE_NAME[l]}'


def cell_index(kind, line, length):
    return KINDS.index(kind) * len(LINES) * len(LENGTHS) + LINES.index(line) * len(LENGTHS) + LENGTHS.index(length)


def bin_index(fmt, over):
    return min(int(np.searchsorted(BINS[fmt], over)), len(BINS[fmt]) - 1)


def _contexts(shots):
    """(B, format, bin, cell, shot) -> (B, context, cell, shot)"""
    return np.stack([shots[:, FORMATS.index(f)][:, bins].sum(1) for _, f, bins in CONTEXTS], 1)


def _counts(d, names, classes):
    """shots (B, format, overs bin, cell, shot), runs conceded and dismissals (B, format, overs bin, cell)."""
    b = pd.Categorical(d.bat, categories=names).codes
    f = d.format.map({x: i for i, x in enumerate(FORMATS)}).to_numpy()
    ph = np.array([bin_index(x, o) for x, o in zip(d.format, d.over)])
    kind = np.where(d.bowl_style.isin(SPIN), 1, 0)
    c = kind * 30 + d.line.map({x: i for i, x in enumerate(LINES)}).to_numpy() * 6 + d.length.map({x: i for i, x in enumerate(LENGTHS)}).to_numpy()
    s = d.shot.map({x: i for i, x in enumerate(classes)}).to_numpy()
    w = d.w.to_numpy() if 'w' in d else np.ones(len(d))  # recency weight per ball
    shape = (len(names), len(FORMATS), NBINS, len(CELLS))
    shots = np.zeros(shape + (len(classes),), np.float32)
    runs, outs = np.zeros(shape, np.float32), np.zeros(shape, np.float32)
    np.add.at(shots, (b, f, ph, c, s), w)
    np.add.at(runs, (b, f, ph, c), d.bowl_run.fillna(0).to_numpy() * w)
    np.add.at(outs, (b, f, ph, c), d.bat_out.fillna(0).to_numpy() * w)
    return shots, runs, outs


def _smooth(P):
    """P: (B, cells, shots) counts -> smoothed shot distributions, counts per cell, cell weights."""
    n = P.sum(-1)
    pop = P.sum(0)
    pop_dist = pop / np.clip(pop.sum(-1, keepdims=True), 1, None)
    D = (P + PRIOR * pop_dist) / (n + PRIOR)[..., None]
    w = pop.sum(-1) / pop.sum()  # how common each delivery type is
    return D, n, w


def _js(p, q):
    """Jensen-Shannon distance (base 2, in [0, 1]) along the last axis."""
    m = (p + q) / 2
    kl = lambda a, b: np.where(a > 0, a * np.log2(np.clip(a, 1e-12, None) / np.clip(b, 1e-12, None)), 0).sum(-1)
    return np.sqrt(np.clip((kl(p, m) + kl(q, m)) / 2, 0, 1))


def _embed(Pc, fmt):
    """Batter style vectors for one format, from context counts Pc (B, context, cell, shot).
    Per context: how his shot mix differs from that context's average batter (so each source's tagging cancels out),
    sqrt (Hellinger) so rare shots count, weighted by how common the delivery is and how much he has faced it.
    Each of the format's own contexts then borrows from the others by carry(); the parts are joined, weighted by
    their share of balls. Also returns the mixed shot distributions D, balls n and average mix pop for reports."""
    Xc = []
    for k in range(len(CONTEXTS)):
        P = Pc[:, k]
        if P.sum() == 0:
            Xc.append(None)
            continue
        D, n, cw = _smooth(P)
        pop = P.sum(0) / np.clip(P.sum((0, 2))[:, None], 1, None)
        Xc.append((np.sqrt(D) - np.sqrt(pop)[None]) * np.sqrt(cw)[None, :, None] * (n / (n + PRIOR))[..., None])
    targets = [k for k, (_, f, _) in enumerate(CONTEXTS) if f == fmt]
    share = np.array([Pc[:, k].sum() for k in targets], float)
    share /= share.sum()
    X = np.stack([np.sqrt(st) * sum(carry(t, c) * Xc[c] for c in range(len(CONTEXTS)) if Xc[c] is not None and carry(t, c) > 0)
                  for st, t in zip(share, targets)], 1)  # (B, target contexts, cell, shot)
    X = X / np.linalg.norm(X.reshape(len(Pc), -1), axis=1).clip(1e-9)[:, None, None, None]
    dw = np.array([sum(st * carry(t, c) for st, t in zip(share, targets)) for c in range(len(CONTEXTS))])
    P = (Pc * dw[None, :, None, None]).sum(1)
    D, n, _ = _smooth(P)
    pop = P.sum(0) / np.clip(P.sum((0, 2))[:, None], 1, None)
    return X, D, n, pop


def build(d, classes, path=HERE / 'profiles.npz', log=print):
    d = d.dropna(subset=['bat', 'line', 'length', 'shot', 'bowl_style'])
    vc = d.bat.value_counts()
    names = sorted(vc[vc >= MIN_BALLS].index)
    d = d[d.bat.isin(names)]
    # recency: weight within each batter's career, so recent seasons shape his style but his total evidence
    # (how many balls he has faced) stays the same - retired players remain valid comparisons
    w = d['w'] if 'w' in d else pd.Series(1.0, index=d.index)
    d = d.assign(w=w * d.groupby('bat').bat.transform('size') / w.groupby(d.bat).transform('sum'))
    shots, runs, outs = _counts(d, names, classes)
    hands = d.groupby('bat').bat_hand.agg(lambda s: s.mode().iat[0] if s.notna().any() else 'RHB').reindex(names).fillna('RHB')

    # reference points: split each batter's matches at random into two halves. How similar is a batter to himself,
    # and to others? Also a check that the method works: does one half pick out the other half among everyone?
    half = pd.util.hash_pandas_object(d.date.astype(str) + d.bat, index=False).to_numpy() % 2 == 0
    h1, _, _ = _counts(d[half], names, classes)
    h2, _, _ = _counts(d[~half], names, classes)
    B = len(names)
    halves = np.concatenate([_contexts(h1), _contexts(h2)])
    cuts = []
    for fmt in FORMATS:
        fi = FORMATS.index(fmt)
        X = _embed(halves, fmt)[0].reshape(2 * B, -1)
        ok = np.array([i for i in range(B) if h1[i, fi].sum() >= MIN_FORMAT_BALLS / 2 and h2[i, fi].sum() >= MIN_FORMAT_BALLS / 2])
        S = X[ok] @ X[B + ok].T  # first halves x second halves
        self_sim = np.diag(S)
        ranks = (S > self_sim[:, None]).sum(1) + 1
        other_sim = S[~np.eye(len(ok), dtype=bool)]
        c = [float(np.median(self_sim)), float(np.quantile(other_sim, 0.95)), float(np.quantile(other_sim, 0.90))]
        cuts.append(c)
        log(f'similarity check {fmt} ({len(ok)} batters, random match halves): one half finds the other at median rank '
            f'{int(np.median(ranks))} of {len(ok)}, top-1 {np.mean(ranks == 1):.0%}, top-5 {np.mean(ranks <= 5):.0%}; '
            f'reference: same player {c[0]:.3f}, top 5% of pairs {c[1]:.3f}, top 10% {c[2]:.3f}')
    np.savez_compressed(path, shots=shots, runs=runs, outs=outs,
                        batters=np.array(names), hands=hands.to_numpy().astype(str), classes=np.array(classes),
                        cuts=np.array(cuts))  # (format, [same player, top 5% of pairs, top 10% of pairs])
    log(f'saved {Path(path).name} ({B} batters)')


class Similar:
    def __init__(self, path=HERE / 'profiles.npz'):
        z = np.load(path)
        self.shots = z['shots'].astype(np.float32)  # (B, F, phase, cell, shot)
        self.runs, self.outs = z['runs'].astype(np.float32), z['outs'].astype(np.float32)
        self.names = [str(x) for x in z['batters']]
        self.hands = [str(x) for x in z['hands']]
        self.classes = [str(x) for x in z['classes']]
        self._ref = {}
        self.idx = {n: i for i, n in enumerate(self.names)}
        self.by_format = self.shots.sum(2)  # (B, F, cell, shot)
        self.ctx = _contexts(self.shots)    # (B, context, cell, shot)
        self._cache = {}

    def reference(self, fmt):
        """What a score means: similarity of the top 1% / 5% / 10% of all pairs of batters in this format (x100)."""
        if fmt not in self._ref:
            X = self._profile(fmt)[0].reshape(len(self.names), -1)
            ok = self.by_format[:, FORMATS.index(fmt)].sum((1, 2)) >= MIN_FORMAT_BALLS
            S = X[ok] @ X[ok].T
            pairs = S[np.triu_indices(ok.sum(), 1)]
            self._ref[fmt] = {k: round(float(np.quantile(pairs, q)) * 100, 1) for k, q in (('top1', .99), ('top5', .95), ('top10', .90))}
        return self._ref[fmt]

    def _profile(self, fmt):
        if fmt not in self._cache:
            self._cache[fmt] = _embed(self.ctx, fmt)
        return self._cache[fmt]

    def similar(self, batter, fmt, k=10):
        if batter not in self.idx:
            return []
        t, fi = self.idx[batter], FORMATS.index(fmt)
        X = self._profile(fmt)[0]
        sim = X.reshape(len(X), -1) @ X[t].ravel()
        own = self.by_format[:, fi].sum((1, 2))
        order = [j for j in np.argsort(-sim) if j != t and own[j] >= MIN_FORMAT_BALLS]
        return [{'batter': self.names[j], 'hand': self.hands[j], 'score': round(max(float(sim[j]), 0) * 100, 1),
                 'balls': int(own[j]),
                 'other_formats_balls': int(self.by_format[j].sum() - own[j])} for j in order[:k]]

    def compare(self, a, b, fmt):
        ia, ib, fi = self.idx[a], self.idx[b], FORMATS.index(fmt)
        X, D, n, pop = self._profile(fmt)
        js = _js(D[ia], D[ib])
        both = np.minimum(n[ia], n[ib])
        contrib = (X[ia] * X[ib]).sum((0, -1))  # each delivery type's share of the similarity score
        la, lb = a.split(' ')[-1], b.split(' ')[-1]
        nice = lambda k: self.classes[k].replace('_', ' ')
        seen = np.where(both >= MIN_CELL)[0]
        same, diff = [], []
        used = {}
        for c in seen[np.argsort(-contrib[seen])]:  # both lean the same way, away from the average batter
            if contrib[c] <= 0 or len(same) == 4:
                break
            pa, pb, pp = D[ia, c], D[ib, c], pop[c]
            k = ((np.sqrt(pa) - np.sqrt(pp)) * (np.sqrt(pb) - np.sqrt(pp))).argmax()
            more = 'more' if pa[k] > pp[k] else 'less'
            if used.get((k, more), 0) >= 2 or min(abs(pa[k] - pp[k]), abs(pb[k] - pp[k])) < 0.03:
                continue  # don't repeat a tendency, and skip ones too small to matter
            used[(k, more)] = used.get((k, more), 0) + 1
            same.append({'cell': cell_name(c), 'text': f'both play {nice(k)} {more} than most '
                         f'({la} {pa[k] * 100:.0f}%, {lb} {pb[k] * 100:.0f}%, typical {pp[k] * 100:.0f}%)'})
        for c in seen[np.argsort(-js[seen] * np.log1p(both[seen]))][:4]:  # biggest difference on balls both face often
            pa, pb = D[ia, c], D[ib, c]
            kb, ka = (pb - pa).argmax(), (pa - pb).argmax()
            diff.append({'cell': cell_name(c),
                         'text': f'{lb} plays {nice(kb)} {pb[kb] * 100:.0f}% vs {la} {pa[kb] * 100:.0f}%; '
                                 f'{la} plays {nice(ka)} {pa[ka] * 100:.0f}% vs {lb} {pb[ka] * 100:.0f}%'})
        by_kind = {}
        for ki, kind in enumerate(KINDS):
            cs = slice(ki * 30, ki * 30 + 30)
            xa, xb = X[ia][:, cs].ravel(), X[ib][:, cs].ravel()
            den = np.linalg.norm(xa) * np.linalg.norm(xb)
            by_kind[kind] = round(max(float(xa @ xb / den), 0) * 100, 1) if den > 0 else None

        def mix(v):
            """(cells, shots) counts -> % of balls per shot group"""
            tot = v.sum()
            if tot <= 0:
                return None
            sh = v.sum(0) / tot
            return {g: round(float(sum(sh[self.classes.index(x)] for x in xs if x in self.classes)) * 100, 1) for g, xs in SHOT_GROUPS}

        shot_mix = {}
        for ki, kind in enumerate(KINDS):
            cs = slice(ki * 30, ki * 30 + 30)
            shot_mix[kind] = {'a': mix(self.by_format[ia, fi, cs]), 'b': mix(self.by_format[ib, fi, cs]),
                              'typical': mix(self.by_format[:, fi, cs].sum(0))}

        def outcomes(i):
            out = {}
            for ki, kind in enumerate(KINDS):
                cs = slice(ki * 30, ki * 30 + 30)
                balls = self.shots[i, fi, :, cs].sum()
                r, o = self.runs[i, fi, :, cs].sum(), self.outs[i, fi, :, cs].sum()
                out[kind] = {'balls': int(balls), 'rpo': round(float(r / balls * 6), 2) if balls else None,
                             'balls_per_wicket': round(float(balls / o)) if o else None}
            return out

        s = float(contrib.sum())
        return {'a': a, 'b': b, 'format': fmt, 'score': round(max(s, 0) * 100, 1), 'reference': self.reference(fmt),
                'hands': [self.hands[ia], self.hands[ib]], 'by_kind': by_kind, 'same': same, 'different': diff,
                'outcomes': {a: outcomes(ia), b: outcomes(ib)}, 'shot_mix': shot_mix,
                # per-cell distance so the UI can draw where they differ (None = not enough balls from both)
                'cells': [{'kind': k, 'line': l, 'length': ln, 'distance': round(float(js[c]), 3) if both[c] >= MIN_CELL else None}
                          for c, (k, l, ln) in enumerate(CELLS)]}

    def evaluate_plan(self, plan, similars, fmt):
        """For each phase and case: what happened when similar batters faced the plan's best deliveries?"""
        fi = FORMATS.index(fmt)
        t = self.idx.get(plan['batter'])
        D = self._profile(fmt)[1]
        kind_of = lambda style: 'spin' if style in SPIN else 'pace'
        for pi, ph in enumerate(plan['phases']):
            for case in ('fewest_runs', 'runs_wickets'):
                c = ph[case]
                cells = [cell_index(kind_of(c['bowl_style']), x['line'], x['length']) for x in c['best']]
                rows = []
                for sm in similars:
                    j = self.idx[sm['batter']]
                    # this phase if there's enough, else the whole format
                    for sl, scope in ((PLAN_BINS[fmt][pi], 'this phase'), (list(range(len(BINS[fmt]))), 'all phases')):
                        balls = self.shots[j, fi][sl][:, cells].sum()
                        if balls >= MIN_CELL:
                            break
                    if balls < MIN_CELL:
                        rows.append({**sm, 'verdict': 'no data', 'text': f'Too few balls in these areas ({int(balls)})'})
                        continue
                    runs, outs = self.runs[j, fi][sl][:, cells].sum(), self.outs[j, fi][sl][:, cells].sum()
                    all_b = self.shots[j, fi][sl].sum()
                    usual_rpo = self.runs[j, fi][sl].sum() / all_b * 6
                    usual_out = self.outs[j, fi][sl].sum() / all_b
                    rpo, out_rate = runs / balls * 6, outs / balls
                    wicket_gain = case == 'runs_wickets' and out_rate >= 1.3 * usual_out and outs >= 2
                    if rpo <= 0.85 * usual_rpo or wicket_gain:
                        verdict = 'worked'
                    elif rpo >= usual_rpo:
                        verdict = 'did not work'
                    else:
                        verdict = 'partly'
                    # why: the shot he plays in these areas most differently from our batter
                    pj = self.shots[j, fi][:, cells].sum((0, 1)) + 1e-9
                    pj = pj / pj.sum()
                    pt = D[t, cells].mean(0) if t is not None else None
                    last = sm['batter'].split(' ')[-1]
                    if verdict == 'did not work' and pt is not None:
                        s = (pj - pt).argmax()
                        why = (f'He plays {self.classes[s].replace("_", " ")} {pj[s] * 100:.0f}% of the time here, '
                               f'{plan["batter"].split(" ")[-1]} only {pt[s] * 100:.0f}%')
                    else:
                        why = f'Mostly {self.classes[pj.argmax()].replace("_", " ")} ({pj.max() * 100:.0f}%)'
                    text = (f'{rpo:.1f}/over here vs his usual {usual_rpo:.1f}' + (' (all phases)' if scope == 'all phases' else '')
                            + (f', out every {balls / outs:.0f} balls (usually {1 / usual_out:.0f})' if outs and usual_out else '')
                            + f'. {why}')
                    rows.append({**sm, 'verdict': verdict, 'text': text, 'balls': int(balls), 'scope': scope,
                                 'rpo': round(float(rpo), 2), 'usual_rpo': round(float(usual_rpo), 2),
                                 'name': last})
                judged = [r for r in rows if r['verdict'] != 'no data']
                wt = sum(r['score'] for r in judged) or 1
                c['evaluation'] = {'similar': rows, 'worked': sum(r['verdict'] == 'worked' for r in judged),
                                   'judged': len(judged),
                                   'weighted_success': round(sum(r['score'] for r in judged if r['verdict'] == 'worked') / wt * 100)}
        return plan


if __name__ == '__main__':
    import json
    meta = json.loads((HERE / 'meta.json').read_text())
    df = load_all(sys.argv[1] if len(sys.argv) > 1 else HERE / 'data', log=lambda *a: None)
    build(df.assign(w=recency_weight(df.date, meta.get('half_life_years'))), meta['classes'])
