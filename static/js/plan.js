// Bowling plan tab.
import { ROWS, cols, pitchBase } from './charts.js';
import { O, P, PACE, SPIN, binOf, cellName, makeSteps, nice, shotName, stepColor, stepLabels, stepsLegend, styleName } from './logic.js';
import { $, chips, hoverTip, mark, svg } from './ui.js';

// ---------- bowling plan ----------
const CASE_NAME = { fewest_runs: 'Fewest runs', runs_wickets: 'Runs + wickets' };
const METRIC = { fewest_runs: 'rpo', runs_wickets: 'net_rpo' };
export let planData = null, planTimer, planSeq = 0;

function heatmap(g, edges, best, worst, hand, e) {
  const m = METRIC[P.case], cs = cols(hand);
  if (!e || e.dataset.hand !== hand) {  // build once per hand; later calls recolour the same cells, so they animate
    e = svg('svg', { viewBox: '0 0 400 430', class: 'heat fadein', role: 'img' });
    e.dataset.hand = hand; e._cells = {};
    pitchBase(e, hand);
  }
  const key = c => c.line + '|' + c.length;
  const rank = Object.fromEntries([...best.map((c, i) => [key(c), ['good', i + 1]]), ...worst.map((c, i) => [key(c), ['bad', i + 1]])]);
  e.querySelectorAll('.mk').forEach(n => n.remove());
  for (const c of g) {
    const col = cs.find(k => k.line === c.line), [y1, y2] = ROWS[c.length];
    let r = e._cells[key(c)];
    if (!r) { r = svg('rect', { x: col.x, y: y1, width: col.w, height: y2 - y1, class: 'hc' }); e._cells[key(c)] = r; e.append(r); }
    r.style.fill = stepColor(binOf(c[m], edges), edges.length + 1);
    r.style.fillOpacity = c.low_data ? .35 : .92;
    const rows = [{ v: `${c.rpo.toFixed(1)}/over`, l: 'runs conceded' }, { v: `${c.wicket_pct.toFixed(1)}%`, l: 'chance of a wicket' }];
    if (P.case === 'runs_wickets') rows.push({ v: `${c.net_rpo.toFixed(1)}/over`, l: 'net, counting the wicket' });
    rows.push({ v: `${shotName(c.shot, c.length)} ${c.shot_pct}%`, l: 'his usual shot' });
    hoverTip(r, { title: styleName(cellName(c)), rows,
                  note: c.low_data ? `Only ${c.faced} balls faced here, so this is mostly the model's guess` : `${c.faced} balls faced here` });
  }
  for (const c of g) {  // markers on top
    const k = rank[key(c)];
    if (!k) continue;
    const col = cs.find(x => x.line === c.line), [y1, y2] = ROWS[c.length];
    const cx = col.x + col.w / 2, cy = (y1 + y2) / 2, gm = svg('g', { class: 'mk ' + k[0], 'pointer-events': 'none' });
    gm.append(svg('circle', { cx, cy, r: 11, fill: k[0] === 'good' ? 'var(--ink)' : 'var(--surface)', stroke: 'var(--ink)', 'stroke-width': 1.5 }));
    if (k[0] === 'good') gm.append(svg('text', { x: cx, y: cy + 4, 'text-anchor': 'middle' }, k[1]));
    else for (const d of [[-4, -4, 4, 4], [-4, 4, 4, -4]]) gm.append(svg('line', { x1: cx + d[0], y1: cy + d[1], x2: cx + d[2], y2: cy + d[3], stroke: 'var(--ink)', 'stroke-width': 1.6, 'stroke-linecap': 'round' }));
    e.append(gm);
  }
  e.setAttribute('aria-label', `Pitch map of ${CASE_NAME[P.case].toLowerCase()} by line and length. Best: ${best.map(cellName).join('; ')}. Worst: ${worst.map(cellName).join('; ')}.`);
  return e;
}
function planItem(c, i, good) {
  const stats = [`<span><b>${c.rpo.toFixed(1)}</b> runs/over</span>`, `<span><b>${c.wicket_pct.toFixed(1)}%</b> wicket chance</span>`];
  if (P.case === 'runs_wickets') stats.push(`<span><b>${c.net_rpo.toFixed(1)}</b> net</span>`);
  const does = good ? `He mostly plays ${shotName(c.shot, c.length)} (${c.shot_pct}%).`
                    : `He plays ${shotName(c.shot, c.length)} (${c.shot_pct}%)${c.zone ? `, mostly through ${nice(c.zone)}` : ''}.`;
  return `<li><span class="mark ${good ? 'good' : 'bad'}" aria-label="${good ? 'best ' + (i + 1) : 'avoid'}">${good ? i + 1 : ''}</span><span><span class="w">${styleName(cellName(c))}</span>
    <span class="d stats">${stats.join('')}</span><span class="d">${does}</span>${c.low_data ? `<span class="lowdata">Only ${c.faced} balls of data here.</span>` : ''}</span></li>`;
}
function renderPlan() {
  const d = planData; if (!d) return;
  const m = METRIC[P.case];
  const all = d.phases.flatMap(ph => ph[P.case].grid.map(c => c[m]));
  const { edges, step } = makeSteps(Math.min(...all), Math.max(...all));
  $('#plegend').innerHTML = `<span>${P.case === 'runs_wickets' ? 'Net runs per over' : 'Runs per over'}</span>${stepsLegend(stepLabels(edges, step))}
    <span class="key"><span class="mark sm good">1</span>Best places to bowl</span>
    <span class="key"><span class="mark sm bad"></span>Where he's strongest</span>
    <span class="key">Faded cells have little data</span>
    ${O.half_life_years ? `<span class="key">Recent seasons count more (weight halves every ${O.half_life_years} years)</span>` : ''}
    ${P.case === 'runs_wickets' ? `<span class="key">Net = runs conceded − his average (${d.wicket_value}) × wicket chance</span>` : ''}
    ${d.batter_known ? '' : `<span class="key err">${d.batter} isn't in the data. Showing a typical ${d.bat_hand === 'LHB' ? 'left' : 'right'}-hander.</span>`}`;
  const el = $('#phases');
  if (el.children.length !== d.phases.length || ![...el.children].every(n => n.classList.contains('phase'))) {
    el.innerHTML = '';  // cards persist between renders so the heatmaps can animate
    for (const _ of d.phases) {
      const card = document.createElement('article'); card.className = 'panel phase fadein';
      card.innerHTML = '<div class="ph-top"></div><div class="ph-heat"></div><div class="ph-lists"></div>';
      el.append(card);
    }
  }
  d.phases.forEach((ph, i) => {
    const c = ph[P.case], st = ph.state, card = el.children[i];
    card.querySelector('.ph-top').innerHTML = `<h2>${ph.name}<span>overs ${ph.overs[0]}-${ph.overs[1]}</span></h2>
      <p class="assume">Assumes a typical first innings: ${Math.round(st.runs)}/${Math.round(st.wkts)} in over ${Math.round(st.over)}, ${d.batter.split(' ').slice(-1)[0]} on ${Math.round(st.bat_runs)} off ${Math.round(st.bat_bf)}</p>
      <h3 class="sect">Best bowler types</h3><p class="hint">Runs per over, bowling their usual lengths</p>
      <div class="brank">${c.bowlers.slice(0, 4).map((b, k) => `<div class="${b.bowl_style === c.bowl_style ? 'sel' : ''}"><span class="i">${k + 1}</span><span>${styleName(b.bowl_style)}</span><span class="v">${b.score.toFixed(1)}/over</span></div>`).join('')}</div>
      <h3 class="sect">${styleName(c.bowl_style)}${P.bowl_style ? '' : ' (recommended)'}</h3>`;
    const slot = card.querySelector('.ph-heat'), old = slot.querySelector('svg');
    const hm = heatmap(c.grid, edges, c.best, c.worst, d.bat_hand, old);
    if (hm !== old) slot.replaceChildren(hm);
    card.querySelector('.ph-lists').innerHTML = `<h3 class="sect">Bowl here</h3><ul class="plist">${c.best.map((x, k) => planItem(x, k, true)).join('')}</ul>
      <h3 class="sect">Avoid: where he's strongest</h3><ul class="plist">${c.worst.map((x, k) => planItem(x, k, false)).join('')}</ul>
      <h3 class="sect">Tested on similar batters</h3>${evalBlock(c.evaluation)}`;
  });
  const rec = [...new Set(d.phases.map(ph => ph[P.case].recommended))];
  $('#pbowler').querySelector('[data-v="auto"]').textContent = `Recommended (${rec.map(styleName).join(' / ')})`;
}

async function loadPlan() {
  if (!P.batter) return;
  const my = ++planSeq;
  $('#phases').classList.add('loading');
  try {
    const r = await fetch('/plan', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ batter: P.batter, format: P.format, bowl_style: P.bowl_style }) });
    const j = await r.json();
    if (my !== planSeq) return;
    $('#phases').classList.remove('loading');
    if (!r.ok) { $('#phases').innerHTML = `<p class="notice err">${typeof j.detail === 'string' ? j.detail : j.detail.map(x => x.msg).join('; ')}</p>`; return; }
    planData = j; renderPlan();
  } catch (e) { $('#phases').innerHTML = `<p class="notice err">Can't reach the planner. Is the server running?</p>`; }
}
export function updatePlan(refetch = true) {
  mark($('#pformat'), P.format); mark($('#pcase'), P.case); mark($('#pbowler'), P.bowl_style || 'auto');
  if (document.activeElement !== $('#pbatter')) $('#pbatter').value = P.batter;
  if (refetch) { clearTimeout(planTimer); planTimer = setTimeout(loadPlan, 150); } else renderPlan();
}
export function initPlan(o) {
  chips($('#pformat'), ['T20', 'ODI'], null, String, v => P.format = v, updatePlan);
  // both cases come back in one response, so switching case only re-renders
  chips($('#pcase'), Object.keys(CASE_NAME), null, v => CASE_NAME[v], v => P.case = v, () => updatePlan(false));
  chips($('#pbowler'), ['auto', ...PACE, ...SPIN].filter(v => v === 'auto' || o.bowl_styles.includes(v)), null,
        v => v === 'auto' ? 'Recommended' : styleName(v), v => P.bowl_style = v === 'auto' ? null : v, updatePlan);
}


// ---------- plan evaluation on similar batters ----------
const VERDICT = { 'worked': ['worked', 'Worked'], 'partly': ['partly', 'Partly worked'],
                  'did not work': ['bad', "Didn't work"], 'no data': ['nodata', 'No data'] };
function evalBlock(e) {
  if (!e || !e.similar.length) return '<p class="hint">No similar batters with enough data to test this plan.</p>';
  return `<div class="eval"><p class="sum">Worked against ${e.worked} of ${e.judged} similar batters (${e.weighted_success}% weighted by similarity)</p>
    <ul class="plist">${e.similar.map(r => { const [cls, word] = VERDICT[r.verdict];
      return `<li><span><span><span class="w">${r.batter}</span><span class="verdict ${cls}">${word}</span></span>
        <span class="d">Similarity ${Math.round(r.score)}. ${r.text}.</span></span></li>`; }).join('')}</ul></div>`;
}
