@file:OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)

package hr.najjeftinijakosarica.app

import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent
import android.speech.RecognizerIntent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import hr.najjeftinijakosarica.jezgra.Katalog
import hr.najjeftinijakosarica.jezgra.Kolicina
import hr.najjeftinijakosarica.jezgra.Lanac
import hr.najjeftinijakosarica.jezgra.Ponuda
import hr.najjeftinijakosarica.jezgra.Racun
import hr.najjeftinijakosarica.jezgra.RezultatStavke
import hr.najjeftinijakosarica.jezgra.Stavka
import hr.najjeftinijakosarica.jezgra.Tekst
import hr.najjeftinijakosarica.jezgra.Upit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

private enum class StanjePodataka { UCITAVANJE, SPREMNO, GRESKA }

@Composable
fun Ekran(podaci: Podaci, spremanje: Spremanje) {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    val poruke = remember { SnackbarHostState() }

    var katalog by remember { mutableStateOf<Katalog?>(null) }
    var stanje by remember { mutableStateOf(StanjePodataka.UCITAVANJE) }
    var provjera by remember { mutableStateOf("") }
    var popis by remember { mutableStateOf(spremanje.popis()) }
    var iskljuceni by remember { mutableStateOf(spremanje.iskljuceniLanci()) }
    var upis by remember { mutableStateOf("") }
    var razumio by remember { mutableStateOf<String?>(null) }
    var kartica by remember { mutableStateOf(0) }
    val zamjena = remember { mutableStateMapOf<Long, Int>() }

    LaunchedEffect(Unit) {
        val lokalni = withContext(Dispatchers.IO) { runCatching { podaci.ucitajLokalno() }.getOrNull() }
        katalog = lokalni
        stanje = if (lokalni != null) StanjePodataka.SPREMNO else StanjePodataka.GRESKA
        provjera = "Provjeravam nove cijene…"
        val novi = withContext(Dispatchers.IO) { runCatching { podaci.osvjezi(lokalni) } }
        provjera = when {
            novi.isFailure -> "Nema veze s internetom – prikazane su zadnje spremljene cijene."
            novi.getOrNull() != null -> { katalog = novi.getOrNull(); stanje = StanjePodataka.SPREMNO; "Cijene su upravo osvježene." }
            else -> "Cijene su najnovije dostupne."
        }
    }

    fun spremiPopis(novi: List<Unos>) { popis = novi; spremanje.spremiPopis(novi) }

    fun dodaj(tekst: String) {
        val k = katalog ?: return
        var novi = popis
        for (dio in Upit.razdvoji(tekst)) {
            val s = Upit.razumi(dio, k)
            // Ista stavka dvaput: količine se zbrajaju (mlijeko dvaput = 2 l).
            val i = novi.indexOfFirst { stavka(it, k).kljuc == s.kljuc && s.grupa != null }
            val dodatna = s.kolicina
            novi = if (i >= 0 && dodatna != null) {
                val stara = stavka(novi[i], k).kolicina ?: dodatna
                novi.toMutableList().also { it[i] = it[i].copy(kolicina = Kolicina(stara.iznos + dodatna.iznos, stara.jedinica)) }
            } else novi + Unos(System.nanoTime(), dio)
        }
        spremiPopis(novi)
    }

    val glas = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { r ->
        if (r.resultCode == Activity.RESULT_OK) {
            val tekst = r.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)?.firstOrNull()
            if (tekst.isNullOrBlank()) scope.launch { poruke.showSnackbar("Nisam razumio. Pokušaj ponovno ili upiši.") }
            else { razumio = tekst; dodaj(tekst) }
        }
    }
    fun slusaj() {
        val namjera = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE, "hr-HR")
            .putExtra(RecognizerIntent.EXTRA_PROMPT, "Reci što trebaš kupiti")
        try { glas.launch(namjera) } catch (e: ActivityNotFoundException) {
            scope.launch { poruke.showSnackbar("Glasovni unos nije dostupan na ovom mobitelu. Upiši popis u polje ispod.") }
        }
    }

    Scaffold(
        topBar = { TopAppBar(title = { Text("Najjeftinija košarica", fontWeight = FontWeight.Bold) }) },
        snackbarHost = { SnackbarHost(poruke) },
    ) { okvir ->
        val k = katalog
        if (k == null) {
            Column(Modifier.padding(okvir).padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                if (stanje == StanjePodataka.UCITAVANJE) { CircularProgressIndicator(); Text("Učitavam cijene…") }
                else Text("Cijene se ne mogu učitati. Provjeri internet i ponovno otvori aplikaciju.")
            }
            return@Scaffold
        }
        val dopusteni = k.lanci.indices.filter { k.lanci[it] !in iskljuceni }.toSet()
        val stavke = popis.map { it to stavka(it, k) }
        val rezultati = stavke.map { (_, s) -> Racun.izracunaj(s, k, dopusteni) }
        val lanci = Racun.poLancima(rezultati, dopusteni)
        val odabrane = rezultati.mapIndexed { i, r -> r.ponude.getOrNull(odabir(r, zamjena[popis[i].id] ?: 0)) }
        val ukupno = odabrane.sumOf { it?.ukupnoCenti ?: 0L }
        val usteda = Racun.usteda(ukupno, lanci).takeIf { odabrane.all { it != null } }

        LazyColumn(Modifier.padding(okvir).fillMaxWidth(), contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item {
                Text("Cijene od ${k.datumPrikaz} · ${k.lanci.size} lanaca · ${k.proizvodi.size.formatiraj()} proizvoda",
                    style = MaterialTheme.typography.bodyMedium)
                if (provjera.isNotEmpty()) Text(provjera, style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.secondary)
            }
            item {
                Button(onClick = { slusaj() }, modifier = Modifier.fillMaxWidth().height(72.dp)) {
                    Text("🎤  Reci što trebaš kupiti", fontSize = 20.sp)
                }
                Spacer(Modifier.height(8.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    OutlinedTextField(value = upis, onValueChange = { upis = it }, modifier = Modifier.weight(1f),
                        label = { Text("ili upiši: kruh, 2 l mlijeka, 6 jaja") }, singleLine = true,
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
                        keyboardActions = KeyboardActions(onDone = { if (upis.isNotBlank()) { dodaj(upis); upis = "" } }))
                    Spacer(Modifier.width(8.dp))
                    OutlinedButton(onClick = { if (upis.isNotBlank()) { dodaj(upis); upis = "" } }) { Text("Dodaj") }
                }
                razumio?.let {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("Razumio sam: „$it”", Modifier.weight(1f), style = MaterialTheme.typography.bodySmall)
                        TextButton(onClick = { slusaj() }) { Text("Reci ponovno") }
                    }
                }
            }
            item {
                Text("Gdje kupuješ", style = MaterialTheme.typography.titleSmall)
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    k.lanci.forEach { ime ->
                        FilterChip(selected = ime !in iskljuceni, label = { Text(ime) }, onClick = {
                            val novi = if (ime in iskljuceni) iskljuceni - ime else iskljuceni + ime
                            if (novi.size < k.lanci.size) { iskljuceni = novi; spremanje.spremiIskljucene(novi) }
                        })
                    }
                }
            }
            if (popis.isEmpty()) item {
                Text("Popis je prazan. Dodirni mikrofon i reci npr. „kruh, mlijeko i deset jaja”.",
                    style = MaterialTheme.typography.bodyLarge)
            } else {
                item { Text("Moj popis", style = MaterialTheme.typography.titleMedium) }
                items(stavke, key = { it.first.id }) { (unos, s) ->
                    val r = rezultati[popis.indexOf(unos)]
                    KarticaStavke(k, unos, s, r,
                        onKolicina = { nova -> spremiPopis(popis.map { if (it.id == unos.id) it.copy(kolicina = nova) else it }) },
                        onUkloni = { spremiPopis(popis.filter { it.id != unos.id }); zamjena.remove(unos.id) },
                        onPrijedlog = { naziv -> spremiPopis(popis.map { if (it.id == unos.id) it.copy(tekst = naziv, kolicina = null) else it }) })
                }
                item {
                    TabRow(selectedTabIndex = kartica) {
                        Tab(selected = kartica == 0, onClick = { kartica = 0 }, text = { Text("Najjeftinije ukupno") })
                        Tab(selected = kartica == 1, onClick = { kartica = 1 }, text = { Text("Sve u jednom lancu") })
                    }
                }
                if (kartica == 0) {
                    items(rezultati.indices.toList(), key = { "r" + popis[it].id }) { i ->
                        val r = rezultati[i]
                        val trenutni = zamjena[popis[i].id] ?: 0
                        KarticaPonude(k, r, odabir(r, trenutni),
                            onSljedeci = { zamjena[popis[i].id] = sljedeci(r, trenutni) },
                            onPrethodni = { zamjena[popis[i].id] = prethodni(r, trenutni) })
                    }
                    item { Ukupno(ukupno, usteda, odabrane.count { it == null }) }
                } else {
                    items(lanci, key = { "l" + it.lanac }) { l -> KarticaLanca(k, l) }
                }
                item {
                    Button(onClick = {
                        val tekst = tekstZaSlanje(k, rezultati, odabrane, ukupno, usteda)
                        val slanje = Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, tekst)
                        ctx.startActivity(Intent.createChooser(slanje, "Pošalji popis"))
                    }, modifier = Modifier.fillMaxWidth()) { Text("📤  Pošalji") }
                }
                item {
                    TextButton(onClick = { spremiPopis(emptyList()); zamjena.clear(); razumio = null }) { Text("Obriši cijeli popis") }
                }
            }
            item {
                Text(k.napomena.ifEmpty { "Cijene su iz službenih cjenika trgovina. Cijena na blagajni i dostupnost proizvoda mogu se razlikovati." },
                    style = MaterialTheme.typography.bodySmall)
                Text("Prikazana je najniža objavljena cijena u lancu; u pojedinoj poslovnici cijena može biti viša.",
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.secondary)
            }
        }
    }
}

/** Stavka s količinom koju je korisnik ručno postavio (ako ju je promijenio). */
private fun stavka(u: Unos, k: Katalog): Stavka {
    val s = Upit.razumi(u.tekst, k)
    return if (u.kolicina != null) s.copy(kolicina = u.kolicina, zadanaKolicina = false) else s
}

/** Ponude se prelistavaju po različitim proizvodima (sljedeći najjeftiniji iz iste skupine). */
private fun razliciti(r: RezultatStavke): List<Int> {
    val vidjeni = HashSet<Int>()
    return r.ponude.indices.filter { vidjeni.add(r.ponude[it].proizvod.indeks) }
}
private fun odabir(r: RezultatStavke, korak: Int): Int = razliciti(r).let { if (it.isEmpty()) 0 else it[korak.coerceIn(0, it.size - 1)] }
private fun sljedeci(r: RezultatStavke, korak: Int) = (korak + 1).coerceAtMost(maxOf(0, razliciti(r).size - 1))
private fun prethodni(r: RezultatStavke, korak: Int) = (korak - 1).coerceAtLeast(0)

private fun Int.formatiraj(): String = toString().reversed().chunked(3).joinToString(".").reversed()

private fun opisKolicine(k: Katalog, kol: Kolicina?): String =
    kol?.let { Tekst.kolicina(it.iznos, k.jedinice[it.jedinica]) } ?: "1 pakiranje"

private fun korak(k: Katalog, s: Stavka): Double {
    val kol = s.kolicina ?: return 1.0
    if (k.jedinice[kol.jedinica] == "kom") return 1.0
    val z = s.grupa?.zadano
    return if (z != null && z.jedinica == kol.jedinica && z.iznos > 0) z.iznos else 0.5
}

@Composable
private fun KarticaStavke(k: Katalog, unos: Unos, s: Stavka, r: RezultatStavke,
                          onKolicina: (Kolicina) -> Unit, onUkloni: () -> Unit, onPrijedlog: (String) -> Unit) {
    val nije = r.ponude.isEmpty()
    Card(colors = CardDefaults.cardColors(containerColor =
        if (nije) MaterialTheme.colorScheme.errorContainer else MaterialTheme.colorScheme.surfaceVariant)) {
        Column(Modifier.padding(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(unos.tekst.replaceFirstChar { it.uppercase() }, style = MaterialTheme.typography.titleMedium)
                    val vrsta = s.grupa?.naziv ?: "nepoznata vrsta"
                    Text("$vrsta · ${opisKolicine(k, s.kolicina)}" + if (s.zadanaKolicina) " (zadano)" else "",
                        style = MaterialTheme.typography.bodySmall)
                }
                s.kolicina?.let { kol ->
                    val d = korak(k, s)
                    TextButton(onClick = { if (kol.iznos - d > 1e-9) onKolicina(kol.copy(iznos = kol.iznos - d)) }) { Text("−", fontSize = 22.sp) }
                    TextButton(onClick = { onKolicina(kol.copy(iznos = kol.iznos + d)) }) { Text("+", fontSize = 22.sp) }
                }
                TextButton(onClick = onUkloni) { Text("✕", fontSize = 18.sp, color = MaterialTheme.colorScheme.tertiary) }
            }
            if (nije) {
                Text(if (s.grupa == null) "Nisam pronašao „${unos.tekst}”. Možda ste mislili:"
                     else "U odabranim trgovinama nema „${unos.tekst}” u toj količini. Najbliže:",
                    style = MaterialTheme.typography.bodySmall)
                FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    r.prijedlozi.forEach { p -> AssistChip(onClick = { onPrijedlog(p.naziv) }, label = { Text(p.naziv) }) }
                }
                if (r.prijedlozi.isEmpty()) Text("Nema sličnih proizvoda. Pokušaj drugim riječima.", style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
private fun KarticaPonude(k: Katalog, r: RezultatStavke, indeks: Int, onSljedeci: () -> Unit, onPrethodni: () -> Unit) {
    val p = r.ponude.getOrNull(indeks)
    Card(Modifier.fillMaxWidth().clickable(enabled = p != null) { onSljedeci() }) {
        Column(Modifier.padding(12.dp)) {
            Text(r.stavka.tekst.replaceFirstChar { it.uppercase() }, style = MaterialTheme.typography.labelLarge,
                color = MaterialTheme.colorScheme.secondary)
            if (p == null) { Text("Nije pronađeno u odabranim trgovinama.", color = MaterialTheme.colorScheme.tertiary); return@Column }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(p.proizvod.naziv, style = MaterialTheme.typography.titleMedium)
                    val pak = Tekst.kolicina(p.proizvod.iznos, k.jedinice[p.proizvod.jedinica])
                    Text("${k.lanci[p.cijena.lanac]} · ${p.pakiranja} × $pak · ${Tekst.eura(p.cijena.centi)}/kom",
                        style = MaterialTheme.typography.bodySmall)
                    Text("${Tekst.eura(p.jedinicnaCenti)}/${k.jedinice[p.proizvod.jedinica]}", style = MaterialTheme.typography.bodySmall)
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text(Tekst.eura(p.ukupnoCenti), fontSize = 22.sp, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)
                    if (p.cijena.akcija) Text("AKCIJA", color = MaterialTheme.colorScheme.tertiary, fontWeight = FontWeight.Bold,
                        style = MaterialTheme.typography.labelSmall)
                }
            }
            if (p.cijena.raspon) Text("Cijena se razlikuje po poslovnici; ovo je najniža u lancu.", style = MaterialTheme.typography.bodySmall)
            val isti = r.ponude.filter { it.ukupnoCenti == p.ukupnoCenti && it !== p }
            if (isti.isNotEmpty()) Text("Ista cijena: " + isti.take(2).joinToString { "${it.proizvod.naziv} (${k.lanci[it.cijena.lanac]})" },
                style = MaterialTheme.typography.bodySmall)
            Row {
                if (indeks > 0) TextButton(onClick = onPrethodni) { Text("◀ Prethodni") }
                Spacer(Modifier.weight(1f))
                Text("Dodirni za sljedeći najjeftiniji", style = MaterialTheme.typography.labelSmall,
                    modifier = Modifier.align(Alignment.CenterVertically))
            }
        }
    }
}

@Composable
private fun Ukupno(ukupno: Long, usteda: Long?, nedostaje: Int) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer)) {
        Column(Modifier.padding(16.dp).fillMaxWidth()) {
            Text("Ukupno: ${Tekst.eura(ukupno)}", fontSize = 24.sp, fontWeight = FontWeight.Bold)
            usteda?.let { Text("Uštedite ${Tekst.eura(it)} u odnosu na najskuplji lanac", fontSize = 18.sp,
                color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.SemiBold) }
            if (nedostaje > 0) Text("Bez $nedostaje stavki koje nisu pronađene.", style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun KarticaLanca(k: Katalog, l: Lanac) {
    var otvoreno by remember { mutableStateOf(false) }
    Card(Modifier.fillMaxWidth().clickable { otvoreno = !otvoreno }) {
        Column(Modifier.padding(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(k.lanci[l.lanac], Modifier.weight(1f), style = MaterialTheme.typography.titleMedium)
                Text(Tekst.eura(l.ukupnoCenti), fontWeight = FontWeight.Bold, fontSize = 20.sp)
            }
            if (l.nedostaje.isEmpty()) Text("Ima cijeli popis", color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.bodySmall)
            else Text("Nedostaje: " + l.nedostaje.joinToString { it.tekst } + " (nije u zbroju)",
                color = MaterialTheme.colorScheme.tertiary, style = MaterialTheme.typography.bodySmall)
            if (otvoreno) l.stavke.forEach { (s, p) ->
                Text("• ${s.tekst}: " + (p?.let { "${it.proizvod.naziv}, ${it.pakiranja} × ${Tekst.eura(it.cijena.centi)} = ${Tekst.eura(it.ukupnoCenti)}" } ?: "nema"),
                    style = MaterialTheme.typography.bodySmall)
            }
            Text("Procjena po lancu, ne pojedina poslovnica.", style = MaterialTheme.typography.labelSmall)
        }
    }
}

private fun tekstZaSlanje(k: Katalog, rezultati: List<RezultatStavke>, odabrane: List<Ponuda?>, ukupno: Long, usteda: Long?): String =
    buildString {
        append("🛒 Najjeftinija košarica (cijene od ${k.datumPrikaz})\n\n")
        rezultati.forEachIndexed { i, r ->
            val p = odabrane[i]
            if (p == null) append("• ${r.stavka.tekst}: nije pronađeno\n")
            else append("• ${p.proizvod.naziv} – ${p.pakiranja} × ${Tekst.eura(p.cijena.centi)} = ${Tekst.eura(p.ukupnoCenti)} (${k.lanci[p.cijena.lanac]})\n")
        }
        append("\nUkupno: ${Tekst.eura(ukupno)}\n")
        usteda?.let { append("Ušteda u odnosu na najskuplji lanac: ${Tekst.eura(it)}\n") }
        append("\n${k.napomena}\n")
        append("Aplikacija: ${BuildConfig.PREUZIMANJE_URL}\n")
    }
