"""Uparivanje službenih poslovnica s OSM trgovinama: samo isti lanac, ulica, kućni broj i mjesto; nikad središte grada."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import lokacije_poslovnica as lp  # noqa: E402

osm = lp.pripremi_osm([
    {"type": "node", "id": 1, "lat": 45.8131, "lon": 15.9772,
     "tags": {"shop": "supermarket", "brand": "Konzum", "addr:street": "Ilica", "addr:housenumber": "12",
              "addr:city": "Zagreb", "addr:postcode": "10000"}},
    {"type": "way", "id": 2, "center": {"lat": 45.5550, "lon": 18.6955},
     "tags": {"shop": "supermarket", "name": "Konzum", "addr:street": "Ulica Ante Starčevića", "addr:housenumber": "5a"}},
    {"type": "node", "id": 3, "lat": 45.80, "lon": 15.95,  # Lidl bez kućnog broja: ne koristi se
     "tags": {"shop": "supermarket", "brand": "Lidl", "addr:street": "Ilica", "addr:city": "Zagreb"}},
    {"type": "node", "id": 4, "lat": 45.3271, "lon": 14.4422,
     "tags": {"shop": "supermarket", "brand": "Interspar", "addr:street": "Zagrebačka", "addr:housenumber": "7",
              "addr:city": "Rijeka"}},
    {"type": "node", "id": 5, "lat": 45.8000, "lon": 15.9000,  # frizer "Konzumacija" nije Konzum
     "tags": {"shop": "hairdresser", "name": "Konzumacija", "addr:street": "Ilica", "addr:housenumber": "12",
              "addr:city": "Zagreb"}},
])
naselja = lp.indeks_mjesta([["Osijek", 45.5550, 18.6955, 0, ""], ["Zagreb", 45.8150, 15.9819, 0, ""],
                            ["Rijeka", 45.3271, 14.4422, 0, ""]])
podaci = {"lanci": ["Konzum", "Lidl", "Spar"], "poslovnice": [
    [0, "0601", "SUPERMARKET,ILICA 12,10000 ZAGREB,0601", "", 0],          # poštanski broj
    [0, "0702", "HIPERMARKET A. STARČEVIĆEVA 5 A OSIJEK", "", 0],         # OSM bez mjesta: naselje unutar 10 km
    [0, "0703", "SUPERMARKET ILICA 12 RIJEKA", "", 0],                    # ista ulica i broj, drugo mjesto: ne
    [0, "0704", "ZAGREB CENTAR", "Zagreb", 0],                            # bez adrese: nikad središte grada
    [1, "L1", "Ilica bb", "Zagreb", 0],                                   # OSM Lidl bez broja: jedini Lidl u Zagrebu
    [2, "S1", "Zagrebačka 7", "Rijeka", 0],                               # Interspar -> Spar, mjesto iz OSM-a
    [2, "S2", "Zagrebačka 8", "Rijeka", 0],                               # drugi kućni broj
]}
lokacije, pokrivenost, trag = lp.upari_sve(podaci, osm, naselja)
po_id = {l[1]: l for l in lokacije}
assert po_id["0601"][2:6] == [45.8131, 15.9772, "n1", "adresa+postanski"], po_id["0601"]
assert po_id["0702"][4:6] == ["w2", "adresa+blizina"], po_id["0702"]
assert po_id["S1"][4:6] == ["n4", "adresa+mjesto"], po_id["S1"]
# Jedina poslovnica lanca u mjestu i jedina OSM trgovina tog lanca oko središta: koordinate OSM trgovine, ne središta.
assert po_id["L1"][2:6] == [45.80, 15.95, "n3", "jedina u mjestu"], po_id["L1"]
for bez in ("0703", "0704", "S2"):
    assert bez not in po_id, (bez, po_id.get(bez))
# 0704 "ZAGREB CENTAR": Konzum u Zagrebu ima dvije službene poslovnice (0601, 0704) -> nema "jedine u mjestu".
assert pokrivenost["Konzum"] == {"poslovnica": 4, "s_koordinatama": 2, "bez_koordinata": 2,
                                 "nema OSM trgovine lanca s istom ulicom, brojem i mjestom": 2}, pokrivenost["Konzum"]
assert all(("lat" in t) == (t["store_id"] in po_id) for t in trag)

# Jedna službena poslovnica, ali dvije OSM trgovine lanca u mjestu: nije jednoznačno, bez koordinata.
dva_lidla = lp.pripremi_osm([
    {"type": "node", "id": 20, "lat": 45.33, "lon": 14.44, "tags": {"shop": "supermarket", "brand": "Lidl"}},
    {"type": "node", "id": 21, "lat": 45.34, "lon": 14.45, "tags": {"shop": "supermarket", "brand": "Lidl"}}])
lok3, _, _ = lp.upari_sve({"lanci": ["Lidl"], "poslovnice": [[0, "L9", "Krešimirova 5", "Rijeka", 0]]}, dva_lidla, naselja)
assert lok3 == [], lok3
# Mjesto iz adrese: iza poštanskog broja, inače zadnje spomenuto.
assert lp.mjesto_poslovnice(lp.tokeni("HIPERMARKET OSJEČKA 71 51000 RIJEKA"), lp.indeks_mjesta(
    [["Rijeka", 45.3, 14.4, 0, ""], ["Osijek", 45.5, 18.6, 0, ""]])) == "rijeka"
assert lp.mjesto_poslovnice(lp.tokeni("Supermarket Zagrebacka 52 Pozega"), lp.indeks_mjesta(
    [["Požega", 45.3, 17.6, 1, ""], ["Zagreb", 45.8, 15.9, 0, ""]])) == "pozega"

# Dvije različite OSM trgovine iste adrese daleko jedna od druge: nejednoznačno, bez koordinata.
dvoje = lp.pripremi_osm([
    {"type": "node", "id": 10, "lat": 45.0, "lon": 15.0,
     "tags": {"shop": "supermarket", "brand": "Konzum", "addr:street": "Glavna", "addr:housenumber": "1", "addr:city": "Selo"}},
    {"type": "node", "id": 11, "lat": 45.2, "lon": 15.0,
     "tags": {"shop": "supermarket", "brand": "Konzum", "addr:street": "Glavna", "addr:housenumber": "1", "addr:city": "Selo"}},
])
k, razlog = lp.upari_poslovnicu("Glavna 1 Selo", dvoje["Konzum"], {})
assert k is None and "nejednoznačno" in razlog

# OSM nedostupan: zadržava se raniji par samo uz nepromijenjenu adresu.
prethodno = {"Konzum|0601": {"lat": 45.8131, "lon": 15.9772, "osm": "n1", "kvaliteta": "adresa+postanski",
                             "adresa": "SUPERMARKET,ILICA 12,10000 ZAGREB,0601"},
             "Spar|S1": {"lat": 1, "lon": 1, "osm": "n9", "kvaliteta": "adresa+mjesto", "adresa": "Stara adresa"}}
lokacije2, _, _ = lp.upari_sve(podaci, None, naselja, prethodno)
assert [l[1] for l in lokacije2] == ["0601"], lokacije2

assert lp.udaljenost_km(45.8150, 15.9819, 45.5550, 18.6955) > 200
print(f"LOKACIJE PASS: {len(lokacije)} uparene (adresa ili jedina u mjestu), bez koordinata {len(podaci['poslovnice']) - len(lokacije)} "
      "(bez adrese, drugo mjesto, drugi broj), dvije OSM trgovine u mjestu odbijeno, nejednoznačno odbijeno, raniji par samo uz istu adresu")
