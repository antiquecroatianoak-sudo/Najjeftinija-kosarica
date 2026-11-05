package hr.najjeftinijakosarica.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val podaci = Podaci(applicationContext)
        val spremanje = Spremanje(applicationContext)
        setContent { Tema { Ekran(podaci, spremanje) } }
    }
}

/** Zelena za uštedu; svijetli i tamni način prema postavci mobitela. */
@Composable
fun Tema(sadrzaj: @Composable () -> Unit) {
    val svijetla = lightColorScheme(
        primary = Color(0xFF1B7A3D), onPrimary = Color.White,
        primaryContainer = Color(0xFFC8EFD3), onPrimaryContainer = Color(0xFF00210C),
        secondary = Color(0xFF4F6354), tertiary = Color(0xFFB3261E),
        background = Color(0xFFF7FBF6), surface = Color(0xFFF7FBF6),
        surfaceVariant = Color(0xFFDDE5DB),
    )
    val tamna = darkColorScheme(
        primary = Color(0xFF8DD9A2), onPrimary = Color(0xFF003918),
        primaryContainer = Color(0xFF005228), onPrimaryContainer = Color(0xFFA8F5BC),
        secondary = Color(0xFFB6CCB9), tertiary = Color(0xFFF2B8B5),
        background = Color(0xFF101510), surface = Color(0xFF101510),
        surfaceVariant = Color(0xFF414941),
    )
    MaterialTheme(colorScheme = if (isSystemInDarkTheme()) tamna else svijetla, content = sadrzaj)
}
