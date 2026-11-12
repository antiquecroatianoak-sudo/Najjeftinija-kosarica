import { ApiError } from './api.js';
import { CYCLE, STATUS, money, parseAmount } from './format.js';
import { closeDialog } from './ui.js';

const FIELDS = ['name', 'category', 'cost', 'currency', 'billing_cycle', 'start_date', 'status'];

function localToday() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

// Quick checks so obvious mistakes show before a round-trip; the server stays authoritative.
const CHECKS = {
  name: (v) => (v ? '' : 'Upišite naziv.'),
  category: (v) => (v ? '' : 'Upišite kategoriju.'),
  cost: (v) => (!v ? 'Upišite trošak.' : parseAmount(v) == null ? 'Upišite iznos, npr. 9,99 (najviše dvije decimale).' : ''),
  currency: (v) => (/^[A-Za-z]{3}$/.test(v) ? '' : 'Troslovni kod valute, npr. EUR.'),
  start_date: (v) => (v ? '' : 'Odaberite datum početka.'),
};

// Create/edit dialog. `save(data, id|null)` returns a promise; API field errors (422) show inline.
export class LicenseForm {
  constructor(save) {
    this.save = save;
    this.dialog = document.getElementById('license-dialog');
    this.form = document.getElementById('license-form');
    this.error = document.getElementById('form-error');
    this.button = document.getElementById('btn-save');
    this.id = null;
    this.dirty = false;

    this.form.addEventListener('submit', (e) => this.#submit(e));
    this.form.addEventListener('input', (e) => { this.dirty = true; this.#clearField(e.target.name); this.#preview(); });
    this.form.addEventListener('change', () => this.#preview());
    this.form.addEventListener('focusout', (e) => {
      const check = CHECKS[e.target.name];
      if (check && this.dirty) this.#setField(e.target.name, check(e.target.value.trim()));
    });
    this.form.querySelectorAll('[data-close]').forEach((b) => b.addEventListener('click', () => this.close()));
    this.form.elements.currency.addEventListener('input', (e) => { e.target.value = e.target.value.toUpperCase(); });
    this.dialog.addEventListener('cancel', (e) => { e.preventDefault(); this.close(); }); // Esc: animated close
    this.dialog.addEventListener('click', (e) => { if (e.target === this.dialog) this.close(); }); // backdrop
  }

  open(license = null) {
    this.id = license?.id ?? null;
    this.form.reset();
    this.#clearErrors();
    this.dirty = false;
    document.getElementById('dlg-title').textContent = license ? 'Uredi licencu' : 'Nova licenca';
    const values = license
      ? { ...license, cost: String(license.cost).replace('.', ',') }
      : { currency: 'EUR', billing_cycle: 'monthly', status: 'active', start_date: localToday() };
    for (const key of FIELDS) if (values[key] != null) this.form.elements[key].value = values[key];
    this.#preview();
    this.dialog.showModal();
    requestAnimationFrame(() => this.form.elements.name.focus());
  }

  close() {
    return closeDialog(this.dialog);
  }

  #values() {
    return Object.fromEntries(FIELDS.map((k) => [k, String(this.form.elements[k].value ?? '').trim()]));
  }

  #preview() {
    const v = this.#values();
    const amount = parseAmount(v.cost);
    const cycle = CYCLE[v.billing_cycle];
    const out = document.getElementById('monthly-preview');
    out.textContent = amount != null && cycle && v.billing_cycle !== 'monthly' && /^[A-Z]{3}$/.test(v.currency)
      ? `≈ ${money(Number(amount) / cycle.months, v.currency)} mjesečno` : '';
    document.getElementById('status-hint').textContent = STATUS[v.status]?.hint ?? '';
  }

  async #submit(event) {
    event.preventDefault();
    this.#clearErrors();
    const data = this.#values();
    let firstBad = null;
    for (const [key, check] of Object.entries(CHECKS)) {
      const msg = check(data[key]);
      if (msg) { this.#setField(key, msg); firstBad ??= key; }
    }
    if (firstBad) { this.form.elements[firstBad].focus(); return; }
    data.cost = parseAmount(data.cost);
    data.currency = data.currency.toUpperCase();

    this.button.disabled = true;
    this.button.setAttribute('aria-busy', 'true');
    try {
      await this.save(data, this.id);
      await this.close();
    } catch (err) {
      if (err instanceof ApiError && Object.keys(err.fields).length) {
        for (const [key, msg] of Object.entries(err.fields)) this.#setField(key, msg);
      } else {
        this.error.textContent = err.message;
        this.error.hidden = false;
      }
    } finally {
      this.button.disabled = false;
      this.button.removeAttribute('aria-busy');
    }
  }

  #setField(key, msg) {
    const slot = this.form.querySelector(`.err[data-for="${key}"]`);
    if (!slot) {
      if (msg) { this.error.textContent = msg; this.error.hidden = false; }
      return;
    }
    slot.textContent = msg;
    const input = this.form.elements[key];
    if (input instanceof HTMLInputElement) {
      if (msg) input.setAttribute('aria-invalid', 'true'); else input.removeAttribute('aria-invalid');
    }
  }

  #clearField(key) {
    if (key) this.#setField(key, '');
  }

  #clearErrors() {
    this.error.hidden = true;
    this.form.querySelectorAll('.err').forEach((el) => { el.textContent = ''; });
    this.form.querySelectorAll('[aria-invalid]').forEach((el) => el.removeAttribute('aria-invalid'));
  }
}
