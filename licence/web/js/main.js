// Wires the presentation layer to the API and the client store.
import { api, editable } from './api.js';
import { BankView } from './bank.js';
import { initRoiCalculator, renderDashboard } from './dashboard.js';
import { LicenseForm } from './form.js';
import { Importer } from './importer.js';
import { renderCategoryOptions, renderLicenses, renderSortHeaders, setQuickFilter, setTabCount, sortState } from './licenses.js';
import { SettingsView } from './settings.js';
import { applyBranding, currentView, go, initRouter, initShortcuts, initTheme } from './shell.js';
import { listParams, loadFromCache, optimistic, startBackgroundSync, state, subscribe, sync } from './store.js';
import { closeDialog, confirmDialog, h, play, toast } from './ui.js';

const QUICK = ['all', 'active', 'inactive', 'cancelled', 'expiring', 'tracked'];
const filtersForm = document.getElementById('filters');
const pending = new Set();
let flashId = null;
let animateNext = true;

// ---- rendering ------------------------------------------------------------------
function render(reason) {
  if (!state.me) return;
  applyBranding(state.me.organization);
  form.defaultCurrency = state.me.organization.reference_currency;
  renderDashboard(state.dashboard, state.analytics, actions, { first: reason === 'cache' || animateNext });
  renderCategoryOptions(state.me.categories);
  renderLicenses(state.items, actions, { animate: animateNext, flashId, filtered: isFiltered(), pending });
  setTabCount(state.dashboard?.counts.total ?? state.items.length);
  renderBell(state.unread);
  renderSync();
  animateNext = false;
  flashId = null;
}

function renderSync() {
  const el = document.getElementById('sync-state');
  el.className = state.online ? 'sync' : 'sync sync--offline';
  el.textContent = !state.online ? 'Izvan mreže – spremljeni podaci'
    : state.fromCache ? 'Osvježavam…' : '';
}

function renderBell(n) {
  const el = document.getElementById('notif-count');
  if (el.textContent !== String(n)) { el.textContent = String(n); play(el, 'is-bump'); }
  el.dataset.zero = String(n === 0);
  document.getElementById('btn-notifications').setAttribute('aria-label', `Obavijesti (${n} nepročitanih)`);
}

subscribe(render);

const isFiltered = () => Boolean(state.filters.q || state.filters.category || state.filters.quick !== 'all');
const findItem = (id) => state.items.find((l) => l.id === id);

async function refresh({ animate = false, only } = {}) {
  animateNext = animate || animateNext;
  try { await sync({ only }); } catch (err) { if (!err.offline) toast(err.message, { type: 'error' }); else renderSync(); }
}

// ---- actions --------------------------------------------------------------------
const actions = {
  create: () => form.open(),
  importFile: () => importer.open(),

  async edit(id) {
    const lic = findItem(id) ?? (await api.list({}).then((all) => all.find((l) => l.id === id)));
    if (lic) form.open(lic);
  },

  async remove(license, row) {
    if (!(await confirmDialog(`„${license.name}” bit će trajno obrisana iz evidencije.`, 'Obriši', 'Obrisati licencu?'))) return;
    if (row) await play(row, 'is-leaving');
    try {
      await optimistic((s) => { s.items = s.items.filter((l) => l.id !== license.id); },
        () => api.remove(license.id));
      toast(`Obrisano: ${license.name}`, { action: { label: 'Poništi', run: () => restore(license) } });
    } catch (err) {
      toast(`Brisanje nije uspjelo: ${err.message}`, { type: 'error' });
    }
  },

  async setStatus(id, status) {
    const name = findItem(id)?.name ?? state.dashboard?.inactive.items.find((i) => i.id === id)?.name ?? '';
    pending.add(id);
    try {
      await optimistic((s) => {
        const item = s.items.find((l) => l.id === id);
        if (item) item.status = status;
        if (s.dashboard) s.dashboard.inactive.items = s.dashboard.inactive.items.filter((i) => i.id !== id);
      }, () => api.patch(id, { status }));
      toast(status === 'cancelled' ? `Otkazano: ${name}` : `Ponovno aktivno: ${name}`);
    } catch (err) {
      toast(`Promjena nije spremljena: ${err.message}`, { type: 'error' });
    } finally {
      pending.delete(id);
    }
  },
};

async function restore(license) {
  try {
    const again = await api.create(editable(license));
    flashId = again.id;
    await refresh();
    toast(`Vraćeno: ${again.name}`);
  } catch (err) { toast(err.message, { type: 'error' }); }
}

const form = new LicenseForm(async (data, id) => {
  if (id) {
    const saved = await optimistic((s) => {
      const item = s.items.find((l) => l.id === id);
      if (item) Object.assign(item, data, { cost: data.cost });
    }, () => api.update(id, data));
    flashId = saved.id;
    toast(`Spremljeno: ${saved.name}`);
  } else {
    const saved = await api.create(data);
    flashId = saved.id;
    if (currentView() !== 'licence') go('licence');
    await refresh();
    toast(`Dodano: ${saved.name}`);
  }
});

const importer = new Importer((result) => {
  if (result.committed && result.created) { animateNext = true; refresh(); toast(`Uvezeno licenci: ${result.created}`); }
});

const bank = new BankView({ licenses: () => state.items, addLicense: (prefill) => form.open(null, prefill) });
const settings = new SettingsView({ onOrgChange: (org) => { state.me.organization = org; applyBranding(org); refresh(); } });

// ---- notifications ------------------------------------------------------------------
async function openNotifications() {
  const dialog = document.getElementById('notif-dialog');
  const list = document.getElementById('notif-list');
  list.replaceChildren(h('li', { class: 'skeleton skeleton--row' }));
  dialog.showModal();
  try {
    const n = await api.notifications();
    list.replaceChildren(...(n.items.length ? n.items.map((x) => h('li', { class: x.read_at ? '' : 'unread' },
      h('div', { class: 'grow' }, h('div', { class: 'title' }, x.message),
        h('div', { class: 'meta' }, `${x.created_at.slice(0, 16).replace('T', ' ')} UTC`))))
      : [h('li', { class: 'empty-row' }, 'Nema obavijesti.')]));
  } catch (err) { toast(err.message, { type: 'error' }); }
}
document.getElementById('btn-notifications').addEventListener('click', openNotifications);
document.getElementById('notif-read').addEventListener('click', async () => {
  await api.readNotifications();
  state.unread = 0;
  renderBell(0);
  document.querySelectorAll('#notif-list .unread').forEach((li) => li.classList.remove('unread'));
});
document.getElementById('notif-dialog').addEventListener('cancel', (e) => { e.preventDefault(); closeDialog(e.target); });

// ---- controls ------------------------------------------------------------------------
let debounce;
filtersForm.addEventListener('input', () => {
  clearTimeout(debounce);
  debounce = setTimeout(() => {
    state.filters.q = filtersForm.elements.q.value.trim();
    state.filters.category = filtersForm.elements.category.value;
    refresh({ animate: true, only: ['items'] });
  }, 180);
});
filtersForm.addEventListener('submit', (e) => e.preventDefault());

function setQuick(value) {
  state.filters.quick = value;
  setQuickFilter(value);
  refresh({ animate: true, only: ['items'] });
}
document.getElementById('quick-filters').addEventListener('click', (e) => {
  const b = e.target.closest('button[data-filter]');
  if (b) setQuick(b.dataset.filter);
});
setQuickFilter('all');

document.querySelectorAll('.seg[role="radiogroup"], .chips[role="radiogroup"]').forEach((group) => {
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
  const b = e.target.closest('button[data-days]');
  if (!b) return;
  state.days = Number(b.dataset.days);
  refresh({ only: ['dashboard'] });
});

document.querySelector('#license-table thead').addEventListener('click', (e) => {
  const b = e.target.closest('.sort');
  if (!b) return;
  sortState.dir = sortState.key === b.dataset.sort && sortState.dir === 'asc' ? 'desc' : 'asc';
  sortState.key = b.dataset.sort;
  renderSortHeaders();
  renderLicenses(state.items, actions, { animate: true, filtered: isFiltered(), pending });
});
renderSortHeaders();

document.getElementById('btn-new').addEventListener('click', () => form.open());
document.getElementById('btn-import').addEventListener('click', () => importer.open());
const exportLink = document.getElementById('btn-export');
exportLink.addEventListener('click', () => {
  const qs = new URLSearchParams(Object.entries(listParams()).filter(([, v]) => v !== '' && v != null)).toString();
  exportLink.href = `/api/export.csv${qs ? `?${qs}` : ''}`;
});

initShortcuts({
  new: () => form.open(),
  search: () => {
    go('licence');
    document.getElementById('view-licence').hidden = false;   // hashchange fires later; show now so focus can land
    filtersForm.elements.q.focus();
  },
  quick: (n) => { go('licence'); setQuick(QUICK[n - 1]); },
  import: () => { go('licence'); importer.open(); },
  export: () => { go('licence'); exportLink.click(); },
  notifications: openNotifications,
  refresh: () => refresh({ animate: true }).then(() => toast('Podaci su osvježeni.')),
});

// ---- start ---------------------------------------------------------------------------------
initTheme();
initRoiCalculator();
loadFromCache();            // instant paint from the last session, then refresh from the server
initRouter((view) => {
  if (view === 'banka') bank.refresh();
  if (view === 'postavke' && state.me) { settings.fill(state.me); settings.refresh(); }
});
refresh({ animate: true }).then(() => {
  if (currentView() === 'postavke' && state.me) { settings.fill(state.me); settings.refresh(); }
  if (currentView() === 'banka') bank.refresh();
});
startBackgroundSync();
