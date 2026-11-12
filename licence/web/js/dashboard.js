import { STATUS, date, inDays, money, plural } from './format.js';
import { badge, countUp, h, play, stagger } from './ui.js';

// Overview view. `actions.setStatus(id, status)` is used by the inactive list,
// `actions.open(id)` jumps to a license in the table.
export function renderDashboard(d, actions, { first = false } = {}) {
  document.getElementById('as-of').textContent = `Stanje na dan ${date(d.as_of)}`;
  renderKpis(d, first);
  renderInactive(d.inactive, actions);
  renderExpiring(d.expiring, d.window_days, actions);
  renderCategories(d.by_category);
}

function moneyValue(el, total, key) {
  countUp(el, Number(total[key]), (n) => money(n, total.currency));
  return el;
}

/** KPI tiles are created once and then updated in place, so numbers can animate. */
function tile(id, cls) {
  let el = document.getElementById(id);
  if (!el) el = h('div', { class: `kpi ${cls}`, id });
  el.className = `kpi ${cls}`;
  return el;
}

function moneyLines(tileEl, totals, key) {
  const lines = totals.length ? totals : [null];
  return lines.map((t, i) => {
    const slot = tileEl.querySelector(`[data-line="${i}"][data-cur="${t?.currency ?? '-'}"]`)
      ?? h('div', { class: `kpi__value${i ? ' kpi__value--2' : ''}`, 'data-line': i, 'data-cur': t?.currency ?? '-' });
    if (t) moneyValue(slot, t, key); else slot.textContent = '—';
    return slot;
  });
}

function renderKpis(d, first) {
  const box = document.getElementById('kpis');
  const c = d.counts;
  const waste = d.inactive.waste;

  const monthly = tile('kpi-monthly', 'kpi--hero');
  monthly.replaceChildren(h('div', { class: 'kpi__label' }, 'Mjesečni trošak'),
    ...moneyLines(monthly, d.totals, 'monthly'),
    h('div', { class: 'kpi__sub' }, 'sve što se trenutačno plaća'));

  const yearly = tile('kpi-yearly', '');
  yearly.replaceChildren(h('div', { class: 'kpi__label' }, 'Godišnje'),
    ...moneyLines(yearly, d.totals, 'yearly'),
    h('div', { class: 'kpi__sub' }, 'procjena: mjesečno × 12'));

  const count = tile('kpi-count', '');
  const countEl = count.querySelector('.kpi__value') ?? h('div', { class: 'kpi__value' });
  countUp(countEl, c.total, (n) => String(Math.round(n)));
  count.replaceChildren(h('div', { class: 'kpi__label' }, 'Licence'), countEl,
    h('div', { class: 'kpi__sub' }, `${c.active} aktivne · ${c.inactive} neaktivne · ${c.cancelled} otkazane`));

  const save = tile('kpi-waste', waste.length ? 'kpi--warn' : '');
  save.replaceChildren(h('div', { class: 'kpi__label' }, 'Moguća ušteda / mj.'),
    ...moneyLines(save, waste, 'monthly'),
    h('div', { class: 'kpi__sub' }, waste.length ? 'otkazivanjem neaktivnih pretplata' : 'nema neaktivnih pretplata'));

  if (box.querySelector('.skeleton') || !box.children.length) {
    box.replaceChildren(monthly, yearly, count, save);
    if (first) stagger([...box.children], 'is-in', 60);
  }
}

function renderInactive(inactive, actions) {
  const counter = document.getElementById('inactive-count');
  const n = String(inactive.items.length);
  if (counter.textContent !== n) { counter.textContent = n; play(counter, 'is-bump'); }
  counter.setAttribute('aria-label', `${n} ${plural(Number(n), 'neaktivna pretplata', 'neaktivne pretplate', 'neaktivnih pretplata')}`);

  const list = document.getElementById('inactive-list');
  if (!inactive.items.length) {
    list.replaceChildren(h('li', { class: 'empty-row' }, '✓ Sve plaćene licence se koriste.'));
    return;
  }
  const rows = inactive.items.map((it) => h('li', { 'data-id': it.id },
    h('div', { class: 'grow' },
      h('div', { class: 'title' }, it.name),
      h('div', { class: 'meta' }, it.category)),
    h('span', { class: 'amount' }, `${money(it.monthly_cost, it.currency)}/mj.`),
    h('div', { class: 'row-actions' },
      h('button', { type: 'button', class: 'btn btn--sm', onclick: (e) => leave(e, () => actions.setStatus(it.id, 'active')),
        'aria-label': `Aktiviraj ${it.name}` }, 'Aktiviraj'),
      h('button', { type: 'button', class: 'btn btn--sm btn--ghost-danger', onclick: (e) => leave(e, () => actions.setStatus(it.id, 'cancelled')),
        'aria-label': `Otkaži ${it.name}` }, 'Otkaži')),
  ));
  list.replaceChildren(...rows);
  stagger(rows);
}

async function leave(event, run) {
  const li = event.currentTarget.closest('li');
  event.currentTarget.disabled = true;
  await play(li, 'is-leaving');
  run();
}

function renderExpiring(items, windowDays, actions) {
  document.querySelectorAll('#window-seg [data-days]').forEach((b) =>
    b.setAttribute('aria-checked', String(Number(b.dataset.days) === windowDays)));
  const list = document.getElementById('expiring-list');
  if (!items.length) {
    list.replaceChildren(h('li', { class: 'empty-row' }, `Ništa ne ističe u sljedećih ${windowDays} dana.`));
    return;
  }
  const rows = items.map((r) => h('li', {},
    h('span', { class: `days${r.days <= 3 ? ' days--soon' : r.days <= 7 ? ' days--near' : ''}` },
      r.days === 0 ? 'danas' : `${r.days} d`),
    h('div', { class: 'grow' },
      h('div', { class: 'title' }, r.name),
      h('div', { class: 'meta' }, `${date(r.date)} · ${inDays(r.days)}`)),
    r.status === 'inactive' ? badge(r.status, STATUS) : null,
    h('span', { class: 'amount' }, money(r.cost, r.currency)),
  ));
  list.replaceChildren(...rows);
  stagger(rows);
}

function renderCategories(rows) {
  const list = document.getElementById('category-bars');
  if (!rows.length) {
    list.replaceChildren(h('li', { class: 'muted' }, 'Još nema troškova.'));
    return;
  }
  // Bars are scaled within each currency only; amounts in different currencies are not comparable.
  const currencies = [...new Set(rows.map((r) => r.currency))];
  const maxBy = {};
  for (const r of rows) maxBy[r.currency] = Math.max(maxBy[r.currency] ?? 0, Number(r.monthly));
  const items = [];
  for (const cur of currencies) {
    if (currencies.length > 1) items.push(h('li', { class: 'bars__cur', 'aria-hidden': 'true' }, cur));
    for (const r of rows.filter((x) => x.currency === cur)) {
      const fill = h('span', { class: 'fill' });
      const scale = maxBy[cur] ? Number(r.monthly) / maxBy[cur] : 0;
      items.push(h('li', {},
        h('span', { class: 'label', title: r.category }, r.category),
        h('span', { class: 'track', role: 'img', 'aria-label': `${Math.round(scale * 100)} % najveće kategorije` }, fill),
        h('span', { class: 'num' }, money(r.monthly, r.currency))));
      requestAnimationFrame(() => requestAnimationFrame(() => { fill.style.transform = `scaleX(${scale})`; }));
    }
  }
  list.replaceChildren(...items);
}
