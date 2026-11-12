// Bank view: statement import, insights, transaction review.
import { api, readFile } from './api.js';
import { date, money } from './format.js';
import { h, toast } from './ui.js';

const STATUS_LABEL = { matched: 'Sparena', suggested: 'Prijedlog', unmatched: 'Nesparena', ignored: 'Zanemarena' };
const STATUS_BADGE = { matched: 'badge--ok', suggested: 'badge--warn', unmatched: '', ignored: 'badge--off' };

export class BankView {
  constructor({ licenses, addLicense }) {
    this.licenses = licenses;       // () => current license list (for manual matching)
    this.addLicense = addLicense;   // (prefill) => opens the license form
    this.status = '';
    document.getElementById('bank-form').addEventListener('submit', (e) => this.import(e));
    document.getElementById('bank-filter').addEventListener('click', (e) => {
      const b = e.target.closest('button[data-status]');
      if (!b) return;
      this.status = b.dataset.status;
      this.refresh();
    });
  }

  async import(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const file = form.elements.file.files[0];
    if (!file) { toast('Odaberite datoteku izvoda.', { type: 'error' }); return; }
    const button = document.getElementById('bank-submit');
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');
    try {
      const s = await api.bankImport({ ...(await readFile(file)), label: form.elements.label.value });
      document.getElementById('bank-result').replaceChildren(h('div', { class: 'notice-box' },
        h('strong', {}, `Uvezeno ${s.imported} transakcija (${s.format})`),
        h('div', { class: 'muted small' }, `automatski sparene ${s.matched} · prijedlozi ${s.suggested} · nesparene ${s.unmatched}`
          + ` · duplikati ${s.duplicates}${s.recurring_unknown ? ` · moguće nepraćene pretplate ${s.recurring_unknown}` : ''}`)));
      form.reset();
      this.refresh();
    } catch (err) {
      toast(err.fields?.file || err.message, { type: 'error' });
    } finally {
      button.disabled = false;
      button.removeAttribute('aria-busy');
    }
  }

  async refresh() {
    document.querySelectorAll('#bank-filter button').forEach((b) => b.setAttribute('aria-checked', String(b.dataset.status === this.status)));
    try {
      const [items, insights] = await Promise.all([api.bankTransactions(this.status), api.bankInsights()]);
      this.renderTable(items);
      this.renderInsights(insights);
    } catch (err) {
      toast(err.message, { type: 'error' });
    }
  }

  renderInsights(ins) {
    const s = ins.summary;
    const box = document.getElementById('bank-insights');
    const parts = [h('p', { class: 'muted small' },
      `Isplate: sparene ${s.matched ?? 0} · prijedlozi ${s.suggested ?? 0} · nesparene ${s.unmatched ?? 0} · zanemarene ${s.ignored ?? 0}`)];
    parts.push(h('h3', { class: 'small' }, 'Moguće nepraćene pretplate'));
    parts.push(ins.recurring_unknown.length
      ? h('ul', { class: 'list' }, ...ins.recurring_unknown.map((r) => h('li', {},
          h('div', { class: 'grow' }, h('div', { class: 'title' }, r.counterparty),
            h('div', { class: 'meta' }, `${r.months} mjeseca zaredom · zadnje ${date(r.last_booked_on)}`)),
          h('span', { class: 'amount' }, money(r.amount, r.currency)),
          h('button', { type: 'button', class: 'btn btn--sm', onclick: () => this.addLicense({
            name: r.counterparty, cost: String(r.amount).replace('.', ','), currency: r.currency, category: 'Ostalo' }) }, 'Dodaj'))))
      : h('p', { class: 'muted small' }, 'Nema ponavljajućih plaćanja izvan evidencije.'));
    parts.push(h('h3', { class: 'small' }, 'Plaćeno drukčije od evidencije'));
    parts.push(ins.price_drift.length
      ? h('ul', { class: 'list' }, ...ins.price_drift.map((d) => h('li', {},
          h('div', { class: 'grow' }, h('div', { class: 'title' }, d.name), h('div', { class: 'meta' }, `${date(d.booked_on)} · u evidenciji ${money(d.registered, d.currency)}`)),
          h('span', { class: 'amount' }, money(d.paid, d.currency)))))
      : h('p', { class: 'muted small' }, 'Sparena plaćanja odgovaraju evidenciji.'));
    box.replaceChildren(...parts);
  }

  renderTable(items) {
    const tbody = document.querySelector('#bank-table tbody');
    if (!items.length) {
      tbody.replaceChildren(h('tr', {}, h('td', { colspan: '6', class: 'empty-cell' },
        h('div', { class: 'empty' }, h('p', { class: 'empty__title' }, 'Nema transakcija'),
          h('p', { class: 'muted' }, this.status ? 'Za ovaj filtar nema transakcija.' : 'Uvezite izvod da biste sparili plaćanja s licencama.')))));
      return;
    }
    const licenses = this.licenses();
    tbody.replaceChildren(...items.map((t) => {
      const select = h('select', { 'aria-label': `Licenca za ${t.counterparty}` }, h('option', { value: '' }, 'Odaberi licencu…'),
        ...licenses.map((l) => h('option', { value: l.id }, l.name)));
      select.value = t.license_id ?? '';
      const out = Number(t.amount) < 0;
      return h('tr', { 'data-id': t.id },
        h('td', { 'data-label': 'Datum' }, date(t.booked_on)),
        h('td', { 'data-label': 'Primatelj', class: 'name' }, t.counterparty || '—', h('div', { class: 'muted small' }, t.description)),
        h('td', { class: 'num', 'data-label': 'Iznos' }, money(t.amount, t.currency)),
        h('td', { 'data-label': 'Licenca' }, out ? select : h('span', { class: 'muted' }, 'uplata'),
          t.match_note ? h('div', { class: 'muted small' }, `${t.match_note} (${Math.round((t.match_score ?? 0) * 100)} %)`) : null),
        h('td', { 'data-label': 'Status' }, h('span', { class: `badge ${STATUS_BADGE[t.status]}` }, STATUS_LABEL[t.status])),
        h('td', { class: 'actions' }, out ? [
          h('button', { type: 'button', class: 'btn btn--sm', onclick: () => this.resolve(t.id, 'match', select.value) },
            t.status === 'suggested' ? 'Potvrdi' : 'Spari'),
          t.status !== 'ignored' ? h('button', { type: 'button', class: 'btn btn--sm', onclick: () => this.resolve(t.id, 'ignore') }, 'Zanemari')
            : h('button', { type: 'button', class: 'btn btn--sm', onclick: () => this.resolve(t.id, 'reset') }, 'Vrati'),
        ] : null));
    }));
  }

  async resolve(id, action, licenseId) {
    if (action === 'match' && !licenseId) { toast('Odaberite licencu.', { type: 'error' }); return; }
    try {
      await api.bankResolve(id, action, licenseId || null);
      toast(action === 'match' ? 'Transakcija je sparena.' : action === 'ignore' ? 'Transakcija je zanemarena.' : 'Vraćeno.');
      this.refresh();
    } catch (err) {
      toast(err.message, { type: 'error' });
    }
  }
}
