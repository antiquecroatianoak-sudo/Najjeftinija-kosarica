// Small DOM + motion helpers shared by all views.
// Text is always inserted as text nodes (never innerHTML), so user data cannot inject markup.

export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value == null || value === false) continue;
    if (key.startsWith('on') && typeof value === 'function') el.addEventListener(key.slice(2), value);
    else if (key === 'class') el.className = value;
    else if (key === 'style' && typeof value === 'object') Object.assign(el.style, value); // CSSOM: CSP-safe
    else el.setAttribute(key, value === true ? '' : value);
  }
  for (const child of children.flat()) {
    if (child == null || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return el;
}

export function badge(status, STATUS) {
  const s = STATUS[status] ?? { label: status, badge: '', dot: '' };
  return h('span', { class: `badge ${s.badge}` }, h('i', { class: `dot ${s.dot}`, 'aria-hidden': 'true' }), s.label);
}

const motionQuery = matchMedia('(prefers-reduced-motion: reduce)');
export const reducedMotion = () => motionQuery.matches;

/** Play a CSS animation class once; resolves when it ends (immediately with reduced motion). */
export function play(el, cls) {
  return new Promise((resolve) => {
    if (reducedMotion() || !el.isConnected) return resolve();
    el.classList.remove(cls);
    void el.offsetWidth; // restart
    el.classList.add(cls);
    const done = () => { el.classList.remove(cls); resolve(); };
    el.addEventListener('animationend', done, { once: true });
    setTimeout(done, 1600); // safety net if the animation is cancelled
  });
}

/** Stagger entrance animation over a list of elements. */
export function stagger(elements, cls = 'is-in', step = 28, max = 12) {
  if (reducedMotion()) return;
  elements.forEach((el, i) => {
    el.style.animationDelay = `${Math.min(i, max) * step}ms`;
    el.classList.add(cls);
    el.addEventListener('animationend', () => { el.classList.remove(cls); el.style.animationDelay = ''; }, { once: true });
  });
}

/** Animate a number from its previous value to `to`. `format(n)` renders it. */
export function countUp(el, to, format, duration = 650) {
  const from = Number(el.dataset.value ?? 0);
  el.dataset.value = String(to);
  if (reducedMotion() || from === to) { el.textContent = format(to); return; }
  const start = performance.now();
  const tick = (now) => {
    const t = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - t, 3);
    el.textContent = format(from + (to - from) * eased);
    if (t < 1 && el.dataset.value === String(to)) requestAnimationFrame(tick);
    else if (t >= 1) el.textContent = format(to);
  };
  requestAnimationFrame(tick);
}

/** Close a <dialog> with an exit animation. */
export async function closeDialog(dialog, value) {
  if (!dialog.open) return;
  await play(dialog, 'is-closing');
  dialog.close(value);
}

// ---- toasts ---------------------------------------------------------------
const toasts = () => document.getElementById('toasts');

export function toast(message, { type = 'info', action, timeout = 4000 } = {}) {
  const box = h('div', { class: `toast${type === 'error' ? ' toast--error' : ''}` },
    h('span', { class: 'toast__msg' }, message));
  let timer;
  const dismiss = async () => {
    clearTimeout(timer);
    if (!box.isConnected) return;
    await play(box, 'is-leaving');
    box.remove();
  };
  if (action) {
    box.append(h('button', { type: 'button', class: 'toast__btn', onclick: () => { dismiss(); action.run(); } }, action.label));
  }
  if (type === 'error') box.setAttribute('role', 'alert');
  toasts().append(box);
  while (toasts().children.length > 3) toasts().firstElementChild.remove();
  timer = setTimeout(dismiss, action ? Math.max(timeout, 6000) : timeout);
  box.addEventListener('pointerenter', () => clearTimeout(timer));
  box.addEventListener('pointerleave', () => { timer = setTimeout(dismiss, 2000); });
  return dismiss;
}

// ---- confirm dialog --------------------------------------------------------
export function confirmDialog(text, okLabel = 'Obriši', title = 'Jeste li sigurni?') {
  const dialog = document.getElementById('confirm-dialog');
  document.getElementById('confirm-text').textContent = text;
  document.getElementById('confirm-ok').textContent = okLabel;
  document.getElementById('confirm-title').textContent = title;
  dialog.returnValue = '';
  dialog.showModal();
  return new Promise((resolve) => {
    dialog.addEventListener('close', () => resolve(dialog.returnValue === 'ok'), { once: true });
  });
}
