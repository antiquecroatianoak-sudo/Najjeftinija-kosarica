import { STATUS, ago, date, inDays, money, monthLabel, parseAmount, pct, plural } from './format.js';
import { badge, countUp, h, play, stagger } from './ui.js';

// Overview. actions: setStatus(id, status), edit(id)
export function renderDashboard(d, analytics, actions, { first = false } = {}) {
  if (!d) return;
  document.getElementById('as-of').textContent = `Stanje na dan ${date(d.as_of)}`;
  renderRoi(d.roi, first);
  renderKpis(d, first);
  renderInactive(d.inactive, actions);
  renderExpiring(d.expiring, d.window_days);
  renderCategories(d.by_category);
  if (analytics) renderAnalytics(analytics, actions);
}

// ---- ROI hero + calculator ------------------------------------------------------
const CALC_KEY = 'lp-roi-calc';
let lastRoi = null;

function loadCalc() {
  try { return JSON.parse(localStorage.getItem(CALC_KEY) || '{}'); } catch { return {}; }
}

export function initRoiCalculator() {
  const share = document.getElementById('calc-share');
  const cost = document.getElementById('calc-cost');
  const saved = loadCalc();
  if (saved.share != null) share.value = saved.share;
  if (saved.cost) cost.value = saved.cost;
  const update = () => {
    try { localStorage.setItem(CALC_KEY, JSON.stringify({ share: share.value, cost: cost.value })); } catch { /* optional */ }
    renderCalc();
  };
  share.addEventListener('input', update);
  cost.addEventListener('input', update);
}

function renderCalc() {
  const roi = lastRoi;
  if (!roi) return;
  const cur = roi.currency;
  const share = Number(document.getElementById('calc-share').value) / 100;
  document.getElementById('calc-share-out').textContent = `${Math.round(share * 100)} %`;
  const costInput = document.getElementById('calc-cost');
  const monthlyCost = Number(parseAmount(costInput.value || '0') ?? NaN);
  costInput.setAttribute('aria-invalid', String(Number.isNaN(monthlyCost)));
  const saving = Number(roi.projected_saving_12m) * share;
  const invest = Number.isNaN(monthlyCost) ? 0 : monthlyCost * 12;
  const net = saving - invest;
  document.getElementById('calc-saving').textContent = money(saving, cur);
  const netEl = document.getElementById('calc-net');
  netEl.textContent = money(net, cur);
  netEl.dataset.sign = net > 0 ? 'pos' : net < 0 ? 'neg' : '';
  const roiEl = document.getElementById('calc-roi');
  if (invest > 0) {
    const value = (net / invest) * 100;
    roiEl.textContent = pct(value.toFixed(0));
    roiEl.dataset.sign = value >= 0 ? 'pos' : 'neg';
  } else {
    roiEl.textContent = '—';
    roiEl.dataset.sign = '';
  }
  document.getElementById('calc-note').textContent = invest > 0
    ? 'ROI = (ušteda − trošak upravljanja) ÷ trošak upravljanja, za sljedećih 12 mjeseci.'
    : 'Upišite trošak upravljanja (npr. sate rada) da biste dobili postotak povrata.';
}

function renderRoi(roi, first) {
  lastRoi = roi;
  const cur = roi.currency;
  countUp(document.getElementById('roi-loss'), Number(roi.monthly_loss), (n) => money(n, cur), first ? 900 : 500);
  const waste = Number(roi.waste_share_pct);
  document.getElementById('waste-pct').textContent = pct(waste);
  document.getElementById('waste-bar').setAttribute('aria-label', `Neiskorišteno ${pct(waste)} mjesečne potrošnje`);
  requestAnimationFrame(() => {
    document.getElementById('waste-used').style.flexBasis = `${100 - waste}%`;
    document.getElementById('waste-waste').style.flexBasis = `${waste}%`;
  });
  const sub = document.getElementById('roi-sub');
  sub.textContent = roi.inactive_count
    ? `${roi.inactive_count} ${plural(roi.inactive_count, 'licenca se plaća', 'licence se plaćaju', 'licenci se plaća')}, a ne koristi · ${money(roi.yearly_loss, cur)} godišnje`
    : 'Nema neiskorištenih licenci – sve što plaćate se koristi.';
  const action = document.getElementById('roi-action');
  const next = roi.next_avoidable_charge;
  action.replaceChildren(...(next
    ? ['Sljedeći korak: otkažite ', h('b', {}, next.name), ` ${next.days === 0 ? 'danas' : `do ${date(next.date)}`} i izbjegnite naplatu od `,
       h('b', {}, money(next.cost, next.currency)), '.']
    : []));
  if (roi.missing_rates.length) {
    action.append(h('span', { class: 'roi__warn' }, ` Bez tečaja za ${roi.missing_rates.join(', ')} – ti iznosi nisu uračunati.`));
  }
  renderCalc();
}

// ---- KPI tiles ------------------------------------------------------------------
function tile(id, cls) {
  const el = document.getElementById(id) ?? h('div', { id });
  el.className = `kpi ${cls}`;
  return el;
}

function valueSlot(tileEl, key, cls = 'kpi__value') {
  return tileEl.querySelector(`[data-k="${key}"]`) ?? h('div', { class: cls, 'data-k': key });
}

function renderKpis(d, first) {
  const box = document.getElementById('kpis');
  const ref = d.reference_total;
  const monthly = tile('kpi-monthly', 'kpi--hero');
  const main = valueSlot(monthly, 'ref');
  countUp(main, Number(ref.monthly), (n) => money(n, ref.currency));
  // other currencies: converted ones are already in the main figure, the rest are shown separately
  const missing = new Set(ref.missing_rates);
  const lines = d.totals.filter((t) => missing.has(t.currency))
    .map((t) => h('div', { class: 'kpi__line' }, `+ ${money(t.monthly, t.currency)}`));
  const note = ref.missing_rates.length ? `bez tečaja za ${ref.missing_rates.join(', ')} – prikazano odvojeno`
    : ref.rate_date ? `preračunato tečajem ECB ${date(ref.rate_date)}` : 'sve što se trenutačno plaća';
  monthly.replaceChildren(h('div', { class: 'kpi__label' }, `Mjesečni trošak (${ref.currency})`), main,
    ...lines, h('div', { class: 'kpi__sub' }, note));

  const yearly = tile('kpi-yearly', '');
  const y = valueSlot(yearly, 'y');
  countUp(y, Number(ref.yearly), (n) => money(n, ref.currency));
  yearly.replaceChildren(h('div', { class: 'kpi__label' }, 'Godišnje'), y, h('div', { class: 'kpi__sub' },
    `procjena: mjesečno × 12${ref.missing_rates.length ? ` · bez ${ref.missing_rates.join(', ')}` : ''}`));

  const c = d.counts;
  const count = tile('kpi-count', '');
  const n = valueSlot(count, 'n');
  countUp(n, c.total, (v) => String(Math.round(v)));
  count.replaceChildren(h('div', { class: 'kpi__label' }, 'Licence'), n,
    h('div', { class: 'kpi__sub' }, `${c.active} aktivne · ${c.inactive} neaktivne · ${c.cancelled} otkazane`),
    h('div', { class: 'kpi__sub' }, `${c.tracked} s automatskim praćenjem korištenja`));

  if (box.querySelector('.skeleton') || !box.children.length) {
    box.replaceChildren(monthly, yearly, count);
    if (first) stagger([...box.children], 'is-in', 60);
  }
}

// ---- lists ----------------------------------------------------------------------
function renderInactive(inactive, actions) {
  const counter = document.getElementById('inactive-count');
  const n = String(inactive.items.length);
  if (counter.textContent !== n) { counter.textContent = n; play(counter, 'is-bump'); }
  const list = document.getElementById('inactive-list');
  if (!inactive.items.length) {
    list.replaceChildren(h('li', { class: 'empty-row' }, '✓ Sve plaćene licence se koriste.'));
    return;
  }
  const rows = inactive.items.map((it) => h('li', { 'data-id': it.id },
    h('div', { class: 'grow' },
      h('div', { class: 'title' }, it.name),
      h('div', { class: 'meta' }, [it.category, it.tracked ? `zadnje korištenje: ${ago(it.last_used_at) ?? 'nikad'}` : 'status postavljen ručno'].join(' · '))),
    h('span', { class: 'amount' }, `${money(it.monthly_cost, it.currency)}/mj.`),
    h('div', { class: 'row-actions' },
      h('button', { type: 'button', class: 'btn btn--sm', onclick: () => actions.setStatus(it.id, 'active'),
        'aria-label': `Aktiviraj ${it.name}` }, 'Aktiviraj'),
      h('button', { type: 'button', class: 'btn btn--sm btn--ghost-danger', onclick: () => actions.setStatus(it.id, 'cancelled'),
        'aria-label': `Otkaži ${it.name}` }, 'Otkaži'))));
  list.replaceChildren(...rows);
  stagger(rows);
}

function renderExpiring(items, windowDays) {
  document.querySelectorAll('#window-seg [data-days]').forEach((b) =>
    b.setAttribute('aria-checked', String(Number(b.dataset.days) === windowDays)));
  const list = document.getElementById('expiring-list');
  if (!items.length) {
    list.replaceChildren(h('li', { class: 'empty-row' }, `Ništa ne ističe u sljedećih ${windowDays} dana.`));
    return;
  }
  const rows = items.map((r) => h('li', {},
    h('span', { class: `days${r.days <= 3 ? ' days--soon' : r.days <= 7 ? ' days--near' : ''}` }, r.days === 0 ? 'danas' : `${r.days} d`),
    h('div', { class: 'grow' }, h('div', { class: 'title' }, r.name), h('div', { class: 'meta' }, `${date(r.date)} · ${inDays(r.days)}`)),
    r.status === 'inactive' ? badge(r.status, STATUS) : null,
    h('span', { class: 'amount' }, money(r.cost, r.currency))));
  list.replaceChildren(...rows);
  stagger(rows);
}

function renderCategories(rows) {
  const list = document.getElementById('category-bars');
  if (!rows.length) {
    list.replaceChildren(h('li', { class: 'muted' }, 'Još nema troškova.'));
    return;
  }
  const currencies = [...new Set(rows.map((r) => r.currency))];
  const maxBy = {};
  for (const r of rows) maxBy[r.currency] = Math.max(maxBy[r.currency] ?? 0, Number(r.monthly));
  const items = [];
  for (const cur of currencies) {
    if (currencies.length > 1) items.push(h('li', { class: 'bars__cur', 'aria-hidden': 'true' }, cur));
    for (const r of rows.filter((x) => x.currency === cur)) {
      const fill = h('span', { class: 'fill' });
      const scale = maxBy[cur] ? Number(r.monthly) / maxBy[cur] : 0;
      items.push(h('li', {},
        h('span', { class: 'label', title: r.category }, r.category),
        h('span', { class: 'track', role: 'img', 'aria-label': `${Math.round(scale * 100)} % najveće kategorije` }, fill),
        h('span', { class: 'num' }, money(r.monthly, r.currency))));
      requestAnimationFrame(() => requestAnimationFrame(() => { fill.style.transform = `scaleX(${scale})`; }));
    }
  }
  list.replaceChildren(...items);
}

// ---- analytics ------------------------------------------------------------------
function renderAnalytics(a, actions) {
  document.getElementById('forecast-cur').textContent = a.currency;
  const max = Math.max(...a.forecast.map((f) => Number(f.amount)), 0);
  const cols = a.forecast.map((f) => {
    const bar = h('span', { class: 'forecast__bar' });
    const scale = max ? Number(f.amount) / max : 0;
    requestAnimationFrame(() => requestAnimationFrame(() => { bar.style.transform = `scaleY(${scale})`; }));
    bar.style.height = '100%';
    return h('div', { class: 'forecast__col', role: 'listitem', tabindex: '0',
      title: `${monthLabel(f.month)}: ${money(f.amount, a.currency)}`, 'aria-label': `${monthLabel(f.month)}: ${money(f.amount, a.currency)}` },
      bar, h('span', { class: 'forecast__m', 'aria-hidden': 'true' }, monthLabel(f.month)));
  });
  document.getElementById('forecast').replaceChildren(...cols);
  const total = a.forecast.reduce((s, f) => s + Number(f.amount), 0);
  document.getElementById('forecast-note').textContent = `Ukupno ${money(total, a.currency)} u 12 mjeseci prema stvarnim datumima naplate`
    + (a.unconverted.length ? ` (bez ${a.unconverted.join(', ')} – nema tečaja).` : '.');

  const list = document.getElementById('negotiation-list');
  if (!a.negotiation.length) {
    list.replaceChildren(h('li', { class: 'empty-row' }, 'Nema obnova u sljedećih 90 dana koje traže pregovore.'));
    return;
  }
  list.replaceChildren(...a.negotiation.slice(0, 6).map((c) => h('li', {},
    h('span', { class: `days${c.days <= 7 ? ' days--near' : ''}` }, `${c.days} d`),
    h('div', { class: 'grow' },
      h('div', { class: 'title' }, c.name),
      h('div', { class: 'meta' }, `obnova ${date(c.renews_on)} · ${money(c.cost, c.currency)}`),
      h('div', { class: 'reasons' }, c.reasons.map((r) => h('span', { class: `reason reason--${r.code}`, title: r.text }, r.text)))),
    h('button', { type: 'button', class: 'btn btn--sm', onclick: () => actions.edit(c.id), 'aria-label': `Uredi ${c.name}` }, 'Uredi'))));
}
