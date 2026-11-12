// App shell: hash navigation, organization branding, theme, keyboard shortcuts.
import { play } from './ui.js';

export const VIEWS = ['pregled', 'licence', 'banka', 'postavke'];
const TITLES = { pregled: 'Pregled', licence: 'Licence', banka: 'Banka', postavke: 'Postavke' };

export function currentView() {
  const name = location.hash.replace(/^#\/?/, '');
  return VIEWS.includes(name) ? name : 'pregled';
}

function moveInk() {
  const active = document.querySelector('.tab[aria-current="page"]');
  const ink = document.querySelector('.tabs__ink');
  if (!active || !ink) return;
  ink.style.width = `${active.offsetWidth}px`;
  ink.style.transform = `translateX(${active.offsetLeft}px)`;
}

export function initRouter(onChange) {
  let shown = null;
  const show = () => {
    const name = currentView();
    document.querySelectorAll('.tab').forEach((t) => {
      if (t.dataset.view === name) t.setAttribute('aria-current', 'page'); else t.removeAttribute('aria-current');
    });
    // inactive views are hidden: they are separate pages of the app, not optional content
    document.querySelectorAll('.view').forEach((v) => { v.hidden = v.dataset.view !== name; });
    moveInk();
    if (shown && shown !== name) {
      play(document.getElementById(`view-${name}`), 'is-entering');
      document.getElementById('main').focus({ preventScroll: true });
      window.scrollTo({ top: 0 });
    }
    document.title = `${TITLES[name]} · License Pulse`;
    shown = name;
    onChange?.(name);
  };
  addEventListener('hashchange', show);
  addEventListener('resize', moveInk);
  document.fonts?.ready.then(moveInk);
  show();
}

export function go(view) {
  if (currentView() !== view) location.hash = `#/${view}`;
}

// ---- organization branding ---------------------------------------------------
function readable(hex) {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  return lum > 0.55 ? '#0b0d10' : '#ffffff';
}

export function applyBranding(org) {
  if (!org) return;
  const root = document.documentElement.style;
  if (/^#[0-9a-f]{6}$/i.test(org.accent)) {
    root.setProperty('--accent', org.accent);
    root.setProperty('--accent-text', readable(org.accent));
    root.setProperty('--accent-soft', `color-mix(in srgb, ${org.accent} 14%, transparent)`);
  }
  const chip = document.getElementById('org-name');
  chip.textContent = org.name;
  chip.title = `Organizacija: ${org.name}`;
}

// ---- theme: system -> light -> dark -> system --------------------------------
const THEMES = ['system', 'light', 'dark'];
const LABEL = { system: 'Tema: prema sustavu', light: 'Tema: svijetla', dark: 'Tema: tamna' };
const KEY = 'licence-theme';

function applyTheme(theme) {
  if (theme === 'system') delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = theme;
  const btn = document.getElementById('btn-theme');
  btn.setAttribute('aria-label', `${LABEL[theme]} (promijeni)`);
  btn.title = LABEL[theme];
}

export function initTheme() {
  let theme = 'system';
  try { theme = localStorage.getItem(KEY) || 'system'; } catch { /* storage blocked */ }
  if (!THEMES.includes(theme)) theme = 'system';
  applyTheme(theme);
  document.getElementById('btn-theme').addEventListener('click', () => {
    theme = THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length];
    applyTheme(theme);
    try { localStorage.setItem(KEY, theme); } catch { /* per-device convenience */ }
  });
}

// ---- keyboard shortcuts -------------------------------------------------------
/** handlers: { new, search, quick(n), import, export, notifications, refresh } */
export function initShortcuts(handlers) {
  let pendingG = 0;
  addEventListener('keydown', (e) => {
    const typing = e.target.closest?.('input, select, textarea, [contenteditable]');
    if (typing || e.metaKey || e.ctrlKey || e.altKey || document.querySelector('dialog[open]')) return;
    const key = e.key.toLowerCase();
    if (pendingG && Date.now() - pendingG < 1200) {
      pendingG = 0;
      const target = { p: 'pregled', l: 'licence', b: 'banka', s: 'postavke' }[key];
      if (target) { e.preventDefault(); go(target); }
      return;
    }
    const actions = {
      n: handlers.new, '/': handlers.search, i: handlers.import, e: handlers.export,
      o: handlers.notifications, r: handlers.refresh, '?': () => document.getElementById('help-dialog').showModal(),
      g: () => { pendingG = Date.now(); },
    };
    if (/^[1-6]$/.test(key)) { e.preventDefault(); handlers.quick(Number(key)); return; }
    const fn = actions[e.key === '?' ? '?' : key];
    if (fn) { e.preventDefault(); fn(); }
  });
}
