// DOM helpers: element builders, tooltip, stepped legend chips, batter picker.
import { S, nice, searchBatters } from './logic.js';

export const $ = s => document.querySelector(s);
// ---------- small builders ----------
// chips() re-renders the predictor by default; predict.js registers its update() here
export const hooks = { update() {} };
export function chips(el, values, key, label = nice, onPick, after = () => hooks.update()) {
  el.innerHTML = '';
  for (const v of values) {
    const b = document.createElement('button');
    b.className = 'chip'; b.type = 'button'; b.textContent = label(v); b.dataset.v = v;
    b.onclick = () => { onPick ? onPick(v) : (S[key] = v); after(); };
    el.append(b);
  }
}
export const mark = (el, v) => el.querySelectorAll('.chip').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.v === String(v))));
export const svg = (tag, attrs = {}, text) => {
  const e = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  if (text != null) e.textContent = text;
  return e;
};
export const tip = $('#tip');
// content: a string, or { title, rows: [{ v: value, l: label, key: colour }], note }, or a function returning either.
// Text goes in with textContent (names come from data), values lead, labels follow.
function showTip(e, content) {
  const c = typeof content === 'function' ? content() : content;
  tip.replaceChildren();
  const add = (cls, text, parent = tip) => { const n = document.createElement('div'); n.className = cls; n.textContent = text; parent.append(n); return n; };
  if (typeof c === 'string') tip.append(c);
  else {
    if (c.title) add('tt', c.title);
    for (const r of c.rows || []) {
      const row = document.createElement('div'); row.className = 'tr';
      const k = document.createElement('i'); k.className = 'tk' + (r.key ? '' : ' none'); if (r.key) k.style.borderColor = r.key;
      const v = document.createElement('b'); v.textContent = r.v;
      const l = document.createElement('span'); l.textContent = r.l || '';
      row.append(k, v, l); tip.append(row);
    }
    if (c.note) add('tn', c.note);
  }
  const pad = 14, w = tip.offsetWidth, h = tip.offsetHeight;
  let x = e.clientX + pad, y = e.clientY + pad;
  if (x + w > innerWidth - 8) x = e.clientX - w - pad;   // keep it on screen
  if (y + h > innerHeight - 8) y = e.clientY - h - pad;
  tip.style.left = Math.max(8, x) + 'px'; tip.style.top = Math.max(8, y) + 'px'; tip.style.opacity = 1;
}
export function hoverTip(el, content) {
  el._tip = content;  // elements that update in place just swap their content
  if (el._hasTip) return;
  el._hasTip = true;
  el.addEventListener('pointermove', e => showTip(e, el._tip));
  el.addEventListener('pointerleave', () => tip.style.opacity = 0);
}

// ---------- batter picker: typing narrows the list, nothing runs until a batter is chosen ----------
export function picker(input, getList, getSelected, onPick) {
  const box = document.createElement('ul');
  box.className = 'pickbox'; box.id = input.id + '-list'; box.hidden = true; box.setAttribute('role', 'listbox');
  input.after(box);
  input.setAttribute('role', 'combobox'); input.setAttribute('aria-autocomplete', 'list');
  input.setAttribute('aria-expanded', 'false'); input.setAttribute('aria-controls', box.id);
  input.autocomplete = 'off'; input.spellcheck = false;
  let items = [], active = -1, typed = false;

  const search = q => searchBatters(getList(), q);
  const setActive = i => {
    active = i;
    [...box.querySelectorAll('[role=option]')].forEach((li, k) => li.setAttribute('aria-selected', String(k === i)));
    if (i >= 0) { input.setAttribute('aria-activedescendant', `${box.id}-${i}`); box.children[i].scrollIntoView({ block: 'nearest' }); }
    else input.removeAttribute('aria-activedescendant');
  };
  const close = () => { box.hidden = true; input.setAttribute('aria-expanded', 'false'); input.removeAttribute('aria-activedescendant'); typed = false; };
  const revert = () => { input.value = getSelected() || ''; };
  const choose = name => { close(); input.value = name; if (name !== getSelected()) onPick(name); input.blur(); };
  const render = () => {
    const { hits, total } = search(typed ? input.value : '');
    items = hits; box.replaceChildren();
    const note = text => { const li = document.createElement('li'); li.className = 'pe'; li.textContent = text; box.append(li); };
    hits.forEach(([name, hand, balls], i) => {
      const li = document.createElement('li'), n = document.createElement('span'), m = document.createElement('span');
      li.id = `${box.id}-${i}`; li.setAttribute('role', 'option');
      n.className = 'pn'; n.textContent = name;
      m.className = 'pm'; m.textContent = `${hand === 'LHB' ? 'Left' : 'Right'}-handed, ${balls.toLocaleString()} balls`;
      li.append(n, m);
      li.addEventListener('mousedown', e => { e.preventDefault(); choose(name); });
      li.addEventListener('mousemove', () => { if (active !== i) setActive(i); });
      box.append(li);
    });
    if (!hits.length) note(`No batter matches "${input.value.trim()}".`);
    else if (total > hits.length) note(`${(total - hits.length).toLocaleString()} more. Keep typing to narrow the list.`);
    box.hidden = false; input.setAttribute('aria-expanded', 'true');
    setActive(hits.length ? 0 : -1);
  };
  box.addEventListener('mousedown', e => e.preventDefault());  // keep focus when dragging the scrollbar
  input.addEventListener('focus', () => { typed = false; input.select(); render(); });
  input.addEventListener('click', () => { if (box.hidden) render(); });
  input.addEventListener('input', () => { typed = true; render(); });
  input.addEventListener('blur', () => { close(); revert(); });
  input.addEventListener('keydown', e => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      if (box.hidden) return render();
      if (items.length) setActive((active + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length);
    } else if (e.key === 'Enter') {
      if (!box.hidden && active >= 0) { e.preventDefault(); choose(items[active][0]); }
    } else if (e.key === 'Escape' && !box.hidden) { e.preventDefault(); close(); revert(); }
  });
}
