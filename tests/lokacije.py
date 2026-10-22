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
    [1, "L1", "Ilica bb", "Zagreb", 0],                                   # OSM Lidl bez kućnog broja: samo lanac+mjesto nije pouzdano
    [2, "S1", "Zagrebačka 7", "Rijeka", 0],                               # Interspar -> Spar, mjesto iz OSM-a
    [2, "S2", "Zagrebačka 8", "Rijeka", 0],                               # drugi kućni broj
]}
lokacije, pokrivenost, trag = lp.upari_sve(podaci, osm, naselja)
po_id = {l[1]: l for l in lokacije}
assert po_id["0601"][2:6] == [45.8131, 15.9772, "n1", "adresa+postanski"], po_id["0601"]
assert po_id["0702"][4:6] == ["w2", "adresa+blizina"], po_id["0702"]
assert po_id["S1"][4:6] == ["n4", "adresa+mjesto"], po_id["S1"]
for bez in ("0703", "0704", "L1", "S2"):
    assert bez not in po_id, (bez, po_id.get(bez))
assert pokrivenost["Konzum"] == {"poslovnica": 4, "s_koordinatama": 2, "bez_koordinata": 2,
                                 "nema OSM trgovine lanca s istom ulicom, brojem i mjestom": 2}, pokrivenost["Konzum"]
assert all(("lat" in t) == (t["store_id"] in po_id) for t in trag)

# Nevaljane koordinate (izvan Hrvatske / nisu broj) se odbacuju.
assert lp.pripremi_osm([{"type": "node", "id": 30, "lat": 48.2, "lon": 16.37, "tags": {"shop": "supermarket", "brand": "Lidl",
    "addr:street": "Ilica", "addr:housenumber": "1", "addr:city": "Zagreb"}},
    {"type": "node", "id": 31, "lat": None, "lon": 15.9, "tags": {"shop": "supermarket", "brand": "Lidl"}}]) == {}
# Ista OSM trgovina za dvije poslovnice različitih adresa: obje bez koordinata (višeznačno). Ista adresa pod dva store_id
# (npr. "...KRAPINA-PJ77-1" i "-PJ77-2") dijeli koordinate.
jedna = lp.pripremi_osm([{"type": "node", "id": 40, "lat": 46.16, "lon": 15.87, "tags": {"shop": "supermarket", "brand": "KTC",
    "addr:street": "Bobovje", "addr:housenumber": "52c", "addr:city": "Krapina"}}])
lok4, pok4, _ = lp.upari_sve({"lanci": ["KTC"], "poslovnice": [[0, "a", "TRGOVINA-BOBOVJE 52 C KRAPINA-PJ77-1", "", 0],
    [0, "b", "TRGOVINA-BOBOVJE 52 C KRAPINA-PJ77-2", "", 0]]}, jedna, {})
assert [l[1] for l in lok4] == ["a", "b"], lok4
lok5, pok5, _ = lp.upari_sve({"lanci": ["KTC"], "poslovnice": [[0, "a", "TRGOVINA-BOBOVJE 52 C KRAPINA", "", 0],
    [0, "c", "PRODAVAONICA BOBOVJE 52 C KRAPINA CENTAR", "", 0]]}, jedna, {})
assert lok5 == [] and pok5["KTC"]["viseznacno"] == 2, (lok5, pok5)

# Dvije različite OSM trgovine iste adrese daleko jedna od druge: nejednoznačno, bez koordinata.
dvoje = lp.pripremi_osm([
    {"type": "node", "id": 10, "lat": 45.0, "lon": 15.0,
     "tags": {"shop": "supermarket", "brand": "Konzum", "addr:street": "Glavna", "addr:housenumber": "1", "addr:city": "Selo"}},
    {"type": "node", "id": 11, "lat": 45.2, "lon": 15.0,
     "tags": {"shop": "supermarket", "brand": "Konzum", "addr:street": "Glavna", "addr:housenumber": "1", "addr:city": "Selo"}},
])
k, razlog = lp.upari_poslovnicu("Glavna 1 Selo", dvoje["Konzum"], {})
assert k is None and razlog.startswith("višeznačno")

# OSM nedostupan: zadržava se raniji par samo uz nepromijenjenu adresu.
prethodno = {"Konzum|0601": {"lat": 45.8131, "lon": 15.9772, "osm": "n1", "kvaliteta": "adresa+postanski",
                             "adresa": "SUPERMARKET,ILICA 12,10000 ZAGREB,0601"},
             "Spar|S1": {"lat": 1, "lon": 1, "osm": "n9", "kvaliteta": "adresa+mjesto", "adresa": "Stara adresa"}}
lokacije2, _, _ = lp.upari_sve(podaci, None, naselja, prethodno)
assert [l[1] for l in lokacije2] == ["0601"], lokacije2

assert lp.udaljenost_km(45.8150, 15.9819, 45.5550, 18.6955) > 200
print(f"LOKACIJE PASS: {len(lokacije)} uparene po ulici, broju i mjestu; bez koordinata {len(podaci['poslovnice']) - len(lokacije)} "
      "(bez adrese/samo lanac i mjesto, drugo mjesto, drugi broj); nevaljane koordinate odbačene; višeznačno odbijeno "
      "(dvije OSM trgovine iste adrese, jedna OSM trgovina za dvije adrese); raniji par samo uz istu adresu")
