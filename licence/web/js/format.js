// Display helpers. Amounts arrive from the API as decimal strings ("12.50").

const LOCALE = 'hr-HR';
const moneyFormats = new Map();

export function money(amount, currency) {
  if (!moneyFormats.has(currency)) {
    let fmt;
    try {
      fmt = new Intl.NumberFormat(LOCALE, { style: 'currency', currency });
    } catch {
      const plain = new Intl.NumberFormat(LOCALE, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      fmt = { format: (n) => `${plain.format(n)} ${currency}` };
    }
    moneyFormats.set(currency, fmt);
  }
  return moneyFormats.get(currency).format(Number(amount));
}

/** Parse user input like "1.234,50", "1234.5" or "9,99" -> "1234.50"-style string, or null. */
export function parseAmount(text) {
  let t = String(text).trim().replace(/\s/g, '');
  if (!t) return null;
  if (t.includes(',') && t.includes('.')) {
    // the later separator is the decimal one
    t = t.lastIndexOf(',') > t.lastIndexOf('.') ? t.replace(/\./g, '').replace(',', '.') : t.replace(/,/g, '');
  } else {
    t = t.replace(',', '.');
  }
  return /^\d+(\.\d{1,2})?$/.test(t) ? t : null;
}

export function date(iso) {
  if (!iso) return '';
  const [y, m, d] = iso.split('-');
  return `${Number(d)}. ${Number(m)}. ${y}.`;
}

export function inDays(days) {
  if (days === 0) return 'danas';
  if (days === 1) return 'sutra';
  const last = days % 10, lastTwo = days % 100;
  const word = last === 1 && lastTwo !== 11 ? 'dan' : 'dana';
  return `za ${days} ${word}`;
}

export function plural(n, one, few, many) {
  const last = n % 10, lastTwo = n % 100;
  if (last === 1 && lastTwo !== 11) return one;
  if (last >= 2 && last <= 4 && (lastTwo < 12 || lastTwo > 14)) return few;
  return many;
}

export const CYCLE = {
  monthly: { label: 'Mjesečno', months: 1 },
  quarterly: { label: 'Tromjesečno', months: 3 },
  yearly: { label: 'Godišnje', months: 12 },
};

export const STATUS = {
  active: { label: 'Aktivna', badge: 'badge--ok', dot: 'dot--ok', hint: 'Plaća se i tim je koristi.' },
  inactive: { label: 'Neaktivna', badge: 'badge--warn', dot: 'dot--warn', hint: 'Plaća se, ali se ne koristi – prikazuje se kao moguća ušteda.' },
  cancelled: { label: 'Otkazana', badge: 'badge--off', dot: 'dot--off', hint: 'Više se ne plaća i ne ulazi u troškove.' },
};

/** "prije 3 dana" from a UTC timestamp ("YYYY-MM-DD HH:MM:SS" or ISO). */
export function ago(ts) {
  if (!ts) return null;
  const then = Date.parse(ts.includes('T') ? ts : `${ts.replace(' ', 'T')}Z`);
  if (Number.isNaN(then)) return null;
  const days = Math.floor((Date.now() - then) / 86_400_000);
  if (days <= 0) return 'danas';
  if (days === 1) return 'jučer';
  return `prije ${days} ${plural(days, 'dan', 'dana', 'dana')}`;
}

export function pct(value) {
  return `${new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 1 }).format(Number(value))} %`;
}

export function monthLabel(ym) {
  const [y, m] = ym.split('-').map(Number);
  return new Intl.DateTimeFormat(LOCALE, { month: 'short' }).format(new Date(y, m - 1, 1)).replace('.', '');
}
