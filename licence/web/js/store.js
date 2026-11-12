// Client data layer: local cache for instant first paint, optimistic updates
// with rollback, and background sync (interval, tab focus, reconnect).
import { api } from './api.js';

const CACHE_VERSION = 2;
const listeners = new Set();

export const state = {
  me: null,
  dashboard: null,
  analytics: null,
  items: [],          // licenses for the current filter
  filters: { q: '', category: '', quick: 'all' },
  days: 30,
  fromCache: false,
  online: navigator.onLine,
  lastSync: null,
  unread: 0,
};

export function subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); }
function emit(reason) { for (const fn of listeners) fn(reason); }

// ---- local cache (per organization; a convenience, never the source of truth) ----
const cacheKey = (orgId) => `lp-cache:${orgId}`;
const lastOrgKey = 'lp-last-org';

function readCache() {
  try {
    const org = localStorage.getItem(lastOrgKey);
    if (!org) return null;
    const data = JSON.parse(localStorage.getItem(cacheKey(org)) || 'null');
    return data && data.v === CACHE_VERSION ? data : null;
  } catch { return null; }
}

function writeCache() {
  if (!state.me) return;
  try {
    const org = state.me.organization.id;
    localStorage.setItem(lastOrgKey, org);
    localStorage.setItem(cacheKey(org), JSON.stringify({
      v: CACHE_VERSION, me: state.me, dashboard: state.dashboard, analytics: state.analytics,
      items: state.items, at: Date.now(),
    }));
  } catch { /* storage full or blocked: ignore */ }
}

export function loadFromCache() {
  const cached = readCache();
  if (!cached) return false;
  Object.assign(state, { me: cached.me, dashboard: cached.dashboard, analytics: cached.analytics,
    items: cached.items, fromCache: true, lastSync: cached.at });
  emit('cache');
  return true;
}

// ---- server sync --------------------------------------------------------------
export function listParams() {
  const { q, category, quick } = state.filters;
  const p = { q, category };
  if (['active', 'inactive', 'cancelled'].includes(quick)) p.status = quick;
  if (quick === 'expiring') p.expiring = 30;
  if (quick === 'tracked') p.tracked = 1;
  return p;
}

let seq = 0;
export async function sync({ only } = {}) {
  const mine = ++seq;
  try {
    const tasks = {
      me: !only || only.includes('me') ? api.me() : null,
      dashboard: !only || only.includes('dashboard') ? api.dashboard(state.days) : null,
      analytics: !only || only.includes('analytics') ? api.analytics() : null,
      items: !only || only.includes('items') ? api.list(listParams()) : null,
    };
    const keys = Object.keys(tasks).filter((k) => tasks[k]);
    const values = await Promise.all(keys.map((k) => tasks[k]));
    if (mine !== seq && !only) return;
    keys.forEach((k, i) => { state[k] = values[i]; });
    if (state.dashboard) state.unread = state.dashboard.unread_notifications ?? state.unread;
    state.fromCache = false;
    state.online = true;
    state.lastSync = Date.now();
    writeCache();
    emit('sync');
  } catch (err) {
    if (err.offline) { state.online = false; emit('offline'); }
    throw err;
  }
}

/** Apply a local change at once, run the request, roll back if it fails. */
export async function optimistic(apply, request, { refresh = ['dashboard', 'analytics', 'items'] } = {}) {
  const snapshot = structuredClone({ items: state.items, dashboard: state.dashboard });
  apply(state);
  emit('optimistic');
  try {
    const result = await request();
    sync({ only: refresh }).catch(() => {});
    return result;
  } catch (err) {
    Object.assign(state, snapshot);
    emit('rollback');
    throw err;
  }
}

// ---- background sync ----------------------------------------------------------
export function startBackgroundSync(intervalMs = 60_000) {
  const tick = () => { if (document.visibilityState === 'visible') sync().catch(() => {}); };
  setInterval(tick, intervalMs);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && Date.now() - (state.lastSync ?? 0) > 15_000) tick();
  });
  addEventListener('online', () => { state.online = true; emit('online'); tick(); });
  addEventListener('offline', () => { state.online = false; emit('offline'); });
}
