// Constants, state and pure helpers. No DOM access here, so it runs under `node --test`.
export const nice = s => s.replace(/_/g, ' ');
// a "leave" against a short or back-of-a-length ball is usually a duck or sway
export const shotName = (s, len = S.length) => s === 'leave' && (len === 'SHORT' || len === 'SHORT_OF_A_GOOD_LENGTH') ? 'leave / duck' : nice(s);
export const LINES = ['WIDE_OUTSIDE_OFFSTUMP', 'OUTSIDE_OFFSTUMP', 'ON_THE_STUMPS', 'DOWN_LEG', 'WIDE_DOWN_LEG'];
export const LENGTHS = ['FULL_TOSS', 'YORKER', 'FULL', 'GOOD_LENGTH', 'SHORT_OF_A_GOOD_LENGTH', 'SHORT']; // batter end first
export const LINE_NAME = { WIDE_OUTSIDE_OFFSTUMP: 'wide outside off', OUTSIDE_OFFSTUMP: 'outside off', ON_THE_STUMPS: 'on the stumps', DOWN_LEG: 'down leg', WIDE_DOWN_LEG: 'wide down leg' };
export const LINE_SHORT = { WIDE_OUTSIDE_OFFSTUMP: 'wide', OUTSIDE_OFFSTUMP: 'off', ON_THE_STUMPS: 'stumps', DOWN_LEG: 'leg', WIDE_DOWN_LEG: 'wide' };
export const LEN_NAME = { FULL_TOSS: 'full toss', YORKER: 'yorker', FULL: 'full', GOOD_LENGTH: 'good length', SHORT_OF_A_GOOD_LENGTH: 'back of a length', SHORT: 'short' };
export const LEN_SHORT = { FULL_TOSS: 'FT', YORKER: 'Y', FULL: 'F', GOOD_LENGTH: 'GL', SHORT_OF_A_GOOD_LENGTH: 'BoL', SHORT: 'S' };
export const PACE = ['right-arm fast', 'right-arm medium', 'left-arm fast', 'left-arm medium'];
export const SPIN = ['off spin', 'leg spin', 'left-arm orthodox', 'left-arm wrist spin'];
export const OVERS = { T20: 20, ODI: 50, Test: 200 };
export const OVER_STEP = { T20: 1, ODI: 5, Test: 10 }; // over dropdown granularity
export const overBin = (o, f = S.format) => { const st = OVER_STEP[f], lo = Math.floor((o - 1) / st) * st + 1; return { lo, hi: Math.min(lo + st - 1, OVERS[f]) }; };
export const overLabel = (o = S.over) => { const b = overBin(o); return b.lo === b.hi ? `over ${b.lo}` : `overs ${b.lo}-${b.hi}`; };
export const SERIES = ['var(--s1)', 'var(--s2)', 'var(--s3)'];

export const S = { // default delivery
  format: 'ODI', batter: 'Virat Kohli', bat_hand: 'RHB', bowl_style: 'right-arm fast', variation: 'stock',
  line: 'OUTSIDE_OFFSTUMP', length: 'GOOD_LENGTH', over: 12, inns: 1, runs: 68, wkts: 1, target: 280,
  bat_runs: 32, balls_faced: 40, prev: [], ground: '', daynight: ''
};
export const O = {}, hands = {};  // filled from /options at startup

// ---------- stepped colour scale (5 steps of one hue, rounded breaks) ----------
export function makeSteps(lo, hi, n = 5) {
  const raw = Math.max((hi - lo) / n, 1e-6), mag = 10 ** Math.floor(Math.log10(raw));
  for (const m of [1, 2, 2.5, 5, 10, 20]) {
    const step = m * mag, edges = [];
    for (let e = Math.floor(lo / step) * step + step; e < hi - 1e-9; e += step) edges.push(+e.toFixed(6));
    if (edges.length <= n - 1) return { edges, step };
  }
  return { edges: [], step: 1 };
}
export const binOf = (v, edges) => edges.filter(e => v >= e).length;
export const stepColor = (bin, nbins) => `var(--h${1 + Math.round(bin * 4 / Math.max(1, nbins - 1))})`;
export function stepLabels(edges, step) {
  const dec = edges.some(e => Math.abs(e - Math.round(e)) > 1e-9);  // 2.5-wide steps need the .5
  const f = x => (dec ? x.toFixed(1) : String(Math.round(x))).replace('-', '−');
  const to = edges.some(e => e < 0) ? ' to ' : '-';  // "−5 to 0" reads better than "−5-0"
  if (!edges.length) return ['all'];
  return [`under ${f(edges[0])}`, ...edges.slice(1).map((e, i) => `${f(edges[i])}${to}${f(e)}`), `${f(edges[edges.length - 1])}+`];
}
export function stepsLegend(labels) {
  return `<span class="steps">${labels.map((l, i) => `<span class="step"><i style="background:${stepColor(i, labels.length)}"></i><span>${l}</span></span>`).join('')}</span>`;
}

export const fold = s => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
export const P = { format: 'ODI', batter: '', bowl_style: null, case: 'fewest_runs' };
export const styleName = v => v[0].toUpperCase() + v.slice(1);
export const cellName = c => `${LEN_NAME[c.length]}, ${LINE_NAME[c.line]}`;
export const Q = { format: 'ODI', batter: '', pick: null, list: null };

// list arrives most-experienced first; every word typed must appear in the name (accents ignored)
export function searchBatters(all, q, max = 40) {
  const toks = fold(q).split(/\s+/).filter(Boolean);
  if (!toks.length) return { hits: all.slice(0, max), total: all.length };
  const scored = [];
  for (const row of all) {
    const f = fold(row[0]);
    if (!toks.every(t => f.includes(t))) continue;
    const words = f.split(/[\s'-]+/);
    scored.push([f.startsWith(toks.join(' ')) ? 0 : toks.every(t => words.some(w => w.startsWith(t))) ? 1 : 2, row]);
  }
  scored.sort((a, b) => a[0] - b[0] || b[1][2] - a[1][2]);
  return { hits: scored.slice(0, max).map(x => x[1]), total: scored.length };
}
