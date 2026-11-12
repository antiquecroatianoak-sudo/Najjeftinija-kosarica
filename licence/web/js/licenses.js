import { h, pill } from './dom.js';
import { CYCLE_LABEL, STATUS, date, money } from './format.js';

// Renders the license table. `actions.edit(license)` / `actions.remove(license)`.
export function renderLicenses(items, actions) {
  const tbody = document.querySelector('#license-table tbody');
  document.getElementById('license-empty').hidden = items.length > 0;
  tbody.replaceChildren(...items.map((l) => h('tr', { 'data-id': l.id },
    h('td', { 'data-label': 'Naziv' }, l.name),
    h('td', { 'data-label': 'Kategorija' }, l.category),
    h('td', { class: 'num', 'data-label': 'Trošak' }, money(l.cost, l.currency)),
    h('td', { 'data-label': 'Ciklus' }, CYCLE_LABEL[l.billing_cycle] ?? l.billing_cycle),
    h('td', { class: 'num', 'data-label': 'Mjesečno' }, money(l.monthly_cost, l.currency)),
    h('td', { 'data-label': 'Početak' }, date(l.start_date)),
    h('td', { 'data-label': 'Status' }, pill(l.status, STATUS)),
    h('td', { class: 'actions' },
      h('button', { type: 'button', class: 'btn btn--sm', onclick: () => actions.edit(l) }, 'Uredi'),
      h('button', { type: 'button', class: 'btn btn--sm btn--danger', onclick: () => actions.remove(l) }, 'Obriši')),
  )));
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
