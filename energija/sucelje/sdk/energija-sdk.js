// Energija SDK – tanki klijent za API v1 (bez ovisnosti). Radi u pregledniku i u bilo kojoj web aplikaciji.
//
//   import { EnergijaKlijent } from "./sdk/energija-sdk.js";
//   const k = EnergijaKlijent.za({ api: "https://energija.local:8443", token: "…" });
//   const p = await k.pregled();
//   const odjava = k.uzivo((d) => console.log(d.tok.pv_w));
//
// Jedan klijent po adresi API-ja dijele sve komponente na stranici (jedna SSE veza, jedna predmemorija).

const REGISTAR = new Map();

export class GreskaApi extends Error {
  constructor(status, poruka) { super(poruka); this.status = status; }
}

export class EnergijaKlijent {
  /** Zajednički klijent za danu adresu (prazno = isti izvor kao stranica). */
  static za({ api = "", token = null } = {}) {
    const kljuc = `${api}|${token || ""}`;
    if (!REGISTAR.has(kljuc)) REGISTAR.set(kljuc, new EnergijaKlijent({ api, token }));
    return REGISTAR.get(kljuc);
  }

  constructor({ api = "", token = null } = {}) {
    this.api = api.replace(/\/$/, "");
    this.token = token;
    this._slusaci = new Set();
    this._izvor = null;
    this._zadnje = null;
    this._predmemorija = new Map();
  }

  async _zahtjev(metoda, put, tijelo) {
    const zaglavlja = { "Content-Type": "application/json" };
    if (this.token) zaglavlja.Authorization = `Bearer ${this.token}`;
    const r = await fetch(this.api + put, {
      method: metoda, headers: zaglavlja, credentials: this.api ? "include" : "same-origin",
      body: tijelo === undefined ? undefined : JSON.stringify(tijelo),
    });
    let podaci = {};
    try { podaci = await r.json(); } catch (_) { /* prazan odgovor */ }
    if (!r.ok) throw new GreskaApi(r.status, podaci.greska || r.statusText);
    return podaci;
  }

  get(put) { return this._zahtjev("GET", put); }
  post(put, tijelo) { return this._zahtjev("POST", put, tijelo); }
  del(put) { return this._zahtjev("DELETE", put); }

  /** GET s kratkom predmemorijom (više komponenti traži isti resurs u istom trenutku). */
  async getPredmemorirano(put, ms = 3000) {
    const z = this._predmemorija.get(put);
    if (z && Date.now() - z.t < ms) return z.p;
    const p = this.get(put);
    this._predmemorija.set(put, { t: Date.now(), p });
    p.catch(() => this._predmemorija.delete(put));
    return p;
  }

  // --- resursi
  sustav() { return this.getPredmemorirano("/api/v1/sustav", 60000); }
  pregled() { return this.getPredmemorirano("/api/v1/pregled"); }
  tok() { return this.getPredmemorirano("/api/v1/tok"); }
  bojler() { return this.getPredmemorirano("/api/v1/bojler"); }
  solar() { return this.getPredmemorirano("/api/v1/solar"); }
  baterija() { return this.getPredmemorirano("/api/v1/baterija"); }
  pastir() { return this.getPredmemorirano("/api/v1/pastir"); }
  navodnjavanje() { return this.getPredmemorirano("/api/v1/navodnjavanje"); }
  odluke() { return this.getPredmemorirano("/api/v1/odluke"); }
  dijagnostika() { return this.getPredmemorirano("/api/v1/dijagnostika"); }
  usteda(dana = 30) { return this.getPredmemorirano(`/api/v1/usteda?dana=${dana}`, 30000); }
  povijest(serije, raspon = "24h") {
    return this.getPredmemorirano(`/api/v1/povijest?serije=${encodeURIComponent(serije.join(","))}&raspon=${raspon}`, 20000);
  }
  dogadjaji(sati = 24) { return this.get(`/api/v1/dogadjaji?sati=${sati}`); }
  postavke(promjene) { return promjene ? this.post("/api/v1/postavke", promjene) : this.get("/api/v1/postavke"); }
  naredba(tijelo) { this._predmemorija.clear(); return this.post("/api/v1/naredbe", tijelo); }
  pozivnica(uloga) { return this.post("/api/v1/pristup/pozivnice", { uloga }); }
  fleksibilnost() { return this.get("/api/v1/fleksibilnost"); }
  zahtjeviMreze() { return this.get("/api/v1/mreza/zahtjevi"); }
  upari(kod, ime) { return this.post("/api/v1/upari", { kod, ime }); }

  /** Pretplata na događaje uživo (SSE). Vraća funkciju za odjavu. */
  uzivo(fn) {
    this._slusaci.add(fn);
    if (this._zadnje) fn(this._zadnje);
    if (!this._izvor) this._spoji();
    return () => {
      this._slusaci.delete(fn);
      if (!this._slusaci.size && this._izvor) { this._izvor.close(); this._izvor = null; }
    };
  }

  _spoji() {
    const upit = this.token ? `?token=${encodeURIComponent(this.token)}` : "";
    this._izvor = new EventSource(`${this.api}/api/v1/uzivo${upit}`, { withCredentials: !!this.api });
    this._izvor.addEventListener("stanje", (e) => {
      try { this._zadnje = JSON.parse(e.data); } catch (_) { return; }
      this._slusaci.forEach((fn) => { try { fn(this._zadnje); } catch (err) { console.error(err); } });
    });
    // EventSource se sam ponovno spaja (retry: 3000 s poslužitelja)
  }
}
