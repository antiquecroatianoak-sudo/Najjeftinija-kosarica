import { CYCLE, STATUS, ago, date, money, plural } from './format.js';
import { badge, h, play, stagger } from './ui.js';

const STATUS_ORDER = { active: 0, inactive: 1, cancelled: 2 };
const byName = (a, b) => a.name.localeCompare(b.name, 'hr', { sensitivity: 'base' });
const SORTERS = {
  name: byName,
  category: (a, b) => a.category.localeCompare(b.category, 'hr', { sensitivity: 'base' }),
  cost: (a, b) => a.currency.localeCompare(b.currency) || Number(a.cost) - Number(b.cost),
  // reference currency when a rate exists, so different currencies sort together
  monthly: (a, b) => Number(a.monthly_ref ?? a.monthly_cost) - Number(b.monthly_ref ?? b.monthly_cost),
  usage: (a, b) => (a.last_used_at ?? '').localeCompare(b.last_used_at ?? ''),
  renewal: (a, b) => (a.next_renewal ?? '9999').localeCompare(b.next_renewal ?? '9999'),
  status: (a, b) => STATUS_ORDER[a.status] - STATUS_ORDER[b.status],
};

export const sortState = { key: 'name', dir: 'asc' };

export function sortItems(items) {
  const cmp = SORTERS[sortState.key] ?? byName;
  const sign = sortState.dir === 'asc' ? 1 : -1;
  return [...items].sort((a, b) => sign * cmp(a, b) || byName(a, b));
}

export function renderSortHeaders() {
  document.querySelectorAll('#license-table .sort').forEach((btn) => {
    const active = btn.dataset.sort === sortState.key;
    btn.dataset.dir = active ? sortState.dir : '';
    const th = btn.closest('th');
    if (active) th.setAttribute('aria-sort', sortState.dir === 'asc' ? 'ascending' : 'descending');
    else th.removeAttribute('aria-sort');
  });
}

function usageCell(l) {
  if (!l.usage_key) return h('span', { class: 'usage usage--none' }, 'ručno');
  const last = ago(l.last_used_at);
  return h('span', { class: 'usage' },
    last ? `${l.active_users_30d} ${plural(l.active_users_30d, 'korisnik', 'korisnika', 'korisnika')} · ${last}` : 'još nema prijava');
}

// actions: edit(license), remove(license, row)
export function renderLicenses(items, actions, { animate = false, flashId = null, filtered = false, pending = new Set() } = {}) {
  const tbody = document.querySelector('#license-table tbody');
  document.getElementById('result-count').textContent =
    `${items.length} ${plural(items.length, 'licenca', 'licence', 'licenci')}${filtered ? ' prema filtru' : ''}`;

  if (!items.length) {
    // the empty state is real content in the table, not a hidden element
    tbody.replaceChildren(h('tr', { class: 'empty-tr' }, h('td', { colspan: '8', class: 'empty-cell' },
      h('div', { class: 'empty' },
        h('p', { class: 'empty__title' }, filtered ? 'Nema rezultata' : 'Još nema licenci'),
        h('p', { class: 'muted' }, filtered ? 'Promijenite pretragu ili brzi filtar.' : 'Dodajte prvu pretplatu ili uvezite postojeći popis.'),
        filtered ? null : h('div', { class: 'view__actions' },
          h('button', { type: 'button', class: 'btn btn--primary', onclick: () => actions.create() }, '+ Nova licenca'),
          h('button', { type: 'button', class: 'btn', onclick: () => actions.importFile() }, 'Uvoz CSV / Excel'))))));
    return;
  }

  const rows = sortItems(items).map((l) => h('tr', { 'data-id': l.id, class: pending.has(l.id) ? 'is-pending' : null },
    h('td', { class: 'name', 'data-label': 'Naziv' }, l.name, l.usage_key ? h('span', { class: 'track-badge', title: 'Praćenje korištenja' }, l.usage_key) : null),
    h('td', { 'data-label': 'Kategorija' }, l.category),
    h('td', { class: 'num', 'data-label': 'Trošak' },
      money(l.cost, l.currency), h('span', { class: 'muted' }, ` / ${CYCLE[l.billing_cycle]?.label.toLowerCase() ?? l.billing_cycle}`)),
    h('td', { class: 'num', 'data-label': 'Mjesečno' }, money(l.monthly_cost, l.currency)),
    h('td', { 'data-label': 'Korištenje' }, usageCell(l)),
    h('td', { 'data-label': 'Obnova' }, l.next_renewal ? date(l.next_renewal) : '—'),
    h('td', { 'data-label': 'Status' }, badge(l.status, STATUS)),
    h('td', { class: 'actions' },
      h('button', { type: 'button', class: 'btn btn--sm', onclick: () => actions.edit(l.id), 'aria-label': `Uredi ${l.name}` }, 'Uredi'),
      h('button', { type: 'button', class: 'btn btn--sm btn--ghost-danger', onclick: (e) => actions.remove(l, e.currentTarget.closest('tr')),
        'aria-label': `Obriši ${l.name}` }, 'Obriši'))));
  tbody.replaceChildren(...rows);
  if (animate) stagger(rows);
  if (flashId) {
    const row = tbody.querySelector(`tr[data-id="${CSS.escape(flashId)}"]`);
    if (row) { row.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); play(row, 'is-flash'); }
  }
}

export function renderCategoryOptions(categories) {
  const select = document.querySelector('#filters select[name="category"]');
  const current = select.value;
  select.replaceChildren(h('option', { value: '' }, 'Sve kategorije'), ...categories.map((c) => h('option', { value: c }, c)));
  select.value = categories.includes(current) ? current : '';
  document.getElementById('category-options').replaceChildren(...categories.map((c) => h('option', { value: c })));
}

export function setQuickFilter(value) {
  document.querySelectorAll('#quick-filters [data-filter]').forEach((b) =>
    b.setAttribute('aria-checked', String(b.dataset.filter === value)));
}

export function setTabCount(n) {
  const el = document.getElementById('tab-count');
  if (el.textContent !== String(n)) { el.textContent = String(n); play(el, 'is-bump'); }
}
