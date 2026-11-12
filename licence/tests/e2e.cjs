// End-to-end check of the whole flow in a real browser (Chromium via Playwright).
// Usage (from licence/):  node tests/e2e.cjs [screenshot-dir]
// Starts its own server on a free port with an in-memory demo database.
const { spawn } = require('node:child_process');
const path = require('node:path');
const { chromium } = require('playwright');

const ROOT = path.resolve(__dirname, '..');
const shotDir = process.argv[2];
let failures = 0;
const check = (ok, msg) => { console.log(`${ok ? 'ok  ' : 'FAIL'} ${msg}`); if (!ok) failures++; };

function startServer() {
  return new Promise((resolve, reject) => {
    const proc = spawn('python3', ['-m', 'licence_app', '--port', '0', '--db', ':memory:', '--demo', '--quiet'],
      { cwd: ROOT, stdio: ['ignore', 'pipe', 'inherit'] });
    proc.stdout.on('data', (buf) => {
      const m = /http:\/\/[\d.]+:(\d+)/.exec(buf.toString());
      if (m) resolve({ proc, url: `http://127.0.0.1:${m[1]}` });
    });
    proc.on('exit', (code) => reject(new Error(`server exited ${code}`)));
    setTimeout(() => reject(new Error('server did not start')), 10000);
  });
}

async function newPage(browser, url, errors, opts = {}) {
  const page = await browser.newPage(opts);
  page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(`console: ${m.text()}`); });
  await page.goto(url);
  await page.waitForSelector('#license-table tbody tr[data-id]', { state: 'attached' });
  return page;
}

const rowCount = (p) => p.locator('#license-table tbody tr[data-id]').count();
const waitRows = (p, n) => p.waitForFunction((n) => document.querySelectorAll('#license-table tbody tr[data-id]').length === n, n);
const waitText = (p, sel, text) => p.waitForFunction(([s, t]) => document.querySelector(s)?.textContent.trim() === t, [sel, text]);

(async () => {
  const { proc, url } = await startServer();
  const browser = await chromium.launch();
  const errors = [];
  try {
    // ---------- layout on several widths, both themes ----------
    for (const [w, h, scheme] of [[1280, 900, 'light'], [768, 1024, 'dark'], [360, 780, 'dark'], [320, 640, 'light']]) {
      const p = await newPage(browser, url, errors, { viewport: { width: w, height: h }, colorScheme: scheme });
      for (const view of ['pregled', 'licence']) {
        await p.goto(`${url}/#/${view}`);
        await p.waitForSelector(`#view-${view}:not([hidden])`);
        await p.waitForTimeout(400);
        const overflow = await p.evaluate(() => document.documentElement.scrollWidth - innerWidth);
        check(overflow <= 0, `${w}px ${scheme} #/${view}: no horizontal scroll (${overflow})`);
        if (view === 'pregled') {
          const squeezed = await p.evaluate(() => [...document.querySelectorAll('.list .title')]
            .filter((t) => t.getBoundingClientRect().width < 120).map((t) => t.textContent));
          check(squeezed.length === 0, `${w}px: list titles have room (${squeezed.join(', ')})`);
        }
        await p.waitForTimeout(500); // let count-up finish before screenshots
        if (shotDir) await p.screenshot({ path: path.join(shotDir, `${view}-${w}-${scheme}.png`), fullPage: true });
      }
      await p.close();
    }

    // ---------- lifecycle: entry -> display -> edit -> detect -> delete -> undo ----------
    const p = await newPage(browser, url, errors, { viewport: { width: 1280, height: 900 } });
    check(await p.title() === 'Pregled · Licence tima', 'title follows view');
    check((await p.textContent('#tab-count')).trim() === '7', 'nav badge shows 7 licenses');
    check(!(await p.isVisible('#license-empty')) && await p.evaluate(() =>
      getComputedStyle(document.getElementById('license-empty')).display === 'none'), 'empty state hidden when rows exist');
    check((await p.textContent('#inactive-count')).trim() === '2', 'dashboard detects 2 inactive');
    await p.waitForFunction(() => document.querySelector('#kpi-monthly .kpi__value')?.textContent.includes('137,73'));
    check(true, 'monthly total 137,73 € shown (count-up settled)');

    // keyboard shortcut "n" opens form; client validation catches bad cost before the server
    await p.keyboard.press('n');
    await p.waitForSelector('#license-dialog[open]');
    const f = '#license-form ';
    await p.fill(f + '[name=name]', 'Jira Software');
    await p.fill(f + '[name=category]', 'Razvoj');
    await p.fill(f + '[name=cost]', '12,345');
    await p.click('#btn-save');
    check(/dvije decimale/.test(await p.textContent('.err[data-for=cost]')), 'inline error for 3 decimals');
    check(await p.getAttribute(f + '[name=cost]', 'aria-invalid') === 'true', 'cost marked aria-invalid');
    await p.fill(f + '[name=cost]', '1.234,50');
    await p.click('label:has(input[value=yearly])');
    check((await p.textContent('#monthly-preview')).includes('102,88'), 'live monthly preview 1.234,50/12');
    await p.click('#btn-save');
    await p.waitForSelector('#license-dialog:not([open])', { state: 'attached' });
    await waitRows(p, 8);
    check(p.url().endsWith('#/licence'), 'after create: navigated to Licence view');
    check(await p.locator('tr', { hasText: 'Jira Software' }).locator('td.num').first().textContent()
      .then((t) => t.includes('1.234,50')), 'created row shows 1.234,50 €');

    // edit -> inactive -> appears in dashboard detection
    await p.locator('tr', { hasText: 'Jira Software' }).getByRole('button', { name: /Uredi/ }).click();
    await p.waitForSelector('#license-dialog[open]');
    check(await p.inputValue(f + '[name=cost]') === '1234,50', 'edit form prefilled');
    await p.click('label:has(input[value=inactive])');
    await p.click('#btn-save');
    await p.waitForSelector('#license-dialog:not([open])', { state: 'attached' });
    await p.click('.tab[data-view=pregled]');
    await waitText(p, '#inactive-count', '3');
    check(await p.locator('#inactive-list li', { hasText: 'Jira Software' }).count() === 1, 'edited license detected as inactive');

    // expiring window switch
    await p.click('#window-seg [data-days="7"]');
    await p.waitForFunction(() => document.querySelector('#window-seg [data-days="7"]').getAttribute('aria-checked') === 'true');
    const exp7 = await p.locator('#expiring-list li').allTextContents();
    await p.click('#window-seg [data-days="90"]');
    await p.waitForFunction(() => document.querySelector('#window-seg [data-days="90"]').getAttribute('aria-checked') === 'true');
    const exp90 = await p.locator('#expiring-list li').allTextContents();
    check(exp90.length >= exp7.length && exp90.length > 1, `expiring window 7d=${exp7.length} 90d=${exp90.length}`);

    // cancel from dashboard
    await p.locator('#inactive-list li', { hasText: 'Jira Software' }).getByRole('button', { name: /Otkaži/ }).click();
    await waitText(p, '#inactive-count', '2');
    check(true, 'cancel from dashboard removes it from inactive');

    // filters, search, sorting
    await p.click('.tab[data-view=licence]');
    await p.click('#status-seg [data-status=cancelled]');
    await waitRows(p, 2);
    check(true, 'status filter: 2 cancelled');
    await p.click('#status-seg [data-status=""]');
    await waitRows(p, 8);
    await p.keyboard.press('/');
    await p.waitForFunction(() => document.activeElement?.name === 'q', null, { timeout: 3000 })
      .then(() => check(true, '"/" focuses search'), () => check(false, '"/" focuses search'));
    await p.keyboard.type('dizajn');
    await waitRows(p, 2);
    check(true, 'search by category');
    await p.fill('#filters [name=q]', 'nema-toga');
    await waitText(p, '#empty-title', 'Nema rezultata');
    check(true, 'empty state for no results');
    await p.fill('#filters [name=q]', '');
    await waitRows(p, 8);
    await p.click('.sort[data-sort=monthly]');
    await p.click('.sort[data-sort=monthly]');
    check(await p.getAttribute('th:has(.sort[data-sort=monthly])', 'aria-sort') === 'descending', 'sort desc by monthly');

    // delete with confirm, then undo
    await p.locator('tr', { hasText: 'Jira Software' }).getByRole('button', { name: /Obriši/ }).click();
    await p.waitForSelector('#confirm-dialog[open]');
    await p.click('#confirm-dialog button[value=ok]');
    await waitRows(p, 7);
    check(true, 'delete after confirm');
    await p.click('.toast__btn');
    await waitRows(p, 8);
    check(await p.locator('tr', { hasText: 'Jira Software' }).count() === 1, 'undo restores deleted license');

    // Esc closes dialog; theme toggle cycles
    await p.click('#btn-new');
    await p.waitForSelector('#license-dialog[open]');
    await p.keyboard.press('Escape');
    await p.waitForSelector('#license-dialog:not([open])', { state: 'attached' });
    check(true, 'Esc closes form');
    await p.click('#btn-theme');
    check(await p.evaluate(() => document.documentElement.dataset.theme) === 'light', 'theme toggle -> light');
    await p.click('#btn-theme');
    check(await p.evaluate(() => document.documentElement.dataset.theme) === 'dark', 'theme toggle -> dark');

    // reload keeps data (server state), reduced motion works
    const rm = await newPage(browser, `${url}/#/licence`, errors, { reducedMotion: 'reduce' });
    check(await rowCount(rm) === 8, 'fresh page (reduced motion) sees 8 licenses');
    await rm.close();

    check(errors.length === 0, `no JS/CSP errors${errors.length ? ': ' + errors.join(' | ') : ''}`);
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
