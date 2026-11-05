package hr.najjeftinijakosarica.app

import android.content.Context
import hr.najjeftinijakosarica.jezgra.Kolicina
import org.json.JSONArray
import org.json.JSONObject

/** Jedan unos s popisa: izgovoreni/upisani tekst i količina koju je korisnik možda sam promijenio. */
data class Unos(val id: Long, val tekst: String, val kolicina: Kolicina? = null)

/** Popis i odabir lanaca ostaju spremljeni u mobitelu i kad se aplikacija zatvori. */
class Spremanje(ctx: Context) {
    private val prefs = ctx.getSharedPreferences("kosarica", Context.MODE_PRIVATE)

    fun popis(): List<Unos> = runCatching {
        val a = JSONArray(prefs.getString("popis", "[]"))
        (0 until a.length()).map { i ->
            val o = a.getJSONObject(i)
            val kol = if (o.has("iznos")) Kolicina(o.getDouble("iznos"), o.getInt("jedinica")) else null
            Unos(o.getLong("id"), o.getString("tekst"), kol)
        }
    }.getOrDefault(emptyList())

    fun spremiPopis(popis: List<Unos>) {
        val a = JSONArray()
        for (u in popis) a.put(JSONObject().apply {
            put("id", u.id); put("tekst", u.tekst)
            u.kolicina?.let { put("iznos", it.iznos); put("jedinica", it.jedinica) }
        })
        prefs.edit().putString("popis", a.toString()).apply()
    }

    /** Isključeni lanci po imenu (imena ostaju ista i kad se katalog promijeni). null = još nije biran. */
    fun iskljuceniLanci(): Set<String> = prefs.getStringSet("iskljuceni", emptySet())!!.toSet()

    fun spremiIskljucene(lanci: Set<String>) {
        prefs.edit().putStringSet("iskljuceni", lanci).apply()
    }
}
