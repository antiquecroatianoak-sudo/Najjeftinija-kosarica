import { api } from './api.js';
import { renderDashboard } from './dashboard.js';
import { LicenseForm } from './form.js';
import { renderCategoryOptions, renderLicenses } from './licenses.js';

const filtersForm = document.getElementById('filters');
const notice = document.getElementById('notice');
let noticeTimer;

function notify(message, ok = false) {
  clearTimeout(noticeTimer);
  notice.textContent = message;
  notice.className = ok ? 'notice notice--ok' : 'notice';
  notice.hidden = false;
  if (ok) noticeTimer = setTimeout(() => { notice.hidden = true; }, 3000);
}

function currentFilters() {
  return Object.fromEntries(new FormData(filtersForm));
}

const actions = {
  edit: (license) => form.open(license),
  async remove(license) {
    if (!confirm(`Obrisati licencu „${license.name}”?`)) return;
    await run(() => api.remove(license.id), 'Licenca je obrisana.');
  },
  async setStatus(id, status) {
    await run(() => api.patch(id, { status }), status === 'cancelled' ? 'Pretplata je otkazana.' : 'Licenca je aktivna.');
  },
};

const form = new LicenseForm(async (data, id) => {
  if (id) await api.update(id, data); else await api.create(data);
  notify(id ? 'Promjene su spremljene.' : 'Licenca je dodana.', true);
  await refresh();
});

async function run(op, okMessage) {
  try {
    await op();
    notify(okMessage, true);
    await refresh();
  } catch (err) {
    notify(err.message);
  }
}

let seq = 0;
async function refresh() {
  const mine = ++seq; // ignore responses that arrive after a newer refresh started
  try {
    const [dashboard, items, meta] = await Promise.all([api.dashboard(), api.list(currentFilters()), api.meta()]);
    if (mine !== seq) return;
    renderDashboard(dashboard, actions);
    renderCategoryOptions(meta.categories);
    renderLicenses(items, actions);
  } catch (err) {
    if (mine === seq) notify(err.message);
  }
}

let debounce;
filtersForm.addEventListener('input', () => {
  clearTimeout(debounce);
  debounce = setTimeout(refresh, 200);
});
filtersForm.addEventListener('submit', (e) => e.preventDefault());
document.getElementById('btn-new').addEventListener('click', () => form.open());

refresh();
