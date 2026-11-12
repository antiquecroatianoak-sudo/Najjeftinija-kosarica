import { CYCLE, STATUS, date, money, plural } from './format.js';
import { badge, h, play, stagger } from './ui.js';

const STATUS_ORDER = { active: 0, inactive: 1, cancelled: 2 };
const SORTERS = {
  name: (a, b) => a.name.localeCompare(b.name, 'hr', { sensitivity: 'base' }),
  category: (a, b) => a.category.localeCompare(b.category, 'hr', { sensitivity: 'base' }),
  cost: (a, b) => a.currency.localeCompare(b.currency) || Number(a.cost) - Number(b.cost),
  monthly: (a, b) => a.currency.localeCompare(b.currency) || Number(a.monthly_cost) - Number(b.monthly_cost),
  start: (a, b) => a.start_date.localeCompare(b.start_date),
  status: (a, b) => STATUS_ORDER[a.status] - STATUS_ORDER[b.status],
};

export const sortState = { key: 'name', dir: 'asc' };

export function sortItems(items) {
  const cmp = SORTERS[sortState.key] ?? SORTERS.name;
  const sign = sortState.dir === 'asc' ? 1 : -1;
  return [...items].sort((a, b) => sign * cmp(a, b) || SORTERS.name(a, b));
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

// Renders the table. `actions.edit(license)` / `actions.remove(license)`.
export function renderLicenses(items, actions, { animate = false, flashId = null, filtered = false } = {}) {
  const tbody = document.querySelector('#license-table tbody');
  const empty = document.getElementById('license-empty');
  empty.hidden = items.length > 0;
  document.querySelector('#license-table thead').hidden = items.length === 0;
  document.getElementById('empty-title').textContent = filtered ? 'Nema rezultata' : 'Još nema licenci';
  document.getElementById('empty-text').textContent = filtered
    ? 'Promijenite pretragu ili filtre.' : 'Dodajte prvu pretplatu da biste pratili troškove.';
  empty.querySelector('[data-action="new"]').hidden = filtered;
  document.getElementById('result-count').textContent =
    `${items.length} ${plural(items.length, 'licenca', 'licence', 'licenci')}${filtered ? ' (filtrirano)' : ''}`;

  const rows = sortItems(items).map((l) => h('tr', { 'data-id': l.id },
    h('td', { class: 'name', 'data-label': 'Naziv' }, l.name),
    h('td', { 'data-label': 'Kategorija' }, l.category),
    h('td', { class: 'num', 'data-label': 'Trošak' },
      money(l.cost, l.currency), h('span', { class: 'muted' }, ` / ${CYCLE[l.billing_cycle]?.label.toLowerCase() ?? l.billing_cycle}`)),
    h('td', { class: 'num', 'data-label': 'Mjesečno' }, money(l.monthly_cost, l.currency)),
    h('td', { 'data-label': 'Početak' }, date(l.start_date)),
    h('td', { 'data-label': 'Status' }, badge(l.status, STATUS)),
    h('td', { class: 'actions' },
      h('button', { type: 'button', class: 'btn btn--sm', onclick: () => actions.edit(l), 'aria-label': `Uredi ${l.name}` }, 'Uredi'),
      h('button', { type: 'button', class: 'btn btn--sm btn--ghost-danger', onclick: (e) => actions.remove(l, e.currentTarget.closest('tr')),
        'aria-label': `Obriši ${l.name}` }, 'Obriši')),
  ));
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
  select.replaceChildren(h('option', { value: '' }, 'Sve kategorije'),
    ...categories.map((c) => h('option', { value: c }, c)));
  select.value = categories.includes(current) ? current : '';
  document.getElementById('category-options')
    .replaceChildren(...categories.map((c) => h('option', { value: c })));
}

export function setTabCount(n) {
  const el = document.getElementById('tab-count');
  if (el.textContent !== String(n)) { el.textContent = String(n); play(el, 'is-bump'); }
}
