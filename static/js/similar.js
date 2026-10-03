// Similar players tab.
import { DIF_LABELS, difmap, radar } from './charts.js';
import { O, Q, stepsLegend, styleName } from './logic.js';
import { $, chips, mark } from './ui.js';

// ---------- similar players ----------
let simSeq = 0, repSeq = 0;
async function post(url, body) {
  const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const j = await r.json();
  if (!r.ok) throw new Error(typeof j.detail === 'string' ? j.detail : j.detail.map(x => x.msg).join('; '));
  return j;
}
async function loadSimilar() {
  if (!Q.batter) return;
  const my = ++simSeq;
  $('#simlist').classList.add('loading');
  try {
    const j = await post('/similar', { batter: Q.batter, format: Q.format, k: 12 });
    if (my !== simSeq) return;
    $('#simlist').classList.remove('loading');
    Q.list = j.similar; Q.hand = j.hand; Q.ref = j.reference;
    $('#simref').innerHTML = `<span>Similarity runs from 0 to 100. For reference, of all pairs of ${Q.format} batters the top 1% score <b>${Math.round(j.reference.top1)}</b>+,
      the top 5% <b>${Math.round(j.reference.top5)}</b>+ and the top 10% <b>${Math.round(j.reference.top10)}</b>+.</span>`;
    if (!Q.list.some(x => x.batter === Q.pick)) Q.pick = Q.list[0] && Q.list[0].batter;
    renderSimList(); loadReport();
  } catch (e) {
    $('#simlist').classList.remove('loading');
    Q.list = []; $('#simlist').innerHTML = `<p class="notice err">${e.message}</p>`; $('#report').innerHTML = '';
  }
}
function renderSimList() {
  const el = $('#simlist'); el.innerHTML = '';
  if (!Q.list.length) { el.innerHTML = '<p class="notice">No batters with enough data in this format.</p>'; return; }
  for (const x of Q.list) {
    const b = document.createElement('button'); b.className = 'simcard'; b.type = 'button';
    b.setAttribute('aria-pressed', String(x.batter === Q.pick));
    b.innerHTML = `<span class="sc">${Math.round(x.score)}</span><span class="nm">${x.batter}</span><span></span>
      <span class="t"><span style="width:${Math.min(x.score, 100)}%"></span></span>
      <span class="meta">${x.hand}, ${x.balls.toLocaleString()} ${Q.format} balls${x.other_formats_balls ? ` (+${x.other_formats_balls.toLocaleString()} in other formats)` : ''}</span>`;
    b.onclick = () => { Q.pick = x.batter; renderSimList(); loadReport(); };
    el.append(b);
  }
}
async function loadReport() {
  if (!Q.pick) return;
  const my = ++repSeq;
  $('#report').classList.add('loading');
  try {
    const c = await post('/compare', { a: Q.batter, b: Q.pick, format: Q.format });
    if (my !== repSeq) return;
    $('#report').classList.remove('loading'); renderReport(c);
  } catch (e) { $('#report').innerHTML = `<p class="notice err">${e.message}</p>`; }
}
function renderReport(c) {
  const la = c.a.split(' ').slice(-1)[0], lb = c.b.split(' ').slice(-1)[0];
  const kinds = Object.entries(c.by_kind).map(([k, v]) => `<div><span>vs ${k}</span><span class="t"><span style="width:${v || 0}%"></span></span><span>${v == null ? '-' : Math.round(v)}</span></div>`).join('');
  const li = xs => xs.length ? xs.map(x => `<li style="grid-template-columns:1fr"><span><span class="w">${styleName(x.cell)}</span><span class="d">${styleName(x.text)}.</span></span></li>`).join('') : '<li class="d">Not enough balls that both batters have faced.</li>';
  const orow = n => { const o = c.outcomes[n]; const f = (k, key) => o[k][key] == null ? '-' : o[k][key];
    return `<tr><td>${n}</td><td>${f('pace', 'rpo')}</td><td>${f('pace', 'balls_per_wicket')}</td><td>${f('spin', 'rpo')}</td><td>${f('spin', 'balls_per_wicket')}</td></tr>`; };
  $('#report').innerHTML = `<h2>${c.a} <span class="d" style="font-weight:400">vs</span> ${c.b}</h2>
    <div class="row" style="margin-top:6px"><span class="big">${Math.round(c.score)}</span>
      <span class="d">Similarity in ${c.format}, ${c.score >= c.reference.top1 ? 'in the top 1% of all pairs' : c.score >= c.reference.top5 ? 'in the top 5% of all pairs' : c.score >= c.reference.top10 ? 'in the top 10% of all pairs' : 'outside the top 10% of pairs'}</span></div>
    <div class="kinds">${kinds}</div>
    <div class="cols2">
      <div><h3 class="sect">Where they play alike</h3><ul class="plist">${li(c.same)}</ul></div>
      <div><h3 class="sect">Where they differ</h3><ul class="plist">${li(c.different)}</ul></div>
    </div>
    <h3 class="sect">Shot mix</h3><p class="hint">Share of balls for each kind of shot</p>
    <div class="legend"><span class="lkey"><i style="border-color:var(--s1)"></i>${c.a}</span><span class="lkey"><i style="border-color:var(--s2)"></i>${c.b}</span><span class="lkey"><i class="dash" style="border-color:var(--muted)"></i>typical batter</span></div>
    <div class="radars"><figure id="rd-pace"><figcaption>vs pace</figcaption></figure><figure id="rd-spin"><figcaption>vs spin</figcaption></figure></div>
    <details class="nums"><summary>Show numbers</summary><div class="tablewrap" id="mixtable"></div></details>
    <h3 class="sect">How differently they play each ball</h3><p class="hint">Drawn for ${la} (${c.hands[0]}). Faded cells: not enough balls from both.</p>
    <div class="legend">${stepsLegend(DIF_LABELS)}</div>
    <div class="difmaps"><figure id="dm-pace"><figcaption>vs pace</figcaption></figure><figure id="dm-spin"><figcaption>vs spin</figcaption></figure></div>
    <h3 class="sect">Outcomes in ${c.format}</h3>
    <div class="tablewrap"><table class="out"><thead><tr><th></th><th>pace runs/over</th><th>balls/wkt</th><th>spin runs/over</th><th>balls/wkt</th></tr></thead>
      <tbody>${orow(c.a)}${orow(c.b)}</tbody></table></div>`;
  $('#dm-pace').prepend(difmap(c, 'pace')); $('#dm-spin').prepend(difmap(c, 'spin'));
  for (const kind of ['pace', 'spin']) {
    const mx = c.shot_mix[kind];
    if (mx && (mx.a || mx.b)) $('#rd-' + kind).prepend(radar(mx, c.a, c.b));
    else $('#rd-' + kind).insertAdjacentHTML('afterbegin', '<p class="d" style="font-size:13px">Not enough balls.</p>');
  }
  // the same numbers as a table, so nothing is only readable by hovering (names via textContent)
  const groups = Object.keys(c.shot_mix.pace.typical || c.shot_mix.spin.typical || {});
  const tbl = document.createElement('table'); tbl.className = 'out';
  const head = tbl.createTHead().insertRow();
  ['', `${la} pace`, `${lb} pace`, 'typical pace', `${la} spin`, `${lb} spin`, 'typical spin'].forEach(h => { const th = document.createElement('th'); th.textContent = h; head.append(th); });
  const body = tbl.createTBody();
  for (const g of groups) {
    const row = body.insertRow(); row.insertCell().textContent = g;
    for (const kind of ['pace', 'spin']) for (const who of ['a', 'b', 'typical']) {
      const m = c.shot_mix[kind][who]; row.insertCell().textContent = m ? m[g].toFixed(1) + '%' : '-';
    }
  }
  $('#mixtable').append(tbl);
}
export function updateSim(refetch = true) {
  mark($('#sformat'), Q.format);
  if (document.activeElement !== $('#sbatter')) $('#sbatter').value = Q.batter;
  if (!O.profiled.has(Q.batter)) {  // too little data to profile: say so here instead of asking the server
    simSeq++; repSeq++; Q.list = null;
    const p = document.createElement('p'); p.className = 'notice';
    p.textContent = `${Q.batter} has too little data to profile. Pick another batter.`;
    $('#simlist').replaceChildren(p); $('#report').replaceChildren();
    return;
  }
  if (refetch) loadSimilar();
}
export function initSim() {
  chips($('#sformat'), ['T20', 'ODI', 'Test'], null, String, v => Q.format = v, updateSim);
}
