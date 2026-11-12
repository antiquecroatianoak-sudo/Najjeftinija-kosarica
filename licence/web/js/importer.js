// Import wizard: file -> column mapping (auto-suggested) -> result.
import { api, readFile } from './api.js';
import { closeDialog, h, toast } from './ui.js';

const LABELS = {
  name: 'Naziv', category: 'Kategorija', cost: 'Trošak po ciklusu', currency: 'Valuta',
  billing_cycle: 'Ciklus naplate', start_date: 'Datum početka', status: 'Status', usage_key: 'Ključ korištenja',
};
const DEFAULT_CHOICES = {
  currency: [['EUR', 'EUR'], ['USD', 'USD'], ['GBP', 'GBP'], ['CHF', 'CHF']],
  billing_cycle: [['monthly', 'Mjesečno'], ['quarterly', 'Tromjesečno'], ['yearly', 'Godišnje']],
  status: [['active', 'Aktivna'], ['inactive', 'Neaktivna'], ['cancelled', 'Otkazana']],
};

export class Importer {
  constructor(onDone) {
    this.onDone = onDone;
    this.dialog = document.getElementById('import-dialog');
    this.body = document.getElementById('import-body');
    this.actions = document.getElementById('import-actions');
    this.dialog.querySelectorAll('[data-close]').forEach((b) => b.addEventListener('click', () => this.close()));
    this.dialog.addEventListener('cancel', (e) => { e.preventDefault(); this.close(); });
    this.dialog.querySelector('form').addEventListener('submit', (e) => e.preventDefault());
  }

  close() { return closeDialog(this.dialog); }

  step(n) {
    this.dialog.querySelectorAll('.steps li').forEach((li) => {
      if (Number(li.dataset.step) === n) li.setAttribute('aria-current', 'step'); else li.removeAttribute('aria-current');
    });
  }

  open() {
    this.file = null;
    this.preview = null;
    this.step(1);
    const input = h('input', { type: 'file', accept: '.csv,.txt,.xlsx', id: 'import-file', 'aria-describedby': 'import-help' });
    const zone = h('label', { class: 'dropzone', for: 'import-file' },
      h('strong', {}, 'Odaberite ili povucite datoteku'),
      h('span', { class: 'muted small', id: 'import-help' }, 'CSV (; ili ,) ili Excel .xlsx, do 5 MB i 5 000 redaka. Prvi redak je zaglavlje.'),
      input);
    for (const ev of ['dragenter', 'dragover']) zone.addEventListener(ev, (e) => { e.preventDefault(); zone.classList.add('is-over'); });
    for (const ev of ['dragleave', 'drop']) zone.addEventListener(ev, () => zone.classList.remove('is-over'));
    zone.addEventListener('drop', (e) => { e.preventDefault(); if (e.dataTransfer.files[0]) this.load(e.dataTransfer.files[0]); });
    input.addEventListener('change', () => input.files[0] && this.load(input.files[0]));
    this.body.replaceChildren(zone, h('p', { class: 'hint' },
      'Stupci se prepoznaju automatski (hrvatski i engleski nazivi). U sljedećem koraku sve možete provjeriti i promijeniti.'));
    this.actions.replaceChildren(h('button', { type: 'button', class: 'btn', onclick: () => this.close() }, 'Odustani'));
    this.dialog.showModal();
  }

  async load(file) {
    try {
      this.file = await readFile(file);
      this.preview = await api.importPreview(this.file);
      this.renderMapping();
    } catch (err) {
      toast(err.fields?.file || err.message, { type: 'error' });
    }
  }

  renderMapping() {
    const p = this.preview;
    this.step(2);
    const options = [h('option', { value: '' }, '— nije u datoteci —'),
      ...p.headers.map((name, i) => h('option', { value: String(i) }, name || `Stupac ${i + 1}`))];
    const rows = p.fields.map((field) => {
      const select = h('select', { 'data-field': field, 'aria-label': `Stupac za ${LABELS[field]}` },
        ...options.map((o) => o.cloneNode(true)));
      select.value = p.mapping[field] == null ? '' : String(p.mapping[field]);
      const required = p.required.includes(field);
      let fallback = null;
      if (DEFAULT_CHOICES[field] || field === 'category') {
        fallback = DEFAULT_CHOICES[field]
          ? h('select', { 'data-default': field, 'aria-label': `Zadana vrijednost za ${LABELS[field]}` },
              h('option', { value: '' }, '—'), ...DEFAULT_CHOICES[field].map(([v, t]) => h('option', { value: v }, t)))
          : h('input', { 'data-default': field, placeholder: 'npr. Ostalo', 'aria-label': `Zadana vrijednost za ${LABELS[field]}` });
      }
      return h('tr', {},
        h('th', { scope: 'row' }, LABELS[field], required ? h('span', { class: 'req', title: 'obavezno' }, ' *') : null),
        h('td', {}, select),
        h('td', {}, fallback ?? h('span', { class: 'muted small' }, '—')));
    });
    const sample = h('div', { class: 'sample' }, h('table', {},
      h('thead', {}, h('tr', {}, ...p.headers.map((x) => h('th', {}, x)))),
      h('tbody', {}, ...p.sample.map((r) => h('tr', {}, ...p.headers.map((_, i) => h('td', {}, r[i] ?? '')))))));
    this.body.replaceChildren(
      h('p', {}, h('strong', {}, `${p.rows} ${p.rows === 1 ? 'redak' : 'redaka'}`), ` · format ${p.format.toUpperCase()}`),
      h('table', { class: 'map-table' },
        h('thead', {}, h('tr', {}, h('th', {}, 'Polje'), h('th', {}, 'Stupac u datoteci'), h('th', {}, 'Ako stupca nema'))),
        h('tbody', {}, ...rows)),
      h('label', { class: 'check' }, h('input', { type: 'checkbox', id: 'imp-skip-dup', checked: true }), h('span', {}, 'Preskoči licence koje već postoje (isti naziv)')),
      h('label', { class: 'check' }, h('input', { type: 'checkbox', id: 'imp-skip-invalid' }), h('span', {}, 'Uvezi ispravne retke i preskoči neispravne')),
      h('p', { class: 'muted small' }, 'Pregled prvih redaka:'), sample);
    const submit = h('button', { type: 'button', class: 'btn btn--primary', onclick: () => this.commit(submit) }, h('span', { class: 'btn__label' }, 'Uvezi'));
    this.actions.replaceChildren(h('button', { type: 'button', class: 'btn', onclick: () => this.open() }, 'Natrag'), submit);
  }

  async commit(button) {
    const mapping = {};
    const defaults = {};
    this.body.querySelectorAll('[data-field]').forEach((s) => { mapping[s.dataset.field] = s.value === '' ? null : Number(s.value); });
    this.body.querySelectorAll('[data-default]').forEach((s) => { if (s.value.trim()) defaults[s.dataset.default] = s.value.trim(); });
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');
    try {
      const result = await api.importCommit({
        ...this.file, mapping, defaults,
        skip_duplicates: document.getElementById('imp-skip-dup').checked,
        skip_invalid: document.getElementById('imp-skip-invalid').checked,
      });
      this.renderResult(result);
      this.onDone(result);
    } catch (err) {
      if (err.body?.committed === false) this.renderResult(err.body);
      else toast(err.fields?.mapping || err.fields?.file || err.message, { type: 'error' });
    } finally {
      button.disabled = false;
      button.removeAttribute('aria-busy');
    }
  }

  renderResult(r) {
    this.step(3);
    const errors = r.errors.map((e) => h('li', {}, `Redak ${e.line}: `,
      Object.entries(e.errors).map(([k, v]) => `${LABELS[k] ?? k} – ${v}`).join('; ')));
    this.body.replaceChildren(
      h('p', { class: 'result-big' }, r.committed ? `Uvezeno: ${r.created}` : 'Ništa nije uvezeno'),
      h('p', { class: 'muted' }, [r.skipped_duplicates ? `Preskočeno postojećih: ${r.skipped_duplicates}.` : '',
        r.error_count ? `Neispravnih redaka: ${r.error_count}.` : 'Svi retci su ispravni.',
        !r.committed ? 'Ispravite datoteku ili označite „Uvezi ispravne retke”.' : ''].filter(Boolean).join(' ')),
      errors.length ? h('ol', { class: 'errors' }, ...errors) : null);
    this.actions.replaceChildren(
      r.committed ? null : h('button', { type: 'button', class: 'btn', onclick: () => this.renderMapping() }, 'Natrag na mapiranje'),
      h('button', { type: 'button', class: 'btn btn--primary', onclick: () => this.close() }, 'Gotovo'));
  }
}
