// SVG charts: pitch map, wagon wheel, radar, difference map.
import { LENGTHS, LEN_NAME, LINES, LINE_NAME, LINE_SHORT, S, binOf, nice, stepColor, styleName } from './logic.js';
import { hoverTip, svg } from './ui.js';

// ---------- pitch map (view from behind the bowler; batter's stumps at the top) ----------
// not to scale: off / stumps / leg drawn equal width so the ball is easy to place; the wide bands take up the rest
export const COLW = [68, 44, 44, 44, 68], ROWS = { FULL_TOSS: [18, 46], YORKER: [58, 92], FULL: [92, 160], GOOD_LENGTH: [160, 248], SHORT_OF_A_GOOD_LENGTH: [248, 322], SHORT: [322, 400] };
export const X0 = 14;
export function cols(hand = S.bat_hand) { // off side on the left for a right-hander (as seen from behind the bowler)
  const order = hand === 'LHB' ? [...LINES].reverse() : LINES;
  let x = X0; return order.map((l, i) => { const w = hand === 'LHB' ? COLW[4 - i] : COLW[i]; const c = { line: l, x, w }; x += w; return c; });
}
// grass, pitch strip, crease, stumps, length bands and labels; returns the column layout
export function pitchBase(p, hand) {
  p.innerHTML = ''; p.classList.add('pitchmap');
  const cs = cols(hand), W = cs.reduce((a, c) => a + c.w, 0);
  p.append(svg('rect', { x: X0, y: 0, width: W, height: 430, rx: 10, fill: 'var(--grass)' }));
  p.append(svg('rect', { x: X0 + 30, y: 10, width: W - 60, height: 410, rx: 4, fill: 'var(--pitch)', stroke: 'var(--pitch-edge)' }));
  p.append(svg('line', { x1: X0 + 30, x2: X0 + W - 30, y1: 58, y2: 58, stroke: 'var(--crease)', 'stroke-width': 2 }));
  const midx = cs.find(c => c.line === 'ON_THE_STUMPS'); const cx = midx.x + midx.w / 2;
  for (const d of [-7, 0, 7]) p.append(svg('rect', { x: cx + d - 2, y: 28, width: 4, height: 12, rx: 1.5, fill: 'var(--stump)' }));
  for (const L of LENGTHS) {
    const [y1, y2] = ROWS[L];
    if (L !== 'FULL_TOSS') p.append(svg('line', { x1: X0 + 30, x2: X0 + W - 30, y1: y2, y2, stroke: 'var(--pitch-edge)', 'stroke-dasharray': '3 4' }));
    p.append(svg('text', { x: X0 + W + 6, y: (y1 + y2) / 2 + 4 }, LEN_NAME[L]));
  }
  cs.forEach(c => p.append(svg('text', { x: c.x + c.w / 2, y: 418, 'text-anchor': 'middle' }, LINE_SHORT[c.line])));
  const offLeft = hand !== 'LHB';
  p.append(svg('text', { x: X0 + 4, y: 12, class: 'side' }, offLeft ? 'OFF' : 'LEG'));
  p.append(svg('text', { x: X0 + W - 4, y: 12, class: 'side', 'text-anchor': 'end' }, offLeft ? 'LEG' : 'OFF'));
  return { cs, W };
}
// ---------- wagon wheel (same view: bowler at the bottom, off side left for a right-hander) ----------
const ZONE_ANG = { mid_off: [0, 45], cover: [45, 90], point: [90, 135], third_man: [135, 180],
                   mid_on: [0, 45], mid_wicket: [45, 90], square_leg: [90, 135], fine_leg: [135, 180] };
const OFFSIDE = new Set(['mid_off', 'cover', 'point', 'third_man']);
export function wheel(share, color, hand, e) {
  const cx = 100, cy = 96, R = 86, r0 = 10;
  const offSign = hand === 'LHB' ? 1 : -1;
  const pt = (deg, r, s) => { const t = deg * Math.PI / 180; return [cx + s * r * Math.sin(t), cy + r * Math.cos(t)]; };
  if (!e || e.dataset.hand !== hand) {  // build once per hand; later calls only recolour, so zones animate
    e = svg('svg', { viewBox: '0 0 200 204', class: 'wheel fadein', role: 'img' });
    e.dataset.hand = hand; e._w = {};
    e.append(svg('circle', { cx, cy, r: R + 4, fill: 'var(--grass)' }));
    for (const z of Object.keys(ZONE_ANG)) {
      const s = OFFSIDE.has(z) ? offSign : -offSign, [a1, a2] = ZONE_ANG[z], sw = s > 0 ? 0 : 1;
      const [x1, y1] = pt(a1, r0, s), [x2, y2] = pt(a1, R, s), [x3, y3] = pt(a2, R, s), [x4, y4] = pt(a2, r0, s);
      e._w[z] = svg('path', { class: 'wedge', d: `M${x1} ${y1}L${x2} ${y2}A${R} ${R} 0 0 ${sw} ${x3} ${y3}L${x4} ${y4}A${r0} ${r0} 0 0 ${1 - sw} ${x1} ${y1}Z` });
      e.append(e._w[z]);
    }
    e.append(svg('circle', { cx, cy, r: R * .55, fill: 'none', stroke: 'var(--surface)', 'stroke-opacity': .7, 'stroke-dasharray': '2 3', 'pointer-events': 'none' }));
    e.append(svg('rect', { x: cx - 3, y: cy - 4, width: 6, height: 24, rx: 1, fill: 'var(--pitch)', stroke: 'var(--pitch-edge)', 'stroke-width': .6, 'pointer-events': 'none' }));
    e.append(svg('text', { x: cx + offSign * (R - 4), y: 12, 'text-anchor': offSign < 0 ? 'start' : 'end' }, 'OFF'));
    e.append(svg('text', { x: cx - offSign * (R - 4), y: 12, 'text-anchor': offSign < 0 ? 'end' : 'start' }, 'LEG'));
    e.append(svg('text', { x: cx, y: 202, 'text-anchor': 'middle' }, 'bowler'));
  }
  const max = Math.max(...Object.values(share));
  const ranked = Object.entries(share).sort((a, b) => b[1] - a[1]);
  for (const [z, v] of Object.entries(share)) {
    const w = e._w[z];
    w.style.fill = color; w.style.fillOpacity = (0.14 + 0.82 * v / max).toFixed(3);
    hoverTip(w, { title: nice(z), rows: [{ v: Math.round(v * 100) + '%', l: 'of his runs from this shot' }] });
  }
  e.querySelectorAll('.zl').forEach(n => n.remove());
  for (const [z, v] of ranked.slice(0, 2)) {  // label the two biggest zones directly
    const s = OFFSIDE.has(z) ? offSign : -offSign, [a1, a2] = ZONE_ANG[z], [x, y] = pt((a1 + a2) / 2, R * .74, s);
    e.append(svg('text', { x, y: y + 3.5, 'text-anchor': 'middle', class: 'zl', 'pointer-events': 'none' }, Math.round(v * 100) + '%'));
  }
  e.setAttribute('aria-label', 'Scoring zones: ' + ranked.map(([z, v]) => `${nice(z)} ${Math.round(v * 100)}%`).join(', '));
  return e;
}

// how differently two batters play a ball, in three named steps (Jensen-Shannon distance between their shot mixes)
export const DIF_EDGES = [0.15, 0.3], DIF_LABELS = ['almost the same', 'some differences', 'very different'];
export function difmap(c, kind) {
  const e = svg('svg', { viewBox: '0 0 400 430', class: 'heat fadein', role: 'img' });
  const { cs } = pitchBase(e, c.hands[0]);
  for (const x of c.cells.filter(x => x.kind === kind)) {
    const col = cs.find(k => k.line === x.line), [y1, y2] = ROWS[x.length];
    const bin = x.distance == null ? 0 : binOf(x.distance, DIF_EDGES);
    const r = svg('rect', { x: col.x, y: y1, width: col.w, height: y2 - y1, class: 'hc',
      style: `fill: ${stepColor(bin, 3)}; fill-opacity: ${x.distance == null ? .12 : .92}` });
    hoverTip(r, x.distance == null
      ? { title: `${styleName(kind)}, ${LEN_NAME[x.length]}, ${LINE_NAME[x.line]}`, note: 'Not enough balls from both batters' }
      : { title: `${styleName(kind)}, ${LEN_NAME[x.length]}, ${LINE_NAME[x.line]}`, rows: [{ v: DIF_LABELS[bin], l: `(distance ${x.distance.toFixed(2)})` }] });
    e.append(r);
  }
  e.setAttribute('aria-label', `Where they play ${kind} differently; darker = more different.`);
  return e;
}

// shot mix of both batters (and the typical batter) as a radar, one per bowler kind
export function radar(mix, nameA, nameB) {
  const axes = Object.keys(mix.typical || mix.a || mix.b), n = axes.length;
  const cx = 150, cy = 140, R = 96;
  const series = [[mix.typical, 'var(--muted)', 'typical batter', true], [mix.a, 'var(--s1)', nameA], [mix.b, 'var(--s2)', nameB]].filter(x => x[0]);
  const peak = Math.max(...series.flatMap(([m]) => axes.map(k => m[k])));
  const top = [10, 20, 30, 40, 50, 60, 80, 100].find(x => x >= peak) || 100;
  const pos = (i, v) => { const t = -Math.PI / 2 + i * 2 * Math.PI / n, r = R * v / top; return [cx + r * Math.cos(t), cy + r * Math.sin(t)]; };
  const e = svg('svg', { viewBox: '0 0 300 290', class: 'radar', role: 'img' });
  for (const f of [0.5, 1]) e.append(svg('polygon', { class: 'ring', points: axes.map((_, i) => pos(i, top * f).join(',')).join(' ') }));
  e.append(svg('text', { x: cx + 3, y: cy - R - 3, class: 'tick' }, top + '%'));
  e.append(svg('text', { x: cx + 3, y: cy - R / 2 - 3, class: 'tick' }, top / 2 + '%'));
  axes.forEach((k, i) => {
    const [x, y] = pos(i, top);
    e.append(svg('line', { class: 'spoke', x1: cx, y1: cy, x2: x, y2: y }));
    const [lx, ly] = pos(i, top * 1.16), ca = Math.cos(-Math.PI / 2 + i * 2 * Math.PI / n);
    e.append(svg('text', { x: lx, y: ly + 3, 'text-anchor': Math.abs(ca) < .2 ? 'middle' : ca > 0 ? 'start' : 'end' }, k));
  });
  for (const [m, col, , dashed] of series) {
    e.append(svg('polygon', { class: 'series', points: axes.map((k, i) => pos(i, m[k]).join(',')).join(' '),
      fill: dashed ? 'none' : col, 'fill-opacity': dashed ? 0 : .12, stroke: col, 'stroke-width': dashed ? 1.5 : 2,
      'stroke-dasharray': dashed ? '4 3' : 'none', 'stroke-linejoin': 'round', 'pointer-events': 'none' }));
  }
  axes.forEach((k, i) => {  // one hit area per axis: a wedge from the centre, bigger than the marks
    const a1 = -Math.PI / 2 + (i - .5) * 2 * Math.PI / n, a2 = a1 + 2 * Math.PI / n, RR = R * 1.1;
    const h = svg('path', { class: 'hit', d: `M${cx} ${cy}L${cx + RR * Math.cos(a1)} ${cy + RR * Math.sin(a1)}A${RR} ${RR} 0 0 1 ${cx + RR * Math.cos(a2)} ${cy + RR * Math.sin(a2)}Z` });
    hoverTip(h, { title: k, rows: series.slice().reverse().map(([m, col, name]) => ({ v: m[k].toFixed(1) + '%', l: name, key: col })) });
    e.append(h);
  });
  e.setAttribute('aria-label', 'Shot mix: ' + axes.map(k => `${k} ${series.map(([m, , name]) => `${name} ${m[k]}%`).join(', ')}`).join('; '));
  return e;
}
