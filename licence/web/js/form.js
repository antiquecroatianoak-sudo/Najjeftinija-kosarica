import { ApiError } from './api.js';

function localToday() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

const FIELDS = ['name', 'category', 'cost', 'currency', 'billing_cycle', 'start_date', 'status'];

// Create/edit dialog. `save(data, id|null)` must return a promise; field errors from
// the API (422) are shown next to the inputs.
export class LicenseForm {
  constructor(save) {
    this.save = save;
    this.dialog = document.getElementById('license-dialog');
    this.form = document.getElementById('license-form');
    this.error = document.getElementById('form-error');
    this.id = null;
    this.form.addEventListener('submit', (e) => this.#submit(e));
    document.getElementById('btn-cancel').addEventListener('click', () => this.dialog.close());
  }

  open(license = null) {
    this.id = license?.id ?? null;
    this.form.reset();
    this.#clearErrors();
    document.getElementById('dlg-title').textContent = license ? 'Uredi licencu' : 'Nova licenca';
    const values = license ?? { currency: 'EUR', billing_cycle: 'monthly', status: 'active',
      start_date: localToday() };
    for (const key of FIELDS) if (values[key] != null) this.form.elements[key].value = values[key];
    this.dialog.showModal();
    this.form.elements.name.focus();
  }

  async #submit(event) {
    event.preventDefault();
    this.#clearErrors();
    const data = Object.fromEntries(FIELDS.map((k) => [k, this.form.elements[k].value.trim()]));
    data.currency = data.currency.toUpperCase();
    const button = document.getElementById('btn-save');
    button.disabled = true;
    try {
      await this.save(data, this.id);
      this.dialog.close();
    } catch (err) {
      if (err instanceof ApiError && Object.keys(err.fields).length) {
        for (const [key, msg] of Object.entries(err.fields)) this.#fieldError(key, msg);
      } else {
        this.error.textContent = err.message;
        this.error.hidden = false;
      }
    } finally {
      button.disabled = false;
    }
  }

  #fieldError(key, msg) {
    const slot = this.form.querySelector(`.err[data-for="${key}"]`);
    if (!slot) {
      this.error.textContent = msg;
      this.error.hidden = false;
      return;
    }
    slot.textContent = msg;
    this.form.elements[key]?.setAttribute('aria-invalid', 'true');
  }

  #clearErrors() {
    this.error.hidden = true;
    this.form.querySelectorAll('.err').forEach((el) => { el.textContent = ''; });
    this.form.querySelectorAll('[aria-invalid]').forEach((el) => el.removeAttribute('aria-invalid'));
  }
}
