// Shot predictor tab.
import { ROWS, X0, cols, pitchBase, wheel } from './charts.js';
import { LENGTHS, LEN_NAME, LEN_SHORT, LINE_NAME, O, OVERS, OVER_STEP, S, SERIES, hands, nice, overBin, overLabel, shotName, styleName } from './logic.js';
import { $, chips, hooks, hoverTip, mark, svg, tip } from './ui.js';

function drawPitch() {
  const p = $('#pitch');
  const { cs, W } = pitchBase(p, S.bat_hand);
  // selected line + length highlight
  const sc = cs.find(c => c.line === S.line), [ly1, ly2] = ROWS[S.length];
  p.append(svg('rect', { x: sc.x, y: 0, width: sc.w, height: 430, fill: 'var(--ball)', 'fill-opacity': .07 }));
  p.append(svg('rect', { x: X0, y: ly1, width: W, height: ly2 - ly1, fill: 'var(--ball)', 'fill-opacity': .07 }));
  // ball
  const bx = sc.x + sc.w / 2, by = (ly1 + ly2) / 2;
  if (S.length === 'FULL_TOSS') p.append(svg('circle', { cx: bx, cy: by, r: 13, fill: 'none', stroke: 'var(--ball)', 'stroke-dasharray': '2 3' }));
  p.append(svg('circle', { cx: bx, cy: by, r: 9, fill: 'var(--ball)' }));
  p.append(svg('path', { d: `M${bx - 6} ${by - 3} Q${bx} ${by + 2} ${bx + 6} ${by - 3}`, stroke: '#fff', 'stroke-width': 1.2, fill: 'none', 'stroke-dasharray': '1.5 1.5', opacity: .8 }));
  // hit cells last so they sit on top
  for (const c of cs) for (const L of LENGTHS) {
    const [y1, y2] = ROWS[L];
    const r = svg('rect', { x: c.x, y: y1, width: c.w, height: y2 - y1, class: 'cell' });
    r.onclick = () => { S.line = c.line; S.length = L; update(); };
    hoverTip(r, `${LEN_NAME[L]}, ${LINE_NAME[c.line]}`);
    p.append(r);
  }
  $('#pitchtext').textContent = `${styleName(LEN_NAME[S.length])}, ${LINE_NAME[S.line]}`;
}
$('#pitch').addEventListener('keydown', e => {
  const cs = cols().map(c => c.line), i = cs.indexOf(S.line), j = LENGTHS.indexOf(S.length);
  const moves = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
  if (!moves[e.key]) return;
  e.preventDefault();
  const [dx, dy] = moves[e.key];
  S.line = cs[Math.max(0, Math.min(cs.length - 1, i + dx))];
  S.length = LENGTHS[Math.max(0, Math.min(LENGTHS.length - 1, j + dy))];
  update();
});

// ---------- this over ----------
function drawOver() {
  const el = $('#overballs'); el.innerHTML = '';
  S.prev.forEach((p, i) => {
    const b = document.createElement('button');
    b.className = 'ballslot done'; b.type = 'button';
    b.innerHTML = `<span><b>${p.runs}</b>${LEN_SHORT[p.length]}</span>`;
    b.setAttribute('aria-label', `Ball ${i + 1}: ${LEN_NAME[p.length]}, ${LINE_NAME[p.line]}, ${shotName(p.shot, p.length)}, ${p.runs} runs. Click to remove.`);
    hoverTip(b, { title: styleName(`${LEN_NAME[p.length]}, ${LINE_NAME[p.line]}`), rows: [{ v: shotName(p.shot, p.length), l: 'shot' }, { v: String(p.runs), l: p.runs === 1 ? 'run' : 'runs' }], note: 'Click to remove' });
    b.onclick = () => { S.prev.splice(i, 1); tip.style.opacity = 0; update(); };
    el.append(b);
  });
  for (let i = S.prev.length; i < 6; i++) {
    const d = document.createElement('div');
    d.className = 'ballslot' + (i === S.prev.length ? ' now' : '');
    d.textContent = i === S.prev.length ? 'now' : i + 1;
    el.append(d);
  }
  $('#overtext').textContent = `${styleName(overLabel())}, ball ${S.prev.length + 1}`;
}
$('#playbtn').onclick = () => {
  const box = $('#played'); box.classList.toggle('open');
  if (!box.classList.contains('open')) return;
  const top = last ? last.top.map(t => t.shot) : [];
  const rest = O.classes.filter(c => !top.includes(c));
  chips($('#playedshot'), [...top, ...rest], null, v => shotName(v), v => { box.dataset.shot = v; mark($('#playedshot'), v); });
  box.dataset.shot = top[0] || 'defend'; mark($('#playedshot'), box.dataset.shot);
  chips($('#playedruns'), ['0', '1', '2', '3', '4', '6'], null, String, v => {
    const r = +v;
    S.prev.push({ line: S.line, length: S.length, shot: box.dataset.shot, runs: r });
    S.runs += r; S.bat_runs += r; S.balls_faced += 1;
    if (S.prev.length >= 6) { S.prev = []; S.over = Math.min(S.over + 1, OVERS[S.format]); }
    box.classList.remove('open');
  });
};
$('#clearover').onclick = () => { S.prev = []; update(); };

// ---------- match situation ----------
function bindNum(id) { const el = $('#' + id); el.oninput = () => { if (el.value !== '') { S[id] = +el.value; update(false); } }; }
['runs', 'wkts', 'target', 'bat_runs', 'balls_faced'].forEach(bindNum);
// a range stands for its middle over (the model takes a single over number)
$('#over').onchange = e => { const b = overBin(+e.target.value); S.over = Math.round((b.lo + b.hi) / 2); update(); };
let overFor = null;
function overOptions() {
  if (overFor !== S.format) {
    const opts = [];
    for (let lo = 1; lo <= OVERS[S.format]; lo += OVER_STEP[S.format]) { const b = overBin(lo); opts.push(`<option value="${lo}">${b.lo === b.hi ? lo : `${b.lo}-${b.hi}`}</option>`); }
    $('#over').innerHTML = opts.join(''); overFor = S.format;
  }
  $('#over').value = overBin(S.over).lo;
}
$('#ground').onchange = e => { S.ground = e.target.value; update(); };
$('#daynight').onchange = e => { S.daynight = e.target.value; update(); };

// ---------- render everything from S ----------
function clamp() {
  S.over = Math.max(1, Math.min(S.over || 1, OVERS[S.format]));
  if (S.format !== 'Test' && S.inns > 2) S.inns = 2;
}
export function update(syncInputs = true) {
  clamp();
  // batting hand is a fact from the data, never an input; a batter who isn't in the data is drawn as a typical right-hander
  S.bat_hand = hands[S.batter] || 'RHB';
  mark($('#format'), S.format); mark($('#pace'), S.bowl_style); mark($('#spin'), S.bowl_style);
  mark($('#variation'), S.variation); mark($('#inns'), S.inns);
  const t20 = S.format === 'T20';
  $('#variation').querySelectorAll('.chip').forEach(b => b.disabled = !t20);
  $('#varnote').textContent = t20 ? '' : 'only recorded in T20 data';
  chipsInns();
  $('#targetfield').style.display = S.inns === 2 && S.format !== 'Test' ? '' : 'none';
  overOptions();
  if (syncInputs) for (const k of ['runs', 'wkts', 'target', 'bat_runs', 'balls_faced']) $('#' + k).value = S[k];
  if (document.activeElement !== $('#batter')) $('#batter').value = S.batter;
  const n = O.batterBalls[S.batter];
  $('#batinfo').textContent = n ? `${S.bat_hand === 'LHB' ? 'Left' : 'Right'}-handed, ${n.toLocaleString()} balls in data` : S.batter ? 'Not in the data' : '';
  drawPitch(); drawOver();
  predictSoon();
}
let innsFor = null;
function chipsInns() {
  const want = S.format === 'Test' ? 4 : 2;
  if (innsFor !== want) { chips($('#inns'), [...Array(want)].map((_, i) => String(i + 1)), null, String, v => S.inns = +v); innsFor = want; }
  mark($('#inns'), S.inns);
}

// ---------- predict ----------
let timer, seq = 0, last = null;
function predictSoon() { clearTimeout(timer); timer = setTimeout(predict, 120); }
async function predict() {
  if (!S.batter) return;
  const my = ++seq;
  const body = { format: S.format, batter: S.batter, bowl_style: S.bowl_style, line: S.line, length: S.length,
    over: S.over, inns: S.inns, runs: S.runs, wkts: S.wkts, bat_runs: S.bat_runs, balls_faced: S.balls_faced, prev: S.prev,
    variation: S.format === 'T20' ? S.variation : null };
  if (S.inns === 2 && S.format !== 'Test') body.target = S.target;
  if (S.ground) body.ground = S.ground;
  if (S.daynight) body.daynight = S.daynight;
  $('#results').classList.add('loading');
  try {
    const r = await fetch('/predict', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const j = await r.json();
    if (my !== seq) return; // a newer request is in flight
    $('#results').classList.remove('loading');
    if (!r.ok) { $('#notices').innerHTML = `<p class="notice err">${typeof j.detail === 'string' ? j.detail : j.detail.map(d => d.msg).join('; ')}</p>`; return; }
    last = j; render(j);
  } catch (e) { $('#notices').innerHTML = `<p class="notice err">Can't reach the predictor. Is the server running?</p>`; }
}
function render(j) {
  $('#summary').innerHTML = `<b>${LEN_NAME[S.length][0].toUpperCase() + LEN_NAME[S.length].slice(1)}, ${LINE_NAME[S.line]}</b>
    <span class="meta"><span>${styleName(S.bowl_style)}${S.format === 'T20' && S.variation !== 'stock' ? ', ' + S.variation : ''} to ${S.batter} (${S.bat_hand})</span><span>${S.format}, ${overLabel()}, ball ${S.prev.length + 1}</span><span>Score ${S.runs}/${S.wkts}</span></span>`;
  $('#notices').innerHTML = j.batter_known ? '' : `<p class="notice">${S.batter} isn't in the data, so this is a typical ${S.bat_hand === 'LHB' ? 'left' : 'right'}-hander. Scoring maps show everyone's average.</p>`;
  // cards and bars persist between predictions, so wheels and bars animate to new values
  const cards = $('#cards');
  if (cards.children.length !== 3) {
    cards.innerHTML = '';
    for (let i = 0; i < 3; i++) {
      const c = document.createElement('article'); c.className = 'card fadein';
      c.innerHTML = '<div class="head"></div><div class="rank"></div><div class="wslot"></div><div class="caption"></div>';
      cards.append(c);
    }
  }
  j.top.forEach((t, i) => {
    const c = cards.children[i];
    c.querySelector('.head').innerHTML = `<span class="swatch" style="background:${SERIES[i]}"></span><span class="name"></span><span class="pct">${Math.round(t.pct)}%</span>`;
    c.querySelector('.name').textContent = shotName(t.shot);
    c.querySelector('.rank').textContent = ['Most likely', 'Second most likely', 'Third most likely'][i];
    const slot = c.querySelector('.wslot'), cap = c.querySelector('.caption');
    if (t.shot === 'leave') {
      slot.innerHTML = `<div class="nomap">${shotName('leave') === 'leave' ? 'A leave' : 'A leave or duck'} doesn't score, so there's no scoring map</div>`;
      cap.innerHTML = '';
    } else {
      const old = slot.querySelector('svg'), w = wheel(t.share, SERIES[i], S.bat_hand, old);
      if (w !== old) slot.replaceChildren(w);
      const [z, v] = Object.entries(t.share).sort((a, b) => b[1] - a[1])[0];
      cap.innerHTML = `Mostly through <b>${nice(z)}</b> (${Math.round(v * 100)}%)<br><span class="m">${t.runs >= 40 ? `from ${S.batter.split(' ').slice(-1)[0]}'s own scoring, recent seasons weighted more` : 'Little data for this batter, so this is mostly the average batter'}</span>`;
    }
  });
  const topIdx = Object.fromEntries(j.top.map((t, i) => [t.shot, i]));
  const bars = $('#bars'); bars._rows = bars._rows || {};
  for (const [sh, pc] of Object.entries(j.shots)) {  // already sorted, most likely first
    let row = bars._rows[sh];
    if (!row) {
      row = document.createElement('div'); row.className = 'bar';
      row.innerHTML = '<span class="n"></span><span class="t"><span class="f"></span></span><span class="v"></span>';
      bars._rows[sh] = row;
    }
    row.classList.toggle('top', sh in topIdx);
    row.querySelector('.n').textContent = shotName(sh);
    const f = row.querySelector('.f');
    f.style.width = pc + '%'; f.style.backgroundColor = sh in topIdx ? SERIES[topIdx[sh]] : '';
    row.querySelector('.v').textContent = (pc < 1 ? '<1' : Math.round(pc)) + '%';
    bars.append(row);  // moves the row into the new order
  }
}


hooks.update = update;  // see ui.js: chips() calls it by default
