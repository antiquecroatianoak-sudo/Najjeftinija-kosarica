const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
const data={verzija:2,datum:'2026-10-19',lanci:['Konzum','Lidl','Spar'],proizvodi:[['Mlijeko trajno','1 l',1,'l',0,[0,1.1,1,1.2]],['Mlijeko svježe','0,5 l',0.5,'l',0,[1,0.7,2,0.8]],['Kruh bijeli','500 g',0.5,'kg',0,[1,1,0,1.5]],['Jaja','10 kom',10,'kom',0,[0,2.5,2,3]]]};
for(const width of [320,390,768,1280]){
const context=await browser.newContext({viewport:{width,height:950},serviceWorkers:'block'});const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.route('**/data/proizvodi.json',r=>r.fulfill({json:data}));await page.goto('http://localhost:8765');await page.waitForSelector('.spremno');
assert(await page.locator('#zakljucaj').isDisabled());
await page.locator('#unos').fill('kruh, 2 mlijeka i jaja');await page.locator('#rucni-unos button').click();assert.equal(await page.locator('#popis li').count(),3);
await page.locator('#popis li').first().getByRole('button',{name:'Više Kruh',exact:true}).click();assert.equal(await page.locator('#popis li .broj').first().textContent(),'2×');
await page.locator('#lanci-nista').click();assert(await page.locator('#zakljucaj').isDisabled());await page.locator('#lanci-sve').click();
await page.locator('#zakljucaj').click();assert.equal(await page.locator('#kartice li').count(),3);assert.equal(await page.locator('#ukupno').textContent(),'6,70 €');
await page.locator('.kvacica').first().click();assert.match(await page.locator('#napredak').textContent(),/1 od 3/);
await page.locator('.sljedeci').first().click();await page.reload();await page.waitForSelector('.spremno');assert(await page.locator('#rezultati').isVisible());assert.match(await page.locator('#napredak').textContent(),/1 od 3/);
await page.locator('#otkljucaj').click();await page.locator('input[value="pakiranje"]').check();await page.locator('#unos').fill('nepostojeci proizvod');await page.locator('#rucni-unos button').click();await page.locator('#zakljucaj').click();assert(await page.locator('#nedostaje').isVisible());assert.match(await page.locator('#ukupno-oznaka').textContent(),/pronađenih/);assert((await page.locator('.trgovina-red .iznos').allTextContents()).some(x=>x.startsWith('od ')));
assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:`test-results/kosarica-${width}.png`,fullPage:true});assert.deepEqual(errors,[]);console.log('PASS',width,'layout, quantities, stores, totals, alternatives, persistence, partial prices');await context.close();
}
const context=await browser.newContext({serviceWorkers:'block'});const page=await context.newPage();let fail=true;await page.route('**/data/proizvodi.json',r=>r.fulfill(fail?{status:503,body:''}:{json:data}));await page.goto('http://localhost:8765');await page.locator('#ponovi').waitFor();assert(await page.locator('#zakljucaj').isDisabled());fail=false;await page.locator('#ponovi').click();await page.waitForSelector('.spremno');console.log('PASS failed price load and retry');await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
