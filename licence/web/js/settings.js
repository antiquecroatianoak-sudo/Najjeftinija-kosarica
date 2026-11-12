// Settings: organization branding, password, and (admins) users, tokens, webhooks, rates, system.
import { api } from './api.js';
import { date } from './format.js';
import { confirmDialog, h, toast } from './ui.js';

function fieldErrors(form, err) {
  form.querySelectorAll('.err').forEach((e) => { e.textContent = ''; });
  const fields = err.fields || {};
  let shown = false;
  for (const [k, v] of Object.entries(fields)) {
    const slot = form.querySelector(`.err[data-for="${k}"]`);
    if (slot) { slot.textContent = v; shown = true; }
  }
  if (!shown) toast(Object.values(fields)[0] || err.message, { type: 'error' });
}

export class SettingsView {
  constructor({ onOrgChange }) {
    this.onOrgChange = onOrgChange;
    document.getElementById('org-form').addEventListener('submit', (e) => this.saveOrg(e));
    document.getElementById('password-form').addEventListener('submit', (e) => this.savePassword(e));
  }

  fill(me) {
    this.me = me;
    const f = document.getElementById('org-form');
    const o = me.organization;
    f.elements.name.value = o.name;
    f.elements.accent.value = o.accent;
    f.elements.reference_currency.value = o.reference_currency;
    f.elements.inactivity_days.value = o.inactivity_days;
    f.elements.notify_days.value = o.notify_days;
    const admin = me.user.role === 'admin';
    for (const el of f.elements) el.disabled = !admin;
    document.getElementById('password-form').elements.username.value = me.user.username;
    document.getElementById('settings-role').textContent =
      `Prijavljeni ste kao ${me.user.username} (${admin ? 'administrator' : 'član'}) u organizaciji ${o.name}.`;
  }

  async saveOrg(e) {
    e.preventDefault();
    const f = e.currentTarget;
    try {
      const org = await api.updateOrg({
        name: f.elements.name.value.trim(), accent: f.elements.accent.value,
        reference_currency: f.elements.reference_currency.value.trim().toUpperCase(),
        inactivity_days: Number(f.elements.inactivity_days.value), notify_days: Number(f.elements.notify_days.value),
      });
      f.querySelectorAll('.err').forEach((x) => { x.textContent = ''; });
      toast('Postavke organizacije su spremljene.');
      this.onOrgChange(org);
    } catch (err) { fieldErrors(f, err); }
  }

  async savePassword(e) {
    e.preventDefault();
    const f = e.currentTarget;
    try {
      await api.changePassword(f.elements.current.value, f.elements.password.value);
      f.reset();
      toast('Lozinka je promijenjena. Preglednik će zatražiti novu prijavu.');
    } catch (err) { fieldErrors(f, err); }
  }

  async refresh() {
    const box = document.getElementById('admin-settings');
    if (this.me?.user.role !== 'admin') {
      box.replaceChildren(h('p', { class: 'notice-box' },
        'Korisnike, API tokene, webhookove i tečajnu listu uređuje administrator vaše organizacije.'));
      return;
    }
    try {
      const [users, tokens, hooks, rates, system] = await Promise.all(
        [api.users(), api.tokens(), api.webhooks(), api.rates(), api.system()]);
      box.replaceChildren(
        h('div', { class: 'grid2' }, this.usersPanel(users), this.tokensPanel(tokens)),
        h('div', { class: 'grid2' }, this.webhooksPanel(hooks), this.ratesPanel(rates)),
        this.systemPanel(system));
    } catch (err) { toast(err.message, { type: 'error' }); }
  }

  panel(title, ...children) {
    return h('article', { class: 'panel' }, h('header', { class: 'panel__head' }, h('h2', {}, title)), ...children);
  }

  usersPanel(users) {
    const form = h('form', { class: 'inline-form', novalidate: true },
      h('label', { class: 'field' }, h('span', { class: 'field__label' }, 'Korisničko ime'), h('input', { name: 'username', autocomplete: 'off', required: true })),
      h('label', { class: 'field' }, h('span', { class: 'field__label' }, 'Početna lozinka'), h('input', { name: 'password', type: 'password', autocomplete: 'new-password', minlength: '12' })),
      h('label', { class: 'field' }, h('span', { class: 'field__label' }, 'Uloga'),
        h('select', { name: 'role' }, h('option', { value: 'member' }, 'Član'), h('option', { value: 'admin' }, 'Administrator'))),
      h('button', { type: 'submit', class: 'btn' }, 'Dodaj'));
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      try {
        await api.createUser({ username: form.elements.username.value.trim(), password: form.elements.password.value, role: form.elements.role.value });
        toast('Korisnik je dodan.');
        this.refresh();
      } catch (err) { toast(Object.values(err.fields)[0] || err.message, { type: 'error' }); }
    });
    return this.panel('Korisnici',
      h('ul', { class: 'list' }, ...users.map((u) => h('li', {},
        h('div', { class: 'grow' }, h('div', { class: 'title' }, u.username), h('div', { class: 'meta' }, u.role === 'admin' ? 'administrator' : 'član')),
        u.id === this.me.user.id ? h('span', { class: 'muted small' }, 'vi') :
          h('button', { type: 'button', class: 'btn btn--sm btn--ghost-danger', onclick: async () => {
            if (!(await confirmDialog(`Ukloniti korisnika ${u.username}?`, 'Ukloni'))) return;
            try { await api.deleteUser(u.id); this.refresh(); } catch (err) { toast(Object.values(err.fields)[0] || err.message, { type: 'error' }); }
          } }, 'Ukloni')))),
      form);
  }

  tokensPanel(tokens) {
    const secret = h('div');
    const form = h('form', { class: 'inline-form' },
      h('label', { class: 'field' }, h('span', { class: 'field__label' }, 'Naziv (npr. Okta, Entra ID)'), h('input', { name: 'name', autocomplete: 'off' })),
      h('button', { type: 'submit', class: 'btn' }, 'Izradi token'));
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      try {
        const t = await api.createToken(form.elements.name.value.trim());
        secret.replaceChildren(h('div', { class: 'secret' }, h('code', {}, t.token),
          h('button', { type: 'button', class: 'btn btn--sm', onclick: () => navigator.clipboard?.writeText(t.token).then(() => toast('Kopirano.')) }, 'Kopiraj')),
          h('p', { class: 'hint' }, 'Token se prikazuje samo sada. Spremite ga u sustav prijava.'),
          h('pre', { class: 'snippet' }, `curl -X POST ${location.origin}/api/usage \\\n  -H "Authorization: Bearer ${t.token}" \\\n  -H "Content-Type: application/json" \\\n  -d '{"events":[{"license":"slack","user":"ana@tvrtka.hr"}]}'`));
        form.reset();
        const list = await api.tokens();
        tokenList.replaceChildren(...tokenItems(list));
      } catch (err) { toast(Object.values(err.fields)[0] || err.message, { type: 'error' }); }
    });
    const tokenItems = (list) => list.length ? list.map((t) => h('li', {},
      h('div', { class: 'grow' }, h('div', { class: 'title' }, t.name),
        h('div', { class: 'meta' }, `izrađen ${date(t.created_at.slice(0, 10))} · ${t.last_used_at ? `zadnja upotreba ${date(t.last_used_at.slice(0, 10))}` : 'još nije korišten'}`)),
      h('button', { type: 'button', class: 'btn btn--sm btn--ghost-danger', onclick: async () => {
        if (!(await confirmDialog(`Opozvati token ${t.name}? Sustav koji ga koristi više neće slati podatke.`, 'Opozovi'))) return;
        await api.deleteToken(t.id); this.refresh();
      } }, 'Opozovi'))) : [h('li', { class: 'empty-row' }, 'Nema tokena.')];
    const tokenList = h('ul', { class: 'list' }, ...tokenItems(tokens));
    return this.panel('Praćenje korištenja (API tokeni)',
      h('p', { class: 'panel__hint' }, 'Sustav prijava (SSO) ili skripta šalje događaje korištenja; status licenci se tada mijenja automatski.'),
      tokenList, form, secret);
  }

  webhooksPanel({ items, events }) {
    const secret = h('div');
    const form = h('form', { class: 'stack' },
      h('label', { class: 'field' }, h('span', { class: 'field__label' }, 'URL primatelja (https)'), h('input', { name: 'url', type: 'url', placeholder: 'https://…', autocomplete: 'off' })),
      h('fieldset', { class: 'field' }, h('legend', { class: 'field__label' }, 'Događaji (ništa označeno = svi)'),
        h('div', { class: 'chips' }, ...events.map((ev) => h('label', { class: 'check' }, h('input', { type: 'checkbox', value: ev }), h('span', { class: 'small' }, ev))))),
      h('button', { type: 'submit', class: 'btn' }, 'Dodaj webhook'));
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const chosen = [...form.querySelectorAll('input[type=checkbox]:checked')].map((c) => c.value);
      try {
        const hook = await api.createWebhook({ url: form.elements.url.value.trim(), events: chosen.length ? chosen : '*' });
        toast('Webhook je dodan.');
        await this.refresh();
        document.getElementById('webhook-secret')?.replaceChildren(h('div', { class: 'secret' }, h('code', {}, hook.secret)),
          h('p', { class: 'hint' }, 'Tajna za provjeru potpisa (X-LicensePulse-Signature) prikazuje se samo sada.'));
      } catch (err) { toast(Object.values(err.fields)[0] || err.message, { type: 'error' }); }
    });
    secret.id = 'webhook-secret';
    return this.panel('Webhookovi',
      h('p', { class: 'panel__hint' }, 'Potpisani JSON događaji (istek, automatska neaktivnost, promjene, banka) za automatizaciju tijekova rada.'),
      h('ul', { class: 'list' }, ...(items.length ? items.map((w) => h('li', {},
        h('div', { class: 'grow' }, h('div', { class: 'title' }, w.url), h('div', { class: 'meta' }, w.events === '*' ? 'svi događaji' : w.events.replaceAll(',', ', '))),
        h('div', { class: 'row-actions' },
          h('button', { type: 'button', class: 'btn btn--sm', onclick: async () => {
            await api.testWebhook(w.id); toast('Testni događaj je u redu za slanje (do 20 s).');
          } }, 'Test'),
          h('button', { type: 'button', class: 'btn btn--sm', onclick: async () => {
            const d = await api.deliveries(w.id);
            toast(d.length ? d.slice(0, 3).map((x) => `${x.event}: ${x.status}${x.last_error ? ` (${x.last_error})` : ''}`).join(' · ') : 'Još nema isporuka.', { timeout: 8000 });
          } }, 'Isporuke'),
          h('button', { type: 'button', class: 'btn btn--sm btn--ghost-danger', onclick: async () => {
            if (!(await confirmDialog(`Ukloniti webhook ${w.url}?`, 'Ukloni'))) return;
            await api.deleteWebhook(w.id); this.refresh();
          } }, 'Ukloni')))) : [h('li', { class: 'empty-row' }, 'Nema webhookova.')])),
      form, secret);
  }

  ratesPanel(r) {
    const form = h('form', { class: 'inline-form' },
      h('label', { class: 'field' }, h('span', { class: 'field__label' }, 'Valuta'), h('input', { name: 'cur', maxlength: '3', placeholder: 'BAM' })),
      h('label', { class: 'field' }, h('span', { class: 'field__label' }, 'Jedinica za 1 EUR'), h('input', { name: 'rate', inputmode: 'decimal', placeholder: '1,95583' })),
      h('button', { type: 'submit', class: 'btn' }, 'Spremi tečaj'));
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      try {
        await api.setRate(form.elements.cur.value.trim().toUpperCase(), form.elements.rate.value.replace(',', '.'));
        toast('Tečaj je spremljen.');
        this.refresh();
      } catch (err) { toast(Object.values(err.fields)[0] || err.message, { type: 'error' }); }
    });
    const rows = r.items.filter((x) => x.currency !== 'EUR');
    return this.panel('Tečajna lista',
      h('p', { class: 'panel__hint' }, `Izvor: Europska središnja banka${r.auto ? ', automatsko osvježavanje svakih 6 h' : ' (automatsko osvježavanje isključeno)'}`
        + `${r.last_fetch ? ` · zadnje ${date(r.last_fetch.slice(0, 10))}` : ' · još nije dohvaćena'}. Ručni tečaj ima prednost.`),
      h('button', { type: 'button', class: 'btn btn--sm', onclick: async () => {
        try { const res = await api.refreshRates(); toast(`Tečajna lista od ${date(res.date)}: ${res.currencies} valuta.`); this.refresh(); }
        catch (err) { toast(err.message, { type: 'error' }); }
      } }, 'Osvježi sada'),
      rows.length ? h('div', { class: 'sample' }, h('table', {},
        h('thead', {}, h('tr', {}, h('th', {}, 'Valuta'), h('th', {}, 'za 1 EUR'), h('th', {}, 'Datum'), h('th', {}, 'Izvor'))),
        h('tbody', {}, ...rows.map((x) => h('tr', {}, h('td', {}, x.currency), h('td', {}, x.per_eur),
          h('td', {}, x.rate_date ? date(x.rate_date) : '—'), h('td', {}, x.source === 'manual' ? 'ručno' : 'ECB'))))))
        : h('p', { class: 'muted small' }, 'Nema tečajeva – iznosi u drugim valutama prikazuju se odvojeno.'),
      form);
  }

  systemPanel(s) {
    const tasks = Object.entries(s.tasks);
    return this.panel('Sustav',
      h('p', { class: 'muted small' }, `Shema baze v${s.schema_version} · okruženje ${s.environment}`),
      h('ul', { class: 'list' }, ...(tasks.length ? tasks.map(([name, t]) => h('li', {},
        h('div', { class: 'grow' }, h('div', { class: 'title' }, name), h('div', { class: 'meta' }, t.at)),
        h('span', { class: `badge ${t.ok ? 'badge--ok' : 'badge--warn'}` }, t.ok ? 'u redu' : t.error)))
        : [h('li', { class: 'empty-row' }, 'Pozadinski zadaci još nisu pokrenuti.')])));
  }
}
