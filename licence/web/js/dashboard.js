import { h, pill } from './dom.js';
import { STATUS, date, inDays, money } from './format.js';

// Renders the overview. `actions.setStatus(id, status)` is used by the inactive list.
export function renderDashboard(d, actions) {
  document.getElementById('as-of').textContent = `· stanje ${date(d.as_of)}`;
  renderKpis(d);
  renderInactive(d.inactive, actions);
  renderRenewals(d.renewals);
  renderCategories(d.by_category);
}

function moneyLines(totals, key) {
  if (!totals.length) return [h('div', { class: 'kpi__value' }, '—')];
  return totals.map((t) => h('div', { class: 'kpi__value' }, money(t[key], t.currency)));
}

function renderKpis(d) {
  const c = d.counts;
  const waste = d.inactive.waste;
  document.getElementById('kpis').replaceChildren(
    h('div', { class: 'kpi' },
      h('div', { class: 'kpi__label' }, 'Mjesečni trošak'), ...moneyLines(d.totals, 'monthly'),
      h('div', { class: 'kpi__sub' }, 'aktivne i neaktivne koje se plaćaju')),
    h('div', { class: 'kpi' },
      h('div', { class: 'kpi__label' }, 'Godišnje (procjena)'), ...moneyLines(d.totals, 'yearly')),
    h('div', { class: 'kpi' },
      h('div', { class: 'kpi__label' }, 'Licence'),
      h('div', { class: 'kpi__value' }, String(c.total)),
      h('div', { class: 'kpi__sub' }, `${c.active} aktivnih · ${c.inactive} neaktivnih · ${c.cancelled} otkazanih`)),
    h('div', { class: `kpi ${waste.length ? 'kpi--warn' : ''}` },
      h('div', { class: 'kpi__label' }, 'Moguća ušteda mjesečno'), ...moneyLines(waste, 'monthly'),
      h('div', { class: 'kpi__sub' }, waste.length ? 'otkazivanjem neaktivnih' : 'nema neaktivnih pretplata')),
  );
}

function renderInactive(inactive, actions) {
  document.getElementById('inactive-count').textContent = String(inactive.items.length);
  const list = document.getElementById('inactive-list');
  if (!inactive.items.length) {
    list.replaceChildren(h('li', { class: 'empty-row' }, 'Sve plaćene licence se koriste.'));
    return;
  }
  list.replaceChildren(...inactive.items.map((it) => h('li', {},
    h('div', { class: 'grow' },
      h('div', { class: 'title' }, it.name),
      h('div', { class: 'meta' }, `${it.category} · ${money(it.monthly_cost, it.currency)}/mj.`)),
    h('button', { type: 'button', class: 'btn btn--sm', onclick: () => actions.setStatus(it.id, 'active') }, 'Aktiviraj'),
    h('button', { type: 'button', class: 'btn btn--sm btn--danger', onclick: () => actions.setStatus(it.id, 'cancelled') }, 'Otkaži'),
  )));
}

function renderRenewals(renewals) {
  const list = document.getElementById('renewal-list');
  if (!renewals.length) {
    list.replaceChildren(h('li', { class: 'empty-row' }, 'Nema obnova u sljedećih 30 dana.'));
    return;
  }
  list.replaceChildren(...renewals.map((r) => h('li', {},
    h('div', { class: 'grow' },
      h('div', { class: 'title' }, r.name),
      h('div', { class: 'meta' }, `${date(r.date)} · ${inDays(r.days)}`)),
    r.status === 'inactive' ? pill(r.status, STATUS) : null,
    h('span', { class: 'num' }, money(r.cost, r.currency)),
  )));
}

function renderCategories(rows) {
  const list = document.getElementById('category-bars');
  if (!rows.length) {
    list.replaceChildren(h('li', { class: 'muted' }, 'Još nema troškova.'));
    return;
  }
  // Bars are scaled within each currency only; different currencies are not comparable.
  const maxBy = {};
  for (const r of rows) maxBy[r.currency] = Math.max(maxBy[r.currency] ?? 0, Number(r.monthly));
  list.replaceChildren(...rows.map((r) => {
    const pct = maxBy[r.currency] ? (Number(r.monthly) / maxBy[r.currency]) * 100 : 0;
    return h('li', {},
      h('span', { class: 'label', title: r.category }, r.category),
      h('span', { class: 'track' }, h('span', { class: 'fill', style: { width: `${pct}%`, display: 'block' } })),
      h('span', { class: 'num' }, money(r.monthly, r.currency)));
  }));
}
