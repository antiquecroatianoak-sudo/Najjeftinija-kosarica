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

export function date(iso) {
  if (!iso) return '';
  const [y, m, d] = iso.split('-');
  return `${Number(d)}. ${Number(m)}. ${y}.`;
}

export function inDays(days) {
  if (days === 0) return 'danas';
  if (days === 1) return 'sutra';
  return `za ${days} dana`;
}

export const CYCLE_LABEL = { monthly: 'Mjesečno', quarterly: 'Tromjesečno', yearly: 'Godišnje' };

export const STATUS = {
  active: { label: 'Aktivna', pill: 'pill--ok' },
  inactive: { label: 'Neaktivna', pill: 'pill--warn' },
  cancelled: { label: 'Otkazana', pill: 'pill--off' },
};
