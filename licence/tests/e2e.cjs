// End-to-end check of the whole product in a real browser (Chromium via Playwright).
// Usage (from licence/):  node tests/e2e.cjs [screenshot-dir]
// Starts the real server (CLI) on a free port with an in-memory demo database.
const { spawn } = require('node:child_process');
const path = require('node:path');
const { chromium } = require('playwright');

const ROOT = path.resolve(__dirname, '..');
const shotDir = process.argv[2];
const USER = 'admin';
const PASS = 'e2e-lozinka-dovoljno-duga';
let failures = 0;
const check = (ok, msg) => { console.log(`${ok ? 'ok  ' : 'FAIL'} ${msg}`); if (!ok) failures++; };

const CAMT = `<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.02"><BkToCstmrStmt><Stmt>
<Acct><Id><IBAN>HR1210010051863000160</IBAN></Id></Acct>
<Ntry><Amt Ccy="EUR">43.75</Amt><CdtDbtInd>DBIT</CdtDbtInd><BookgDt><Dt>2026-11-01</Dt></BookgDt><AcctSvcrRef>A1</AcctSvcrRef>
<NtryDtls><TxDtls><RltdPties><Cdtr><Nm>SLACK TECHNOLOGIES</Nm></Cdtr></RltdPties></TxDtls></NtryDtls></Ntry>
<Ntry><Amt Ccy="EUR">15.00</Amt><CdtDbtInd>DBIT</CdtDbtInd><BookgDt><Dt>2026-09-12</Dt></BookgDt><AcctSvcrRef>A2</AcctSvcrRef>
<NtryDtls><TxDtls><RltdPties><Cdtr><Nm>MIRO</Nm></Cdtr></RltdPties></TxDtls></NtryDtls></Ntry>
<Ntry><Amt Ccy="EUR">15.00</Amt><CdtDbtInd>DBIT</CdtDbtInd><BookgDt><Dt>2026-10-12</Dt></BookgDt><AcctSvcrRef>A3</AcctSvcrRef>
<NtryDtls><TxDtls><RltdPties><Cdtr><Nm>MIRO</Nm></Cdtr></RltdPties></TxDtls></NtryDtls></Ntry>
</Stmt></BkToCstmrStmt></Document>`;

function startServer() {
  return new Promise((resolve, reject) => {
    const env = { ...process.env, LICENCE_ADMIN_USER: USER, LICENCE_ADMIN_PASSWORD: PASS, LICENCE_ADMIN_ORG: 'Acme d.o.o.',
      LICENCE_RATES_AUTO: '0', LICENCE_ACCESS_LOG: '0', LICENCE_LOG_FORMAT: 'text' };
    const proc = spawn('python3', ['-m', 'licence_app', 'serve', '--port', '0', '--db', ':memory:', '--demo'],
      { cwd: ROOT, env, stdio: ['ignore', 'pipe', 'inherit'] });
    proc.stdout.on('data', (buf) => {
      const m = /http:\/\/[\d.]+:(\d+)/.exec(buf.toString());
      if (m) resolve({ proc, url: `http://127.0.0.1:${m[1]}` });
    });
    proc.on('exit', (code) => reject(new Error(`server exited ${code}`)));
    setTimeout(() => reject(new Error('server did not start')), 15000);
  });
}

async function newContext(browser, opts = {}) {
  return browser.newContext({ httpCredentials: { username: USER, password: PASS }, acceptDownloads: true, ...opts });
}

function watch(page, errors) {
  page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`));
  page.on('console', (m) => {
    // the offline test aborts API calls on purpose; the browser logs those
    if (m.type() === 'error' && !/ERR_FAILED|ERR_INTERNET_DISCONNECTED|Failed to load resource/.test(m.text())) errors.push(`console: ${m.text()}`);
  });
}

const rows = (p) => p.locator('#license-table tbody tr[data-id]');
const waitRows = (p, n) => p.waitForFunction((n) => document.querySelectorAll('#license-table tbody tr[data-id]').length === n, n);
const waitText = (p, sel, re) => p.waitForFunction(([s, r]) => new RegExp(r).test(document.querySelector(s)?.textContent ?? ''), [sel, re.source ?? re]);

(async () => {
  const { proc, url } = await startServer();
  const browser = await chromium.launch();
  const errors = [];
  try {
    // ---------- authentication ----------
    const anon = await browser.newContext();
    const res = await (await anon.newPage()).goto(url);
    check(res.status() === 401, 'page without credentials -> 401 (browser login prompt)');
    await anon.close();

    // ---------- layout: every view, several widths, both themes ----------
    for (const [w, h, scheme] of [[1280, 900, 'light'], [768, 1024, 'dark'], [360, 780, 'dark'], [320, 640, 'light']]) {
      const ctx = await newContext(browser, { viewport: { width: w, height: h }, colorScheme: scheme });
      const p = await ctx.newPage();
      watch(p, errors);
      for (const view of ['pregled', 'licence', 'banka', 'postavke']) {
        await p.goto(`${url}/#/${view}`);
        await p.waitForSelector(`#view-${view}:not([hidden])`);
        await p.waitForFunction(() => document.querySelector('#org-name').textContent !== '…');
        await p.waitForTimeout(view === 'pregled' ? 1000 : 500);
        const overflow = await p.evaluate(() => document.documentElement.scrollWidth - innerWidth);
        check(overflow <= 0, `${w}px ${scheme} #/${view}: no horizontal scroll (${overflow})`);
        if (shotDir) await p.screenshot({ path: path.join(shotDir, `${view}-${w}-${scheme}.png`), fullPage: true });
      }
      await ctx.close();
    }

    const ctx = await newContext(browser, { viewport: { width: 1280, height: 900 } });
    const p = await ctx.newPage();
    watch(p, errors);
    await p.goto(url);
    await p.waitForSelector('#license-table tbody tr[data-id]', { state: 'attached' });

    // ---------- branding & ROI ----------
    check(await p.title() === 'Pregled · License Pulse', 'title: Pregled · License Pulse');
    check((await p.textContent('#org-name')).trim() === 'Acme d.o.o.', 'organization name in header');
    await waitText(p, '#roi-loss', /85,98/);
    check(true, 'ROI hero: monthly loss 85,98 € at the top');
    check(/62,4/.test(await p.textContent('#waste-pct')), 'waste share 62,4 %');
    check(/Zoom Pro/.test(await p.textContent('#roi-action')), 'next avoidable charge named');
    await p.fill('#calc-cost', '20');
    await waitText(p, '#calc-roi', /%/);
    const roiText = await p.textContent('#calc-roi');
    check(/^\d/.test(roiText.trim()), `ROI calculator with management cost: ${roiText}`);
    await p.fill('#calc-share', '50');
    check(/50/.test(await p.textContent('#calc-share-out')), 'cancel-share slider updates');
    check(await p.locator('#forecast .forecast__col').count() === 12, '12-month payment plan rendered');
    check(await p.locator('#negotiation-list li').count() >= 1, 'negotiation candidates rendered');

    // ---------- quick filters & shortcuts ----------
    await p.evaluate(() => document.activeElement.blur());   // shortcuts are off while typing in a field
    await p.keyboard.press('3');
    await waitRows(p, 2);
    check(p.url().endsWith('#/licence'), 'key 3 -> Licence view, inactive filter');
    await p.click('#quick-filters [data-filter=expiring]');
    await p.waitForFunction(() => document.querySelector('#quick-filters [data-filter=expiring]').getAttribute('aria-checked') === 'true');
    await p.waitForTimeout(300);
    check(await rows(p).count() >= 1, 'quick filter: expiring within 30 days');
    await p.keyboard.press('1');
    await waitRows(p, 7);
    await p.keyboard.press('?');
    await p.waitForSelector('#help-dialog[open]');
    await p.keyboard.press('Escape');
    await p.keyboard.press('g');
    await p.keyboard.press('b');
    await p.waitForSelector('#view-banka:not([hidden])');
    check(true, '"?" help and "g b" navigation');

    // ---------- create with validation, usage tracking fields ----------
    await p.keyboard.press('n');
    await p.waitForSelector('#license-dialog[open]');
    const f = '#license-form ';
    await p.fill(f + '[name=name]', 'Jira Software');
    await p.fill(f + '[name=category]', 'Razvoj');
    await p.fill(f + '[name=cost]', '12,345');
    await p.fill(f + '[name=usage_key]', 'Jira');
    check(await p.inputValue(f + '[name=name]') === 'Jira Software', 'typed text stays in its field (no focus theft)');
    await p.click('#btn-save');
    const costErr = await p.textContent('.err[data-for=cost]');
    check(/dvije decimale/.test(costErr), `inline validation (3 decimals): "${costErr}"`);
    await p.fill(f + '[name=cost]', '1.234,50');
    await p.click('label:has(input[value=yearly])');
    check((await p.textContent('#monthly-preview')).includes('102,88'), 'live monthly preview');
    await p.click('#btn-save');
    await p.waitForSelector('#license-dialog:not([open])', { state: 'attached' });
    await waitRows(p, 8);
    check(p.url().endsWith('#/licence'), 'after create: Licence view');
    const jira = p.locator('tr', { hasText: 'Jira Software' });
    check(/jira/.test(await jira.locator('.track-badge').textContent()), 'usage key badge (lower-cased)');
    check(/još nema prijava/.test(await jira.textContent()), 'usage column: no logins yet');

    // ---------- edit (optimistic) ----------
    await jira.getByRole('button', { name: /Uredi/ }).click();
    await p.waitForSelector('#license-dialog[open]');
    check(await p.inputValue(f + '[name=cost]') === '1234,50', 'edit form prefilled');
    await p.click('label:has(input[value=inactive])');
    await p.click('#btn-save');
    await p.waitForSelector('#license-dialog:not([open])', { state: 'attached' });
    await p.click('.tab[data-view=pregled]');
    await waitText(p, '#inactive-count', /^3$/);
    check(true, 'edited license detected as inactive on dashboard');

    // ---------- optimistic cancel from dashboard ----------
    const t0 = Date.now();
    await p.locator('#inactive-list li', { hasText: 'Jira Software' }).getByRole('button', { name: /Otkaži/ }).click();
    await p.waitForFunction(() => ![...document.querySelectorAll('#inactive-list li')].some((li) => li.textContent.includes('Jira')));
    check(true, `cancel removes it immediately (${Date.now() - t0} ms)`);
    await waitText(p, '#inactive-count', /^2$/);

    // ---------- delete with confirm + undo ----------
    await p.click('.tab[data-view=licence]');
    await p.locator('tr', { hasText: 'Jira Software' }).getByRole('button', { name: /Obriši/ }).click();
    await p.waitForSelector('#confirm-dialog[open]');
    await p.click('#confirm-dialog button[value=ok]');
    await waitRows(p, 7);
    await p.click('.toast__btn');
    await waitRows(p, 8);
    check(await p.locator('tr', { hasText: 'Jira Software' }).count() === 1, 'delete + undo');

    // ---------- import wizard ----------
    await p.click('#btn-import');
    await p.waitForSelector('#import-dialog[open]');
    const csv = 'Naziv;Kategorija;Cijena;Valuta;Naplata;Datum početka;Status\n'
      + 'Miro;Dizajn;15,00;EUR;mjesečno;12.9.2025.;aktivna\nLoom;Komunikacija;12,50;USD;godišnje;1.2.2025.;neaktivna\n';
    await p.setInputFiles('#import-file', { name: 'licence.csv', mimeType: 'text/csv', buffer: Buffer.from(csv) });
    await p.waitForSelector('.map-table');
    check(await p.inputValue('[data-field=cost]') === '2', 'import: columns mapped automatically');
    await p.click('#import-actions .btn--primary');
    await waitText(p, '.result-big', /Uvezeno: 2/);
    await p.click('#import-actions .btn--primary');
    await waitRows(p, 10);
    check(true, 'import wizard: 2 licenses imported');

    // ---------- export ----------
    const [download] = await Promise.all([p.waitForEvent('download'), p.click('#btn-export')]);
    const file = await download.path();
    const text = require('node:fs').readFileSync(file, 'utf8');
    check(download.suggestedFilename().startsWith('licence-') && text.includes(';Miro;Dizajn;15.00;EUR;'), 'CSV export downloaded');

    // ---------- bank ----------
    await p.click('.tab[data-view=banka]');
    await p.setInputFiles('#bank-form [name=file]', { name: 'izvod.xml', mimeType: 'application/xml', buffer: Buffer.from(CAMT) });
    await p.click('#bank-submit');
    await waitText(p, '#bank-result', /Uvezeno 3 transakcija/);
    await p.waitForFunction(() => document.querySelectorAll('#bank-table tbody tr[data-id]').length === 3);
    check(/Sparena/.test(await p.locator('#bank-table tr', { has: p.locator('td.name', { hasText: 'SLACK TECHNOLOGIES' }) }).textContent()), 'bank: Slack payment matched automatically');
    const bankSummary = await p.textContent('#bank-result');
    // MIRO payments match the "Miro" license imported above, Slack matches Slack Pro
    check(/automatski sparene 3/.test(bankSummary), `bank import summary: "${bankSummary}"`);

    // ---------- settings: branding, token ----------
    await p.click('.tab[data-view=postavke]');
    await p.waitForSelector('#admin-settings .panel');
    await p.fill('#org-form [name=name]', 'Acme Grupa');
    await p.$eval('#org-form [name=accent]', (el) => { el.value = '#0a7d33'; });
    await p.click('#org-form button[type=submit]');
    await waitText(p, '#org-name', /Acme Grupa/);
    const accent = await p.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--accent').trim());
    check(accent === '#0a7d33', `organization accent applied (${accent})`);
    const tokenForm = p.locator('#admin-settings .panel', { hasText: 'API tokeni' });
    await tokenForm.locator('input[name=name]').fill('Okta');
    await tokenForm.getByRole('button', { name: 'Izradi token' }).click();
    await p.waitForSelector('.secret code');
    check(/^lp_/.test(await p.textContent('.secret code')), 'API token shown once with usage example');

    // ---------- notifications ----------
    await p.click('#btn-notifications');
    await p.waitForSelector('#notif-dialog[open]');
    check(await p.locator('#notif-list li').count() >= 1, 'notifications panel');
    await p.keyboard.press('Escape');

    // ---------- local cache + offline ----------
    await p.route('**/api/**', (route) => route.abort('internetdisconnected'));
    await p.reload();
    await p.waitForFunction(() => document.querySelectorAll('#license-table tbody tr[data-id]').length > 0);
    await waitText(p, '#sync-state', /Izvan mreže/);
    check(true, 'offline reload: cached data shown with offline indicator');
    await p.unroute('**/api/**');

    check(errors.length === 0, `no JS/CSP errors${errors.length ? ': ' + errors.join(' | ') : ''}`);
    await ctx.close();
  } catch (err) {
    console.log('FAIL', err.stack || err);
    failures++;
  } finally {
    await browser.close();
    proc.kill('SIGTERM');
  }
  console.log(failures ? `\n${failures} PROVJERA NIJE PROŠLO` : '\nSVE PROVJERE SU PROŠLE');
  process.exit(failures ? 1 : 0);
})();
