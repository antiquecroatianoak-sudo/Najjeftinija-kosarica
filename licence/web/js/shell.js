// App shell: hash navigation between views and the theme switch.
import { play } from './ui.js';

const VIEWS = ['pregled', 'licence'];

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
    document.querySelectorAll('.view').forEach((v) => { v.hidden = v.dataset.view !== name; });
    moveInk();
    if (shown && shown !== name) {
      play(document.getElementById(`view-${name}`), 'is-entering');
      document.getElementById('main').focus({ preventScroll: true });
      window.scrollTo({ top: 0 });
    }
    document.title = `${name === 'licence' ? 'Licence' : 'Pregled'} · Licence tima`;
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

// ---- theme: system -> light -> dark -> system ------------------------------
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
  try { theme = localStorage.getItem(KEY) || 'system'; } catch { /* storage blocked: use system */ }
  if (!THEMES.includes(theme)) theme = 'system';
  applyTheme(theme);
  document.getElementById('btn-theme').addEventListener('click', () => {
    theme = THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length];
    applyTheme(theme);
    try { localStorage.setItem(KEY, theme); } catch { /* per-device convenience only */ }
  });
}
