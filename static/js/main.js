// Startup: load options, create pickers, switch tabs.
import { O, P, PACE, Q, S, SPIN, hands } from './logic.js';
import { initPlan, planData, updatePlan } from './plan.js';
import { update } from './predict.js';
import { initSim, updateSim } from './similar.js';
import { $, chips, mark, picker } from './ui.js';

const SUBS = { predict: 'Set the delivery, see what the batter plays and where the runs go.',
               plan: 'Where to bowl to a batter in each phase, and where not to.',
               similar: 'Batters who play the same shots to the same deliveries.' };
function showTab(t) {
  mark($('#tabs'), t);
  $('#predictview').hidden = t !== 'predict'; $('#planview').hidden = t !== 'plan'; $('#simview').hidden = t !== 'similar';
  $('#format').hidden = t !== 'predict';
  $('#sub').textContent = SUBS[t];
  if (t === 'similar') {
    const fresh = Q.batter !== S.batter || Q.format !== S.format;
    Q.batter = S.batter; Q.format = S.format;
    updateSim(fresh || !Q.list);
  }
  if (t === 'plan') {
    const fresh = P.batter !== S.batter || (S.format !== 'Test' && P.format !== S.format);
    P.batter = S.batter; if (S.format !== 'Test') P.format = S.format;
    updatePlan(fresh || !planData);
  }
}
$('#tabs').querySelectorAll('.chip').forEach(b => b.onclick = () => { history.replaceState(null, '', '#' + b.dataset.v); showTab(b.dataset.v); });
const tabFromHash = () => ['plan', 'similar'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'predict';
window.addEventListener('hashchange', () => showTab(tabFromHash()));  // back/forward and typed links
// ---------- boot ----------
fetch('/options').then(r => r.json()).then(o => {
  Object.assign(O, o); O.batterBalls = {};
  for (const [n, h, balls] of o.batters) { hands[n] = h; O.batterBalls[n] = balls; }
  O.profiled = o.profiled = new Set(o.profiled);
  picker($('#batter'), () => o.batters, () => S.batter, n => { S.batter = n; update(); });
  picker($('#pbatter'), () => o.batters, () => P.batter, n => { P.batter = n; updatePlan(); });
  picker($('#sbatter'), () => o.batters.filter(b => o.profiled.has(b[0])), () => Q.batter, n => { Q.batter = n; Q.pick = null; updateSim(); });
  chips($('#format'), o.formats, null, String, v => { S.format = v; });
  chips($('#pace'), PACE.filter(p => o.bowl_styles.includes(p)), 'bowl_style', v => v.replace('right-arm ', 'Right ').replace('left-arm ', 'Left '));
  chips($('#spin'), SPIN.filter(p => o.bowl_styles.includes(p)), 'bowl_style', v => ({ 'off spin': 'Off spin', 'leg spin': 'Leg spin', 'left-arm orthodox': 'Left-arm orthodox', 'left-arm wrist spin': 'Left-arm wrist' }[v]));
  chips($('#variation'), o.variations.slice(0, 10), 'variation');
  $('#ground').insertAdjacentHTML('beforeend', o.grounds.map(g => `<option>${g}</option>`).join(''));
  $('#daynight').insertAdjacentHTML('beforeend', o.daynight.map(g => `<option>${g}</option>`).join(''));
  initPlan(o); initSim();
  update();
  showTab(tabFromHash());
});
