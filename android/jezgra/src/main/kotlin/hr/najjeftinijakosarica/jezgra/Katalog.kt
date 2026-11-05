package hr.najjeftinijakosarica.jezgra

import org.json.JSONArray
import org.json.JSONObject

class Grupa(
    val indeks: Int,
    val id: String,
    val naziv: String,
    /** Svaki naziv vrste kao niz korijena riječi (npr. [["krusn", "mrvic"]]). */
    val aliasi: List<List<String>>,
    val zadano: Kolicina?,
)

/** Cijena proizvoda u lancu: najniža objavljena cijena u tom lancu (procjena po lancu, ne pojedina poslovnica). */
class Cijena(val lanac: Int, val centi: Long, val akcija: Boolean, val raspon: Boolean)

class Proizvod(
    val indeks: Int,
    val naziv: String,
    val marka: String?,
    val iznos: Double,
    val jedinica: Int,
    val grupa: Int,
    val rijeci: List<String>,
    val cijene: List<Cijena>,
) {
    fun cijenaU(lanac: Int): Cijena? = cijene.firstOrNull { it.lanac == lanac }
}

class Katalog(
    val datum: String,
    val izdanje: String,
    val napomena: String,
    val valuta: String,
    val lanci: List<String>,
    val jedinice: List<String>,
    val prijedlozi: Set<String>,
    val nastavci: Set<String>,
    val zamjene: Map<String, Set<String>>,
    val grupe: List<Grupa>,
    val proizvodi: List<Proizvod>,
) {
    val grupaPoId: Map<String, Grupa> = grupe.associateBy { it.id }
    val poGrupi: Map<Int, List<Proizvod>> = proizvodi.groupBy { it.grupa }

    /** Prikaz datuma cjenika: 2026-11-05 -> 5.11.2026. */
    val datumPrikaz: String
        get() = datum.split("-").let { if (it.size == 3) "${it[2].toInt()}.${it[1].toInt()}.${it[0]}." else datum }

    companion object {
        const val PODRZANA_VERZIJA = 1

        fun izJsona(tekst: String): Katalog {
            val o = JSONObject(tekst)
            require(o.getInt("verzija") == PODRZANA_VERZIJA) { "Nepodržana verzija kataloga" }
            val jedinice = o.getJSONArray("jedinice").strings()
            val grupeJ = o.getJSONArray("grupe")
            val grupe = (0 until grupeJ.length()).map { i ->
                val g = grupeJ.getJSONObject(i)
                val aliasiJ = g.getJSONArray("aliasi")
                val zadano = g.optJSONArray("zadano")?.let { Kolicina(it.getDouble(0), it.getInt(1)) }
                Grupa(i, g.getString("id"), g.getString("naziv"),
                    (0 until aliasiJ.length()).map { aliasiJ.getJSONArray(it).strings() }, zadano)
            }
            val marke = o.getJSONArray("marke").strings()
            val pJ = o.getJSONArray("proizvodi")
            val proizvodi = ArrayList<Proizvod>(pJ.length())
            for (i in 0 until pJ.length()) {
                val p = pJ.getJSONArray(i)
                val c = p.getJSONArray(6)
                val cijene = ArrayList<Cijena>(c.length() / 3)
                var k = 0
                while (k + 2 < c.length()) {
                    val z = c.getInt(k + 2)
                    cijene.add(Cijena(c.getInt(k), c.getLong(k + 1), z and 1 != 0, z and 2 != 0))
                    k += 3
                }
                val m = p.getInt(1)
                proizvodi.add(Proizvod(i, p.getString(0), if (m >= 0) marke[m] else null, p.getDouble(2), p.getInt(3),
                    p.getInt(4), p.getString(5).split(" ").filter { it.isNotEmpty() }, cijene))
            }
            val zamjeneJ = o.optJSONObject("zamjene") ?: JSONObject()
            val zamjene = zamjeneJ.keys().asSequence().associateWith { zamjeneJ.getJSONArray(it).strings().toSet() }
            return Katalog(o.getString("datum"), o.optString("izdanje"), o.optString("napomena"), o.optString("valuta", "EUR"),
                o.getJSONArray("lanci").strings(), jedinice, o.getJSONArray("prijedlozi").strings().toSet(),
                o.getJSONArray("nastavci").strings().toSet(), zamjene, grupe, proizvodi)
        }

        private fun JSONArray.strings(): List<String> = (0 until length()).map { getString(it) }
    }
}
