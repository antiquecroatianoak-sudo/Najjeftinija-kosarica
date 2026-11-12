// Wires the presentation layer to the API (which fronts the service layer).
import { api, editable } from './api.js';
import { renderDashboard } from './dashboard.js';
import { LicenseForm } from './form.js';
import { renderCategoryOptions, renderLicenses, renderSortHeaders, setTabCount, sortState } from './licenses.js';
import { go, initRouter, initTheme } from './shell.js';
import { confirmDialog, play, toast } from './ui.js';

const filtersForm = document.getElementById('filters');
const state = { days: 30, firstLoad: true, lastItems: [] };

const filters = () => Object.fromEntries(new FormData(filtersForm));
const isFiltered = () => Object.values(filters()).some(Boolean);

// ---- actions ---------------------------------------------------------------
const actions = {
  edit: (license) => form.open(license),

  async remove(license, row) {
    if (!(await confirmDialog(`„${license.name}” bit će trajno obrisana iz evidencije.`))) return;
    try {
      await api.remove(license.id);
      if (row) await play(row, 'is-leaving');
      await refresh();
      toast(`Obrisano: ${license.name}`, {
        action: { label: 'Poništi', run: () => restore(license) },
      });
    } catch (err) {
      toast(err.message, { type: 'error' });
    }
  },

  async setStatus(id, status) {
    try {
      const updated = await api.patch(id, { status });
      await refresh();
      toast(status === 'cancelled' ? `Otkazano: ${updated.name}` : `Ponovno aktivno: ${updated.name}`);
    } catch (err) {
      toast(err.message, { type: 'error' });
      refresh();
    }
  },
};

async function restore(license) {
  try {
    const again = await api.create(editable(license));
    await refresh({ flashId: again.id });
    toast(`Vraćeno: ${again.name}`);
  } catch (err) {
    toast(err.message, { type: 'error' });
  }
}

const form = new LicenseForm(async (data, id) => {
  const saved = id ? await api.update(id, data) : await api.create(data);
  if (!id) go('licence');
  await refresh({ flashId: saved.id });
  toast(id ? `Spremljeno: ${saved.name}` : `Dodano: ${saved.name}`);
});

// ---- data loading ----------------------------------------------------------
let seq = 0;
async function refresh({ flashId = null, animate = false } = {}) {
  const mine = ++seq; // drop responses that arrive after a newer refresh started
  try {
    const [dashboard, items, meta] = await Promise.all([api.dashboard(state.days), api.list(filters()), api.meta()]);
    if (mine !== seq) return;
    state.lastItems = items;
    renderDashboard(dashboard, actions, { first: state.firstLoad });
    renderCategoryOptions(meta.categories);
    renderLicenses(items, actions, { animate: animate || state.firstLoad, flashId, filtered: isFiltered() });
    setTabCount(dashboard.counts.total);
    state.firstLoad = false;
  } catch (err) {
    if (mine === seq) toast(err.message, { type: 'error', timeout: 8000 });
  }
}

// ---- controls --------------------------------------------------------------
let debounce;
filtersForm.addEventListener('input', () => {
  clearTimeout(debounce);
  debounce = setTimeout(() => refresh({ animate: true }), 180);
});
filtersForm.addEventListener('submit', (e) => e.preventDefault());

const statusSeg = document.getElementById('status-seg');
const setStatusFilter = (value) => {
  filtersForm.elements.status.value = value;
  statusSeg.querySelectorAll('button').forEach((b) => b.setAttribute('aria-checked', String(b.dataset.status === value)));
};
statusSeg.addEventListener('click', (e) => {
  const btn = e.target.closest('button[data-status]');
  if (!btn) return;
  setStatusFilter(btn.dataset.status);
  refresh({ animate: true });
});
setStatusFilter('');

// arrow keys inside segmented radio groups
document.querySelectorAll('.seg[role="radiogroup"]').forEach((group) => {
  group.addEventListener('keydown', (e) => {
    if (!['ArrowLeft', 'ArrowRight'].includes(e.key)) return;
    const buttons = [...group.querySelectorAll('button')];
    const i = buttons.indexOf(document.activeElement);
    const next = buttons[(i + (e.key === 'ArrowRight' ? 1 : -1) + buttons.length) % buttons.length];
    next.focus();
    next.click();
  });
});

document.getElementById('window-seg').addEventListener('click', (e) => {
  const btn = e.target.closest('button[data-days]');
  if (!btn) return;
  state.days = Number(btn.dataset.days);
  refresh();
});

document.querySelector('#license-table thead').addEventListener('click', (e) => {
  const btn = e.target.closest('.sort');
  if (!btn) return;
  sortState.dir = sortState.key === btn.dataset.sort && sortState.dir === 'asc' ? 'desc' : 'asc';
  sortState.key = btn.dataset.sort;
  renderSortHeaders();
  renderLicenses(state.lastItems, actions, { animate: true, filtered: isFiltered() });
});
renderSortHeaders();

document.getElementById('btn-new').addEventListener('click', () => form.open());
document.querySelector('[data-action="new"]').addEventListener('click', () => form.open());

// keyboard: "n" new license, "/" search (not while typing or with a dialog open)
addEventListener('keydown', (e) => {
  const typing = e.target.closest?.('input, select, textarea, [contenteditable]');
  if (typing || e.metaKey || e.ctrlKey || e.altKey || document.querySelector('dialog[open]')) return;
  if (e.key === 'n' || e.key === 'N') { e.preventDefault(); form.open(); }
  if (e.key === '/') {
    e.preventDefault();
    go('licence');
    requestAnimationFrame(() => filtersForm.elements.q.focus());
  }
});

initTheme();
initRouter();
refresh();
