// Pomoć za testove: sintetičkom cjeniku dodaje trag službene datoteke (jedna poslovnica po lancu), kakav uvoz daje
// za lance preuzete iz službenih cjenika. Bez traga ponude nisu potvrđene i ne sudjeluju u poretku.
module.exports = `
function uSluzbeno(podaci) {
  podaci.izvori = podaci.lanci.map((_, l) => ["https://lanac" + l + ".hr/cjenik.csv", podaci.datum || "2026-10-21"]);
  podaci.poslovnice = podaci.lanci.map((_, l) => [l, "P" + l, "Ulica " + l, "Grad", l]);
  for (const p of podaci.proizvodi) {
    p[6] = [];
    for (let k = 0; k < p[5].length; k += 2) p[6].push([p[5][k], 1, p[5][k + 1], 0, k / 2 + 2, ""]);
  }
  return podaci;
}
`;
